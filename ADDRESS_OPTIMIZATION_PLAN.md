# ADDRESS Recognition Optimization Plan
**Incremental, Test-Driven Improvements**

**Date:** 2025-11-12
**Baseline Target:** 78.1% (known working configuration)
**Goal:** 85-90% accuracy through systematic improvements
**Strategy:** One change at a time, measure after each, keep only wins

---

## Current Status

- **V2 Performance:** 72.2% (REGRESSION from baseline)
- **Baseline v1:** 78.1% (STABLE - need to restore)
- **Issues:** Over-engineering, batch changes, no incremental testing

---

## Rollback Strategy

### Why Roll Back?

1. V2 introduced multiple changes simultaneously
2. Cannot isolate which changes helped vs. hurt
3. Currently **5.9 percentage points below baseline**
4. Need stable foundation for incremental improvements

---

## Phase 0: Restore Baseline (78.1%)

**Goal:** Get back to known-good configuration
**Success Criteria:** Achieve 78% ± 0.5% on 1000-sample test

### Step 0.1: Restore Baseline EntityRuler Patterns

**File:** `analyzer-de/build_de_address_model.py`

**Restore to:**

```python
patterns = [
    # 1) Single-token street names: "Hauptstraße 42", "Musterweg 7b", "Bismarckstr. 12-14"
    # Note: spaCy tokenizes "Str." as "Str" + ".", so we match "str" without period
    {
        "label": "ADDRESS",
        "pattern": [
            {
                "IS_TITLE": True,
                "LOWER": {
                    "REGEX": r".*(straße|str|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse)$"
                }
            },
            {"IS_PUNCT": True, "OP": "?"},  # optional period after street name
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
        ],
    },
    # 2) Multi-word addresses: "Am Bahnhof 3", "An der Kirche 12b"
    {
        "label": "ADDRESS",
        "pattern": [
            {"LOWER": {"IN": ["am", "an", "auf", "in"]}},
            {"LOWER": {"IN": ["der", "den", "dem"]}, "OP": "?"},
            {"IS_TITLE": True, "OP": "+"},
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
        ],
    },
    # 3) Full address with optional ZIP + city: "Hauptstraße 42, 10115 Berlin"
    {
        "label": "ADDRESS",
        "pattern": [
            {
                "IS_TITLE": True,
                "LOWER": {
                    "REGEX": r".*(straße|str|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse)$"
                }
            },
            {"IS_PUNCT": True, "OP": "?"},  # optional period after street name
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
            {"IS_PUNCT": True, "OP": "?"},  # comma or other punctuation
            {"TEXT": {"REGEX": r"^[0-9]{5}$"}},  # ZIP
            {"IS_TITLE": True, "OP": "+"},      # City
        ],
    },
]
```

### Step 0.2: Restore Baseline Gazetteer

**File:** `analyzer-de/street_gazetteer.py`

**Restore to:**

```python
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
        # Skip punctuation immediately before the number (e.g., "Bahnhofstr. 42")
        j = i - 1
        while j >= 0 and doc[j].is_punct:
            j -= 1

        if j < 0:
            continue

        # Now look backwards for title-cased tokens (street name)
        start = j
        while start >= 0 and doc[start].is_title and (i - start) <= 7:
            start -= 1
        start += 1

        if start > j:
            continue

        street_tokens = doc[start:j+1]
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
```

### Step 0.3: Restore Baseline Normalization

**File:** `analyzer-de/street_gazetteer.py`

**Restore to:**

```python
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
```

### Step 0.4: Verification

**Actions:**
1. Rebuild Docker image: `docker-compose build presidio-analyzer`
2. Restart service: `docker-compose up -d presidio-analyzer`
3. Wait 60s for startup
4. Run test: `docker exec presidio-analyzer-de python /tmp/test_street_recognition.py 1000`

**Expected Result:** 78% ± 0.5%

**If successful:** ✅ Proceed to Phase 1
**If not:** ⚠️ Debug configuration, compare with git history at commit where 78.1% was achieved

**Checkpoint Document:**
```
Date: [DATE]
Test Run: Baseline restoration
Success Rate: [X.X]%
Status: [PASS/FAIL]
Notes: [Any observations]
```

---

## Phase 1: Tokenization Fix (Low Risk, High Value)

**Goal:** Merge "str" + "." tokens to simplify pattern matching
**Expected Gain:** +2-4 percentage points
**Risk:** Low (affects only one specific token pair)

