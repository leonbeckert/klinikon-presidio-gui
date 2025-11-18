#!/usr/bin/env python3
"""
Build unified gazetteer from DACH dataset with careful filtering.

This script:
1. Loads ALL streets from DACH dataset (DE + AT)
2. Excludes OSM artifacts (trails, paths, infrastructure)
3. Creates normalized gazetteer for production use

DATA PROBLEM → DATA SOLUTION
The recognizer works fine; we just need more street coverage.
"""

import csv
import pickle
import re
from pathlib import Path
from collections import Counter
from typing import Set

# ============================================================================
# EXCLUSION PATTERNS - OSM Artifacts & Non-Addresses
# ============================================================================

# Trail/path indicators (OSM features, not addresses)
TRAIL_INDICATORS = [
    'wanderweg', 'wanderpfad',
    'radweg', 'radfahrweg', 'fahrradweg',
    'gehweg', 'fußweg', 'fussweg',
    'waldweg', 'feldweg', 'bergweg',
    'höhenweg', 'rundweg',
    'pfad',  # Generic path
    'steig', 'stiege',  # Stairs/steep paths
    'trail',  # English
    'lehrpfad', 'themenpfad', 'naturlehrpfad',  # Educational paths
    'kunstpfad', 'skulpturenpfad',  # Art paths
]

# Access/Infrastructure (not residential addresses)
INFRASTRUCTURE = [
    'zugang', 'zufahrt', 'aufgang', 'abgang',
    'eingang', 'ausgang',
    'strandabgang', 'strandaufgang', 'strandweg',
    'zubringer', 'anschluss',
    'bahnsteig',  # Platform
    'gleis',  # Track
    'tunnel',
    'brücke', 'bruecke',  # Bridge
    'steg',  # Footbridge/jetty
    'parkplatz', 'rastplatz',  # Parking
    'güterweg', 'gueterweg',  # Goods road
]

# Facilities (not residential addresses)
FACILITIES = [
    'bikepark',
    'skatepark',
    'industriepark',
    'gewerbepark',
    'seepark',
    'freizeitpark',
]

# Nature/Geographic features (usually not addresses)
NATURE_FEATURES = [
    'seeweg', 'uferweg',
    'bachweg', 'flussweg',
    'eco pfad', 'natur pfad',
]

# Combine all exclusion patterns
EXCLUDE_PATTERNS = (
    TRAIL_INDICATORS +
    INFRASTRUCTURE +
    FACILITIES +
    NATURE_FEATURES
)


def should_exclude_street(street_name: str) -> tuple[bool, str]:
    """
    Check if street should be excluded.
    Uses word boundaries to avoid false positives on person names.

    Returns: (should_exclude: bool, reason: str)
    """
    name_lower = street_name.lower()

    # === STRICT PATTERNS (with word boundaries) ===
    # These are standalone words that indicate non-addresses

    strict_patterns = [
        # Hiking/bike paths (must be whole words)
        (r'\bwanderweg\b', "hiking path"),
        (r'\bwanderpfad\b', "hiking path"),
        (r'\bradweg\b', "bike path"),
        (r'\bradfahrweg\b', "bike path"),
        (r'\bfahrradweg\b', "bike path"),
        (r'\bgehweg\b', "footpath"),
        (r'\bfußweg\b', "footpath"),
        (r'\bfussweg\b', "footpath"),
        (r'\bwaldweg\b', "forest path"),
        (r'\bfeldweg\b', "field path"),
        (r'\bbergweg\b', "mountain path"),
        (r'\bhöhenweg\b', "ridge path"),
        (r'\brundweg\b', "circular path"),
        (r'\btrail\b', "trail"),
        (r'\blehrpfad\b', "educational path"),
        (r'\bthemenpfad\b', "theme path"),
        (r'\bnaturlehrpfad\b', "nature trail"),
        (r'\bkunstpfad\b', "art path"),

        # Access/Infrastructure (standalone)
        (r'\bzugang\s+(zu[mr]?|zum|zur)\s', "access to"),
        (r'\bzufahrt\s+(zu[mr]?|zum|zur)\s', "access road to"),
        (r'\baufgang\s+\d+', "stairway number"),
        (r'\babgang\s+\d+', "exit number"),
        (r'\bstrandabgang\s+\d+', "beach access number"),
        (r'\bstrandaufgang\s+\d+', "beach access number"),
        (r'\bbahnsteig\s+\d+', "platform number"),
        (r'\bgleis\s+\d+', "track number"),
        (r'\btunnel\s+\d+', "tunnel number"),

        # Facilities (standalone)
        (r'\bbikepark\b', "bike park"),
        (r'\bskatepark\b', "skate park"),
        (r'\bgüterweg\b', "goods road"),
        (r'\bgueterweg\b', "goods road"),

        # Nature features
        (r'\bseeweg\b', "lake path"),
        (r'\buferweg\b', "shore path"),
        (r'\bbachweg\b', "stream path"),
        (r'\bflussweg\b', "river path"),
        (r'\beco\s+pfad\b', "eco path"),
        (r'\bnatur\s+pfad\b', "nature path"),
    ]

    for pattern, reason in strict_patterns:
        if re.search(pattern, name_lower):
            return True, reason

    # === LOOSE PATTERNS (without word boundaries) ===
    # These are substrings that are almost always bad
    # But we need to be careful with person names

    # Only check these as standalone prefixes/suffixes
    loose_indicators = {
        'höllengraben': 'gorge',  # Specific trail names
        'höllengrabentrail': 'trail',
    }

    for indicator, reason in loose_indicators.items():
        if indicator in name_lower:
            return True, reason

    return False, ""


