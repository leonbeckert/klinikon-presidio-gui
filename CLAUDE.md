# Claude Code Development Notes

## Street Gazetteer Preprocessing

### Overview

The German ADDRESS recognizer uses a gazetteer of 423K street names from OpenPLZ. To speed up startup time, we preprocess and cache the normalized street names as a pickle file.

**Performance improvement:**
- CSV normalization: ~60 seconds on startup
- Pickle loading: ~0.3 seconds on startup
- **200x faster!**

### When to Rebuild the Pickle File

You MUST rebuild the preprocessed pickle file (`streets_normalized.pkl`) if you:

1. **Update the street CSV** (`analyzer-de/data/streets.csv`)
2. **Change the normalization logic** in `normalize_street_name()` function
3. **Add/remove street suffix abbreviations** in the replacement tuples

### How to Rebuild

#### Option 1: Inside Docker Container (Recommended)

```bash
# 1. Ensure containers are running
docker compose up -d

# 2. Run preprocessing script
docker exec presidio-analyzer-de python /app/preprocess_gazetteer_standalone.py

# 3. Copy the generated pickle file to local machine
docker cp presidio-analyzer-de:/app/data/streets_normalized.pkl analyzer-de/data/streets_normalized.pkl

# 4. Restart containers to use the new pickle file
docker compose restart presidio-analyzer-de
```

#### Option 2: On Local Machine

```bash
cd analyzer-de
python preprocess_gazetteer_standalone.py
```

This generates `analyzer-de/data/streets_normalized.pkl` locally.

### Files Involved

- **`analyzer-de/data/streets.csv`** - Source data (423K German street names from OpenPLZ)
- **`analyzer-de/data/streets_normalized.pkl`** - Preprocessed pickle file (7.2 MB, loaded at startup)
- **`analyzer-de/preprocess_gazetteer_standalone.py`** - Script to generate the pickle file
- **`analyzer-de/street_gazetteer.py`** - Main gazetteer module (automatically loads pickle if available, falls back to CSV)

### Verification

After rebuilding, check the analyzer logs on startup:

```bash
docker logs presidio-analyzer-de --tail 10
```

You should see:
```
[street_gazetteer] Loading preprocessed streets from /app/data/streets_normalized.pkl ...
[street_gazetteer] Loaded 422,721 street names (preprocessed).
```

If the pickle file is missing or outdated, you'll see:
```
[street_gazetteer] Preprocessed file not found, loading from CSV ...
[street_gazetteer] (Run 'python preprocess_gazetteer.py' to speed up future loads)
```

### Normalization Logic (Phase 1 Baseline)

The current normalization achieves **94.6% accuracy** by:

1. **Tuple-based replacements** for German street suffix abbreviations:
   - `Str.` → `Straße`
   - `Wg.` → `Weg`
   - `Pl.` → `Platz`
   - `Al.` → `Allee`
   - And 40+ other variants

2. **Targeted regex** for hyphenated streets:
   - `-Str.` → `-Straße` (with dot, to avoid double-expansion bug)

3. **Unicode normalization**:
   - Fancy dashes/apostrophes → ASCII equivalents
   - NFC normalization + casefold

**IMPORTANT:** The two problematic patterns are intentionally **REMOVED** to prevent the "strasseasse" bug:
- ~~`("-Str", "-Straße")`~~ (would match inside "-Straße" → "-Straßeaße")
- ~~`("-str", "-straße")`~~ (would match inside "-straße" → "-straßeaße")

### Git Tracking

The pickle file (`streets_normalized.pkl`) should be:
- **Committed to git** (so other developers don't need to regenerate)
- **Regenerated** only when the source data or normalization logic changes
- **Updated** in pull requests that modify the gazetteer

---

## Docker Container Rebuild Process

### When to Rebuild

You MUST rebuild the Docker container whenever you modify:
- `analyzer-de/street_gazetteer.py` (gazetteer scanner logic)
- `analyzer-de/build_de_address_model.py` (EntityRuler patterns)
- `analyzer-de/sitecustomize.py` (custom Python initialization)
- Configuration files (analyzer-conf.yml, nlp-config-de.yml, recognizers-de.yml)

### Rebuild Commands

```bash
# From the analyzer-de directory:
cd analyzer-de
docker build --no-cache -t presidio-analyzer-de .

# Or use the faster cached build (only if dependencies haven't changed):
docker build -t presidio-analyzer-de .

# Then restart services from project root:
cd ..
docker compose down
docker compose up -d

# Wait for analyzer to be ready (~15 seconds):
sleep 15
```

### Quick Test During Development

For rapid iteration without full rebuilds, you can copy modified files directly to the running container:

```bash
# Copy updated file
docker cp analyzer-de/street_gazetteer.py presidio-analyzer-de:/app/street_gazetteer.py

# Restart analyzer to reload the module
docker restart presidio-analyzer-de && sleep 15

# Test your changes
python3 test_street_recognition.py --samples 500
```

**Warning:** This is only for testing. Always rebuild the container properly before committing changes!

---

## Recent Changes Log

### 2025-11-12: Multi-hyphen Street Name Fix (99.4% Accuracy)
- **Fixed critical bug** with merged multi-hyphen tokens (e.g., "Bertha-von-Suttner-Str.")
- **Phase 5 improvements** to gazetteer scanner:
  - Added sentence context trimming to prevent over-greedy scanning
  - Trim leading "in/bei/von/etc." + optional article ("der/den/dem/die/das")
  - Added "wohnung" to stopwords list
- **Result:** 99.4% accuracy (497/500) on test suite
- **Remaining edge cases:** PLZ confusion, DDR-style street names

### 2025-11-12: Gazetteer Performance Optimization
- Added pickle-based preprocessing for 200x faster startup
- Reverted to Phase 1 tuple-based normalization (94.6% baseline)
- Removed problematic `-Str`/`-str` patterns that caused double-expansion
- Added targeted regex for `-Str.` (with dot) in hyphenated contexts
