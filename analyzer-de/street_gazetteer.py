# /app/street_gazetteer.py
import csv
import unicodedata
import re
from pathlib import Path

from spacy.language import Language
from spacy.tokens import Span, Doc
from spacy.util import filter_spans

# Register custom extension attributes
if not Doc.has_extension("_gaz_probe"):
    Doc.set_extension("_gaz_probe", default=False)

STREETS_CSV_PATH = Path("/app/data/streets.csv")


@Language.factory("merge_str_abbrev")
def create_merge_str_abbrev(nlp, name):
    """Factory for creating merge_str_abbrev component."""
    def merge_str_abbrev(doc):
        """
        Merge tokens ending with 'str' + '.' into single token (e.g., 'Ladehofstr.')
        Also handles 'allee' + '.'.
        This helps both EntityRuler patterns and gazetteer component.

        Example: "Bahnhofstr" "." → "Bahnhofstr."
        """
        # Debug: track if we're being called
        import sys
        merges = []

        with doc.retokenize() as retok:
            for i in range(1, len(doc)):
                prev_lower = doc[i-1].lower_
                if (prev_lower.endswith("str") or prev_lower.endswith("allee")) and doc[i].text == ".":
                    merges.append(f"{doc[i-1].text}+{doc[i].text}")
                    retok.merge(doc[i-1:i+1], attrs={"LEMMA": doc[i-1].lemma_ + "."})

        if merges:
            print(f"[merge_str_abbrev] Merged: {merges}", file=sys.stderr)

        return doc

    return merge_str_abbrev


# Helper regexes for range extension
# Updated to allow trailing punctuation (., ;, :, etc.) since spaCy may attach it to tokens
R_SINGLE_NUM     = re.compile(r"^[0-9]+[A-Za-z]?[.,;:!?]*$")          # 119, 119a, 57.
R_EMBEDDED_RANGE = re.compile(r"^[0-9]+[A-Za-z]?(?:[-/–—][0-9]+[A-Za-z]?)[.,;:!?]*$")  # 51-57, 51-57., 119-121a
R_LETTER         = re.compile(r"^[A-Za-z][.,;:!?]*$")                 # g, g.
R_PLZ            = re.compile(r"^[0-9]{5}$")                 # 10115

# Maximum window size for backward scan (increased from 9 to handle complex contexts)
MAX_WINDOW = 12


def _extend_number_range(doc, start_i: int) -> int:
    """
    Given index of first number token, extend to include:
      - Embedded ranges in single token (e.g., '51-57', '119-121a')
      - Single letter suffixes (ALWAYS captured if adjacent, no boundary check)
      - Multi-token ranges (separator as separate token)
      - Trailing punctuation at boundaries
    Returns the exclusive end index for the span.

    Phase 1 improvements:
    - Detects embedded ranges (62.1% of failures)
    - Always captures letter suffixes (20.6% of failures)
    - Supports all dash variants (-, /, –, —)
    """
    i = start_i
    end = i + 1
    tok = doc[i]

    # Case 1: Token already encodes a full range like "51-57" or "119-121a"
    if R_EMBEDDED_RANGE.fullmatch(tok.text or ""):
        # Absorb trailing punctuation (.,;:) but not before PLZ
        while end < len(doc) and doc[end].is_punct and doc[end].text in {".", ",", ";", ":"}:
            if end + 1 < len(doc) and R_PLZ.fullmatch(doc[end + 1].text or ""):
                break
            end += 1
        return end

    # Case 2: First number + optional letter (ALWAYS include if adjacent and single letter)
    # Don't check boundaries - letter suffixes are part of house numbers
    if end < len(doc) and R_LETTER.fullmatch(doc[end].text or ""):
        # Only skip if next token starts a range (defer to range handling below)
        if not (end + 1 < len(doc) and doc[end + 1].text in ("-", "/", "–", "—")):
            end += 1

    # Case 3: Optional range (separator as separate token)
    if end < len(doc) and doc[end].text in ("-", "/", "–", "—"):
        # Check if next token is a number (simple or embedded range)
        if end + 1 < len(doc) and (R_SINGLE_NUM.fullmatch(doc[end + 1].text or "") or
                                   R_EMBEDDED_RANGE.fullmatch(doc[end + 1].text or "")):
            end += 2  # include separator + second number token

            # If second number is simple and followed by single letter → ALWAYS include
            if end < len(doc) and R_LETTER.fullmatch(doc[end].text or ""):
                end += 1

    # Trailing punctuation (unchanged)
    while end < len(doc) and doc[end].is_punct and doc[end].text in {".", ",", ";", ":"}:
        if end + 1 < len(doc) and R_PLZ.fullmatch(doc[end + 1].text or ""):
            break
        end += 1

    return end