### Step 1.1: Implement str. Token Merger

**File:** `analyzer-de/build_de_address_model.py`

**Add before EntityRuler:**

```python
from spacy.language import Language

# Add tokenization fix for "str." abbreviation
@Language.component("merge_str_abbrev")
def merge_str_abbrev(doc):
    """
    Merge 'str' + '.' into single token 'str.'
    This helps both EntityRuler patterns and gazetteer component.

    Example: "Bahnhofstr" "." → "Bahnhofstr."
    """
    with doc.retokenize() as retok:
        for i in range(1, len(doc)):
            if doc[i-1].lower_ == "str" and doc[i].text == ".":
                retok.merge(doc[i-1:i+1], attrs={"LEMMA": doc[i-1].lemma_ + "."})
    return doc

# Add to pipeline FIRST (before any other components)
if "merge_str_abbrev" not in nlp.pipe_names:
    print("[build] Adding merge_str_abbrev component...")
    nlp.add_pipe("merge_str_abbrev", first=True)
```

**Expected pipeline order:**
```
['merge_str_abbrev', 'tok2vec', 'tagger', 'morphologizer', 'parser',
 'lemmatizer', 'attribute_ruler', 'entity_ruler', 'ner', 'street_gazetteer']
```

### Step 1.2: Test Tokenization

**Quick verification:**

```bash
docker exec presidio-analyzer-de python -c "
import spacy
nlp = spacy.load('/app/models/de_with_address')

test = 'Kontaktadresse: Lutherstr. 173'
doc = nlp(test)
print('Tokens:', [tok.text for tok in doc])
print('Entities:', [(ent.text, ent.label_) for ent in doc.ents])
"
```

**Expected Output:**
```
Tokens: ['Kontaktadresse', ':', 'Lutherstr.', '173']  # Note: merged token
Entities: [('Lutherstr. 173', 'ADDRESS')]
```

### Step 1.3: Full Test Run

**Actions:**
1. Rebuild: `docker-compose build presidio-analyzer`
2. Restart: `docker-compose up -d presidio-analyzer`
3. Test: `docker exec presidio-analyzer-de python /tmp/test_street_recognition.py 1000`

**Success Criteria:**
- ✅ Success rate **> 78.1%** (any improvement)
- ✅ "straße/str." failures **decrease** from baseline
- ✅ No new failure categories introduced

**If successful:** Keep change, document gain, proceed to Phase 2
**If regression:** Revert change, document why, skip to Phase 2

**Checkpoint Document:**
```
Date: [DATE]
Test Run: Phase 1 - Tokenization Fix
Success Rate: [X.X]%
Baseline: 78.1%
Delta: [+/- X.X pp]
Status: [KEEP/REVERT]
Notes: [Observations, failure category changes]
```

---

## Phase 2: Minimal Adjective/Preposition Pattern (Medium Risk, Medium Value)

**Goal:** Catch "Unter den...", "Zum...", "Alte...", "Neue..." patterns
**Expected Gain:** +2-4 percentage points
**Risk:** Medium (new pattern could create false positives)

### Step 2.1: Add Single Targeted Pattern

**File:** `analyzer-de/build_de_address_model.py`

**Add to patterns list (after existing 3 patterns):**

```python
# 4) Adjective/preposition-led streets: "Unter den Eichen 64", "Zum Krückeberg 16", "Alte Landstraße 134"
{
    "label": "ADDRESS",
    "pattern": [
        {"LOWER": {"IN": ["unter", "zum", "zur", "alte", "alter", "neue", "neuer"]}},
        {"LOWER": {"IN": ["den", "der", "dem"]}, "OP": "?"},
        {"IS_TITLE": True, "OP": "+"},
        {"IS_PUNCT": True, "OP": "?"},
        {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?$"}},
        {"TEXT": {"IN": ["-", "/"]}, "OP": "?"},
        {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?$"}, "OP": "?"},
    ],
},
```

**Pattern Coverage:**
- ✅ "Unter den Eichen 64"
- ✅ "Zum Krückeberg 16"
- ✅ "Alte Landstraße 134"
- ✅ "Neue Straße 42"
- ✅ "Zur Mühle 7"

### Step 2.2: Quick Smoke Test

**Test specific failing cases:**

