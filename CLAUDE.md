# Claude Code Development Notes

## 🚨 CRITICAL DOCKER RULES

### Rule #1: ALWAYS Clean Up Before Starting
```bash
docker compose down  # MANDATORY before every "docker compose up"
```
**Why:** Prevents duplicate containers → RAM crashes on Mac

### Rule #2: Code Changes REQUIRE Image Rebuild
```bash
# After editing any .py/.yml/.csv/.pkl file in analyzer-de/:
docker compose down
cd analyzer-de
docker build --no-cache -t presidio-analyzer-de .
cd ..
docker compose up -d && sleep 15
```
**Why:** `docker compose up` uses OLD image - your changes are only on host filesystem

### Rule #3: Use Correct Image Name
**Common issue:** `docker build` creates wrong image name → `docker compose up` can't find it

**Solution:** Use `docker compose build` instead:
```bash
docker compose down
docker compose build --no-cache presidio-analyzer
docker compose up -d && sleep 15
```

**OR** verify image name matches docker-compose.yaml:
```bash
docker images | grep presidio  # Check what exists
docker compose config | grep image  # Check what compose expects
```

### Quick Reference

| Task | Command |
|------|---------|
| Start containers | `docker compose down && docker compose up -d` |
| Rebuild after code changes | `docker compose down && docker compose build --no-cache && docker compose up -d` |
| Check containers running | `docker ps` (should see exactly 3) |
| Check memory usage | `docker stats --no-stream` |
| Emergency cleanup | `docker compose down -v --remove-orphans` |
| View logs | `docker logs presidio-analyzer-de` |
| Verify changes in container | `docker exec presidio-analyzer-de grep "your_change" /app/file.py` |

**Files that require rebuild when changed:**
- Any `.py` file in `analyzer-de/`
- Config files (`.yml`)
- Data files (`.csv`, `.pkl`)
- `Dockerfile`

**For detailed troubleshooting, see DOCKER_TROUBLESHOOTING.md**

---

## 🏠 Local vs Production Deployment

**Two docker-compose files:**

### `docker-compose.local.yaml` - Local Development (Mac 16GB)
```bash
# Use for local development with limited resources
docker compose -f docker-compose.local.yaml down
docker compose -f docker-compose.local.yaml up -d
```

**Resource limits:**
- `presidio-analyzer-de`: 8GB RAM / 4 CPU
- `presidio-anonymizer`: 512MB RAM / 0.5 CPU
- `klinikon-presidio-ui`: 512MB RAM / 0.5 CPU
- **Total**: ~9GB RAM

**Use when:**
- Developing on Mac/laptop with limited resources
- Testing changes locally before deployment
- Single/small batch anonymization

### `docker-compose.yaml` - Production Deployment (Dedicated Server)
```bash
# Default file - used on production server
docker compose down
docker compose up -d
```

**Resource limits:**
- `presidio-analyzer-de`: 16GB RAM / 8 CPU
- `presidio-anonymizer`: 512MB RAM / 0.5 CPU
- `klinikon-presidio-ui`: 512MB RAM / 0.5 CPU
- **Total**: ~17GB RAM

**Server specs:** i5-13500 (14 cores), 64GB RAM, 2x512GB NVMe RAID1

**Use when:**
- Deploying to production server
- High-concurrency batch processing (100+ concurrent requests)
- Processing large batches (93+ texts simultaneously)

**Why separate configs?**
- Production config (16GB/8CPU) would exhaust local Mac resources
- Local config (2GB/1.5CPU) would cause PoolTimeout errors under production load
- Traefik/coolify labels only needed in production

---

## Street Gazetteer Preprocessing

### Quick Facts (Updated 2025-11-14)
- **502K streets** from DE+AT (expanded from 422K)
- Preprocessed pickle file: 8.5 MB, loads in 0.3s
- **200x faster than CSV loading**
- **95.2% recognition accuracy** (DE+AT combined)

### Current Gazetteer Composition
- **Germany:** ~430K streets (from OpenPLZ + DACH dataset)
- **Austria:** ~72K streets (from DACH dataset)
- **Switzerland:** Excluded (French/Italian, not supported)
- **Filtered out:** 39,555 POIs/non-streets (hospitals, parks, trails, etc.)

### When to Rebuild streets_normalized.pkl

Rebuild if you modify:
1. Source data: `raw_data/str_DACH_normalized_cleaned.csv`
2. `normalize_street_name()` function in `street_gazetteer.py`
3. Inclusion/exclusion filters in `preprocess_expanded.py`
4. Street suffix abbreviation tuples

### How to Rebuild (Updated Process)