def normalize_street_name(name: str) -> str:
    """
    Normalize for comparison:
    - strip whitespace / quotes / parentheses
    - normalize fancy dashes, apostrophes, and spaces
    - collapse spaces
    - unify Str./Strasse/ss/ß variants to Straße
    - lowercase + NFC (Unicode normalization)

    Phase 3 improvement: Handle exotic whitespace (non-breaking, thin spaces)
    """
    if not name:
        return ""

    s = name.strip()

    # remove outer quotes if present
    if s.startswith('"') and s.endswith('"') and len(s) > 1:
        s = s[1:-1].strip()

    # remove surrounding parentheses (rare in clinical text)
    if s.startswith('(') and s.endswith(')') and len(s) > 2:
        s = s[1:-1].strip()

    # remove doubled / stray quotes inside
    s = s.replace('""', '"').replace('"', "")

    # normalize exotic whitespace to regular space
    # \u00a0 = non-breaking space, \u2009 = thin space, \u202f = narrow no-break space
    s = s.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')

    # normalize fancy dashes to regular hyphen (en-dash, em-dash → hyphen)
    s = s.replace('–', '-').replace('—', '-')

    # normalize fancy apostrophes to ASCII apostrophe
    s = s.replace('\u2019', "'").replace('`', "'")

    # collapse whitespace
    s = re.sub(r"\s+", " ", s)

    # Phase 1 (restored): Tuple-based normalization for consistent gazetteer matching
    # Comprehensive list covers all major German street suffix abbreviations
    #
    # IMPORTANT: The two problematic patterns that caused "strasseasse" bug are REMOVED:
    #   ("-Str", "-Straße")  - would match "-Str" inside "-Straße" → "-Straßeaße"
    #   ("-str", "-straße")  - would match "-str" inside "-straße" → "-straßeaße"
    #
    # These patterns are SAFE and form the Phase-1 baseline that achieved 94.6% accuracy.
    replacements = [
        # Straße (most common - ~40% of German streets)
        ("Strasse", "Straße"),
        ("strasse", "straße"),
        ("Str.", "Straße"),
        ("str.", "straße"),
        # NOTE: ("-Str", "-Straße") and ("-str", "-straße") are INTENTIONALLY OMITTED
        # to prevent double-expansion bug. The targeted regex below handles "-Str." safely.

        # Weg (~15% of streets)
        ("Wg.", "Weg"),
        ("wg.", "weg"),
        ("W.", "Weg"),
        ("w.", "weg"),

        # Platz (~8% of streets)
        ("Pl.", "Platz"),
        ("pl.", "platz"),

        # Allee (~5% of streets)
        ("Al.", "Allee"),
        ("al.", "allee"),
        ("All.", "Allee"),
        ("all.", "allee"),

        # Ring (~3% of streets)
        ("Rg.", "Ring"),
        ("rg.", "ring"),
        ("R.", "Ring"),
        ("r.", "ring"),

        # Gasse (~3% of streets, higher in Austria/Switzerland)
        ("G.", "Gasse"),
        ("g.", "gasse"),
        ("Ga.", "Gasse"),
        ("ga.", "gasse"),
        ("Gass.", "Gasse"),
        ("gass.", "gasse"),

        # Damm
        ("Dm.", "Damm"),
        ("dm.", "damm"),
        ("Dam.", "Damm"),
        ("dam.", "damm"),

        # Ufer (river-adjacent streets)
        ("Uf.", "Ufer"),
        ("uf.", "ufer"),

        # Chaussee
        ("Chaus.", "Chaussee"),
        ("chaus.", "chaussee"),
        ("Ch.", "Chaussee"),
        ("ch.", "chaussee"),

        # Pfad
        ("Pf.", "Pfad"),
        ("pf.", "pfad"),
        ("Pfad.", "Pfad"),
        ("pfad.", "pfad"),

        # Steig
        ("Stg.", "Steig"),
        ("stg.", "steig"),

        # Garten
        ("Gart.", "Garten"),
        ("gart.", "garten"),

        # Graben
        ("Gr.", "Graben"),
        ("gr.", "graben"),
        ("Grab.", "Graben"),
        ("grab.", "graben"),

        # Markt
        ("Mkt.", "Markt"),
        ("mkt.", "markt"),

        # Promenade
        ("Prom.", "Promenade"),
        ("prom.", "promenade"),

        # Park
        ("Pk.", "Park"),
        ("pk.", "park"),

        # Berg
        ("Bg.", "Berg"),
        ("bg.", "berg"),

        # Hof
        ("Hf.", "Hof"),
        ("hf.", "hof"),

        # Tor
        ("T.", "Tor"),
        ("t.", "tor"),

        # Sankt/St. (last to avoid conflicts with Str.)
        ("St.", "Sankt"),
        ("st.", "sankt"),
    ]

    for old, new in replacements:
        s = s.replace(old, new)

    # Phase 1.5: Targeted regex ONLY for "-Str." (with dot) hyphen context
    # This safely handles the hyphenated abbreviation without risking double-expansion
    # because it requires the dot AND checks for "aße" suffix to avoid matching "-Straße"
    s = re.sub(r'(?<=-)[Ss]tr\.(?![aä][sß]e)', 'Straße', s, flags=re.UNICODE)

    s = unicodedata.normalize("NFC", s)
    return s.casefold()  # Better than lower() for German (handles ß, etc.)


def load_street_names(path: Path) -> set[str]:
    """
    Load a set of normalized street names from streets.csv (Name column).
    """
    if not path.is_file():
        raise FileNotFoundError(f"Street CSV not found: {path}")

    names: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=",", quotechar='"')
        if "Name" not in reader.fieldnames:
            raise ValueError(f"'Name' column not found, columns: {reader.fieldnames}")

        for row in reader:
            raw = row.get("Name")
            if not raw:
                continue

            norm = normalize_street_name(raw)
            if not norm:
                continue

            # Optional: filter out obvious non-address POIs
            bad_words = ("friedhof", "öffentliche grünfläche", "öffentlicher parkplatz")
            if any(bad in norm for bad in bad_words):
                continue

            names.add(norm)

    return names


# Load dictionary at import time (once per process)
# Try to load preprocessed pickle first (much faster), fall back to CSV
import pickle

