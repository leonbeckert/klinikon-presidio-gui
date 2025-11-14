#!/usr/bin/env python3
"""Build expanded DE+AT gazetteer with generous inclusion + smart filtering."""

import csv
import pickle
import re
import unicodedata
from pathlib import Path
from typing import Set

# Configuration
OPENPLZ_CSV = Path("analyzer-de/data/streets.csv")
DACH_CSV = Path("raw_data/str_DACH_normalized_cleaned.csv")
OUTPUT_PKL = Path("analyzer-de/data/streets_normalized_expanded.pkl")

INCLUDE_COUNTRIES = {"DE", "AT"}
MIN_LENGTH = 3

# ============================================================================
# Normalization (copied from street_gazetteer.py)
# ============================================================================

def normalize_street_name(name: str) -> str:
    """Runtime-identical normalization."""
    if not name:
        return ""
    
    s = name.strip()
    if s.startswith('"') and s.endswith('"') and len(s) > 1:
        s = s[1:-1].strip()
    if s.startswith('(') and s.endswith(')') and len(s) > 2:
        s = s[1:-1].strip()
    
    s = s.replace('""', '"').replace('"', "")
    s = s.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    s = s.replace('–', '-').replace('—', '-')
    s = s.replace('\u2019', "'").replace('`', "'")
    s = re.sub(r"\s+", " ", s)
    
    replacements = [
        ("Strasse", "Straße"), ("strasse", "straße"),
        ("Str.", "Straße"), ("str.", "straße"),
        ("Wg.", "Weg"), ("wg.", "weg"), ("W.", "Weg"), ("w.", "weg"),
        ("Pl.", "Platz"), ("pl.", "platz"),
        ("Al.", "Allee"), ("al.", "allee"), ("All.", "Allee"), ("all.", "allee"),
        ("Rg.", "Ring"), ("rg.", "ring"), ("R.", "Ring"), ("r.", "ring"),
        ("G.", "Gasse"), ("g.", "gasse"), ("Ga.", "Gasse"), ("ga.", "gasse"),
        ("Dm.", "Damm"), ("dm.", "damm"),
        ("Uf.", "Ufer"), ("uf.", "ufer"),
        ("Chaus.", "Chaussee"), ("chaus.", "chaussee"),
        ("Pf.", "Pfad"), ("pf.", "pfad"),
        ("Stg.", "Steig"), ("stg.", "steig"),
        ("Gart.", "Garten"), ("gart.", "garten"),
        ("Gr.", "Graben"), ("gr.", "graben"),
        ("Mkt.", "Markt"), ("mkt.", "markt"),
        ("Prom.", "Promenade"), ("prom.", "promenade"),
        ("Pk.", "Park"), ("pk.", "park"),
        ("Bg.", "Berg"), ("bg.", "berg"),
        ("Hf.", "Hof"), ("hf.", "hof"),
        ("T.", "Tor"), ("t.", "tor"),
        ("St.", "Sankt"), ("st.", "sankt"),
    ]
    
    for old, new in replacements:
        s = s.replace(old, new)
    
    s = re.sub(r'(?<=-)[Ss]tr\.(?![aä][sß]e)', 'Straße', s)
    s = unicodedata.normalize("NFC", s)
    return s.casefold()

# ============================================================================
# Filters
# ============================================================================

BAD_SUBSTRINGS = {
    "friedhof", "parkplatz", "parkhaus", "garage", "spielplatz", "sportplatz",
    "klinikum", "krankenhaus", "klinik", "arztpraxis",
    "schule", "grundschule", "gymnasium", "kindergarten", "kita",
    "uni ", "universität", "hochschule", "campus", "rathaus",
    "feuerwehr", "polizei", "kaserne",
    "bahnhof", "hauptbahnhof", "bf ", "bhf ", "zob", "busbahnhof",
    "flugplatz", "flughafen", "hafen", "schiffsanleger",
    "bahnsteig", "gleis ", "steg ", "parkebene",
    "stadion", "arena", "sporthalle", "schwimmbad", "therme",
    "kino", "theater", "casino",
    "kirche", "dom ", "kapelle", "kloster", "moschee", "synagoge", "tempel",
    "park", "naturpark", "wald", "waldlehrpfad", "naturlehrpfad",
    "wanderweg", "radweg", "lehrpfad", "erlebnisweg", "rundweg", "höhenweg",
    "bergstation", "talstation", "seilbahn",
    "einkaufszentrum", "shopping", "center", "gewerbegebiet", "industriepark",
    "messe", "messezentrum", "fabrik", "werk ", "werksgelände",
    "nicht betreten", "privat", "privatweg", "provisorisch",
    "zufahrt haus", "zugang ", "ausfahrt", "grundstückszufahrt",
    "trail", "pfad", "steig",
    "campingplatz", "rastplatz", "schloss", "burg ", "festung",
    "museum", "gedenkstätte", "denkmal", "skulpturen",
    "brunnen", "teich", "see", "brücke", "tunnel",
}