```bash
docker exec presidio-analyzer-de python -c "
import spacy
nlp = spacy.load('/app/models/de_with_address')

tests = [
    'Wohnhaft Unter den Eichen 64.',
    'Patient aus Zum Krückeberg 16 ist eingetroffen.',
    'Bitte an Alte Landstraße 134 schicken.',
    'Der Termin ist in der Neue Straße 42.',
]

for text in tests:
    doc = nlp(text)
    ents = [(ent.text, ent.label_) for ent in doc.ents if ent.label_ == 'ADDRESS']
    print(f'Text: {text}')
    print(f'  Found: {ents}')
    print()
"
```

### Step 2.3: Full Test Run

**Actions:**
1. Rebuild: `docker-compose build presidio-analyzer`
2. Restart: `docker-compose up -d presidio-analyzer`
3. Test: `docker exec presidio-analyzer-de python /tmp/test_street_recognition.py 1000`

**Success Criteria:**
- ✅ Success rate **improves** from Phase 1 result
- ✅ "preposition (am/an/auf/in)" failures **decrease**
- ✅ "other" category failures **decrease**
- ❌ Overall success rate doesn't drop

**If successful:** Keep change, proceed to Phase 3
**If regression:** Revert, document why, proceed to Phase 3

**Checkpoint Document:**
```
Date: [DATE]
Test Run: Phase 2 - Adjective/Preposition Pattern
Success Rate: [X.X]%
Previous Phase: [X.X]%
Delta: [+/- X.X pp]
Status: [KEEP/REVERT]
Failed Categories:
  - preposition: [count] (baseline: 17)
  - other: [count] (baseline: 81)
Notes: [Any false positives observed?]
```

---

## Phase 3: Suffix Fallback in Gazetteer (Medium Risk, Low-Medium Value)

**Goal:** Match streets when CSV has different suffix variant
**Expected Gain:** +1-3 percentage points
**Risk:** Medium (could introduce false matches)

### Step 3.1: Add Controlled Suffix Trimming

**File:** `analyzer-de/street_gazetteer.py`

**Add helper function:**

```python
# Suffix list for fallback matching
SUFFIXES = (
    "straße", "str", "strasse", "weg", "allee", "platz", "gasse",
    "ring", "ufer", "damm", "hof", "chaussee", "landstraße", "pfad",
    "steig", "stieg"
)

def street_in_dict(norm_name: str, strict: bool = False) -> bool:
    """
    Check if normalized street name is in dictionary.

    Args:
        norm_name: Normalized street name
        strict: If True, only exact match. If False, try suffix fallback.

    Returns:
        True if street name found
    """
    # Try exact match first
    if norm_name in STREET_NAMES:
        return True

    # If strict mode, stop here
    if strict:
        return False

    # Fallback: try with one suffix removed
    for sf in SUFFIXES:
        # "hauptstraße" → "haupt"
        if norm_name.endswith(" " + sf):
            base = norm_name[:-(len(sf) + 1)].strip()
            if base and base in STREET_NAMES:
                return True
        # Handle no-space suffix: "hauptstraße" → "haupt"
        if norm_name.endswith(sf) and not norm_name.endswith(" " + sf):
            base = norm_name[:-len(sf)].strip()
            if base and base in STREET_NAMES:
                return True

    return False
```

**Update gazetteer component:**

```python
# Replace this line:
if norm_street not in STREET_NAMES:
    continue

# With:
if not street_in_dict(norm_street, strict=False):
    continue
```

### Step 3.2: Feature Flag (Optional)

**For easy rollback, add environment variable:**

```python
import os

USE_SUFFIX_FALLBACK = os.getenv("GAZ_SUFFIX_FALLBACK", "true").lower() == "true"

# In component:
if not street_in_dict(norm_street, strict=not USE_SUFFIX_FALLBACK):
    continue
```

**To disable:** `docker-compose.yaml` → `environment: GAZ_SUFFIX_FALLBACK=false`

### Step 3.3: Full Test Run

**Actions:**
1. Rebuild: `docker-compose build presidio-analyzer`
2. Restart: `docker-compose up -d presidio-analyzer`
3. Test: `docker exec presidio-analyzer-de python /tmp/test_street_recognition.py 1000`

**Success Criteria:**
- ✅ Success rate improves from Phase 2
- ✅ No significant false positive increase
- ⚠️ Monitor "other" category for unexpected matches