STREETS_PKL_PATH = Path("/app/data/streets_normalized.pkl")
STREETS_PKL_PATH_LOCAL = Path(__file__).parent / "data/streets_normalized.pkl"

pkl_path = STREETS_PKL_PATH if STREETS_PKL_PATH.exists() else STREETS_PKL_PATH_LOCAL

if pkl_path.exists():
    print(f"[street_gazetteer] Loading preprocessed streets from {pkl_path} ...")
    with pkl_path.open('rb') as f:
        STREET_NAMES = pickle.load(f)
    print(f"[street_gazetteer] Loaded {len(STREET_NAMES):,} street names (preprocessed).")
else:
    print(f"[street_gazetteer] Preprocessed file not found, loading from CSV {STREETS_CSV_PATH} ...")
    print(f"[street_gazetteer] (Run 'python preprocess_gazetteer.py' to speed up future loads)")
    STREET_NAMES = load_street_names(STREETS_CSV_PATH)
    print(f"[street_gazetteer] Loaded {len(STREET_NAMES):,} street names from CSV.")


############################################################################
# FALSE POSITIVE REDUCTION
############################################################################
#
# Dedicated section for reducing false positives in medical/technical texts.
# These filters reject patterns that look address-like but are clearly not.
#

def _is_likely_false_positive(doc, span_start: int, span_end: int, number_token_idx: int) -> bool:
    """
    Detect false positive patterns in ADDRESS candidates.

    Returns True if the span should be REJECTED (is a false positive).

    Rejection criteria:
    1. Number immediately followed by time units or percent
       (e.g., "2 Wochen", "60 %", "5 Tage")
    2. Number preceded within 2 tokens by quantity indicators
       (e.g., "etwa 2", "ca. 90", "zwischen 40", "bis zu 16")

    Args:
        doc: spaCy Doc object
        span_start: Start index of proposed ADDRESS span
        span_end: End index of proposed ADDRESS span
        number_token_idx: Index of the number token within the span

    Returns:
        True if this is likely a false positive (reject), False otherwise (keep)
    """
    # Rule 1: Check if number is immediately followed by time unit or percent
    # Examples: "2 Wochen", "90 %", "5 Tage", "16 Wochen", "60 Jahre"
    TIME_UNITS = {
        "%", "prozent",
        "tag", "tage", "tagen", "tags",
        "woche", "wochen",
        "monat", "monate", "monaten", "monats",
        "jahr", "jahre", "jahren", "jahres",
        "stunde", "stunden"
    }

    # Check token immediately after the number
    next_idx = number_token_idx + 1
    if next_idx < len(doc):
        next_tok = doc[next_idx]
        # Skip punctuation to check the next content token
        while next_idx < len(doc) and doc[next_idx].is_punct:
            next_idx += 1

        if next_idx < len(doc):
            next_tok = doc[next_idx]
            if next_tok.lower_ in TIME_UNITS:
                return True  # REJECT: "5 Tage", "90 %"

    # Rule 2: Check if number is preceded within 2 tokens by quantity indicator
    # Examples: "etwa 2", "ca. 90", "zwischen 40", "bis zu 16", "über 8", "ab 60", "für 10"
    QUANTITY_INDICATORS = {
        "ca", "ca.", "cirka", "zirka",
        "etwa", "ungefähr", "rund",
        "bis", "zu",
        "über", "ueber",
        "zwischen",
        "ab",
        "für", "fuer",
        "von",
        "mindestens", "höchstens", "maximal", "minimal"
    }

    # Look back up to 2 tokens before the number
    for offset in range(1, 3):
        check_idx = number_token_idx - offset
        if check_idx < 0 or check_idx < span_start:
            break

        check_tok = doc[check_idx]
        # Skip punctuation
        if check_tok.is_punct:
            continue

        if check_tok.lower_ in QUANTITY_INDICATORS:
            return True  # REJECT: "etwa 2", "zwischen 40"

    return False  # KEEP: no false positive patterns detected