BAD_PATTERNS = [
    r"^[0-9]+$", r"^[0-9]+[a-z]?$", r"^weg [ivx]+$", r"^[a-z]$",
    r"^[ablsrgm][0-9]+$", r"zufahrt (haus )?nr\.? [0-9]+",
    r"^weg [a-z]$", r"^zeile [a-z]$",
]

def should_exclude(norm: str) -> bool:
    if not norm or len(norm) < MIN_LENGTH:
        return True
    lower = norm.lower()
    if any(bad in lower for bad in BAD_SUBSTRINGS):
        return True
    if any(re.search(pat, lower) for pat in BAD_PATTERNS):
        return True
    if not re.search(r"[a-zäöüß]", lower):
        return True
    return False

# ============================================================================
# Loaders
# ============================================================================

def load_openplz() -> Set[str]:
    names = set()
    if not OPENPLZ_CSV.exists():
        print(f"⚠️  {OPENPLZ_CSV} not found")
        return names
    
    print(f"\n[1] Loading OpenPLZ DE...")
    with OPENPLZ_CSV.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get('name', '').strip()
            if raw:
                norm = normalize_street_name(raw)
                if norm and not should_exclude(norm):
                    names.add(norm)
    
    print(f"  → {len(names):,} streets")
    return names

def load_dach() -> Set[str]:
    names = set()
    if not DACH_CSV.exists():
        print(f"⚠️  {DACH_CSV} not found")
        return names
    
    print(f"\n[2] Loading DACH expanded (DE+AT)...")
    stats = {"country": 0, "empty": 0, "filtered": 0, "malformed": 0}
    
    with DACH_CSV.open(encoding='utf-8', errors='replace', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                country = row.get('Country', '').strip().upper()
                if country not in INCLUDE_COUNTRIES:
                    stats["country"] += 1
                    continue
                
                raw = row.get('Name', '').strip()
                if not raw or len(raw) < MIN_LENGTH:
                    stats["empty"] += 1
                    continue
                
                norm = normalize_street_name(raw)
                if not norm or should_exclude(norm):
                    stats["filtered"] += 1
                    continue
                
                names.add(norm)
            except:
                stats["malformed"] += 1
    
    print(f"  → {len(names):,} streets")
    print(f"  → Skipped: country={stats['country']:,}, empty={stats['empty']:,}, "
          f"filtered={stats['filtered']:,}, malformed={stats['malformed']:,}")
    return names

# ============================================================================
# Main
# ============================================================================

def main():
    print("="*80)
    print("Building Expanded DE+AT Gazetteer")
    print("="*80)
    
    openplz = load_openplz()
    dach = load_dach()
    all_names = openplz | dach
    
    print(f"\n[3] Merging...")
    print(f"  → OpenPLZ:    {len(openplz):,}")
    print(f"  → DACH:       {len(dach):,}")
    print(f"  → Combined:   {len(all_names):,}")
    print(f"  → New added:  {len(all_names) - len(openplz):,}")
    
    print(f"\n[4] Sanity checks...")
    tests = ["hauptstrasse", "mühlenstrasse", "am markt", "von-pastor-strasse",
             "babenbergergasse", "donnersmarkstrasse"]  # AT streets
    for test in tests:
        print(f"  {'✓' if test in all_names else '✗'} '{test}'")
    
    print(f"\n[5] Saving...")
    OUTPUT_PKL.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PKL.open('wb') as f:
        pickle.dump(all_names, f)
    
    size_mb = OUTPUT_PKL.stat().st_size / 1024 / 1024
    print(f"  → {OUTPUT_PKL}")
    print(f"  → {len(all_names):,} streets ({size_mb:.1f} MB)")
    
    print("\n" + "="*80)
    print("✓ Complete! Now rebuild Docker container.")
    print("="*80)

if __name__ == "__main__":
    main()
