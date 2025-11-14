# German ADDRESS Recognizer - Production Deployment Guide

**Version:** 1.0.0  
**Status:** ✅ Production Ready  
**Last Updated:** 2025-11-14

---

## Overview

This guide covers deploying the German ADDRESS recognizer to production with proper monitoring, health checks, and operational best practices.

## Performance Characteristics

### What You're Shipping

| Metric | Production Value | Notes |
|--------|------------------|-------|
| **Recall** | 88.0% | Gazetteer-limited (not algorithm-limited) |
| **Precision** | 100% | Zero false positives on medical text |
| **Startup Time** | ~0.3 seconds | Pickle-based preloading |
| **Throughput** | 26-44 requests/sec | Single container |
| **Memory** | ~1.5GB | Stable (2GB limit recommended) |
| **Gazetteer Size** | 422,721 streets | OpenPLZ maximum coverage |

### What This Means

**Recall (88%):**
- Not limited by algorithm quality
- Limited by gazetteer coverage (OpenPLZ dataset)
- Missing 12% are streets not in the 422K database
- To improve: Need OSM data integration (separate project)

**Precision (100%):**
- Zero false positives on real medical corpora
- Multi-layer filtering (gazetteer gates + FP patterns)
- Safe for automated downstream processing

**Customer Message:**
> "Our German address recognizer is based on a 422k-street gazetteer, tuned for medical texts. We achieve ~88% recall on real German addresses and 0 false positives on medical corpora. When in doubt, we prefer *not* to mark something as an address rather than risk mislabeling medical content."

---

## 1. Container Deployment

### Build

```bash
cd analyzer-de
docker build -t presidio-analyzer-de:1.0.0 .
docker tag presidio-analyzer-de:1.0.0 presidio-analyzer-de:latest
```

### Run (Production)

```bash
docker run -d \
  --name presidio-analyzer-de \
  --memory=2g \
  --memory-swap=2g \
  --restart=unless-stopped \
  -p 3000:3000 \
  -e RUN_ADDRESS_SELFTEST=true \
  -e LOG_LEVEL=INFO \
  presidio-analyzer-de:1.0.0
```

**Environment Variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `RUN_ADDRESS_SELFTEST` | `true` | Enable startup self-test (fail-fast) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `RECOGNIZER_REGISTRY_CONF_FILE` | `/app/conf/recognizers-de.yml` | Custom recognizers (set in Dockerfile) |
| `NLP_CONF_FILE` | `/app/conf/nlp-config-de.yml` | NLP engine config (set in Dockerfile) |
| `ANALYZER_CONF_FILE` | `/app/conf/analyzer-conf.yml` | Analyzer settings (set in Dockerfile) |

### Docker Compose (Recommended)

```yaml
version: '3.8'

services:
  presidio-analyzer-de:
    image: presidio-analyzer-de:1.0.0
    container_name: presidio-analyzer-de
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - RUN_ADDRESS_SELFTEST=true
      - LOG_LEVEL=INFO
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 2. Health Checks

### Basic Health Check (Presidio Built-in)

```bash
curl http://localhost:3000/health
# Expected: "Presidio Analyzer service is up"
```

**Use for:** Kubernetes/Docker liveness probes

### Semantic Health Check (ADDRESS Pipeline)

The container runs a self-test on startup that validates:
- ✅ Gazetteer loaded (422,721 streets)
- ✅ Custom spaCy model loads
- ✅ ADDRESS entities detected for known test cases
- ✅ Non-addresses correctly rejected

**Logs on Success:**
```
[selftest] Running ADDRESS pipeline self-test...
[selftest] ✓ All 8 test cases passed
[selftest] ADDRESS pipeline is working correctly
```

**Logs on Failure (Container Exits):**
```
[selftest] FATAL: ADDRESS pipeline self-test failed: [error details]
[selftest] FAILED: 'Am Eiskeller 103' - Prep street 'Am'
```

**Kubernetes Integration:**

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 15
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 10
  periodSeconds: 10
```

### Manual Semantic Test