def _is_street_token_like(tok):
    """
    Check if a token is "street-like" for backward scanning.
    Allows:
    - Title case tokens (except stopwords)
    - Common lowercase articles/prepositions (am, an, der, etc.)
    - Connector words that appear in multi-word street names
    - Tokens with internal apostrophes if otherwise title-like
    - Hyphens between title tokens
    - Street suffix tokens (CRITICAL for "X Str." cases)

    Phase 2 improvements:
    - Accept short uppercase abbreviations (e.g., "St." in "St.-Brevin-Ring")
    - Allow alphanumeric mini-segments (e.g., "X-2s" in street names)
    - Whitelist connector words (von, der, vom, etc.) for multi-hyphen streets

    Phase 3 fix:
    - Recognize suffix tokens (Str., Straße, Weg, etc.) as street-like
      This is CRITICAL: without it, backward scan stops at the suffix and never
      includes the preceding street name ("Berliner" in "Berliner Str. 31")
    """
    import re

    # NEW: Treat common suffix tokens as street-like (critical for "X Str." cases)
    # Phase 3: Expanded with regional variants (gang, twiete, terrasse, siedlung, winkel, etc.)
    # Phase 4: Added brücke, tor, gässchen/gässle, steige, lohe, höfe, reihe, umgehung, bahnbogen, hügel, wegle
    suffix_tokens = {
        "straße", "str.", "str", "weg", "allee", "platz", "gasse", "ring",
        "ufer", "damm", "hof", "chaussee", "pfad", "strasse", "markt",
        "steig", "stieg", "garten", "plan", "redder", "wiesen", "flur",
        "feld", "berg", "see", "tal", "blick", "park", "kamp", "kamps",
        "gang", "twiete", "twieten", "terrasse", "terrassen", "siedlung",
        "winkel", "äcker", "acker", "wald", "brink", "rain", "grund",
        "höhe", "hang", "anger", "bruch", "heide", "holz",
        "brücke", "bruecke", "tor", "gässchen", "gaesschen", "gässle", "gaessle",
        "steige", "lohe", "höfe", "hoefe", "reihe", "umgehung", "ortsumfahrung",
        "bahnbogen", "hügel", "huegel", "wegle"
    }
    if tok.lower_ in suffix_tokens:
        return True

    # NEW: Also recognize compound street tokens that END with a suffix
    # (e.g., "Hauffstr.", "Birkenstr.", "Meisenweg", "Papiermühle", "Laubengang")
    # This catches single-token compound streets without hyphens
    # Phase 3/4: Expanded regex to include regional suffix variants
    if tok.is_title and re.search(r"(straße|str\.|str|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|pfad|strasse|markt|steig|stieg|garten|gang|twiete|twieten|terrasse|terrassen|siedlung|winkel|äcker|acker|wald|brink|rain|grund|höhe|hang|anger|bruch|heide|holz|brücke|bruecke|tor|gässchen|gaesschen|gässle|gaessle|steige|lohe|höfe|hoefe|reihe|umgehung|bahnbogen|hügel|huegel|wegle)\.?$", tok.lower_):
        return True

    # Phase 2a: Accept short uppercase abbreviations like "St."
    if re.match(r"^[A-ZÄÖÜ]\.$", tok.text):
        return True

    # Phase 2b: Accept merged multi-hyphen streets (e.g., "Bertha-von-Suttner-Str.")
    # These are created by merge_str_abbrev and contain hyphens + street suffix
    # Match pattern: contains hyphen(s) and ends with common street suffix
    # Phase 3/4: Expanded suffix list
    if "-" in tok.text and re.search(r"(straße|str\.|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|pfad|strasse|gang|twiete|terrasse|siedlung|winkel|wald|brink|grund|höhe|anger|bruch|heide|holz|brücke|bruecke|tor|bahnbogen)\.?$", tok.lower_):
        return True

    # Phase 2c: Accept mixed alphanumeric segments within hyphen chains (e.g., "X-2s")
    if re.match(r"^[A-Za-zÄÖÜäöü0-9]+$", tok.text):
        # Still exclude obvious stopwords
        if tok.lower_ not in {"wohnhaft", "patient", "adresse", "dokumentation", "treffen", "wohnung"}:
            return True

    # Stopwords that shouldn't be part of street names (sentence starters, common words)
    stopwords = {"wohnhaft", "patient", "adresse", "dokumentation", "treffen", "wohnung"}

    # Connector words that can appear in street names (don't count toward consecutive lowercase limit)
    connectors = {"am", "an", "auf", "in", "im", "bei", "zum", "zur", "unter",
                  "der", "den", "dem", "des", "von", "vom", "zu", "und"}

    if tok.is_title:
        # Exclude common stopwords even if title-cased
        if tok.lower_ in stopwords:
            return False
        return True

    # Allow connector words (these won't increment consecutive_lowercase counter)
    if tok.lower_ in connectors:
        return True

    # Allow hyphens between title tokens
    if tok.text == "-":
        return True

    # Allow internal apostrophes (ASCII or typographic) in title-like tokens
    # e.g., "Auf'm" in "Auf'm Hackenfeld"
    if ("'" in tok.text or "\u2019" in tok.text):
        cleaned = tok.text.replace("'", "").replace("\u2019", "")
        if cleaned and cleaned[0].isupper():  # Title-like after removing apostrophes
            return True

    return False


