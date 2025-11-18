#!/usr/bin/env python3
"""Local version of expanded gazetteer preprocessing."""

import csv
import pickle
import re
from pathlib import Path
from typing import Set

# Import runtime normalization
import sys
sys.path.insert(0, 'analyzer-de')
from street_gazetteer import normalize_street_name

# Configuration
OPENPLZ_DE_CSV = Path("analyzer-de/data/streets.csv")
DACH_EXPANDED_CSV = Path("raw_data/str_DACH_normalized_cleaned.csv")
OUTPUT_PKL = Path("analyzer-de/data/streets_normalized_expanded.pkl")

INCLUDE_COUNTRIES = {"DE", "AT"}
MIN_LENGTH = 3

# Exclusion filters
BAD_SUBSTRINGS = {
    "friedhof", "öffentliche grünfläche", "öffentlicher parkplatz",
    "parkplatz", "parkhaus", "garage", "tiefgarage",
    "spielplatz", "sportplatz", "bolzplatz",
    "klinikum", "krankenhaus", "klinik", "arztpraxis",
    "schule", "grundschule", "gymnasium", "realschule",
    "kindergarten", "kita",
    "uni ", "universität", "hochschule", "campus",
    "rathaus", "gemeindeamt",
    "feuerwehr", "polizei",
    "bahnhof", "hauptbahnhof", "bf ", "bhf ",
    "flugplatz", "flughafen",
    "hafen", "schiffsanleger",
    "zob", "busbahnhof",
    "bahnsteig", "gleis ", "steg ",
    "stadion", "arena", "sporthalle",
    "schwimmbad", "therme",
    "kino", "theater",
    "casino",
    "kirche", "dom ", "kapelle", "kloster",
    "moschee", "synagoge", "tempel",
    "park", "naturpark",
    "wald", "waldlehrpfad", "naturlehrpfad",
    "wanderweg", "radweg", "lehrpfad", "erlebnisweg",
    "bergstation", "talstation",
    "einkaufszentrum", "shopping", "center", "zentrum",
    "gewerbegebiet", "industriepark",
    "messe", "messezentrum",
    "fabrik", "werk ", "werksgelände",
    "nicht betreten", "privat", "privatweg",
    "zufahrt haus", "zugang ", "ausfahrt",
    "grundstückszufahrt",
    "trail", "pfad", "steig", "rundweg", "höhenweg",
    "campingplatz", "rastplatz",
    "schloss", "burg ", "festung",
    "museum", "gedenkstätte",
    "brunnen", "teich", "see",
    "brücke", "tunnel",
    "skulpturen", "denkmal",
}

BAD_PATTERNS = [
    r"^[0-9]+$",
    r"^[0-9]+[a-z]?$",
    r"^weg [ivx]+$",
    r"^[a-z]$",
    r"^b[0-9]+$",
    r"^a[0-9]+$",
    r"^[lsrgm][0-9]+$",
    r"zufahrt (haus )?nr\.? [0-9]+",
    r"^weg [a-z]$",
    r"^zeile [a-z]$",
]

def should_exclude_name(norm: str) -> bool:
    if not norm or len(norm) < MIN_LENGTH:
        return True
    norm_lower = norm.lower()
    for bad in BAD_SUBSTRINGS:
        if bad in norm_lower:
            return True
    for pattern in BAD_PATTERNS:
        if re.search(pattern, norm_lower):
            return True
    if not re.search(r"[a-zäöüß]", norm_lower):
        return True
    return False

def load_openplz_streets() -> Set[str]:
    names = set()
    if not OPENPLZ_DE_CSV.exists():
        print(f"⚠️  OpenPLZ not found: {OPENPLZ_DE_CSV}")
        return names
    
    print(f"\n[1] Loading OpenPLZ DE streets...")
    with OPENPLZ_DE_CSV.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = row.get('name', '').strip()
            if not raw_name:
                continue
            norm = normalize_street_name(raw_name)
            if norm and not should_exclude_name(norm):
                names.add(norm)
    
    print(f"  → {len(names):,} streets")
    return names

def load_dach_expanded_streets() -> Set[str]:
    names = set()
    if not DACH_EXPANDED_CSV.exists():
        print(f"⚠️  DACH file not found: {DACH_EXPANDED_CSV}")
        return names
    
    print(f"\n[2] Loading DACH expanded (DE+AT)...")
    skipped = {"country": 0, "empty": 0, "short": 0, "filtered": 0, "malformed": 0}
    
    with DACH_EXPANDED_CSV.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            try:
                country = row.get('Country', '').strip().upper()
                if country not in INCLUDE_COUNTRIES:
                    skipped["country"] += 1
                    continue
                
                raw_name = row.get('Name', '').strip()
                if not raw_name or len(raw_name) < MIN_LENGTH:
                    skipped["empty"] += 1
                    continue
                
                norm = normalize_street_name(raw_name)
                if not norm:
                    skipped["empty"] += 1
                    continue
                
                if should_exclude_name(norm):
                    skipped["filtered"] += 1
                    continue
                
                names.add(norm)
            except Exception:
                skipped["malformed"] += 1
    
    print(f"  → {len(names):,} streets")
    print(f"  → Skipped: country={skipped['country']:,}, empty={skipped['empty']:,}, "
          f"filtered={skipped['filtered']:,}, malformed={skipped['malformed']:,}")
    return names

def build_gazetteer():
    print("="*80)
    print("Building Expanded DE+AT Gazetteer")
    print("="*80)
    
    openplz = load_openplz_streets()
    dach = load_dach_expanded_streets()
    all_names = openplz | dach
    
    print(f"\n[3] Merging...")
    print(f"  → OpenPLZ: {len(openplz):,}")
    print(f"  → DACH: {len(dach):,}")
    print(f"  → Combined: {len(all_names):,}")
    print(f"  → New added: {len(all_names) - len(openplz):,}")
    
    print(f"\n[4] Sanity checks...")
    for test in ["hauptstrasse", "mühlenstrasse", "am markt", "von-pastor-strasse"]:
        print(f"  {'✓' if test in all_names else '✗'} '{test}'")
    
    print(f"\n[5] Saving to {OUTPUT_PKL}...")
    OUTPUT_PKL.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PKL.open('wb') as f:
        pickle.dump(all_names, f)
    
    print(f"  → Saved {len(all_names):,} streets ({OUTPUT_PKL.stat().st_size / 1024 / 1024:.1f} MB)")
    print("\n" + "="*80)
    print("✓ Complete!")
    print("="*80)

if __name__ == "__main__":
    build_gazetteer()
