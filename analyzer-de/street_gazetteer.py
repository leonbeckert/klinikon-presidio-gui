# /app/street_gazetteer.py
import csv
import unicodedata
import re
from pathlib import Path

from spacy.language import Language
from spacy.tokens import Span
from spacy.util import filter_spans


STREETS_CSV_PATH = Path("/app/data/streets.csv")

# Helper regexes for range extension
R_SINGLE_NUM = re.compile(r"^[0-9]+[A-Za-z]?$")          # 119 or 119a
R_LETTER     = re.compile(r"^[A-Za-z]$")                 # g
R_PLZ        = re.compile(r"^[0-9]{5}$")                 # 10115


def _extend_number_range(doc, start_i: int) -> int:
    """
    Given index of first number token (e.g., '119'), extend to include:
      - optional single letter after the first number (e.g., '119 g')
      - optional '-' or '/' + second number (e.g., '119-121' or '119-121a')
      - optional single letter after the second number
      - optional trailing punctuation ('.', ',', ';', ':') directly after
    Returns the exclusive end index for the span.
    """
    i = start_i
    end = i + 1

    # optional letter after the first number (e.g., '119 g')
    if end < len(doc) and R_LETTER.fullmatch(doc[end].text or ""):
        end += 1

    # optional range separator + second number (+ optional letter)
    if end + 1 < len(doc) and doc[end].text in ("-", "/") and R_SINGLE_NUM.fullmatch(doc[end + 1].text or ""):
        end += 2
        # optional letter after the second number (e.g., '121 a')
        if end < len(doc) and R_LETTER.fullmatch(doc[end].text or ""):
            end += 1

    # optional trailing punctuation tightly attached to number/range
    if end < len(doc) and doc[end].is_punct and doc[end].text in {".", ",", ";", ":"}:
        end += 1

    # Edge case fix: if we only have a single number (no letter yet) and next is a letter
    # immediately followed by punctuation, PLZ, or end of string, include that letter
    # This handles cases like "38g, Friedberg" where 'g' is tokenized separately
    if end < len(doc) and R_LETTER.fullmatch(doc[end].text or ""):
        # Include letter if at boundary (end of doc, punctuation, or PLZ)
        next_is_boundary = (
            (end + 1 == len(doc)) or  # End of string
            (end + 1 < len(doc) and doc[end + 1].is_punct and doc[end + 1].text in {".", ",", ";", ":"}) or  # Punctuation
            (end + 1 < len(doc) and R_PLZ.fullmatch(doc[end + 1].text or ""))  # PLZ
        )
        if next_is_boundary:
            end += 1

    return end


def normalize_street_name(name: str) -> str:
    """
    Normalize for comparison:
    - strip whitespace / quotes
    - collapse spaces
    - unify Str./Strasse/ss/ß variants to Straße
    - lowercase + NFC
    """
    if not name:
        return ""

    s = name.strip()

    # remove outer quotes if present
    if s.startswith('"') and s.endswith('"') and len(s) > 1:
        s = s[1:-1].strip()

    # remove doubled / stray quotes inside
    s = s.replace('""', '"').replace('"', "")

    # collapse whitespace
    s = re.sub(r"\s+", " ", s)

    # unify Straße variants (but NOT general ss → ß, only in specific contexts)
    replacements = [
        ("Strasse", "Straße"),
        ("strasse", "straße"),
        ("Str.", "Straße"),
        ("str.", "straße"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

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
print(f"[street_gazetteer] Loading streets from {STREETS_CSV_PATH} ...")
STREET_NAMES = load_street_names(STREETS_CSV_PATH)
print(f"[street_gazetteer] Loaded {len(STREET_NAMES):,} street names.")


def _is_street_token_like(tok):
    """
    Check if a token is "street-like" for backward scanning.
    Allows:
    - Title case tokens
    - Common lowercase articles/prepositions (am, an, der, etc.)
    - Single lowercase connectors (des, der, von, etc.) between title tokens
    - Tokens with internal apostrophes if otherwise title-like
    - Hyphens between title tokens
    """
    if tok.is_title:
        return True

    # Common lowercase articles/prepositions that appear in street names
    if tok.lower_ in {"am", "an", "auf", "in", "im", "bei", "zum", "zur", "unter", "der", "den", "dem"}:
        return True

    # Single lowercase connectors (for "Str. des Friedens", "Von-der-Leyen-Str.")
    if tok.lower_ in {"des", "von"}:
        return True

    # Allow hyphens between title tokens
    if tok.text == "-":
        return True

    # Allow internal apostrophes (ASCII or typographic) in title-like tokens
    # e.g., "Auf'm" in "Auf'm Hackenfeld"
    if ("'" in tok.text or "'" in tok.text):
        cleaned = tok.text.replace("'", "").replace("'", "")
        if cleaned and cleaned[0].isupper():  # Title-like after removing apostrophes
            return True

    return False


@Language.component("street_gazetteer")
def street_gazetteer(doc):
    """
    Gazetteer-based ADDRESS component:

    - For each numeric token (potential house number),
      look left for a title-cased sequence (street name).
    - If normalized street name is in STREET_NAMES set, create ADDRESS span.

    G1 improvements:
    - Skip Roman numerals (e.g., "II. Vereinsstr. 169")
    - Extend range detection (e.g., "62-68")
    """
    new_ents = list(doc.ents)

    for i, tok in enumerate(doc):
        if not (tok.like_num or tok.text.isdigit()):
            continue

        # Look backwards for potential street name tokens
        # Skip punctuation immediately before the number (e.g., "Bahnhofstr. 42")
        j = i - 1
        while j >= 0 and doc[j].is_punct:
            j -= 1

        if j < 0:
            continue

        # Now look backwards for street-like tokens (title-cased, apostrophes, articles)
        # Guard: don't allow 2+ consecutive lowercase words
        start = j
        consecutive_lowercase = 0
        while start >= 0 and _is_street_token_like(doc[start]) and (i - start) <= 7:
            # Track consecutive lowercase to prevent over-greedy scans
            if doc[start].is_lower and doc[start].is_alpha:
                consecutive_lowercase += 1
                if consecutive_lowercase >= 2:  # Stop if 2+ consecutive lowercase words
                    break
            else:
                consecutive_lowercase = 0  # Reset on non-lowercase token
            start -= 1
        start += 1

        # G1: Skip Roman numerals at the beginning (e.g., "II. Vereinsstr.")
        # Roman numerals pattern: I, II, III, IV, V, VI, VII, VIII, IX, X, etc.
        if start > 0 and re.match(r"^[IVX]+$", doc[start].text):
            # Skip the Roman numeral
            start += 1
            # Skip any following punctuation
            while start <= j and doc[start].is_punct:
                start += 1

        if start > j:
            continue

        # Safety: cap street span at 7 tokens max
        if (j - start + 1) > 7:
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
        new_ents.append(span)

    doc.ents = filter_spans(new_ents)
    return doc