**If successful:** Keep change, proceed to Phase 4
**If regression OR false positives increase:** Revert or set `GAZ_SUFFIX_FALLBACK=false`

**Checkpoint Document:**
```
Date: [DATE]
Test Run: Phase 3 - Suffix Fallback
Success Rate: [X.X]%
Previous Phase: [X.X]%
Delta: [+/- X.X pp]
Status: [KEEP/REVERT]
Notes: [Any false positives? Which suffixes helped most?]
```

---

## Phase 4: House Number Range Extension (Low Risk, Low Value)

**Goal:** Fully capture ranges like "119-125" instead of just "119"
**Expected Gain:** +0.5-1 percentage points (cosmetic improvement)
**Risk:** Very Low

### Step 4.1: Add Range Detection Helper

**File:** `analyzer-de/street_gazetteer.py`

**Add helper function:**

```python
def extend_number_range(doc, num_token_idx: int) -> int:
    """
    Extend span to include number ranges like '119-125' or '119/121'.

    Args:
        doc: spaCy Doc
        num_token_idx: Index of first number token

    Returns:
        End index (exclusive) for the address span
    """
    end = num_token_idx + 1

    # Check if next token is range separator
    if end < len(doc) and doc[end].text in ("-", "/"):
        # Check if token after separator is a number
        if end + 1 < len(doc) and (doc[end + 1].like_num or doc[end + 1].text.isdigit()):
            end = end + 2  # Include separator + second number

    return end
```

**Update gazetteer component:**

```python
# Replace this line:
span_end = i + 1  # include number

# With:
span_end = extend_number_range(doc, i)
```

### Step 4.2: Test Range Detection

**Quick test:**

```bash
docker exec presidio-analyzer-de python -c "
import spacy
nlp = spacy.load('/app/models/de_with_address')

tests = [
    'Adresse: Moorkamp 119-125',
    'Bitte an Paradiesweg 100-106 schicken.',
    'Patient wohnt Hauptstraße 7/9.',
]

for text in tests:
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == 'ADDRESS':
            print(f'{text} → {ent.text}')
"
```

**Expected:** Full range captured (e.g., "Moorkamp 119-125" not just "Moorkamp 119")

### Step 4.3: Full Test Run

**Actions:**
1. Rebuild: `docker-compose build presidio-analyzer`
2. Restart: `docker-compose up -d presidio-analyzer`
3. Test: `docker exec presidio-analyzer-de python /tmp/test_street_recognition.py 1000`

**Success Criteria:**
- ✅ Success rate stable or slight improvement
- ✅ Range addresses fully captured
- ✅ No new failures introduced

**Note:** This is primarily a **quality improvement** rather than accuracy boost, since partial range detection (e.g., "119" from "119-125") still counts as successful detection for anonymization purposes.

**Checkpoint Document:**
```
Date: [DATE]
Test Run: Phase 4 - Number Range Extension
Success Rate: [X.X]%
Previous Phase: [X.X]%
Delta: [+/- X.X pp]
Status: [KEEP/REVERT]
Notes: [Range coverage improved? Any edge cases?]
```

---

## Phase 5 (Optional): ZIP-Aware Validation

**Goal:** Reduce false positives when ZIP code is present
**Expected Gain:** +0-2 percentage points (precision, not recall)
**Risk:** High (could reject valid addresses if data incomplete)

### Step 5.1: Add PLZ Mapping (Conservative Mode)

**File:** `analyzer-de/street_gazetteer.py`

**Update loader:**

```python
def load_street_names_and_plz(path: Path) -> tuple[set[str], dict[str, set[str]]]:
    """
    Load street names and postal codes from streets.csv.
    Returns: (street_names_set, street_to_plz_dict)
    """
    if not path.is_file():
        raise FileNotFoundError(f"Street CSV not found: {path}")

    names: set[str] = set()
    to_plz: dict[str, set[str]] = {}

    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=",", quotechar='"')
        for row in reader:
            raw = row.get("Name")
            plz = row.get("PostalCode", "")

            if not raw:
                continue

            norm = normalize_street_name(raw)
            if not norm:
                continue

            bad_words = ("friedhof", "öffentliche grünfläche", "öffentlicher parkplatz")
            if any(bad in norm for bad in bad_words):
                continue

            names.add(norm)

            # Store PLZ mapping if valid 5-digit ZIP
            if plz and plz.isdigit() and len(plz) == 5:
                if norm not in to_plz:
                    to_plz[norm] = set()
                to_plz[norm].add(plz)

    return names, to_plz

# Load
STREET_NAMES, STREET_TO_PLZ = load_street_names_and_plz(STREETS_CSV_PATH)
print(f"[street_gazetteer] Loaded {len(STREET_NAMES):,} street names with {len(STREET_TO_PLZ):,} PLZ mappings.")
```

