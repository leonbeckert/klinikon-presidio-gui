# Docker Troubleshooting Guide

## Understanding Docker: Images vs Containers

### CRITICAL: Why Code Changes Don't Magically Appear in Containers

**Common mistake:** Editing a Python file, then running `docker compose down && docker compose up -d`, expecting the changes to work.

**Why this fails:** Docker has THREE layers:

```
┌─────────────────────────────────────────┐
│ HOST FILESYSTEM (your local files)     │  ← You edit code HERE
│ - analyzer-de/street_gazetteer.py      │
└─────────────────────────────────────────┘
                 ↓ docker build
┌─────────────────────────────────────────┐
│ DOCKER IMAGE (frozen snapshot)          │  ← Old code is frozen HERE
│ - /app/street_gazetteer.py (OLD CODE!) │
└─────────────────────────────────────────┘
                 ↓ docker compose up
┌─────────────────────────────────────────┐
│ RUNNING CONTAINER                        │  ← Runs from OLD image
└─────────────────────────────────────────┘
```

**Solution:** Run `docker build` to update the image before `docker compose up`

## Common Mistakes and Solutions

### Mistake 1: "I changed code but tests still fail the same way"

**Diagnosis:**
```bash
docker images | grep presidio-analyzer-de      # Check image build time
docker exec presidio-analyzer-de ls -l /app/street_gazetteer.py  # Check container file
ls -l analyzer-de/street_gazetteer.py          # Check host file
```

**Fix:** Rebuild the image
```bash
docker compose down
cd analyzer-de && docker build --no-cache -t presidio-analyzer-de . && cd ..
docker compose up -d
```

### Mistake 2: "I added print statements but don't see them in logs"

**Diagnosis:**
```bash
docker exec presidio-analyzer-de grep "your debug message" /app/street_gazetteer.py
```

**Fix:** If not found → rebuild the image

### Mistake 3: "Changes work with docker cp but disappear after restart"

**Explanation:** `docker cp` copies files into the running container (bypasses image). When you restart, a NEW container is created from the OLD image.

**Fix:** Always rebuild the image for permanent changes

### Mistake 4: "Mac freezing/crashing during Docker operations"

**Cause:** Duplicate containers stacking up (running `docker compose up` without `docker compose down` first)

**Fix:**
```bash
docker compose down -v --remove-orphans
docker ps -a  # Should show no presidio containers
docker compose up -d
```

### Mistake 5: "Code changes require rebuild but image name mismatch"

**Problem:** `docker build` creates image with one name, but `docker compose` expects a different name.

**Diagnosis:**
```bash
docker images | grep presidio  # Check what images exist
docker compose config | grep image  # Check what compose expects
```

**Fix:** Ensure `docker build -t` uses the exact name from docker-compose.yaml:
```yaml
# In docker-compose.yaml:
services:
  presidio-analyzer:
    build: ./analyzer-de
    container_name: presidio-analyzer-de
    image: presidio-analyzer-de  # ← This is the image name
```

```bash
# Build command MUST match:
docker build -t presidio-analyzer-de ./analyzer-de
```

**OR** use `docker compose build` instead:
```bash
docker compose down
docker compose build --no-cache presidio-analyzer
docker compose up -d
```

## Resource Monitoring

```bash
# Check memory usage
docker stats --no-stream

# Count containers (should be ≤ 3 for this project)
docker ps | wc -l

# View resource limits
docker compose config | grep -A 5 "resources:"
```

## Emergency Cleanup

```bash
# Nuclear option - remove everything
docker compose down -v --remove-orphans
docker system prune -a

# Verify cleanup
docker ps -a
docker images
```

## Verification Checklist

After making changes and rebuilding:

```bash
# 1. Verify image was rebuilt
docker images | grep presidio-analyzer-de  # Check timestamp

# 2. Verify file is in container
docker exec presidio-analyzer-de ls -l /app/street_gazetteer.py

# 3. Verify specific change is present
docker exec presidio-analyzer-de grep "your_new_function" /app/street_gazetteer.py

# 4. Check logs for expected behavior
docker logs presidio-analyzer-de --tail 50
```