```bash
# Test ADDRESS detection
curl -X POST http://localhost:3000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hauptstraße 42, 10115 Berlin","language":"de","entities":["ADDRESS"]}' \
  | jq '.[] | select(.entity_type=="ADDRESS")'

# Expected: One ADDRESS entity for "Hauptstraße 42"
```

---

## 3. Monitoring & Telemetry

### Log Metrics (Already Implemented)

The gazetteer component logs diagnostic counters to stderr:

```
[gaz] STREET_NAMES=422,721
[gaz] candidates=15 hits=12 spans_written=12
```

**Metrics Exposed:**

| Metric | Description | Use Case |
|--------|-------------|----------|
| `STREET_NAMES` | Gazetteer size | Verify correct data loaded |
| `candidates` | Number-like tokens scanned | Volume indicator |
| `hits` | Gazetteer matches found | Recall proxy |
| `spans_written` | Final ADDRESS entities | Output volume |

### Recommended Aggregation (Grafana/Loki)

**Sample LogQL Queries:**

```logql
# Average hits per document
avg_over_time({container="presidio-analyzer-de"} |~ "\\[gaz\\] .* hits=" | regexp "hits=(?P<hits>\\d+)" | unwrap hits [5m])

# Total ADDRESS entities detected (rate)
rate({container="presidio-analyzer-de"} |~ "spans_written=" | regexp "spans_written=(?P<spans>\\d+)" | unwrap spans [1m])

# Self-test failures (should be 0)
count_over_time({container="presidio-analyzer-de"} |~ "FATAL.*self-test failed" [1h])
```

### Alerting Rules

**Critical Alerts:**

```yaml
# Container restart loop (self-test failing)
- alert: AddressRecognizerSelfTestFailing
  expr: rate(container_restart_total{name="presidio-analyzer-de"}[5m]) > 0
  for: 5m
  annotations:
    summary: "ADDRESS recognizer self-test failing (container restart loop)"

# Memory pressure
- alert: AddressRecognizerHighMemory
  expr: container_memory_usage_bytes{name="presidio-analyzer-de"} > 1.8e9
  for: 10m
  annotations:
    summary: "ADDRESS recognizer using >1.8GB memory (2GB limit)"
```

**Warning Alerts:**

```yaml
# Gazetteer not loading
- alert: AddressRecognizerNoGazetteerLog
  expr: absent_over_time({container="presidio-analyzer-de"} |~ "Loaded.*street names" [15m])
  annotations:
    summary: "No gazetteer load log in 15 minutes (container might not be starting properly)"

# Abnormally low hit rate
- alert: AddressRecognizerLowHitRate
  expr: avg_over_time({container="presidio-analyzer-de"} |~ "\\[gaz\\].*hits=" | regexp "candidates=(?P<c>\\d+).*hits=(?P<h>\\d+)" | unwrap h / c [1h]) < 0.1
  for: 1h
  annotations:
    summary: "ADDRESS gazetteer hit rate <10% (potential data issue)"
```

---

## 4. Version Pinning & Artifacts

### Dependencies (Locked)

**In Dockerfile:**
```dockerfile
RUN pip install --no-cache-dir "spacy==3.7.2"
RUN pip install --no-cache-dir \
  https://github.com/explosion/spacy-models/releases/download/de_core_news_md-3.7.0/de_core_news_md-3.7.0-py3-none-any.whl
```

**Why Pinned:**
- spaCy 3.8.x has warnings with de_core_news_md-3.7.0
- Newer models (3.8.x) may have different tokenization → impacts gazetteer lookup
- Stick with 3.7.x until tested with 3.8 models

### Critical Artifacts (Git-Tracked)

| File | Version Control | Purpose |
|------|----------------|---------|
| `streets_normalized.pkl` | ✅ Committed (7.2MB) | 422K preprocessed street names |
| `street_gazetteer.py` | ✅ Committed | Core ADDRESS recognizer logic |
| `build_de_address_model.py` | ✅ Committed | Model build reproducibility |
| `conf/*.yml` | ✅ Committed | Presidio configuration |

**Regenerating Gazetteer (When Updating Data):**

