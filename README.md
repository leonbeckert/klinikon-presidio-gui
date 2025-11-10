# Klinikon Pseudonymisierer 🏥

**DSGVO-konforme Pseudonymisierung von deutschen Texten**

Produktionsreifes System zur automatischen Erkennung und Anonymisierung personenbezogener Daten in medizinischen Dokumenten deutscher Kliniken.

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
┌─────────────────┐
│   Streamlit UI  │  (Port 8501) - Browser-Interface
└────────┬────────┘
         │
         ├──────────► Presidio Analyzer  (Port 5002)
         │            └─ spaCy DE Model
         │            └─ Custom Recognizers
         │
         └──────────► Presidio Anonymizer (Port 5001)
                      └─ Anonymization Operators
```

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

# 3. Container bauen und starten
docker compose up -d --build

# 4. Logs verfolgen (optional)
docker compose logs -f
```

### Services verfügbar nach ~60 Sekunden:

- **Web-UI**: http://localhost:8501
- **Analyzer-API**: http://localhost:5002
- **Anonymizer-API**: http://localhost:5001

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
# docker-compose.yml
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
# Health-Checks
curl http://localhost:5002/health
curl http://localhost:5001/health

# Analyzer mit Beispiel-Text
curl -X POST http://localhost:5002/analyze \
  -H "Content-Type: application/json" \
  --data @tests/sample-data/beispiel-text.txt
```

### Test-Daten

Im Verzeichnis `tests/sample-data/` finden sich Beispiel-Texte.

---

## 🛠️ Wartung & Betrieb

### Logs einsehen

```bash
# Alle Services
docker compose logs -f

# Nur Analyzer
docker compose logs -f presidio-analyzer

# Letzte 100 Zeilen
docker compose logs --tail=100
```

### Container neustarten

```bash
# Alle Services
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
# docker-compose.yml anpassen
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

## 📚 Weiterführende Dokumentation

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
**Datum:** März 2024
**Status:** Production-Ready

---

**Entwickelt für deutsche Kliniken zur DSGVO-konformen text-Pseudonymisierung.**
