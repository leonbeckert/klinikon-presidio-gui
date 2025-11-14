#!/usr/bin/env python3
"""
Expanded gazetteer preprocessing for DE+AT streets.

Strategy:
1. Include DE+AT streets from multiple sources
2. Be generous with inclusion (real streets only)
3. Filter out POIs, facilities, landmarks
4. Use same normalization as runtime
5. Deduplicate by normalized name

Target: 800K-1M unique normalized streets
Expected improvement: AT from 57% → 80%+, DE stays ~94%
"""

import csv
import pickle
import re
from pathlib import Path
from typing import Set

# Import the runtime normalization function
import sys
sys.path.insert(0, str(Path(__file__).parent))
from street_gazetteer import normalize_street_name

# ============================================================================
# Configuration
# ============================================================================

# Source files
OPENPLZ_DE_CSV = Path("/app/data/streets.csv")  # Existing 422K DE streets
DACH_EXPANDED_CSV = Path(__file__).parent.parent / "raw_data" / "str_DACH_normalized_cleaned.csv"  # 632K streets
OUTPUT_PKL = Path("/app/data/streets_normalized.pkl")

# Only include these countries
INCLUDE_COUNTRIES = {"DE", "AT"}

# ============================================================================
# Exclusion filters
# ============================================================================

# POIs, facilities, landmarks to exclude (substring match, case-insensitive)
BAD_SUBSTRINGS = {
    # Existing exclusions
    "friedhof", "öffentliche grünfläche", "öffentlicher parkplatz",

    # Facilities
    "parkplatz", "parkhaus", "garage", "tiefgarage",
    "spielplatz", "sportplatz", "bolzplatz",
    "klinikum", "krankenhaus", "klinik", "arztpraxis", "gesundheitszentrum",
    "schule", "grundschule", "gymnasium", "realschule", "berufsschule",
    "kindergarten", "kita",
    "uni ", "universität", "hochschule", "campus",
    "rathaus", "gemeindeamt", "bürgeramt",
    "feuerwehr", "polizei", "kaserne",

    # Transport facilities (not streets)
    "bahnhof", "hauptbahnhof", "bf ", "bhf ",
    "flugplatz", "flughafen", "airport",
    "hafen", "anlegestelle", "schiffsanleger",
    "bushof", "zob", "busbahnhof",
    "bahnsteig", "gleis ", "steg ",
    "parkebene", "tiefgarage",

    # Sports & entertainment
    "stadion", "arena", "sporthalle", "turnhalle",
    "schwimmbad", "freibad", "hallenbad", "therme", "sauna",
    "kino", "theater", "oper", "philharmonie",
    "casino", "disco", "club",

    # Religious buildings
    "kirche", "dom ", "kapelle", "kloster", "abtei",
    "moschee", "synagoge", "tempel",

    # Parks & nature (not streets)
    "park", "naturpark", "wildpark",
    "wald", "forst", "waldlehrpfad", "naturlehrpfad",
    "wanderweg", "radweg", "lehrpfad", "erlebnisweg",
    "bergstation", "talstation", "seilbahn",

    # Commercial/industrial
    "einkaufszentrum", "shopping", "center", "zentrum",
    "gewerbegebiet", "industriepark", "industriegebiet",
    "messe", "messezentrum", "ausstellungsgelände",
    "fabrik", "werk ", "werksgelände",

    # Generic/invalid
    "nicht betreten", "privat", "privatweg", "provisorisch",
    "zufahrt haus", "zugang ", "ausfahrt", "einfahrt",
    "grundstückszufahrt", "feuerwehr zufahrt",
    "abschnitt", "bauabschnitt", "baulos",
    "trail", "pfad", "steig", "rundweg", "höhenweg",
    "campingplatz", "rastplatz", "parkplatz",
    "schloss", "burg ", "festung", "turm",
    "museum", "gedenkstätte", "denkmal",
    "brunnen", "quelle", "teich", "see",
    "brücke", "tunnel", "unterführung",
    "grenze", "grenzübergang",
}

# Invalid patterns (regex match)
BAD_PATTERNS = [
    r"^[0-9]+$",  # Pure numbers
    r"^[0-9]+[a-z]?$",  # Numbers with optional letter (e.g., "3a")
    r"^weg [ivx]+$",  # Roman numeral ways without proper names
    r"^[a-z]$",  # Single letters
    r"^b[0-9]+$",  # Highway codes (B515, B6)
    r"^a[0-9]+$",  # Autobahn codes (A2, A10)
    r"^[lsrgm][0-9]+$",  # Road codes
    r"^av[0-9]+",  # AV codes
    r"zufahrt (haus )?nr\.? [0-9]+",  # House access roads
    r"^weg [a-z]$",  # Generic way letters (Weg A, Weg B)
    r"^zeile [a-z]$",  # Generic row letters
]

