#!/usr/bin/env python3
"""
Standalone preprocessing script to speed up gazetteer loading.
Does NOT import street_gazetteer to avoid slow CSV load.
Copies the necessary functions inline.
"""
import csv
import pickle
import unicodedata
import re
from pathlib import Path

# Same normalization function from street_gazetteer.py
def normalize_street_name(name: str) -> str:
    """
    Normalize for comparison (copied from street_gazetteer.py).
    """
    if not name:
        return ""

    s = name.strip()

    # remove outer quotes if present
    if s.startswith('"') and s.endswith('"') and len(s) > 1:
        s = s[1:-1].strip()

    # remove surrounding parentheses
    if s.startswith('(') and s.endswith(')') and len(s) > 2:
        s = s[1:-1].strip()

    # remove doubled / stray quotes inside
    s = s.replace('""', '"').replace('"', "")

    # normalize exotic whitespace to regular space
    s = s.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')

    # normalize fancy dashes to regular hyphen
    s = s.replace('–', '-').replace('—', '-')

    # normalize fancy apostrophes to ASCII apostrophe
    s = s.replace('\u2019', "'").replace('`', "'")

    # collapse whitespace
    s = re.sub(r"\s+", " ", s)

    # Tuple-based normalization (Phase 1 baseline)
    replacements = [
        # Straße
        ("Strasse", "Straße"),
        ("strasse", "straße"),
        ("Str.", "Straße"),
        ("str.", "straße"),
        # Weg
        ("Wg.", "Weg"),
        ("wg.", "weg"),
        ("W.", "Weg"),
        ("w.", "weg"),
        # Platz
        ("Pl.", "Platz"),
        ("pl.", "platz"),
        # Allee
        ("Al.", "Allee"),
        ("al.", "allee"),
        ("All.", "Allee"),
        ("all.", "allee"),
        # Ring
        ("Rg.", "Ring"),
        ("rg.", "ring"),
        ("R.", "Ring"),
        ("r.", "ring"),
        # Gasse
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
        # Ufer
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
        # Sankt/St.
        ("St.", "Sankt"),
        ("st.", "sankt"),
    ]

    for old, new in replacements:
        s = s.replace(old, new)

    # Targeted regex for "-Str."
    s = re.sub(r'(?<=-)[Ss]tr\.(?![aä][sß]e)', 'Straße', s, flags=re.UNICODE)

    s = unicodedata.normalize("NFC", s)
    return s.casefold()


def load_and_normalize_streets(csv_path: Path) -> set[str]:
    """Load and normalize street names from CSV."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Street CSV not found: {csv_path}")

    names: set[str] = set()
    print(f"Reading CSV...")

    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=",", quotechar='"')
        if "Name" not in reader.fieldnames:
            raise ValueError(f"'Name' column not found, columns: {reader.fieldnames}")

        count = 0
        for row in reader:
            raw = row.get("Name")
            if not raw:
                continue

            norm = normalize_street_name(raw)
            if not norm:
                continue

            # Filter out non-address POIs
            bad_words = ("friedhof", "öffentliche grünfläche", "öffentlicher parkplatz")
            if any(bad in norm for bad in bad_words):
                continue

            names.add(norm)
            count += 1

            if count % 50000 == 0:
                print(f"  Processed {count:,} streets...")

    return names


def main():
    # Determine paths (Docker or local)
    csv_path = Path("/app/data/streets.csv")
    output_path = Path("/app/data/streets_normalized.pkl")

    if not csv_path.exists():
        csv_path = Path("./analyzer-de/data/streets.csv")
        output_path = Path("./analyzer-de/data/streets_normalized.pkl")

    print(f"Loading and normalizing streets from {csv_path}...")
    street_names = load_and_normalize_streets(csv_path)

    print(f"Loaded {len(street_names):,} normalized street names")
    print(f"Saving to {output_path}...")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('wb') as f:
        pickle.dump(street_names, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Verify
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✓ Saved successfully ({size_mb:.1f} MB)")

    # Test loading speed
    import time
    start = time.time()
    with output_path.open('rb') as f:
        test_load = pickle.load(f)
    elapsed = time.time() - start
    print(f"✓ Pickle loads in {elapsed:.2f}s (vs ~60s for CSV normalization)")
    print(f"✓ Verified: {len(test_load):,} entries")


if __name__ == "__main__":
    main()
