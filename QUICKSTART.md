# Quick-Start Guide - 5 Minuten Setup

Los geht's in 3 Schritten! ⚡

---

## Voraussetzungen

- Docker Desktop installiert ([Download](https://www.docker.com/products/docker-desktop/))
- Mind. 6 GB freier RAM
- Terminal/Kommandozeile

---

## Schritt 1: Setup validieren

```bash
# Ins Projektverzeichnis wechseln
cd /pfad/zu/PresidioGUI

# Validierung durchführen
./validate.sh
```

✅ Alle Checks grün? → Weiter zu Schritt 2!

---

## Schritt 2: Starten

```bash
# Option A: Mit Makefile (empfohlen)
make up

# Option B: Direkt mit Docker Compose
docker compose up -d --build
```

⏱️ **Wartezeit: ~60 Sekunden** (spaCy-Modell lädt)

---

## Schritt 3: Öffnen & Testen

1. Browser öffnen: **http://localhost:8501**

2. Klick auf **"📋 Beispieltext laden"**

3. Klick auf **"🔍 Analysieren"**
   → Siehst du erkannte Entitäten? ✅

4. Klick auf **"🔒 Anonymisieren"**
   → Ist der Text pseudonymisiert? ✅

**Fertig!** 🎉

---

## Schnelltest (API)

```bash
# Health-Check
curl http://localhost:5002/health

# Test-Analyse
curl -X POST http://localhost:5002/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient Max Mustermann, KVNR M123456789, wohnt in Berlin.",
    "language": "de"
  }' | jq .
```

---

## Stoppen

```bash
# Option A: Mit Makefile
make down

# Option B: Direkt
docker compose down
```

---

## Häufige Probleme

### "Port already in use"
→ Andere Anwendung nutzt 8501/5001/5002
```bash
# Prüfen was Port belegt
lsof -i :8501
# Process beenden oder andere Ports in docker-compose.yml
```

### "Out of memory"
→ Docker-RAM erhöhen
```
Docker Desktop → Settings → Resources → Memory: 8 GB
```

### Services starten nicht
```bash
# Logs anschauen
docker compose logs -f

# Neustart mit frischem Build
docker compose down
docker compose up -d --build
```

---

## Nächste Schritte

📖 **Vollständige Doku**: Siehe [README.md](README.md)
🚀 **Production**: Siehe [PRODUCTION.md](PRODUCTION.md)
🔧 **Konfiguration**: Siehe Abschnitt in README.md

---

## Alle Kommandos auf einen Blick

```bash
# Validieren
./validate.sh

# Starten
make up

# Stoppen
make down

# Logs
make logs

# Status
make health

# Aufräumen
make clean
```

---

**Support?** Siehe [README.md](README.md) oder öffne ein GitHub Issue.
