# /app/street_gazetteer.py
import csv
import unicodedata
import re
from pathlib import Path

from spacy.language import Language
from spacy.tokens import Span
from spacy.util import filter_spans


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
        if tok.lower_ not in {"wohnhaft", "patient", "adresse", "dokumentation", "treffen"}:
            return True

    # Stopwords that shouldn't be part of street names (sentence starters, common words)
    stopwords = {"wohnhaft", "patient", "adresse", "dokumentation", "treffen"}

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
        # Write to span group instead of doc.ents to avoid NER conflicts
        gaz_addresses = []

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

            # Look backwards for potential street name tokens
            # Skip punctuation immediately before the number (e.g., "Bahnhofstr. 42")
            j = i - 1
            while j >= 0 and doc[j].is_punct:
                j -= 1

            if j < 0:
                continue

            # Now look backwards for street-like tokens (title-cased, apostrophes, articles)
            # Guard: don't allow 2+ consecutive lowercase words (except connector words)
            # Phase 2: Connector words (von, der, vom, etc.) don't count toward consecutive lowercase
            connectors = {"am", "an", "auf", "in", "im", "bei", "zum", "zur", "unter",
                         "der", "den", "dem", "des", "von", "vom", "zu", "und"}

            start = j
            consecutive_lowercase = 0
            # Phase 2: Widen window to 9 tokens for long multi-hyphen names
            while start >= 0 and _is_street_token_like(doc[start]) and (i - start) <= 9:
                # Track consecutive lowercase to prevent over-greedy scans
                # Don't count connector words toward the limit
                if doc[start].is_lower and doc[start].is_alpha and doc[start].lower_ not in connectors:
                    consecutive_lowercase += 1
                    if consecutive_lowercase >= 2:  # Stop if 2+ consecutive lowercase words
                        break
                else:
                    consecutive_lowercase = 0  # Reset on non-lowercase token or connector
                start -= 1
            start += 1

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

            # Safety: cap street span at 9 tokens max (matches scan window)
            if (j - start + 1) > 9:
                continue

            street_tokens = doc[start:j+1]
            norm_street = normalize_street_name(street_tokens.text)

            if norm_street not in STREET_NAMES:
                continue

            # Build ADDRESS span = street + full number (incl. range / optional letters / trailing punct)
            span_start = start
            span_end = _extend_number_range(doc, i)
            label = doc.vocab.strings["ADDRESS"]
            span = Span(doc, span_start, span_end, label=label)
            gaz_addresses.append(span)

        # Write to span group instead of doc.ents to avoid NER conflicts
        # A resolver component will merge these with NER predictions later
        doc.spans["gaz_address"] = gaz_addresses
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