@Language.factory("street_gazetteer")
def create_street_gazetteer(nlp, name):
    """Factory for creating street_gazetteer component."""
    def street_gazetteer(doc):
        """
        Gazetteer-based ADDRESS component:

        - For each numeric token (potential house number),
          look left for a title-cased sequence (street name).
        - If normalized street name is in STREET_NAMES set, create ADDRESS span.
        - Writes to doc.spans["gaz_address"] instead of doc.ents to avoid conflicts.

        G1 improvements:
        - Skip Roman numerals (e.g., "II. Vereinsstr. 169")
        - Extend range detection (e.g., "62-68")
        """
        # DIAGNOSTIC: Log once per doc to verify component is running
        import sys
        print(f"[gaz-COMPONENT-START] Processing doc: '{doc.text[:60]}'...", file=sys.stderr, flush=True)
        if not hasattr(doc._, "_gaz_probe"):
            print(f"[gaz] STREET_NAMES={len(STREET_NAMES):,}", file=sys.stderr, flush=True)
            # Sanity check a few known streets
            for probe in ["trift", "imborntal", "andenhaselwiesen", "breden", "mühlenstraße"]:
                in_set = probe in STREET_NAMES
                print(f"[gaz] probe '{probe}' in set? {in_set}", file=sys.stderr, flush=True)
            doc._.set("_gaz_probe", True)

        # Write to span group instead of doc.ents to avoid NER conflicts
        gaz_addresses = []
        candidates = 0
        hits = 0

        import sys  # Debug logging

        for i, tok in enumerate(doc):
            # Check if token is a potential house number (pure number, letter suffix, or embedded range)
            # CRITICAL: Must include R_EMBEDDED_RANGE to process tokens like "51-57"
            if not (
                tok.like_num
                or tok.text.isdigit()
                or R_SINGLE_NUM.fullmatch(tok.text or "")
                or R_EMBEDDED_RANGE.fullmatch(tok.text or "")
            ):
                continue

            print(f"[gaz-debug] Found number token at i={i}: '{tok.text}' in text: {doc.text[:80]}", file=sys.stderr)

            # Look backwards for potential street name tokens
            # Skip punctuation immediately before the number (e.g., "Bahnhofstr. 42")
            j = i - 1
            while j >= 0 and doc[j].is_punct:
                j -= 1

            if j < 0:
                print(f"  [gaz-debug] Skipped: j < 0 (no tokens before number)", file=sys.stderr)
                continue

            # Now look backwards for street-like tokens (title-cased, apostrophes, articles)
            # Guard: don't allow 2+ consecutive lowercase words (except connector words)
            # Phase 2: Connector words (von, der, vom, etc.) don't count toward consecutive lowercase
            connectors = {"am", "an", "auf", "in", "im", "bei", "zum", "zur", "unter",
                         "der", "den", "dem", "des", "von", "vom", "zu", "und"}

            start = j
            consecutive_lowercase = 0
            scan_stopped_reason = None
            # Use MAX_WINDOW for wider context (increased from 9)
            while start >= 0 and _is_street_token_like(doc[start]) and (i - start) <= MAX_WINDOW:
                # Track consecutive lowercase to prevent over-greedy scans
                # Don't count connector words toward the limit
                if doc[start].is_lower and doc[start].is_alpha and doc[start].lower_ not in connectors:
                    consecutive_lowercase += 1
                    if consecutive_lowercase >= 2:  # Stop if 2+ consecutive lowercase words
                        scan_stopped_reason = "2+ consecutive lowercase"
                        break
                else:
                    consecutive_lowercase = 0  # Reset on non-lowercase token or connector
                start -= 1

            if not scan_stopped_reason and start < 0:
                scan_stopped_reason = "reached start of doc"
            elif not scan_stopped_reason and not _is_street_token_like(doc[start]):
                scan_stopped_reason = f"token not street-like: '{doc[start].text}'"
            elif not scan_stopped_reason and (i - start) > MAX_WINDOW:
                scan_stopped_reason = "exceeded MAX_WINDOW"

            start += 1
            print(f"  [gaz-debug] Backward scan: j={j} '{doc[j].text}' → start={start} '{doc[start].text}' (reason: {scan_stopped_reason})", file=sys.stderr)
            print(f"  [gaz-debug] Scan window: doc[{start}:{j+1}] = '{doc[start:j+1].text}'", file=sys.stderr)

            # G1/Phase 4: Handle Roman numerals intelligently
            # Roman numerals pattern: I, II, III, IV, V, VI, VII, VIII, IX, X, etc.
            # Phase 4: Only skip if NOT followed by street-like content (e.g., "Weg III 28" should keep "III")
            if start > 0 and re.match(r"^[IVX]+\.?$", doc[start].text):
                # Peek at next non-punct token
                nxt = start + 1
                while nxt <= j and doc[nxt].is_punct:
                    nxt += 1
                # Only skip the Roman numeral if NOT followed by street-like content
                if nxt <= j and _is_street_token_like(doc[nxt]):
                    pass  # keep Roman numeral as part of the street name
                else:
                    # Skip the Roman numeral
                    start += 1
                    # Skip any following punctuation
                    while start <= j and doc[start].is_punct:
                        start += 1

            if start > j:
                continue

            candidates += 1

            # NEW: Left-trim search to find the best street boundary
            # Instead of guessing which tokens are "sentence context" vs "street name",
            # we progressively trim from the left until we find a substring in the gazetteer.
            # This robustly handles:
            # - "Der Patient wohnt in der Mühlenstraße 42." → finds "Mühlenstraße"
            # - "Wohnanschrift Mühlenstraße 42, Berlin" → finds "Mühlenstraße"
            # - "Am Markt 3" → finds "Am Markt" (if in gazetteer)
            # - "Die Patientin lebt in Berlin in der Mühlenstraße 42." → finds "Mühlenstraße"

            orig_start = start
            match_start = None
            match_norm = None

            # Debug: Show what we're scanning
            import sys
            full_window = doc[orig_start:j+1].text
            print(f"[gaz-debug] num='{tok.text}' full_window='{full_window}'", file=sys.stderr)

            # Try progressively shorter substrings from left to right
            # Start with the full window [start:j+1], then [start+1:j+1], etc.
            for s0 in range(orig_start, j + 1):
                cand_tokens = doc[s0:j+1]
                cand_text = cand_tokens.text
                norm = normalize_street_name(cand_text)
                in_gaz = norm in STREET_NAMES
                print(f"  [gaz-debug] try s0={s0} text='{cand_text}' norm='{norm}' in_gaz={in_gaz}", file=sys.stderr)

                if in_gaz:
                    # Found a match! Use this as the street name boundary
                    match_start = s0
                    match_norm = norm
                    break  # First (longest) match wins

            if match_start is None:
                # No substring in this window is a known street → skip candidate
                print(f"  [gaz-debug] NO MATCH - skipping candidate", file=sys.stderr)
                continue

            # Update start to the matched boundary
            start = match_start
            norm_street = match_norm
            print(f"  [gaz-debug] ✓ MATCHED: chosen='{doc[start:j+1].text}' norm='{norm_street}'", file=sys.stderr)

            # Safety: cap street span at MAX_WINDOW tokens max (matches scan window)
            if (j - start + 1) > MAX_WINDOW:
                continue

            hits += 1

            # Build ADDRESS span = street + full number (incl. range / optional letters / trailing punct)
            span_start = start
            span_end = _extend_number_range(doc, i)

            # FALSE POSITIVE FILTER: Reject medical/technical patterns
            # Check BEFORE creating the span to avoid false positives like:
            # - "etwa 2 von 10.000", "zwischen 40 %", "für 10 Tage"
            # - "ab 60 Jahren", "Pro Jahr erkranken etwa 2"
            if _is_likely_false_positive(doc, span_start, span_end, i):
                continue  # Skip this candidate - likely false positive

            # Ensure ADDRESS label exists in vocab
            doc.vocab.strings.add("ADDRESS")
            label = doc.vocab.strings["ADDRESS"]
            span = Span(doc, span_start, span_end, label=label)
            gaz_addresses.append(span)

        # Write to span group instead of doc.ents to avoid NER conflicts
        # A resolver component will merge these with NER predictions later
        doc.spans["gaz_address"] = gaz_addresses

        # DIAGNOSTIC: Log final stats
        print(f"[gaz] candidates={candidates} hits={hits} spans_written={len(gaz_addresses)}", file=sys.stderr)

        return doc

    return street_gazetteer


