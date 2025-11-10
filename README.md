# Klinikon Pseudonymisierer 🏥

**DSGVO-konforme Pseudonymisierung von deutschen Texten**

Produktionsreifes System zur automatischen Erkennung und Anonymisierung personenbezogener Daten in medizinischen Dokumenten deutscher Kliniken.

## 📖 Schnell-Navigation

- [Features](#-features) - Erkannte Entitäten und Anonymisierungs-Strategien
- [Architektur](#️-architektur) - System-Übersicht und Port-Mapping
- [Schnellstart](#-schnellstart) - Installation in 3 Minuten
- [Verwendung](#-verwendung) - Web-UI und API-Beispiele
- [Konfiguration](#-konfiguration) - Custom Recognizers hinzufügen
- [Dokumentation](#-dokumentation) - Alle verfügbaren Docs
- [Wartung & Betrieb](#️-wartung--betrieb) - Makefile-Commands und Troubleshooting

---

## 🎯 Features

### Erkannte Entitäten

**Standard-Entitäten (via spaCy DE):**
- `PERSON` - Namen von Personen
- `LOCATION` - Städte, Adressen, Orte
- `ORGANIZATION` - Kliniken, Praxen, Versicherungen

**Medizinische Custom-Recognizers:**
- `DE_KVNR` - Krankenversichertennummer (z.B. M123456789)
- `PATIENT_ID` - Patientennummern (verschiedene Formate)
- `DATE_OF_BIRTH` - Geburtsdaten (dd.mm.yyyy)
- `DE_PHONE_NUMBER` - Deutsche Telefonnummern
- `EMAIL_ADDRESS` - E-Mail-Adressen
- `DE_IBAN` - Bankverbindungen
- `DE_ZIP_CODE` - Postleitzahlen

### Anonymisierungs-Strategien

1. **Streng** - Vollständiger Ersatz mit Platzhaltern (`<PERSON>`, `<KVNR>`, etc.)
2. **Maskierung** - Teilweise Maskierung (z.B. `Max M******`, `M9876****`)
3. **Hash** - Kryptografische Hashes (konsistent, pseudonymisiert)

---

## 🏗️ Architektur

```
                    Docker Network: presidio-network
┌────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌─────────────────┐                                        │
│  │  Streamlit UI   │  Port 8501:8501                       │
│  │  (Browser)      │  Limits: 512MB RAM, 0.5 CPU           │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ├──────────► Presidio Analyzer                    │
│           │            Host: presidio-analyzer:3000 (intern)│
│           │            Port: 5002→3000 (extern→intern)      │
│           │            Limits: 2GB RAM, 1.5 CPU             │
│           │            └─ spaCy DE Model (de_core_news_md)  │
│           │            └─ Custom German Recognizers         │
│           │                                                  │
│           └──────────► Presidio Anonymizer                  │
│                        Host: presidio-anonymizer:3000       │
│                        Port: 5001→3000 (extern→intern)      │
│                        Limits: 512MB RAM, 0.5 CPU           │
│                        └─ Anonymization Operators           │
│                                                              │
└────────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
    localhost:8501    localhost:5002      localhost:5001
     (Web-UI)         (Analyzer-API)    (Anonymizer-API)
```

**Port-Mapping**:
- Extern (von Host): `localhost:5002` und `localhost:5001`
- Intern (zwischen Containern): `presidio-analyzer:3000` und `presidio-anonymizer:3000`

**Vorteile dieser Architektur:**
- ✅ **Microservices** - Analyzer und Anonymizer getrennt skalierbar
- ✅ **Stateless** - Keine Datenbank nötig (KISS-Prinzip)
- ✅ **Health-Checks** - Automatische Container-Überwachung
- ✅ **Resource-Limits** - Verhindert Memory-Leaks
- ✅ **Retry-Logic** - Robuste API-Kommunikation

---

## 🚀 Schnellstart

### Voraussetzungen

- Docker & Docker Compose
- Mind. 4 GB RAM (für spaCy-Modell)
- Linux/macOS oder Windows mit WSL2

### Installation

```bash
# 1. Repository klonen / Dateien kopieren
cd presidio-medical-de

# 2. Environment-Datei erstellen
cp .env.example .env

# 3. Validierung durchführen (optional, empfohlen)
./validate.sh

# 4. Container bauen und starten
docker compose up -d --build
# ODER mit Makefile:
make up

# 5. Logs verfolgen (optional)
docker compose logs -f
# ODER:
make logs
```

### Services verfügbar nach ~60 Sekunden:

- **Web-UI**: http://localhost:8501
- **Analyzer-API**: http://localhost:5002 (extern) → Port 3000 (intern)
- **Anonymizer-API**: http://localhost:5001 (extern) → Port 3000 (intern)

> **Hinweis**: Die Services kommunizieren intern über Port 3000, sind aber extern über 5001/5002 erreichbar.

---

## 📋 Verwendung

### Web-Interface

1. Browser öffnen: http://localhost:8501
2. **Beispieltext laden** für Demo-Daten
3. **Analysieren** klicken → Erkennt alle Entitäten
4. **Anonymisierungs-Strategie** in Sidebar wählen
5. **Anonymisieren** klicken → Pseudonymisierter Text
6. **Als Textdatei herunterladen** für weitere Verarbeitung

### API-Nutzung (Direkt)

#### Analyse:
```bash
curl -X POST http://localhost:5002/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient Max Mustermann, KVNR M123456789, wohnt in Berlin.",
    "language": "de",
    "score_threshold": 0.0
  }' | jq .
```

**Antwort:**
```json
[
  {
    "entity_type": "PERSON",
    "start": 8,
    "end": 23,
    "score": 0.85,
    "analysis_explanation": null
  },
  {
    "entity_type": "DE_KVNR",
    "start": 30,
    "end": 40,
    "score": 0.85
  },
  {
    "entity_type": "LOCATION",
    "start": 51,
    "end": 57,
    "score": 0.75
  }
]
```

#### Anonymisierung:
```bash
curl -X POST http://localhost:5001/anonymize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient Max Mustermann, KVNR M123456789",
    "analyzer_results": [
      {"entity_type": "PERSON", "start": 8, "end": 23, "score": 0.85},
      {"entity_type": "DE_KVNR", "start": 30, "end": 40, "score": 0.85}
    ],
    "anonymizers": {
      "PERSON": {"type": "replace", "new_value": "<PATIENT>"},
      "DE_KVNR": {"type": "replace", "new_value": "<KVNR>"}
    }
  }' | jq .
```

**Antwort:**
```json
{
  "text": "Patient <PATIENT>, KVNR <KVNR>",
  "items": [...]
}
```

---

## 🔧 Konfiguration

### Environment-Variablen

Die `.env` Datei steuert die grundlegende Konfiguration:

```bash
# Logging-Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Umgebung (development, production)
APP_ENV=production

# Optional: Port-Overrides (Standard: siehe docker-compose.yaml)
# ANALYZER_PORT=5002
# ANONYMIZER_PORT=5001
# UI_PORT=8501
```

**Wichtig**: Nach Änderungen der `.env` Container neu starten:
```bash
make restart
# ODER:
docker compose restart
```

### Analyzer-Konfiguration anpassen

**Datei:** `analyzer-de/analyzer-config-medical-de.yml`

#### Neuen Custom-Recognizer hinzufügen:

```yaml
recognizer_registry:
  recognizers:
    - name: DeCustomRecognizer
      supported_languages:
        - de
      supported_entities:
        - CUSTOM_ENTITY
      patterns:
        - name: custom_pattern
          regex: 'YOUR_REGEX_HERE'
          score: 0.8
```

**Beispiele für Custom-Recognizers:**

```yaml
# Versichertennummer der Krankenkasse (IK-Nummer)
- name: DeIKNumberRecognizer
  supported_languages: [de]
  supported_entities: [DE_IK_NUMBER]
  patterns:
    - name: ik_number
      regex: '\b\d{9}\b'
      score: 0.6

# Arztnummer (LANR)
- name: DeLanrRecognizer
  supported_languages: [de]
  supported_entities: [DE_LANR]
  patterns:
    - name: lanr_pattern
      regex: '\b\d{9}\b'  # 9-stellig
      score: 0.65

# ICD-10 Codes
- name: DeICD10Recognizer
  supported_languages: [de]
  supported_entities: [ICD10_CODE]
  patterns:
    - name: icd10_pattern
      regex: '\b[A-Z]\d{2}(\.\d{1,2})?\b'
      score: 0.5
```

### Anonymisierungs-Strategien anpassen

**Datei:** `klinikon-presidio-ui/helpers.py` → `MEDICAL_ANONYMIZERS`

```python
MEDICAL_ANONYMIZERS = {
    "custom_strategy": {
        "PERSON": {"type": "replace", "new_value": "<NAME>"},
        "DE_KVNR": {"type": "hash", "hash_type": "sha256"},
        # ... weitere Entities
    }
}
```

**Verfügbare Anonymizer-Typen:**

| Typ | Beschreibung | Beispiel |
|-----|--------------|----------|
| `replace` | Ersetzt mit festem String | `<PATIENT>` |
| `mask` | Maskiert Zeichen | `Max M****` |
| `hash` | Kryptografischer Hash | `a3f8b9...` |
| `redact` | Schwärzt komplett | `████████` |
| `keep` | Behält Original | `Max Mustermann` |

---

## 🔒 Datenschutz & Sicherheit

### DSGVO-Konformität

✅ **Keine persistente Speicherung** - Alle Daten nur im RAM, keine Datenbank
✅ **Lokales Deployment** - Daten verlassen nie die Klinik-Infrastruktur
✅ **Audit-Logging** - Alle Operationen werden geloggt
✅ **Pseudonymisierung** nach Art. 4 Nr. 5 DSGVO

### Empfohlene Production-Settings

```yaml
# docker-compose.yaml
services:
  presidio-analyzer:
    environment:
      LOG_LEVEL: WARNING  # Reduziert Logging in Produktion
    deploy:
      resources:
        limits:
          memory: 2G      # Verhindert Memory-Leaks
          cpus: '1.5'
```

### Sicherheits-Checkliste

- [ ] `.env` Datei NICHT in Git committen
- [ ] Firewall: Nur Port 8501 nach außen exponieren (5001, 5002 intern)
- [ ] HTTPS via Reverse-Proxy (nginx/Traefik) einrichten
- [ ] Container-Updates regelmäßig einspielen
- [ ] Log-Rotation konfigurieren
- [ ] Backup-Strategie für Config-Files

---

## 🧪 Tests

### Manuelle Tests

```bash
# Health-Checks (alle Services)
make health
# ODER einzeln:
curl http://localhost:5002/health
curl http://localhost:5001/health

# Analyzer mit Beispiel-Text testen
curl -X POST http://localhost:5002/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient Max Mustermann, geb. 15.03.1978, KVNR M123456789",
    "language": "de",
    "score_threshold": 0.0
  }' | jq .
```

### Test-Daten

Im Verzeichnis `tests/sample-data/` findet sich `beispiel-text.txt` mit einem vollständigen medizinischen Beispieltext, der alle Entitätstypen enthält. Dieser kann im Web-UI über "Beispieltext laden" geladen werden.

---

## 🛠️ Wartung & Betrieb

### Makefile-Commands

Das Projekt enthält ein Makefile mit nützlichen Shortcuts:

```bash
make up          # Container starten (mit --build)
make down        # Container stoppen und entfernen
make restart     # Container neustarten
make logs        # Logs aller Services anzeigen
make health      # Health-Checks durchführen
make test        # Test-Suite ausführen
make clean       # Container, Volumes, Images entfernen
make validate    # Validierung durchführen
```

### Logs einsehen

```bash
# Alle Services (mit Makefile)
make logs

# Traditionell mit Docker Compose:
docker compose logs -f

# Nur Analyzer
docker compose logs -f presidio-analyzer

# Letzte 100 Zeilen
docker compose logs --tail=100
```

### Container neustarten

```bash
# Alle Services (mit Makefile)
make restart

# Traditionell:
docker compose restart

# Nur ein Service
docker compose restart presidio-analyzer
```

### Updates einspielen

```bash
# Neue Images pullen
docker compose pull

# Neu bauen und starten
docker compose up -d --build
# ODER:
make up
```

### Ressourcen-Monitoring

```bash
# Container-Ressourcen
docker stats

# Disk-Usage
docker system df
```

### Troubleshooting

**Problem: Analyzer startet nicht**
```bash
# Logs prüfen
docker compose logs presidio-analyzer

# Häufig: spaCy-Modell fehlt
docker compose exec presidio-analyzer python -m spacy validate
```

**Problem: UI zeigt "Service nicht erreichbar"**
```bash
# Health-Checks prüfen
docker compose ps

# Container neustarten
docker compose restart
```

**Problem: Zu hoher RAM-Verbrauch**
```yaml
# docker-compose.yaml anpassen
deploy:
  resources:
    limits:
      memory: 1.5G  # Reduzieren
```

---

## 📊 Performance

### Benchmarks (ca. Werte)

| Text-Länge | Analyse | Anonymisierung | Total |
|------------|---------|----------------|-------|
| 500 Zeichen | ~100ms | ~50ms | ~150ms |
| 2.000 Zeichen | ~300ms | ~100ms | ~400ms |
| 10.000 Zeichen | ~1.2s | ~300ms | ~1.5s |

**Hardware:** 4 CPU Cores, 8 GB RAM

### Optimierungen

1. **spaCy-Modell wählen:**
   - `de_core_news_sm` (klein, schneller, weniger akkurat)
   - `de_core_news_md` (empfohlen, ausgewogen)
   - `de_core_news_lg` (groß, langsamer, genauer)

2. **Resource-Limits erhöhen:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 4G
   ```

3. **Load-Balancing:**
   - Mehrere Analyzer-Instanzen via Docker Swarm/Kubernetes

---

## 📚 Dokumentation

### Projekt-Dokumentation

Dieses Projekt enthält umfassende Dokumentation:

- **README.md** (diese Datei) - Übersicht, Installation, Verwendung
- **ARCHITECTURE.md** - Detaillierte technische Architektur, Komponenten-Design
- **API_IMPLEMENTATION_GUIDE.md** - Ausführliche API-Integration und Beispiele
- **CHANGELOG.md** - Versions-Historie und geplante Features
- **Makefile** - Convenience-Commands (make up, make down, make logs, make health, etc.)
- **validate.sh** - Pre-flight Validierung vor dem ersten Start

### Externe Ressourcen

- [Microsoft Presidio Docs](https://microsoft.github.io/presidio/)
- [spaCy Deutsch](https://spacy.io/models/de)
- [DSGVO - Art. 4 Pseudonymisierung](https://dsgvo-gesetz.de/art-4-dsgvo/)

---

## 🤝 Support & Beiträge

### Häufige Fragen

**Q: Kann ich weitere Sprachen hinzufügen?**
A: Ja, in `analyzer-config-medical-de.yml` unter `supported_languages` weitere Sprachen eintragen und entsprechende spaCy-Modelle installieren.

**Q: Wie kann ich eigene Entitäten hinzufügen?**
A: Siehe Abschnitt "Konfiguration" → Custom-Recognizers hinzufügen.

**Q: Werden Daten gespeichert?**
A: Nein. Das System ist vollständig stateless. Alle Verarbeitungen erfolgen im RAM.

### Bekannte Limitierungen

- **Nur AMD64-Container** - ARM (Apple Silicon) benötigt Emulation
- **spaCy NER-Grenzen** - Medizinische Fachbegriffe können übersehen werden
- **Regex-Limits** - Sehr ungewöhnliche Formate werden ggf. nicht erkannt

---

## 📄 Lizenz

Dieses Projekt nutzt Open-Source-Komponenten:
- **Microsoft Presidio** - MIT License
- **spaCy** - MIT License
- **Streamlit** - Apache 2.0 License

Eigener Code: Kann gemäß Projekt-Lizenz verwendet werden.

---

## 🔖 Version

**Version:** 1.0.0
**Datum:** November 2025
**Status:** Production-Ready

### Projekt-Struktur

```
PresidioGUI/
├── README.md                          # Diese Datei
├── ARCHITECTURE.md                    # Technische Dokumentation
├── API_IMPLEMENTATION_GUIDE.md        # API-Integration
├── CHANGELOG.md                       # Versions-Historie
├── docker-compose.yaml                # Service-Orchestrierung
├── .env.example                       # Environment-Vorlage
├── Makefile                           # Convenience-Commands
├── validate.sh                        # Pre-flight Checks
├── analyzer-de/                       # Presidio Analyzer Service
│   ├── Dockerfile
│   ├── analyzer-config-medical-de.yml # Haupt-Konfiguration
│   ├── recognizers-de.yml             # Custom Recognizers
│   └── nlp-config-de.yml              # spaCy-Konfiguration
├── klinikon-presidio-ui/              # Streamlit Web-Interface
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                         # Hauptanwendung
│   └── helpers.py                     # API-Client & Business Logic
└── tests/
    └── sample-data/
        └── beispiel-text.txt          # Beispiel-Medizintext
```

---

**Entwickelt für deutsche Kliniken zur DSGVO-konformen Text-Pseudonymisierung.**