# Minimum length for street names
MIN_LENGTH = 3

# ============================================================================
# Helper functions
# ============================================================================

def should_exclude_name(norm: str) -> bool:
    """Check if normalized name should be excluded."""
    if not norm or len(norm) < MIN_LENGTH:
        return True

    # Check bad substrings (case-insensitive)
    norm_lower = norm.lower()
    for bad in BAD_SUBSTRINGS:
        if bad in norm_lower:
            return True

    # Check bad patterns
    for pattern in BAD_PATTERNS:
        if re.search(pattern, norm_lower):
            return True

    # Require at least one letter
    if not re.search(r"[a-zäöüß]", norm_lower):
        return True

    return False


def load_openplz_streets() -> Set[str]:
    """Load existing OpenPLZ DE streets."""
    names = set()

    if not OPENPLZ_DE_CSV.exists():
        print(f"⚠️  OpenPLZ file not found: {OPENPLZ_DE_CSV}")
        return names

    print(f"\n[1] Loading OpenPLZ DE streets from {OPENPLZ_DE_CSV}...")

    with OPENPLZ_DE_CSV.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = row.get('name', '').strip()
            if not raw_name:
                continue

            norm = normalize_street_name(raw_name)
            if norm and not should_exclude_name(norm):
                names.add(norm)

    print(f"  → Loaded {len(names):,} streets from OpenPLZ")
    return names


def load_dach_expanded_streets() -> Set[str]:
    """Load DE+AT streets from expanded DACH dataset."""
    names = set()

    if not DACH_EXPANDED_CSV.exists():
        print(f"⚠️  DACH expanded file not found: {DACH_EXPANDED_CSV}")
        return names

    print(f"\n[2] Loading expanded DACH streets from {DACH_EXPANDED_CSV}...")

    skipped_country = 0
    skipped_empty = 0
    skipped_short = 0
    skipped_filtered = 0
    skipped_malformed = 0

    with DACH_EXPANDED_CSV.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, 1):
            try:
                # Get country (handle malformed rows)
                country = row.get('Country', '').strip().upper()

                # Skip if not DE/AT
                if country not in INCLUDE_COUNTRIES:
                    skipped_country += 1
                    continue

                # Get street name
                raw_name = row.get('Name', '').strip()
                if not raw_name:
                    skipped_empty += 1
                    continue

                # Skip very short names
                if len(raw_name) < MIN_LENGTH:
                    skipped_short += 1
                    continue

                # Normalize
                norm = normalize_street_name(raw_name)
                if not norm:
                    skipped_empty += 1
                    continue

                # Apply filters
                if should_exclude_name(norm):
                    skipped_filtered += 1
                    continue

                names.add(norm)

            except Exception as e:
                skipped_malformed += 1
                if skipped_malformed <= 10:  # Show first 10 errors
                    print(f"  ⚠️  Row {i} malformed: {e}")

    print(f"  → Loaded {len(names):,} streets from DACH dataset")
    print(f"  → Skipped: country={skipped_country:,}, empty={skipped_empty:,}, "
          f"short={skipped_short:,}, filtered={skipped_filtered:,}, malformed={skipped_malformed:,}")

    return names


def build_gazetteer():
    """Build complete gazetteer from all sources."""
    print("="*80)
    print("Building expanded DE+AT street gazetteer")
    print("="*80)

    # Load from all sources
    openplz_names = load_openplz_streets()
    dach_names = load_dach_expanded_streets()

    # Merge (union)
    all_names = openplz_names | dach_names

    print(f"\n[3] Merging and deduplicating...")
    print(f"  → OpenPLZ: {len(openplz_names):,} streets")
    print(f"  → DACH expanded: {len(dach_names):,} streets")
    print(f"  → Combined unique: {len(all_names):,} streets")
    print(f"  → New streets added: {len(all_names) - len(openplz_names):,}")

    # Sanity checks
    print(f"\n[4] Sanity checks...")
    test_streets = [
        "hauptstrasse",  # Common German
        "mühlenstrasse",  # With umlaut
        "am markt",  # Preposition-starting
        "an den haselwiesen",  # Multi-word
        "von-pastor-strasse",  # Hyphenated
    ]

    for street in test_streets:
        in_set = street in all_names
        status = "✓" if in_set else "✗"
        print(f"  {status} '{street}' in gazetteer: {in_set}")

    # Save
    print(f"\n[5] Saving to {OUTPUT_PKL}...")
    OUTPUT_PKL.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PKL.open('wb') as f:
        pickle.dump(all_names, f)

    print(f"  → Saved {len(all_names):,} normalized street names")
    print(f"  → File size: {OUTPUT_PKL.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n" + "="*80)
    print("✓ Gazetteer preprocessing complete!")
    print("="*80)

    return all_names


if __name__ == "__main__":
    build_gazetteer()