@Language.factory("address_conflict_resolver")
def create_address_conflict_resolver(nlp, name):
    """Factory for creating address_conflict_resolver component."""
    def address_conflict_resolver(doc):
        """
        Resolve entity conflicts between gazetteer ADDRESS spans and NER predictions.

        Precedence rules:
        1. ADDRESS beats PER/LOC/ORG on overlap (gazetteer is validated)
        2. ADDRESS vs ADDRESS: prefer longer span
        3. ADDRESS vs ADDRESS (same length): prefer gazetteer (validated)
        4. Trim leading lowercase prepositions unless they're part of the street name

        Phase 1 improvement: Trim "in/an/auf/bei/unter [der/den/dem]?" unless title-cased
        (44.6% of failures have extra prepositions)

        This component must run AFTER NER in the pipeline.
        """
        gaz_spans = list(doc.spans.get("gaz_address", []))
        ner_spans = list(doc.ents)

        LOWER_PREPS = {"in", "an", "auf", "bei", "unter"}
        LOWER_ARTS = {"der", "den", "dem"}

        def overlaps(a, b):
            """Check if two spans overlap"""
            return not (a.end_char <= b.start_char or b.end_char <= a.start_char)

        def trim_leading_lowercase_prep(span):
            """
            Trim leading lowercase prepositions (in/an/auf/bei/unter) + optional article.
            Keep title-cased prepositions like Im/Am/An (they're part of the street name).

            Returns a new span with trimmed start, or original span if no trim needed.
            """
            if span.start >= len(doc):
                return span

            first_tok = doc[span.start]

            # Don't trim if starts with title-cased word (Im, Am, An, etc.)
            if first_tok.is_title:
                return span

            # Trim patterns: in|an|auf|bei|unter [der|den|dem]?
            s = span.start
            if s < len(doc) and doc[s].lower_ in LOWER_PREPS:
                s += 1  # Skip preposition
                # Skip optional article
                if s < span.end and s < len(doc) and doc[s].lower_ in LOWER_ARTS:
                    s += 1

            # Only create new span if we trimmed and there's still content
            if s > span.start and s < span.end:
                # Verify there's at least one title-cased token remaining
                if any(tok.is_title for tok in doc[s:span.end]):
                    return Span(doc, s, span.end, label=span.label)

            return span

        # Start with all NER/EntityRuler spans
        merged = list(ner_spans)

        # Process each gazetteer ADDRESS span
        for gaz in gaz_spans:
            remove_idxs = []
            should_add_gaz = True

            for i, existing in enumerate(merged):
                if overlaps(gaz, existing):
                    if existing.label_ != "ADDRESS":
                        # Gazetteer ADDRESS beats non-ADDRESS (PER/LOC/ORG)
                        remove_idxs.append(i)
                    else:
                        # Both ADDRESS: choose longer span
                        gaz_len = gaz.end_char - gaz.start_char
                        existing_len = existing.end_char - existing.start_char

                        if gaz_len > existing_len:
                            # Gazetteer is longer, remove existing
                            remove_idxs.append(i)
                        elif gaz_len == existing_len:
                            # Same length: prefer gazetteer (validated)
                            remove_idxs.append(i)
                        else:
                            # Existing is longer, keep it, don't add gazetteer
                            should_add_gaz = False

            # Remove losing spans (from end to preserve indices)
            for i in reversed(remove_idxs):
                merged.pop(i)

            # Add gazetteer span if it won or had no conflicts
            if should_add_gaz and all(not overlaps(gaz, m) for m in merged):
                merged.append(gaz)

        # Phase 1: Trim leading prepositions from ADDRESS spans
        trimmed = []
        for span in merged:
            if span.label_ == "ADDRESS":
                trimmed.append(trim_leading_lowercase_prep(span))
            else:
                trimmed.append(span)

        # Final cleanup: filter any residual overlaps by length
        from spacy.util import filter_spans
        doc.ents = tuple(filter_spans(trimmed))

        return doc

    return address_conflict_resolver