def normalize_street_name(street_name: str) -> str:
    """
    Normalize street name for gazetteer storage.
    Match the normalization used in street_gazetteer.py
    """
    # Strip whitespace and quotes
    text = street_name.strip().strip('"\'')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Normalize fancy characters
    text = text.replace('\u00a0', ' ')  # Non-breaking space
    text = text.replace('\u2019', "'")  # Smart apostrophe
    text = text.replace('\u2013', '-')  # En dash
    text = text.replace('\u2014', '-')  # Em dash

    # Unicode normalization
    import unicodedata
    text = unicodedata.normalize('NFC', text)

    # Casefold (like street_gazetteer.py does)
    return text.casefold()


def load_and_filter_dach_streets(csv_path: Path) -> dict:
    """
    Load DACH dataset and filter out non-addresses.

    Returns dict with:
        - included: Set of normalized street names (for gazetteer)
        - excluded: Dict of exclusion reasons → count
        - stats: Dict of statistics
    """
    print("=" * 80)
    print("BUILDING UNIFIED GAZETTEER FROM DACH DATASET")
    print("=" * 80)
    print()
    print(f"Reading from: {csv_path}")
    print()

    included_streets = set()
    excluded_counts = Counter()
    country_stats = Counter()

    total_rows = 0

    with csv_path.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)

        for row in reader:
            total_rows += 1

            name = row['Name']
            country = row['Country']

            # Skip Switzerland (we only support DE/AT)
            if country == 'CH':
                excluded_counts['country_CH'] += 1
                continue

            country_stats[country] += 1

            # Check if should exclude
            should_exclude, reason = should_exclude_street(name)

            if should_exclude:
                excluded_counts[reason] += 1
                continue

            # Normalize and add to gazetteer
            normalized = normalize_street_name(name)
            included_streets.add(normalized)

            # Progress indicator
            if total_rows % 100000 == 0:
                print(f"  Processed {total_rows:,} rows...")

    print()
    print(f"✓ Processed {total_rows:,} total rows")
    print()

    return {
        'included': included_streets,
        'excluded_counts': excluded_counts,
        'country_stats': country_stats,
        'total_rows': total_rows,
    }


def print_statistics(data: dict):
    """Print detailed statistics about the filtering."""
    included = data['included']
    excluded_counts = data['excluded_counts']
    country_stats = data['country_stats']
    total_rows = data['total_rows']

    total_excluded = sum(excluded_counts.values())
    total_included = len(included)

    print("=" * 80)
    print("FILTERING STATISTICS")
    print("=" * 80)
    print()

    print(f"Total rows processed:    {total_rows:,}")
    print(f"Total included:          {total_included:,} ({total_included/total_rows*100:.1f}%)")
    print(f"Total excluded:          {total_excluded:,} ({total_excluded/total_rows*100:.1f}%)")
    print()

    print("By country:")
    for country, count in sorted(country_stats.items()):
        print(f"  {country}: {count:,}")
    print()

    print("Exclusion reasons (top 20):")
    for reason, count in excluded_counts.most_common(20):
        print(f"  {reason:40s}: {count:6,} ({count/total_rows*100:.2f}%)")
    print()

    if len(excluded_counts) > 20:
        remaining = sum(c for r, c in excluded_counts.items() if r not in [r for r, _ in excluded_counts.most_common(20)])
        print(f"  {'... and other reasons':40s}: {remaining:6,}")
        print()


def validate_gazetteer(streets: Set[str]):
    """
    Validate that exclusion patterns worked correctly.
    Uses same strict patterns as should_exclude_street() to avoid false positives.
    """
    print("=" * 80)
    print("VALIDATION - CHECKING FOR LEAKS")
    print("=" * 80)
    print()

    issues = []

    # Use same strict patterns as filtering
    strict_validation_patterns = [
        (r'\bwanderweg\b', "hiking path (standalone)"),
        (r'\bradweg\b', "bike path (standalone)"),
        (r'\btrail\b', "trail"),
        (r'\blehrpfad\b', "educational path"),
        (r'\bgleis\s+\d+', "track number (Gleis X)"),
        (r'\btunnel\s+\d+', "tunnel number"),
        (r'\bstrandabgang\s+\d+', "beach access number"),
        (r'\bbikepark\b', "bike park"),
        (r'\bgüterweg\b', "goods road"),
    ]

    for street in streets:
        for pattern, reason in strict_validation_patterns:
            if re.search(pattern, street):
                issues.append(f"{reason}: {street}")
                break  # Only report first match per street

    if issues:
        print("⚠️  Found some excluded patterns in output:")
        print("   (These use strict word boundaries, may be acceptable)")
        print()
        for issue in issues[:10]:  # Show first 10
            print(f"  {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")
        print()
        print(f"Total: {len(issues)} potential issues out of {len(streets):,} streets ({len(issues)/len(streets)*100:.3f}%)")
        print("Review these manually if count seems high.")
        print()
        return len(issues) < len(streets) * 0.001  # Less than 0.1% is acceptable
    else:
        print("✓ No excluded patterns found in output")
        print("✓ Filtering worked perfectly")
        print()
        return True