```bash
# 1. Run preprocessing script (on host, not in Docker)
python3 preprocess_expanded.py
# Output: analyzer-de/data/streets_normalized_expanded.pkl

# 2. Replace production gazetteer
cp analyzer-de/data/streets_normalized_expanded.pkl \
   analyzer-de/data/streets_normalized.pkl

# 3. Rebuild Docker container
docker compose down
docker compose build --no-cache presidio-analyzer
docker compose up -d && sleep 15

# 4. Verify gazetteer loaded
docker logs presidio-analyzer-de 2>&1 | grep "Loaded.*street"
# Should show: "Loaded 502,236 street names (preprocessed)."

# 5. Run tests
python3 dev_tools/tests/test_dach_recognition_simple.py --samples 1000
python3 dev_tools/tests/test_false_positives.py
docker compose down && docker compose up -d

# Or locally
cd analyzer-de && python preprocess_gazetteer_standalone.py
```

### Verify

```bash
docker logs presidio-analyzer-de --tail 10
```

Should see:
```
[street_gazetteer] Loaded 422,721 street names (preprocessed).
```

### Important Notes

- **Commit** `streets_normalized.pkl` to git (so others don't need to regenerate)
- Current normalization: **94.6% accuracy** (Phase 1 baseline)
- Removed `-Str`/`-str` patterns (caused "strasseasse" bug)

---

## Repository Organization

```
PresidioGUI/
├── analyzer-de/              # Docker analyzer service (TRACKED)
│   ├── data/
│   │   ├── streets.csv       # ⚠️ CRITICAL - Docker needs this
│   │   └── streets_normalized.pkl  # ⚠️ CRITICAL - Docker needs this
│   ├── street_gazetteer.py
│   └── Dockerfile
├── klinikon-presidio-ui/     # Docker UI service (TRACKED)
├── AI_NOTES/                 # Analysis docs (GITIGNORED)
├── dev_tools/                # Dev/debug scripts (GITIGNORED)
│   ├── debug/
│   ├── scripts/
│   └── tests/
├── test_data/                # Test results (GITIGNORED)
├── raw_data/                 # Large source files (GITIGNORED)
├── CLAUDE.md                 # This file
└── DOCKER_TROUBLESHOOTING.md # Detailed Docker help
```

**Never move/delete** `analyzer-de/data/streets.csv` or `streets_normalized.pkl` - Docker container depends on them!

---

## Development Workflow

### Making Code Changes

1. Edit files in `analyzer-de/` on host
2. Rebuild image: `docker compose build --no-cache presidio-analyzer`
3. Restart: `docker compose down && docker compose up -d`
4. Verify: `docker exec presidio-analyzer-de grep "your_change" /app/your_file.py`
5. Test: Run scripts from `dev_tools/tests/`

### Quick Test (No Rebuild)

For rapid iteration ONLY (not for commits):
```bash
docker cp analyzer-de/street_gazetteer.py presidio-analyzer-de:/app/street_gazetteer.py
docker restart presidio-analyzer-de && sleep 15
```

**⚠️ Changes lost on container restart! Always rebuild before committing.**

### Running Tests

```bash
# Tests auto-detect project root, run from anywhere:
python dev_tools/tests/test_street_recognition.py --samples 500
python dev_tools/tests/test_false_positives.py

# Test concatenated address recognition (NEW - 2025-11-17)
python dev_tools/tests/test_concatenated_addresses.py
```

---

## Recent Achievements

**99.4% ADDRESS Recognition Accuracy** (497/500 test cases)

### 2025-11-17: Concatenated Address Recognition 🎯
- **NEW**: Handles addresses without spacing (e.g., "Graseggerstraße105")
- Added `split_concatenated_addresses` pipeline component (runs FIRST in pipeline)
- Splits concatenated tokens: "Hauptstraße42b" → "Hauptstraße" + "42b"
- **100% test success rate** (34/34 test cases passing)
- Preserves medical code integrity (F32.1, B12, HbA1c not affected)
- Supports all German street suffixes (60+ variants)
- Test file: `dev_tools/tests/test_concatenated_addresses.py`
- **Pipeline order**: `split_concatenated_addresses` → `merge_str_abbrev` → ... → `street_gazetteer`

### 2025-11-12: Multi-hyphen Street Name Fix
- Fixed merged multi-hyphen tokens (e.g., "Bertha-von-Suttner-Str.")
- Added sentence context trimming
- Improved stopword filtering

### 2025-11-12: Performance Optimization
- Pickle preprocessing: 200x faster startup
- Optimized normalization (94.6% baseline)