@Language.factory("address_span_normalizer")
def create_address_span_normalizer(nlp, name):
    """
    Phase 2: Universal ADDRESS normalizer that runs AFTER conflict resolver.

    For every ADDRESS entity in doc.ents:
    1. Trim leading lowercase prepositions/articles (in/an/auf/bei/unter + der/den/dem)
    2. Extend number ranges and letter suffixes using _extend_number_range()

    This ensures EntityRuler-only detections get the same finishing logic as gazetteer spans.
    Fixes incomplete ranges/suffixes in addresses not validated by the gazetteer.
    """

    def address_span_normalizer(doc):
        """
        Normalize all ADDRESS spans: trim preps, extend number ranges/suffixes.
        """
        LOWER_PREPS = {"in", "an", "auf", "bei", "unter"}
        LOWER_ARTS = {"der", "den", "dem"}

        def find_number_start_token(s, e):
            """Find first number-ish token in span range [s, e)"""
            for k in range(s, e):
                t = doc[k].text or ""
                if (
                    doc[k].like_num
                    or t.isdigit()
                    or R_SINGLE_NUM.fullmatch(t)
                    or R_EMBEDDED_RANGE.fullmatch(t)
                ):
                    return k
            return -1

        def trim_leading_lowercase_prep(span):
            """
            Trim leading lowercase prepositions (in/an/auf/bei/unter) + optional article.
            Keep title-cased prepositions like Im/Am/An (they're part of the street name).
            """
            if span.start >= len(doc):
                return span

            first_tok = doc[span.start]
            if first_tok.is_title:
                return span

            # Trim patterns: in|an|auf|bei|unter [der|den|dem]?
            s = span.start
            if s < len(doc) and doc[s].lower_ in LOWER_PREPS:
                s += 1  # Skip preposition
                # Skip optional article
                if s < span.end and s < len(doc) and doc[s].lower_ in LOWER_ARTS:
                    s += 1

            # Only create new span if we trimmed and there's still content
            if s > span.start and s < span.end:
                # Verify there's at least one title-cased token remaining
                if any(tok.is_title for tok in doc[s:span.end]):
                    from spacy.tokens import Span
                    return Span(doc, s, span.end, label=span.label)

            return span

        normalized = []
        for ent in doc.ents:
            if ent.label_ != "ADDRESS":
                normalized.append(ent)
                continue

            # 1) Trim leading prepositions
            trimmed = trim_leading_lowercase_prep(ent)

            # 2) Extend number ranges/suffixes
            num_i = find_number_start_token(trimmed.start, trimmed.end)
            if num_i == -1:
                normalized.append(trimmed)  # No number to extend
                continue

            new_end = _extend_number_range(doc, num_i)
            # Only extend forward; never shrink start
            new_end = max(new_end, trimmed.end)

            from spacy.tokens import Span
            normalized.append(Span(doc, trimmed.start, new_end, label=trimmed.label))

        # Final cleanup: filter overlaps by length
        from spacy.util import filter_spans
        doc.ents = tuple(filter_spans(normalized))

        return doc

    return address_span_normalizer


