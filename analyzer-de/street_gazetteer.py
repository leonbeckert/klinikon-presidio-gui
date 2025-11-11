# /app/street_gazetteer.py
import csv
import unicodedata
import re
from pathlib import Path

from spacy.language import Language
from spacy.tokens import Span
from spacy.util import filter_spans


STREETS_CSV_PATH = Path("/app/data/streets.csv")


def normalize_street_name(name: str) -> str:
    """
    Normalize for comparison:
    - strip whitespace / quotes
    - collapse spaces
    - unify Str./Strasse variants to Straße
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

    # unify Straße variants
    replacements = [
        ("Strasse", "Straße"),
        ("strasse", "straße"),
        ("Str.", "Straße"),
        ("str.", "straße"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    s = unicodedata.normalize("NFC", s)
    return s.lower()


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


@Language.component("street_gazetteer")
def street_gazetteer(doc):
    """
    Gazetteer-based ADDRESS component:

    - For each numeric token (potential house number),
      look left for a title-cased sequence (street name).
    - If normalized street name is in STREET_NAMES set, create ADDRESS span.
    """
    new_ents = list(doc.ents)

    for i, tok in enumerate(doc):
        if not (tok.like_num or tok.text.isdigit()):
            continue

        # Look backwards for potential street name tokens
        j = i - 1
        start = j
        while start >= 0 and doc[start].is_title and (i - start) <= 5:
            start -= 1
        start += 1

        if start >= i:
            continue

        street_tokens = doc[start:i]
        norm_street = normalize_street_name(street_tokens.text)

        if norm_street not in STREET_NAMES:
            continue

        # Build ADDRESS span = street + house number
        span_start = start
        span_end = i + 1  # include number
        label = doc.vocab.strings["ADDRESS"]
        span = Span(doc, span_start, span_end, label=label)
        new_ents.append(span)

    doc.ents = filter_spans(new_ents)
    return doc