```bash
# Inside container or locally with same environment
python /app/preprocess_gazetteer.py

# Verify
ls -lh /app/data/streets_normalized.pkl  # Should be ~7.2MB
python -c "import pickle; print(len(pickle.load(open('/app/data/streets_normalized.pkl','rb'))))"  # Should be 422,721
```

⚠️ **Treat PKL regeneration as a reviewed change** - test thoroughly before deploying.

---

## 5. Rollout Strategy

### Phase 1: Shadow Mode (1-2 weeks)

**Goal:** Verify 0 FPs in production without affecting operations

```yaml
# Run analyzer alongside existing system
# Log detections but don't act on them
```

**Monitoring:**
- Check logs for `[gaz] candidates=X hits=Y`
- Sample 100-200 documents manually
- Verify no medical terms flagged as ADDRESS
- Confirm hit rate aligns with expectations (~88%)

### Phase 2: Partial Rollout (1 week)

**Goal:** Enable for subset of documents (e.g., administrative forms, discharge letters)

**Document Types:**
- ✅ Entlassungsbriefe (discharge letters)
- ✅ Überweisungen (referrals)  
- ✅ Administrative forms
- ❌ Lab results (minimal addresses expected)
- ❌ Radiology reports (minimal addresses expected)

**Monitoring:**
- False positive rate (expect: 0%)
- Downstream automation success rate
- User feedback from redaction review UI

### Phase 3: Full Rollout

**Goal:** Enable for all document types

**Success Criteria:**
- ✅ Zero FP incidents in Phase 1-2
- ✅ Stable memory/CPU usage
- ✅ No self-test failures
- ✅ Positive user feedback

---

## 6. Operational Runbooks

### Incident: Self-Test Failing (Container Restart Loop)

**Symptoms:**
- Container repeatedly restarting
- Logs show `[selftest] FATAL: ADDRESS pipeline self-test failed`

**Diagnosis:**

```bash
# Check which test case is failing
docker logs presidio-analyzer-de 2>&1 | grep -A 5 "FAILED:"

# Common causes:
# 1. Gazetteer file missing/corrupted
# 2. spaCy model not loaded
# 3. Component registration conflict
```

**Resolution:**

```bash
# Verify gazetteer file
docker exec presidio-analyzer-de ls -lh /app/data/streets_normalized.pkl

# Verify model
docker exec presidio-analyzer-de python -c "import spacy; nlp=spacy.load('/app/models/de_with_address'); print(nlp.pipe_names)"

# If corrupted, rebuild image
docker build --no-cache -t presidio-analyzer-de:1.0.0 .
```

### Incident: High Memory Usage

**Symptoms:**
- Memory usage >1.8GB
- Container OOM killed

**Diagnosis:**

```bash
# Check current usage
docker stats presidio-analyzer-de --no-stream

# Check for memory leaks (run over time)
docker stats presidio-analyzer-de --format "{{.MemUsage}}" 
```

**Resolution:**

```bash
# Restart container (should return to ~1.5GB)
docker restart presidio-analyzer-de

# If persists: investigate request volume
# Gazetteer is loaded once; should not grow with requests
```

### Incident: Low Hit Rate (<10%)

**Symptoms:**
- Logs show `hits=0` or very low numbers consistently
- User reports "addresses not being detected"

**Diagnosis:**

```bash
# Check if gazetteer loaded
docker logs presidio-analyzer-de 2>&1 | grep "Loaded.*street names"

# Expected: "Loaded 422,721 street names"
# If 0 or very low → gazetteer not loaded
```

**Resolution:**

```bash
# Check pickle file integrity
docker exec presidio-analyzer-de python -c "
import pickle
with open('/app/data/streets_normalized.pkl', 'rb') as f:
    streets = pickle.load(f)
    print(f'Streets loaded: {len(streets):,}')
    print('Sample:', list(streets)[:5])
"

# If corrupted: redeploy with fresh image
```

---

## 7. Future Enhancements (Backlog)

### Achieve >90% Recall (Optional)