### Step 5.2: Add Conservative ZIP Check

**In gazetteer component (after finding match):**

```python
# After: if norm_street in STREET_NAMES or street_in_dict(norm_street):

# Look ahead for ZIP code
plz = None
k = span_end
while k < len(doc) and doc[k].is_punct:
    k += 1
if k < len(doc) and re.match(r"^\d{5}$", doc[k].text):
    plz = doc[k].text

# Conservative ZIP validation:
# ONLY reject if we have BOTH street PLZ mapping AND detected PLZ AND they don't match
if plz and norm_street in STREET_TO_PLZ:
    valid_plz_set = STREET_TO_PLZ[norm_street]
    if plz not in valid_plz_set:
        # Confirmed mismatch - skip this address
        continue
    # else: ZIP matches, proceed
# else: No ZIP detected or no mapping → allow (benefit of doubt)
```

### Step 5.3: Feature Flag

```python
USE_PLZ_CHECK = os.getenv("GAZ_PLZ_CHECK", "false").lower() == "true"

# In component:
if USE_PLZ_CHECK and plz and norm_street in STREET_TO_PLZ:
    if plz not in STREET_TO_PLZ[norm_street]:
        continue
```

**Default:** OFF (since test data often lacks ZIP codes)

### Step 5.4: Testing Strategy

**Test with flag OFF first:**
- Should match Phase 4 results

**Test with flag ON:**
- May see recall drop if test data has incomplete/wrong ZIPs
- Should see precision improvement (fewer false matches)

**Success Criteria:**
- ✅ With flag ON: Precision improves (need manual FP review)
- ✅ With flag ON: Recall doesn't drop significantly
- ⚠️ If recall drops >2pp, keep flag OFF by default

**Checkpoint Document:**
```
Date: [DATE]
Test Run: Phase 5 - ZIP Validation
Success Rate (flag OFF): [X.X]%
Success Rate (flag ON): [X.X]%
Previous Phase: [X.X]%
Delta: [+/- X.X pp]
Status: [KEEP with flag OFF/ON]
Notes: [Precision vs recall trade-off analysis]
```

---

## Phase 6 (Optional): Additional Preposition Coverage

**Goal:** Catch remaining preposition-led streets ("Vor dem...", "Auf der...")
**Expected Gain:** +0.5-1 percentage points
**Risk:** Low

### Step 6.1: Analyze Remaining Failures

**Before implementing, review current failures:**

```bash
# Run test and save output
docker exec presidio-analyzer-de python /tmp/test_street_recognition.py 1000 > test_results.txt

# Analyze preposition patterns
grep "preposition" test_results.txt
```

**Look for patterns like:**
- "Vor dem Schlosse 94"
- "Auf der Wiese 83"
- "Hinter den Gärten 12"

### Step 6.2: Add Pattern If Justified

**Only add if you see >10 cases of a specific preposition pattern.**

**File:** `analyzer-de/build_de_address_model.py`

**Add to pattern 2 or 4:**

```python
# Extend existing preposition list:
{"LOWER": {"IN": ["am", "an", "auf", "in", "bei", "im", "vor", "hinter"]}},
```

**Or add new pattern if needed for "Auf der..." / "Vor dem..." specifically**

### Step 6.3: Test and Decide

**Only implement if analysis shows significant opportunity (>15 missed cases).**

---

## Success Metrics & Tracking

### Overall Progress Tracker

| Phase | Description | Target % | Actual % | Delta | Status | Date |
|-------|-------------|----------|----------|-------|--------|------|
| 0 | Baseline Restoration | 78.1% | | | ⏸️ | |
| 1 | Tokenization Fix | 80-82% | | | ⏸️ | |
| 2 | Adjective/Prep Pattern | 82-84% | | | ⏸️ | |
| 3 | Suffix Fallback | 83-86% | | | ⏸️ | |
| 4 | Number Range | 83-86% | | | ⏸️ | |
| 5 | ZIP Validation (opt) | +0-2% precision | | | ⏸️ | |
| 6 | Extra Prepositions (opt) | +0.5-1% | | | ⏸️ | |

