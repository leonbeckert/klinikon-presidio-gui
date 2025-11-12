#!/usr/bin/env python3
"""
Analyze failed ADDRESS recognition cases and categorize by failure type.
"""
import json
import re
from collections import defaultdict
from pathlib import Path


def classify_failure(expected: str, detected, sentence: str) -> list[str]:
    """
    Classify a failure into one or more categories.
    Returns a list of categories since some failures have multiple issues.
    detected can be a list of dicts or a string
    """
    categories = []

    # Normalize detected - handle both list and string formats
    if isinstance(detected, list):
        if not detected:
            detected = ""
        else:
            # Take the first detected entity's text
            detected = detected[0].get('text', '') if detected else ""
    detected = str(detected).strip() if detected else ""

    # Category 1: Complete miss (nothing detected)
    if not detected or detected == "(nothing)":
        categories.append("complete_miss")

        # Sub-classify complete misses
        if "-" in expected and any(char.isdigit() for char in expected):
            # Has hyphenated street name
            if expected.count("-") >= 2:
                categories.append("miss_multi_hyphen_street")
            else:
                categories.append("miss_hyphen_street")

        if re.search(r'\d+[a-zA-Z]', expected):
            categories.append("miss_letter_suffix")

        return categories

    # Category 2: Number range incomplete (e.g., "44-46" detected as "44")
    expected_range = re.search(r'(\d+)[–\-/](\d+)', expected)
    detected_range = re.search(r'(\d+)[–\-/](\d+)', detected)

    if expected_range and not detected_range:
        # Expected has range but detected doesn't
        categories.append("incomplete_range")

    # Category 3: Letter suffix missing (e.g., "44a" detected as "44")
    expected_letter = re.search(r'(\d+)([a-zA-Z])', expected)
    detected_letter = re.search(r'(\d+)([a-zA-Z])', detected)

    if expected_letter and not detected_letter:
        categories.append("missing_letter_suffix")

    # Category 4: Preposition included incorrectly
    if detected.lower().startswith(("in der", "in ", "an der", "an ", "am ")):
        if not expected.lower().startswith(("in der", "in ", "an der", "an ", "am ")):
            categories.append("extra_preposition")

    # Category 5: Street name truncated
    expected_street = re.sub(r'\s*\d+.*$', '', expected).strip()
    detected_street = re.sub(r'\s*\d+.*$', '', detected).strip()

    if expected_street and detected_street:
        if len(detected_street) < len(expected_street) * 0.8:
            categories.append("truncated_street_name")

    # Category 6: Hyphenated street name issues
    if "-" in expected_street and expected_street.count("-") >= 2:
        categories.append("multi_hyphen_street")

    # Category 7: Abbreviation issues (Str. vs Straße)
    if "str." in expected.lower() or "straße" in expected.lower():
        if "str." not in detected.lower() and "straße" not in detected.lower():
            categories.append("abbrev_detection_fail")

    # If no specific category identified but there's a mismatch
    if not categories:
        categories.append("other_mismatch")

    return categories


def analyze_failures(json_path: Path) -> dict:
    """Analyze failures and group by category."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    failed_cases = data.get('failed_cases', [])

    # Category collections
    categories = defaultdict(list)
    category_counts = defaultdict(int)

    # Analyze each failure
    for case in failed_cases:
        expected = case['expected']
        detected_raw = case.get('detected', [])
        sentence = case['sentence']

        # Format detected for display
        if isinstance(detected_raw, list):
            if not detected_raw:
                detected_display = "(nothing)"
            else:
                detected_display = detected_raw[0].get('text', '(nothing)')
        else:
            detected_display = str(detected_raw) if detected_raw else "(nothing)"

        failure_types = classify_failure(expected, detected_raw, sentence)

        for ftype in failure_types:
            categories[ftype].append({
                'expected': expected,
                'detected': detected_display,
                'sentence': sentence
            })
            category_counts[ftype] += 1

    return {
        'total_failures': len(failed_cases),
        'categories': dict(categories),
        'category_counts': dict(sorted(category_counts.items(), key=lambda x: -x[1]))
    }


def generate_markdown_report(analysis: dict, output_path: Path):
    """Generate a detailed markdown report."""

    total = analysis['total_failures']
    categories = analysis['categories']
    counts = analysis['category_counts']

    md = f"""# Failure Analysis Report - German ADDRESS Recognition