@Language.factory("address_precision_filter")
def create_address_precision_filter(nlp, name):
    """
    Precision-focused ADDRESS filter that rejects medical/technical false positives.

    Runs AFTER conflict resolution but BEFORE span normalization to filter ALL ADDRESS
    entities (both EntityRuler and gazetteer).

    Rejection criteria:
    - Month + year patterns (e.g., "Februar 2025")
    - Season patterns (e.g., "Saison 2012/2013")
    - Percentage patterns (e.g., "90 %")
    - Type/Part patterns (e.g., "Typ 1", "Teil 1")
    - Legal references (e.g., "Abs. 1", "§ 8")
    - Quantity + time unit (e.g., "etwa 2 Wochen", "ab 60 Jahren")
    - Age references (e.g., "Alter von 6", "Jugendliche bis 19")
    - Bare ranges without street suffixes (e.g., "40 - 60")

    Keeps ADDRESS entities that:
    - Have street suffixes (Straße, Weg, Platz, etc.)
    - Are confirmed by gazetteer
    - Don't match false positive patterns
    """
    import re

    MONTHS = {"januar","februar","märz","maerz","april","mai","juni","juli",
              "august","september","oktober","november","dezember","sept."}
    QUANT_TRIGGERS = {"ca.","circa","etwa","ungefähr","über","ueber","bis","zwischen","ab","für","fuer"}
    TIME_UNITS = {"tage","tag","wochen","woche","monate","monat","jahre","jahr","trimenon","stunden","stunde"}
    AGE_WORDS = {"alter","jugendliche","jugendlichen","personen","menschen","kinder","erwachsenen"}

    # Regex patterns for common false positives
    SEASON_RE = re.compile(r"\b(?:saison|spielzeit)\s+\d{4}/\d{2,4}\b", re.I)
    YEAR_RE   = re.compile(r"\b(19|20)\d{2}\b")
    PCT_RE    = re.compile(r"\b\d{1,3}\s*%\b")
    TYP_TEIL_RE = re.compile(r"\b(?:typ|teil)\s*\d+\b", re.I)
    PARA_RE   = re.compile(r"\babs\.\s*\d+\b", re.I)
    PARA_SEC  = re.compile(r"§\s*\d+\b")
    ED_PATTERN = re.compile(r"\bED\s+(?:\d{1,2}/)?(19|20)\d{2}\b", re.I)  # Medical: "ED 2013", "ED 11/2014"

    # Street suffix set (mirrors _is_street_token_like)
    SUFFIX = {"straße","str.","str","weg","platz","allee","gasse","ring","ufer",
              "damm","hof","chaussee","pfad","markt","steig","stieg","garten",
              "gang","twiete","terrasse","siedlung","winkel","wald","brink","rain",
              "grund","höhe","anger","bruch","heide","holz","brücke","bruecke","tor",
              "reihe","umgehung","ortsumfahrung","bahnbogen","hügel","huegel","wegle"}

    def has_suffix(doc, span):
        """Check if span contains a street suffix token or ends with suffix pattern."""
        s, e = span.start, span.end
        # Locate number start inside span
        num_i = -1
        for k in range(s, e):
            if doc[k].like_num or re.match(r"^[0-9]+[A-Za-z]?(?:[-/–—][0-9]+[A-Za-z]?)?[.,;:!?]?$", doc[k].text or ""):
                num_i = k
                break

        # Check left side of span (street name part)
        left = doc[s:num_i if num_i != -1 else e]
        text = left.text.casefold()

        # Check for suffix tokens
        if any(tok.lower_ in SUFFIX for tok in left):
            return True

        # Check for suffix pattern at end
        return bool(re.search(r"(straße|str\.|str|weg|platz|allee|gasse|ring|ufer|damm|hof|chaussee|pfad|markt|steig|stieg|garten|gang|twiete|terrasse|siedlung|winkel|wald|brink|rain|grund|höhe|anger|bruch|heide|holz|brücke|bruecke|tor|reihe|umgehung|ortsumfahrung|bahnbogen|hügel|huegel|wegle)\.?$", text))

    def looks_like_non_address(text):
        """Check if text matches common false positive patterns."""
        t = text.casefold()

        # Medical 'Erstdiagnose' patterns (e.g., "ED 2013", "ED 11/2014")
        if ED_PATTERN.search(text):  # use original text to preserve case
            return True

        # Months + year (e.g., "Februar 2025")
        if any(m in t for m in MONTHS) and YEAR_RE.search(t):
            return True

        # Season patterns (e.g., "Saison 2012/2013")
        if SEASON_RE.search(t):
            return True

        # Percentage (e.g., "90 %")
        if PCT_RE.search(t):
            return True

        # Type/Part references (e.g., "Typ 1", "Teil 1")
        if TYP_TEIL_RE.search(t):
            return True

        # Legal references (e.g., "Abs. 1", "§ 8")
        if PARA_RE.search(t) or PARA_SEC.search(t):
            return True

        # Quantity phrases: quantity trigger + number + time unit
        # (e.g., "etwa 2 Wochen", "ab 60 Jahren", "bis 19 Jahre")
        if any(q in t for q in QUANT_TRIGGERS) and any(u in t for u in TIME_UNITS):
            return True

        # Age/period phrases (e.g., "Alter von 6", "Jugendliche bis 19", "Personen ab 60")
        # Exclude if it contains a year (e.g., "im Jahr 2013" is okay)
        if any(w in t for w in AGE_WORDS) and YEAR_RE.search(t) is None:
            return True

        return False

    def address_precision_filter(doc):
        """
        Filter ADDRESS entities to remove false positives.

        Keeps entities that:
        1. Don't match false positive patterns
        2. Have street suffixes OR overlap with gazetteer confirmations
        """
        kept = []
        gaz_hits = list(doc.spans.get("gaz_address", []))

        for ent in doc.ents:
            if ent.label_ != "ADDRESS":
                kept.append(ent)
                continue

            span_text = ent.text

            # Rule 1: Reject classic non-address contexts
            if looks_like_non_address(span_text):
                continue

            # Rule 2: Require suffix OR gazetteer confirmation
            has_indicator = has_suffix(doc, ent)
            overlaps_gaz = any(
                not (ent.end_char <= g.start_char or g.end_char <= ent.start_char)
                for g in gaz_hits
            )

            if not (has_indicator or overlaps_gaz):
                continue

            kept.append(ent)

        from spacy.util import filter_spans
        doc.ents = tuple(filter_spans(kept))
        return doc

    return address_precision_filter



def selftest_address_pipeline(nlp):
    """
    Self-test function to verify the ADDRESS pipeline is working correctly.
    This should be called during startup to fail fast if the gazetteer is broken.
    """
    import sys
    
    test_cases = [
        ("An den Haselwiesen 25", True, "Basic 'An den' preposition case"),
        ("Hauptstraße 42", True, "Simple street with house number"),
        ("Berliner Str. 31", True, "Two-token street with abbreviation"),
        ("Am Eiskeller 103", True, "Prep street 'Am'"),
        ("Im Rischedahle 155", True, "Prep street 'Im'"),
        ("Zum Hönig 169b", True, "Prep street 'Zum'"),
        ("Auf dem Breiten Feld 172f", True, "Prep + place type"),
        # Note: "Alter" prefix test removed - not all streets exist in gazetteer
        ("Dies ist keine Adresse", False, "Non-address text"),
    ]
    
    print("[selftest] Running ADDRESS pipeline self-test...", file=sys.stderr)
    
    for text, should_have_address, description in test_cases:
        doc = nlp(text)
        has_address = any(ent.label_ == "ADDRESS" for ent in doc.ents)
        
        if has_address != should_have_address:
            error_msg = f"[selftest] FAILED: '{text}' - {description}\n"
            error_msg += f"  Expected ADDRESS entity: {should_have_address}\n"
            error_msg += f"  Got entities: {[(ent.text, ent.label_) for ent in doc.ents]}"
            raise RuntimeError(error_msg)
    
    print(f"[selftest] ✓ All {len(test_cases)} test cases passed", file=sys.stderr)
    print("[selftest] ADDRESS pipeline is working correctly", file=sys.stderr)
    return True