**Option A: OSM Data Integration**
- **Effort:** 2-3 days
- **Impact:** 90-95% recall (estimated)
- **Risk:** Medium (data quality, normalization complexity)
- **Change:** Expand `streets_normalized.pkl` to ~800K-1M streets
- **No algorithm changes needed**

**Option B: Fuzzy Matching**
- **Effort:** 1-2 days
- **Impact:** +1-2% recall
- **Risk:** Medium (false positive risk, threshold tuning)
- **Change:** Levenshtein distance ≤2 for gazetteer misses
- **Requires:** Suffix+number guard to prevent medical FPs

**Option C: Place-Type Suffix Expansion**
- **Effort:** 30 minutes
- **Impact:** +0.5-1% recall
- **Risk:** Low
- **Change:** Add "Hof", "Feld", "Park", "Anger" to suffix patterns

### NOT Recommended

❌ **Relaxing FP filters** - Destroys precision  
❌ **Removing suffix requirement** - Opens FP floodgates  
❌ **Aggressive fuzzy matching without guards** - Medical terms risk

---

## 8. Changelog

### v1.0.0 (2025-11-14) - Initial Production Release

**New Features:**
- ✅ German ADDRESS recognition with 422K street gazetteer
- ✅ Multi-layer false positive prevention (medical-context aware)
- ✅ Preposition handling (am/im/zum/zur/aufm/vorm/hinterm/unterm)
- ✅ "Alter" prefix trimming
- ✅ ED pattern filter (medical: "ED 2013", "ED 11/2014")
- ✅ Startup self-test with fail-fast
- ✅ Pickle-based fast loading (0.3s startup)

**Performance:**
- Recall: 88.0% (4,399/5,000 test addresses)
- Precision: 100% (0 FPs on medical text)
- Throughput: 26-44 requests/sec
- Memory: ~1.5GB stable

**Architecture:**
- 8-component spaCy pipeline
- Gazetteer-gated detection (hard requirement)
- 3-layer FP filtering (scanner, precision filter, suffix check)
- Dual lookup: with/without prepositions

**Documentation:**
- FINAL_STATUS_REPORT.md (production documentation)
- analysis.md (failure categorization)
- PREPOSITION_FIX_ANALYSIS.md (implementation findings)
- PRODUCTION_DEPLOYMENT_GUIDE.md (this document)

---

## 9. Support & Troubleshooting

### Quick Diagnostics

```bash
# Verify container is running
docker ps | grep presidio-analyzer-de

# Check startup logs
docker logs presidio-analyzer-de --tail 50

# Test ADDRESS detection
curl -X POST http://localhost:3000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"Ich wohne in der Hauptstraße 42.","language":"de","entities":["ADDRESS"]}' \
  | jq

# Check memory
docker stats presidio-analyzer-de --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

### Log Patterns to Monitor

**Good Signs:**
```
[street_gazetteer] Loaded 422,721 street names (preprocessed).
[selftest] ✓ All 8 test cases passed
[gaz] candidates=X hits=Y spans_written=Y
```

**Warning Signs:**
```
[selftest] WARNING: Could not run self-test
[gaz] STREET_NAMES=0  # Gazetteer not loaded
Worker failed to boot  # Presidio startup issue
```

**Error Signs:**
```
[selftest] FATAL: ADDRESS pipeline self-test failed
[E047] Can't assign a value to unregistered extension
[E004] Can't set up pipeline component: a factory for 'X' already exists
```

---

## 10. Contact & Escalation

**For Production Issues:**
1. Check this runbook first
2. Review logs: `docker logs presidio-analyzer-de`
3. Check monitoring dashboards (Grafana)
4. If self-test failing → rebuild container
5. If persistent → escalate to development team

**Development Team:**
- Code repository: `/Users/leonbeckert/dev/20-clients/PresidioGUI`
- Key files: `analyzer-de/street_gazetteer.py`, `analyzer-de/Dockerfile`
- Documentation: `FINAL_STATUS_REPORT.md`

---

**Document Version:** 1.0.0  
**Last Updated:** 2025-11-14  
**Status:** ✅ Production Ready
