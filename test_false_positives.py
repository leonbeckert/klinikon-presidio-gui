#!/usr/bin/env python3
"""
Test the German ADDRESS recognizer against sample medical texts
and identify false positives (medical terms incorrectly detected as addresses).
"""

import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Any

# Configuration
ANALYZER_URL = "http://localhost:3000/analyze"
SAMPLE_DIR = Path("analyzer-de/data/sample_medical_texts")
OUTPUT_FILE = "false_positives.json"

def read_medical_texts() -> List[Dict[str, str]]:
    """Read all medical text files from the sample directory."""
    texts = []
    for file_path in SAMPLE_DIR.glob("*.md"):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            texts.append({
                "filename": file_path.name,
                "content": content
            })
    return texts

def analyze_text(text: str, language: str = "de") -> List[Dict[str, Any]]:
    """Send text to Presidio Analyzer and get detected entities."""
    payload = {
        "text": text,
        "language": language,
        "entities": ["ADDRESS"]  # Only check for ADDRESS entities
    }

    try:
        response = requests.post(ANALYZER_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling analyzer: {e}")
        return []

def extract_context(text: str, start: int, end: int, context_chars: int = 100) -> str:
    """Extract context around a detected entity."""
    context_start = max(0, start - context_chars)
    context_end = min(len(text), end + context_chars)

    before = text[context_start:start]
    entity = text[start:end]
    after = text[end:context_end]

    # Clean up newlines for better display
    before = before.replace('\n', ' ').strip()
    after = after.replace('\n', ' ').strip()

    return f"...{before} **{entity}** {after}..."

def test_gazetteer():
    """Main function to test gazetteer and identify false positives."""
    print("Testing German ADDRESS recognizer against medical texts...")
    print(f"Sample directory: {SAMPLE_DIR}")
    print(f"Analyzer URL: {ANALYZER_URL}\n")

    # Read all medical texts
    texts = read_medical_texts()
    print(f"Found {len(texts)} medical text files\n")

    if not texts:
        print(f"ERROR: No .md files found in {SAMPLE_DIR}")
        return

    # Test each text
    all_false_positives = []
    total_detections = 0

    for text_info in texts:
        filename = text_info["filename"]
        content = text_info["content"]

        print(f"Analyzing: {filename}")
        print(f"Text length: {len(content)} characters")

        # Analyze the text
        results = analyze_text(content)

        if not results:
            print(f"  → No ADDRESS entities detected\n")
            continue

        print(f"  → Detected {len(results)} ADDRESS entities:\n")
        total_detections += len(results)

        # Process each detection
        for idx, entity in enumerate(results, 1):
            entity_type = entity.get("entity_type", "")
            start = entity.get("start", 0)
            end = entity.get("end", 0)
            score = entity.get("score", 0.0)
            detected_text = content[start:end]

            # Extract context
            context = extract_context(content, start, end)

            print(f"    {idx}. '{detected_text}' (score: {score:.2f})")
            print(f"       Position: {start}-{end}")
            print(f"       Context: {context[:150]}...\n")

            # Store false positive
            false_positive = {
                "filename": filename,
                "detected_text": detected_text,
                "entity_type": entity_type,
                "score": score,
                "start": start,
                "end": end,
                "context": context
            }
            all_false_positives.append(false_positive)

    # Save results
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total files analyzed: {len(texts)}")
    print(f"Total ADDRESS detections: {total_detections}")
    print(f"Total false positives: {len(all_false_positives)}")

    if all_false_positives:
        # Save to JSON file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_false_positives, f, indent=2, ensure_ascii=False)
        print(f"\nFalse positives saved to: {OUTPUT_FILE}")

        # Also create a human-readable text file
        txt_output = OUTPUT_FILE.replace('.json', '.txt')
        with open(txt_output, 'w', encoding='utf-8') as f:
            f.write("FALSE POSITIVES REPORT\n")
            f.write("="*80 + "\n\n")

            for idx, fp in enumerate(all_false_positives, 1):
                f.write(f"{idx}. '{fp['detected_text']}' (score: {fp['score']:.2f})\n")
                f.write(f"   File: {fp['filename']}\n")
                f.write(f"   Position: {fp['start']}-{fp['end']}\n")
                f.write(f"   Context: {fp['context']}\n\n")

        print(f"Human-readable report saved to: {txt_output}")

        # Print unique false positive terms
        unique_terms = sorted(set(fp['detected_text'] for fp in all_false_positives))
        print(f"\nUnique false positive terms ({len(unique_terms)}):")
        for term in unique_terms:
            count = sum(1 for fp in all_false_positives if fp['detected_text'] == term)
            print(f"  - '{term}' ({count}x)")
    else:
        print("\nNo false positives detected! ✓")

if __name__ == "__main__":
    test_gazetteer()
