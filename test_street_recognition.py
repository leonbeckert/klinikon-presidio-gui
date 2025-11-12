#!/usr/bin/env python3
"""
Test script to validate ADDRESS recognition against OpenPLZ street data.
Samples streets from streets.csv, generates test sentences, and validates detection.
"""
import csv
import random
import requests
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

# Configuration
# Use local path when running from host, or Docker path when inside container
if Path("/app/data/streets.csv").exists():
    STREETS_CSV = Path("/app/data/streets.csv")  # Path inside Docker container
else:
    STREETS_CSV = Path("./analyzer-de/data/streets.csv")  # Path on host machine

ANALYZER_URL = "http://localhost:3000/analyze"
SAMPLE_SIZE = 1000  # Number of streets to test

# German sentence templates with context words
SENTENCE_TEMPLATES = [
    "Patient wohnt {street} {number}.",
    "Bitte an {street} {number} schicken.",
    "Der Termin ist in der {street} {number}.",
    "Wohnhaft {street} {number}.",
    "Adresse: {street} {number}",
    "Patient aus {street} {number} ist eingetroffen.",
    "Treffen in der {street} {number} um 10 Uhr.",
    "Dokumentation für {street} {number}.",
    "Kontaktadresse: {street} {number}, {city}",
    "Wohnung in {street} {number}",
]


def load_sample_streets(csv_path: Path, sample_size: int) -> List[Dict[str, str]]:
    """Load a random sample of streets from the CSV."""
    print(f"Loading streets from {csv_path}...")

    streets = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=",", quotechar='"')

        for row in reader:
            name = row.get("Name", "").strip()
            if not name:
                continue

            # Filter out obvious non-streets
            name_lower = name.lower()
            if any(x in name_lower for x in ["friedhof", "öffentliche grünfläche", "parkplatz"]):
                continue

            streets.append({
                "name": name,
                "postal_code": row.get("PostalCode", ""),
                "locality": row.get("Locality", ""),
            })

    # Random sample
    if len(streets) > sample_size:
        streets = random.sample(streets, sample_size)

    print(f"Loaded {len(streets)} streets for testing")
    return streets


def generate_house_number() -> str:
    """Generate realistic German house numbers."""
    number = random.randint(1, 200)

    # Add letter suffix sometimes (7a, 12b, etc.)
    if random.random() < 0.2:
        letter = random.choice("abcdefgh")
        return f"{number}{letter}"

    # Add range sometimes (12-14)
    if random.random() < 0.1:
        return f"{number}-{number + random.choice([2, 4, 6])}"

    return str(number)


def generate_test_sentence(street_info: Dict[str, str]) -> Tuple[str, str, str]:
    """
    Generate a test sentence with an address.
    Returns: (sentence, expected_street, expected_number)
    """
    street = street_info["name"]
    number = generate_house_number()
    city = street_info.get("locality", "")

    template = random.choice(SENTENCE_TEMPLATES)
    sentence = template.format(street=street, number=number, city=city)

    return sentence, street, number


def test_address_recognition(sentence: str, expected_street: str, expected_number: str) -> Dict:
    """
    Test if the analyzer correctly identifies the address.
    Returns result dict with detected addresses and success status.
    """
    try:
        response = requests.post(
            ANALYZER_URL,
            json={
                "text": sentence,
                "language": "de",
                "entities": ["ADDRESS"]
            },
            timeout=10
        )
        response.raise_for_status()
        results = response.json()

        # Extract detected addresses
        detected_addresses = []
        for result in results:
            if result.get("entity_type") == "ADDRESS":
                detected_text = sentence[result["start"]:result["end"]]
                detected_addresses.append({
                    "text": detected_text,
                    "start": result["start"],
                    "end": result["end"],
                    "score": result.get("score", 0)
                })

        # Check if address was detected
        success = False
        for detected in detected_addresses:
            # Success if detected text contains both street name and number
            detected_lower = detected["text"].lower()
            street_lower = expected_street.lower()

            # Normalize for comparison (handle Str./Straße variants)
            street_normalized = street_lower.replace("strasse", "straße").replace("str.", "straße")
            detected_normalized = detected_lower.replace("strasse", "straße").replace("str.", "straße")

            if expected_number in detected["text"] and (
                street_normalized in detected_normalized or
                expected_street.split()[0].lower() in detected_lower  # First word of street
            ):
                success = True
                break

        return {
            "success": success,
            "detected": detected_addresses,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "detected": [],
            "error": str(e)
        }


