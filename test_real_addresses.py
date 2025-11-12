#!/usr/bin/env python3
"""
Test that real German addresses are still detected correctly
after applying the precision filter.
"""

import requests
import json

ANALYZER_URL = "http://localhost:3000/analyze"

# Test cases: real German addresses that should be detected
TEST_ADDRESSES = [
    "Der Patient wohnt in der Hauptstraße 42, 10115 Berlin.",
    "Kontaktadresse: Berliner Str. 31, Hamburg",
    "Am Grünen Winkel 164",
    "Bertha-von-Suttner-Str. 198c",
    "Anschrift: Musterweg 7b, 80331 München",
    "Er lebt in Bismarckstraße 12-14",
    "Wohnt in der Carl-Hesselmann Weg 107",
    "Im Kessler 26, 70794 Filderstadt",
    "Zum Bildstöckle 126",
    "Franz-von-Kobell-Str. 19",
]

def test_address(text):
    """Test a single address."""
    payload = {
        "text": text,
        "language": "de",
        "entities": ["ADDRESS"]
    }
    try:
        response = requests.post(ANALYZER_URL, json=payload, timeout=10)
        response.raise_for_status()
        results = response.json()
        return results
    except Exception as e:
        print(f"ERROR: {e}")
        return []

def main():
    print("Testing Real Address Detection")
    print("=" * 80)
    print()

    total = len(TEST_ADDRESSES)
    detected = 0
    missed = []

    for i, text in enumerate(TEST_ADDRESSES, 1):
        print(f"{i}. Testing: {text}")
        results = test_address(text)

        if results:
            detected += 1
            for r in results:
                detected_text = text[r['start']:r['end']]
                print(f"   ✓ Detected: '{detected_text}' (score: {r['score']:.2f})")
        else:
            missed.append(text)
            print(f"   ✗ MISSED - No detection!")
        print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total test cases: {total}")
    print(f"Successfully detected: {detected}")
    print(f"Missed: {len(missed)}")
    print(f"Detection rate: {(detected/total)*100:.1f}%")

    if missed:
        print(f"\nMissed addresses:")
        for addr in missed:
            print(f"  - {addr}")
    else:
        print("\n✓ All real addresses detected correctly!")

if __name__ == "__main__":
    main()