### Failure Category Tracking

Track these metrics across phases:

```
| Category | Baseline | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|----------|----------|---------|---------|---------|---------|
| straße/str. | 343 | | | | |
| other | 81 | | | | |
| weg | 27 | | | | |
| preposition | 17 | | | | |
| platz | 5 | | | | |
| TOTAL FAILURES | 473 | | | | |
```

---

## Rollback Procedures

### If Phase Fails

1. **Revert code changes** in affected file(s)
2. **Rebuild:** `docker-compose build presidio-analyzer`
3. **Restart:** `docker-compose up -d presidio-analyzer`
4. **Verify:** Re-run test, confirm back to previous phase level
5. **Document:** Update checkpoint with REVERT status and reason

### If Complete Failure

**Nuclear option:** Reset to baseline commit

```bash
# Find baseline commit (78.1% success)
git log --oneline --all --grep="78.1"

# Or manually find commit where baseline was documented
git log --oneline analyzer-de/

# Reset specific files
git checkout <commit-hash> analyzer-de/build_de_address_model.py
git checkout <commit-hash> analyzer-de/street_gazetteer.py

# Rebuild and test
docker-compose build presidio-analyzer
docker-compose up -d presidio-analyzer
```

---

## When to Stop Optimizing

### Plateau Indicators

1. **Three consecutive phases** with <0.5pp improvement
2. **Success rate >86%** with rules alone
3. **Diminishing returns** (<1pp gain per 8+ hours work)

### Next Steps Beyond Rules

If you plateau at 85-88%, consider:

1. **Custom NER Training**
   - Annotate 2,000-5,000 German medical texts
   - Train spaCy NER model on annotated data
   - Expected gain: 88% → 92-95%
   - Effort: 40-80 hours annotation + 8-16 hours training

2. **Hybrid Approach**
   - Rules for common patterns (current system)
   - ML model for edge cases
   - Gazetteer for validation
   - Expected: 92-96% accuracy

3. **Production Acceptance Criteria**
   - 78-82%: Acceptable for initial deployment
   - 83-87%: Good for production use
   - 88-92%: Excellent for medical data
   - >92%: Requires ML/custom training

---

## Testing Commands Reference

### Quick Pattern Test

```bash
docker exec presidio-analyzer-de python -c "
import spacy
nlp = spacy.load('/app/models/de_with_address')
doc = nlp('PUT TEST SENTENCE HERE')
print('Entities:', [(ent.text, ent.label_) for ent in doc.ents])
"
```

### Full Test Run

```bash
docker cp test_street_recognition.py presidio-analyzer-de:/tmp/
docker exec presidio-analyzer-de python /tmp/test_street_recognition.py 1000
```

### Check Pipeline Components

```bash
docker exec presidio-analyzer-de python -c "
import spacy
nlp = spacy.load('/app/models/de_with_address')
print('Pipeline:', nlp.pipe_names)
"
```

### Verify Gazetteer Lookup

```bash
docker exec presidio-analyzer-de python -c "
from street_gazetteer import STREET_NAMES, normalize_street_name
test = 'YOUR STREET NAME'
norm = normalize_street_name(test)
print(f'{test} → {norm} → in_dict={norm in STREET_NAMES}')
"
```

---

## Documentation Requirements

### After Each Phase

Document in `ADDRESS_RECOGNITION_ANALYSIS.md`:

1. **Phase number and description**
2. **Code changes made** (with snippets)
3. **Test results** (success rate, delta)
4. **Decision** (keep/revert)
5. **Lessons learned**

### Final Summary

Once optimization complete, add:

1. **Final accuracy achieved**
2. **Total improvement from baseline**
3. **Which phases were kept**
4. **Remaining failure analysis**
5. **Production deployment recommendation**

---

## Emergency Contacts / Resources

- **OpenPLZ Data:** https://github.com/openpotato/openplzapi.data
- **spaCy Docs:** https://spacy.io/usage/rule-based-matching
- **Presidio Docs:** https://microsoft.github.io/presidio/
- **Test Data:** `/app/data/streets.csv` (423,440 streets)

---

**End of Plan**

**Remember:** One change at a time. Test after each change. Keep only wins. Document everything.