def run_tests(sample_size: int = SAMPLE_SIZE):
    """Run comprehensive tests on sampled streets."""
    print(f"\n{'='*80}")
    print(f"ADDRESS Recognition Test Suite")
    print(f"{'='*80}\n")

    # Load streets
    streets = load_sample_streets(STREETS_CSV, sample_size)

    # Statistics
    total_tests = len(streets)
    successful = 0
    failed = 0
    errors = 0

    failed_cases = []
    error_cases = []

    # Run tests
    print(f"\nRunning {total_tests} tests...\n")

    for i, street_info in enumerate(streets, 1):
        sentence, expected_street, expected_number = generate_test_sentence(street_info)
        result = test_address_recognition(sentence, expected_street, expected_number)

        if result["error"]:
            errors += 1
            error_cases.append({
                "sentence": sentence,
                "expected": f"{expected_street} {expected_number}",
                "error": result["error"]
            })
        elif result["success"]:
            successful += 1
        else:
            failed += 1
            failed_cases.append({
                "sentence": sentence,
                "expected": f"{expected_street} {expected_number}",
                "detected": result["detected"]
            })

        # Progress indicator
        if i % 50 == 0:
            print(f"Progress: {i}/{total_tests} ({i*100//total_tests}%) - "
                  f"Success: {successful}, Failed: {failed}, Errors: {errors}")

    # Final results
    print(f"\n{'='*80}")
    print(f"TEST RESULTS")
    print(f"{'='*80}\n")

    success_rate = (successful / total_tests * 100) if total_tests > 0 else 0

    print(f"Total Tests:    {total_tests}")
    print(f"✓ Successful:   {successful} ({success_rate:.1f}%)")
    print(f"✗ Failed:       {failed} ({failed*100//total_tests if total_tests > 0 else 0}%)")
    print(f"⚠ Errors:       {errors} ({errors*100//total_tests if total_tests > 0 else 0}%)")

    # Show sample failures
    if failed_cases:
        print(f"\n{'='*80}")
        print(f"SAMPLE FAILED CASES (showing first 10)")
        print(f"{'='*80}\n")

        for i, case in enumerate(failed_cases[:10], 1):
            print(f"{i}. Expected: {case['expected']}")
            print(f"   Sentence: {case['sentence']}")
            if case['detected']:
                print(f"   Detected: {', '.join([d['text'] for d in case['detected']])}")
            else:
                print(f"   Detected: (nothing)")
            print()

    # Show sample errors
    if error_cases:
        print(f"\n{'='*80}")
        print(f"SAMPLE ERRORS (showing first 5)")
        print(f"{'='*80}\n")

        for i, case in enumerate(error_cases[:5], 1):
            print(f"{i}. Sentence: {case['sentence']}")
            print(f"   Error: {case['error']}")
            print()

    # Analysis by detection type
    print(f"\n{'='*80}")
    print(f"DETECTION PATTERNS")
    print(f"{'='*80}\n")

    # Analyze failed cases by street type
    street_patterns = defaultdict(int)
    for case in failed_cases:
        expected = case['expected']
        if 'straße' in expected.lower() or 'str.' in expected.lower():
            street_patterns['straße/str.'] += 1
        elif 'weg' in expected.lower():
            street_patterns['weg'] += 1
        elif 'platz' in expected.lower():
            street_patterns['platz'] += 1
        elif any(x in expected.lower() for x in ['am ', 'an ', 'auf ', 'in ']):
            street_patterns['preposition (am/an/auf/in)'] += 1
        else:
            street_patterns['other'] += 1

    print("Failed cases by street type:")
    for pattern, count in sorted(street_patterns.items(), key=lambda x: x[1], reverse=True):
        print(f"  {pattern}: {count}")

    print(f"\n{'='*80}\n")

    return {
        "total": total_tests,
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "success_rate": success_rate,
        "failed_cases": failed_cases,
        "error_cases": error_cases
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test German ADDRESS recognition")
    parser.add_argument("--samples", type=int, default=SAMPLE_SIZE, help="Number of samples to test")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
        print(f"Random seed: {args.seed}")

    results = run_tests(args.samples)

    # Exit code based on success rate
    if results["success_rate"] < 80:
        sys.exit(1)  # Fail if below 80%
    else:
        sys.exit(0)