**Generated:** {Path('failed_cases_5000.json').stat().st_mtime if Path('failed_cases_5000.json').exists() else 'N/A'}
**Total Failures Analyzed:** {total:,}
**Success Rate Context:** 91.3% (4,567/5,000 successful)

---

## Executive Summary

This document provides a comprehensive analysis of the {total:,} failed ADDRESS recognition cases from a 5,000-sample validation test. Failures have been systematically categorized to identify patterns and prioritize improvements.

### Failure Category Overview

| Category | Count | % of Failures | Description |
|----------|-------|---------------|-------------|
"""

    # Add category summary table
    for cat, count in counts.items():
        pct = (count / total) * 100
        desc = get_category_description(cat)
        md += f"| {cat} | {count} | {pct:.1f}% | {desc} |\n"

    md += "\n---\n\n"

    # Detailed sections for each category
    for cat, count in counts.items():
        if count == 0:
            continue

        cases = categories[cat]
        pct = (count / total) * 100

        md += f"## Category: {cat.replace('_', ' ').title()}\n\n"
        md += f"**Count:** {count} failures ({pct:.1f}% of all failures)\n\n"
        md += f"**Description:** {get_category_description(cat)}\n\n"

        # Show first 15 examples
        md += f"### Representative Examples (showing up to 15 of {count})\n\n"

        for i, case in enumerate(cases[:15], 1):
            md += f"**Example {i}:**\n"
            md += f"- Expected: `{case['expected']}`\n"
            md += f"- Detected: `{case['detected']}`\n"
            md += f"- Sentence: *{case['sentence']}*\n\n"

        if count > 15:
            md += f"*...and {count - 15} more cases in this category*\n\n"

        md += "---\n\n"

    # Add recommendations section
    md += generate_recommendations(counts, total)

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f"✓ Markdown report generated: {output_path}")


def get_category_description(category: str) -> str:
    """Get human-readable description for each category."""
    descriptions = {
        'complete_miss': 'Address completely undetected',
        'incomplete_range': 'Number range partially detected (e.g., "44-46" → "44")',
        'missing_letter_suffix': 'House number letter suffix missing (e.g., "44a" → "44")',
        'extra_preposition': 'Preposition incorrectly included in detection',
        'truncated_street_name': 'Street name partially captured',
        'multi_hyphen_street': 'Street with multiple hyphens (e.g., "Bertha-von-Suttner-Str.")',
        'miss_multi_hyphen_street': 'Multi-hyphen street completely missed',
        'miss_hyphen_street': 'Hyphenated street completely missed',
        'miss_letter_suffix': 'Address with letter suffix completely missed',
        'abbrev_detection_fail': 'Abbreviation handling issue (Str./Straße)',
        'other_mismatch': 'Miscellaneous detection mismatch'
    }
    return descriptions.get(category, 'Unknown category')


def generate_recommendations(counts: dict, total: int) -> str:
    """Generate recommendations based on failure patterns."""

    md = "## Recommendations for Improvement\n\n"
    md += "Based on the failure analysis, here are prioritized recommendations:\n\n"

    recommendations = []

    # Check for range issues
    if 'incomplete_range' in counts:
        count = counts['incomplete_range']
        pct = (count / total) * 100
        impact = "HIGH" if pct > 20 else "MEDIUM" if pct > 10 else "LOW"
        recommendations.append({
            'priority': 1,
            'impact': impact,
            'issue': 'Number Range Extension',
            'description': f'Fix `_extend_number_range()` function to properly capture full ranges (e.g., "44-46", "12-14")',
            'affected': f'{count} cases ({pct:.1f}%)',
            'effort': 'MEDIUM - Requires debugging tokenization and boundary detection'
        })

    # Check for letter suffix issues
    letter_issues = counts.get('missing_letter_suffix', 0) + counts.get('miss_letter_suffix', 0)
    if letter_issues > 0:
        pct = (letter_issues / total) * 100
        impact = "HIGH" if pct > 15 else "MEDIUM" if pct > 8 else "LOW"
        recommendations.append({
            'priority': 2,
            'impact': impact,
            'issue': 'Letter Suffix Capture',
            'description': 'Improve detection of single letter suffixes after house numbers (e.g., "44a", "107g")',
            'affected': f'{letter_issues} cases ({pct:.1f}%)',
            'effort': 'MEDIUM - Requires refining boundary detection in `_extend_number_range()`'
        })

    # Check for multi-hyphen issues
    hyphen_issues = counts.get('multi_hyphen_street', 0) + counts.get('miss_multi_hyphen_street', 0)
    if hyphen_issues > 0:
        pct = (hyphen_issues / total) * 100
        impact = "HIGH" if pct > 15 else "MEDIUM" if pct > 8 else "LOW"
        recommendations.append({
            'priority': 3,
            'impact': impact,
            'issue': 'Multi-Hyphen Street Names',
            'description': 'Enhance pattern matching for complex hyphenated streets (e.g., "Bertha-von-Suttner-Str.", "Von-der-Leyen-Straße")',
            'affected': f'{hyphen_issues} cases ({pct:.1f}%)',
            'effort': 'HIGH - May require new EntityRuler patterns or gazetteer normalization improvements'
        })

    # Check for complete miss issues
    if 'complete_miss' in counts:
        count = counts['complete_miss']
        pct = (count / total) * 100
        impact = "HIGH" if pct > 25 else "MEDIUM"
        recommendations.append({
            'priority': 4,
            'impact': impact,
            'issue': 'Complete Detection Failures',
            'description': 'Investigate addresses that are entirely undetected - may indicate pattern gaps or gazetteer mismatches',
            'affected': f'{count} cases ({pct:.1f}%)',
            'effort': 'VARIES - Requires case-by-case analysis'
        })

    # Sort by priority
    recommendations.sort(key=lambda x: x['priority'])

    # Generate markdown table
    md += "| Priority | Impact | Issue | Description | Cases Affected | Estimated Effort |\n"
    md += "|----------|--------|-------|-------------|----------------|------------------|\n"

    for rec in recommendations:
        md += f"| {rec['priority']} | **{rec['impact']}** | {rec['issue']} | {rec['description']} | {rec['affected']} | {rec['effort']} |\n"

    md += "\n### Estimated Impact of Fixes\n\n"

    # Calculate potential improvement
    fixable = counts.get('incomplete_range', 0) + counts.get('missing_letter_suffix', 0) + counts.get('miss_letter_suffix', 0)
    fixable_pct = (fixable / 5000) * 100  # percentage points improvement on full test set

    md += f"""Based on the categorization:
- **Quick wins** (Range + Letter suffix fixes): {fixable} cases = **+{fixable_pct:.1f}pp** potential improvement
- **Current accuracy:** 91.3%
- **Target with quick wins:** ~{91.3 + fixable_pct:.1f}%
- **Theoretical maximum** (all categories fixed): ~{91.3 + (total/5000)*100:.1f}%

**Note:** Some failures may have multiple root causes, so actual improvement may vary.
"""

    return md


if __name__ == '__main__':
    import sys

    json_path = Path('failed_cases_5000.json')
    output_path = Path('FAILURE_ANALYSIS.md')

    if not json_path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    print(f"Analyzing failures from {json_path}...")
    analysis = analyze_failures(json_path)

    print(f"\nFound {analysis['total_failures']} failures in {len(analysis['categories'])} categories")
    print("\nCategory breakdown:")
    for cat, count in analysis['category_counts'].items():
        pct = (count / analysis['total_failures']) * 100
        print(f"  {cat:30s}: {count:4d} ({pct:5.1f}%)")

    print(f"\nGenerating markdown report...")
    generate_markdown_report(analysis, output_path)

    print(f"\n✓ Analysis complete!")
    print(f"  Report saved to: {output_path}")