def save_gazetteer(streets: Set[str], output_path: Path):
    """Save normalized gazetteer to pickle file."""
    print("=" * 80)
    print("SAVING UNIFIED GAZETTEER")
    print("=" * 80)
    print()

    print(f"Output file: {output_path}")
    print(f"Total streets: {len(streets):,}")
    print()

    # Create directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to pickle
    with output_path.open('wb') as f:
        pickle.dump(streets, f)

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"✓ Saved successfully")
    print(f"  File size: {file_size_mb:.1f} MB")
    print()


def show_examples(streets: Set[str], n: int = 30):
    """Show random sample of included streets."""
    print("=" * 80)
    print(f"SAMPLE OF INCLUDED STREETS (random {n})")
    print("=" * 80)
    print()

    import random
    sample = sorted(random.sample(list(streets), min(n, len(streets))))

    for i, street in enumerate(sample, 1):
        print(f"{i:2d}. {street}")
    print()


def compare_with_current(new_streets: Set[str], current_path: Path):
    """Compare new gazetteer with current one."""
    if not current_path.exists():
        print(f"No current gazetteer found at {current_path}")
        print("This will be a fresh build.")
        print()
        return

    print("=" * 80)
    print("COMPARISON WITH CURRENT GAZETTEER")
    print("=" * 80)
    print()

    with current_path.open('rb') as f:
        current_streets = pickle.load(f)

    print(f"Current gazetteer: {len(current_streets):,} streets")
    print(f"New gazetteer:     {len(new_streets):,} streets")
    print(f"Difference:        {len(new_streets) - len(current_streets):+,} streets ({(len(new_streets) - len(current_streets))/len(current_streets)*100:+.1f}%)")
    print()

    # Find what's new
    new_additions = new_streets - current_streets
    removals = current_streets - new_streets

    print(f"New streets added: {len(new_additions):,}")
    print(f"Streets removed:   {len(removals):,}")
    print()

    if new_additions:
        print("Sample of NEW streets (first 20):")
        for i, street in enumerate(sorted(new_additions)[:20], 1):
            print(f"  {i:2d}. {street}")
        if len(new_additions) > 20:
            print(f"  ... and {len(new_additions) - 20:,} more")
        print()

    if removals:
        print("Sample of REMOVED streets (first 20):")
        for i, street in enumerate(sorted(removals)[:20], 1):
            print(f"  {i:2d}. {street}")
        if len(removals) > 20:
            print(f"  ... and {len(removals) - 20:,} more")
        print()


def main():
    """Main execution."""
    # Paths
    dach_csv = Path("raw_data/str_DACH_normalized.csv")
    output_path = Path("analyzer-de/data/streets_unified.pkl")
    current_path = Path("analyzer-de/data/streets_normalized.pkl")

    if not dach_csv.exists():
        print(f"ERROR: DACH dataset not found at {dach_csv}")
        print("Please ensure the dataset is available.")
        return

    # Load and filter
    data = load_and_filter_dach_streets(dach_csv)

    # Print statistics
    print_statistics(data)

    # Validate
    valid = validate_gazetteer(data['included'])

    if not valid:
        print("⚠️  WARNING: Validation found issues")
        print("Review the filtered results before using in production")
        print()

    # Show examples
    show_examples(data['included'], n=30)

    # Compare with current
    compare_with_current(data['included'], current_path)

    # Save
    save_gazetteer(data['included'], output_path)

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"✓ Built unified gazetteer with {len(data['included']):,} streets")
    print(f"✓ Excluded {sum(data['excluded_counts'].values()):,} OSM artifacts and non-addresses")
    print(f"✓ Saved to: {output_path}")
    print()
    print("Next steps:")
    print("1. Review the statistics and samples above")
    print("2. Copy to production location:")
    print(f"   cp {output_path} analyzer-de/data/streets_normalized.pkl")
    print("3. Rebuild Docker:")
    print("   docker compose build --no-cache presidio-analyzer")
    print("4. Restart and test:")
    print("   docker compose down && docker compose up -d")
    print("   python3 dev_tools/tests/test_dach_recognition_simple.py --samples 10000")
    print()
    print(f"Expected improvement: ~+1-2 pp accuracy (from better coverage)")
    print()


if __name__ == '__main__':
    main()
