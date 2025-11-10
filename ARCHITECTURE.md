# Architektur-Dokumentation - Klinikon Pseudonymisierer

Technische Übersicht für Entwickler und System-Architekten.

---

## 🏗️ System-Architektur

### High-Level Übersicht

```
┌────────────────────────────────────────────────────────────┐
│                    Benutzer (Browser)                      │
└────────────────────┬───────────────────────────────────────┘
                     │ HTTP/HTTPS
                     │ Port 8501
┌────────────────────▼───────────────────────────────────────┐
│                  Streamlit Web-UI                          │
│  - klinikon-presidio-ui/app.py (UI-Logik)                              │
│  - klinikon-presidio-ui/helpers.py (API-Client)                        │
│  - Session-State Management                                │
│  - Keine persistente Speicherung                          │
└───────┬──────────────────────────────────┬─────────────────┘
        │                                  │
        │ REST-API                         │ REST-API
        │ JSON                             │ JSON
        │                                  │
┌───────▼──────────────────┐   ┌───────────▼────────────────┐
│  Presidio Analyzer       │   │  Presidio Anonymizer       │
│  Port 5002               │   │  Port 5001                 │
├──────────────────────────┤   ├────────────────────────────┤
│  - NLP Engine (spaCy)    │   │  - Operator Registry       │
│  - Recognizer Registry   │   │  - Text Manipulation       │
│  - Entity Detection      │   │  - Replace/Mask/Hash       │
│  - Score Calculation     │   │  - Format Preservation     │
└──────────────────────────┘   └────────────────────────────┘
        │
        │ Lädt Modell
        ▼
┌────────────────────────┐
│ spaCy DE Model         │
│ de_core_news_md        │
│ - NER (Named Entities) │
│ - POS Tagging          │
│ - Dependency Parsing   │
└────────────────────────┘
```

### Datenfluss

#### Analyse-Flow:
```
1. User gibt Text ein → Streamlit UI (app.py)
2. UI ruft helpers.analyze_text() auf
3. helpers.py sendet POST /analyze → Presidio Analyzer
4. Analyzer nutzt spaCy DE + Custom Recognizers
5. Entities mit Scores werden zurückgegeben
6. UI zeigt Entities gruppiert an
```

#### Anonymisierungs-Flow:
```
1. User wählt Strategie ("streng", "maskierung", "hash")
2. UI ruft helpers.anonymize_text() mit analyzer_results auf
3. helpers.py sendet POST /anonymize → Presidio Anonymizer
4. Anonymizer wendet gewählte Operatoren an
5. Anonymisierter Text wird zurückgegeben
6. UI zeigt Ergebnis + Download-Option
```

---

## 📁 Projektstruktur

```
presidio-medical-de/
│
├── docker-compose.yml          # Orchestrierung aller Services
├── .env.example                # Template für Umgebungsvariablen
├── Makefile                    # Hilfs-Kommandos (make up, make down)
│
├── analyzer-de/                # Custom Presidio Analyzer
│   ├── Dockerfile              # Analyzer-Image mit DE-Modell
│   └── analyzer-config-medical-de.yml  # Custom Recognizers + NLP-Config
│
├── klinikon-presidio-ui/                    # Streamlit Web-Interface
│   ├── Dockerfile              # UI-Image
│   ├── requirements.txt        # Python-Dependencies
│   ├── helpers.py              # API-Client + Business-Logik
│   └── app.py                  # Streamlit-App (UI)
│
├── tests/
│   └── sample-data/
│       └── beispiel-text.txt  # Test-Daten
│
├── validate.sh                 # Pre-Flight Check-Script
├── README.md                   # Hauptdokumentation
├── QUICKSTART.md               # 5-Minuten Setup-Guide
├── PRODUCTION.md               # Production Deployment Guide
├── ARCHITECTURE.md             # Diese Datei
├── CHANGELOG.md                # Versions-Historie
│
├── .gitignore                  # Git-Ignore-Regeln
└── .dockerignore               # Docker-Build-Ignore
```

---

## 🧩 Komponenten-Details

### 1. Presidio Analyzer (`analyzer-de/`)

**Technologie:** Python 3.11, Presidio, spaCy

**Hauptaufgaben:**
- Entity Recognition via NLP
- Custom Pattern-Matching (Regex)
- Score-Berechnung für Confidence
- Multi-Entity-Support

**Konfiguration:** `analyzer-config-medical-de.yml`

```yaml
# Struktur:
supported_languages: [de]
nlp_configuration:          # spaCy-Modell-Config
  nlp_engine_name: spacy
  models: [...]
recognizer_registry:        # Custom Recognizers
  recognizers:
    - name: DeKvnrRecognizer
      patterns: [...]
```

**Custom Recognizers:**
| Name | Entity | Regex-Pattern | Score |
|------|--------|---------------|-------|
| `DeKvnrRecognizer` | `DE_KVNR` | `\b[A-Z]\d{9}\b` | 0.85 |
| `DePhoneRecognizer` | `DE_PHONE_NUMBER` | `0\d{2,5}[\s\-]?\d{5,10}` | 0.7-0.75 |
| `DeIbanRecognizer` | `DE_IBAN` | `\bDE\d{2}\s?(\d{4}\s?){4}\d{2}\b` | 0.9 |
| `DePatientIdRecognizer` | `PATIENT_ID` | `\b(PAT\|PID\|P)[\-\s]?\d{6,10}\b` | 0.8 |
| `DeDateOfBirthRecognizer` | `DATE_OF_BIRTH` | `\b\d{2}\.\d{2}\.\d{4}\b` | 0.85 |

**API-Endpunkte:**
- `GET /health` - Health-Check
- `POST /analyze` - Text analysieren
- `GET /supportedentities` - Verfügbare Entity-Typen
- `GET /recognizers` - Registrierte Recognizers

### 2. Presidio Anonymizer

**Technologie:** Python 3.11, Presidio

**Hauptaufgaben:**
- Text-Manipulation basierend auf Analyzer-Results
- Operator-basierte Transformationen
- Format-Erhaltung (z.B. Whitespace)

**Operator-Typen:**

| Operator | Beschreibung | Beispiel |
|----------|--------------|----------|
| `replace` | Ersetzt mit festem String | `Max` → `<PERSON>` |
| `mask` | Maskiert Zeichen | `Max` → `M**` |
| `hash` | Kryptografischer Hash | `Max` → `5d41402...` |
| `redact` | Schwärzt | `Max` → `███` |
| `keep` | Behält Original | `Max` → `Max` |

**API-Endpunkte:**
- `GET /health` - Health-Check
- `POST /anonymize` - Text anonymisieren
- `POST /deanonymize` - Text de-anonymisieren (mit Mapping)
- `GET /anonymizers` - Verfügbare Operatoren

### 3. Streamlit UI (`klinikon-presidio-ui/`)

**Technologie:** Python 3.11, Streamlit 1.39

**Architektur-Pattern:** Model-View-Controller (MVC)

```
app.py (View/Controller)
    ↓
helpers.py (Model/API-Client)
    ↓
Presidio Services (Backend)
```

**Komponenten:**

#### `app.py` (UI-Layer)
- Streamlit-Page-Config
- Session-State Management
- Render-Funktionen:
  - `render_sidebar()` - Einstellungen & Health-Status
  - `render_entity_table()` - Ergebnisdarstellung
  - `main()` - Hauptlogik

**State-Management:**
```python
st.session_state = {
    'analysis_results': List[Dict],  # Analyzer-Output
    'anonymized_text': Dict,         # Anonymizer-Output
    'input_text': str                # User-Input
}
```

#### `helpers.py` (Business-Logic)
- **API-Client-Funktionen:**
  - `analyze_text()` - Wrapper für /analyze
  - `anonymize_text()` - Wrapper für /anonymize
  - `check_service_health()` - Health-Checks

- **Error-Handling:**
  - Retry-Logic (3 Versuche)
  - Custom-Exceptions
  - Timeout-Handling (30s)

- **Vordefinierte Konfigurationen:**
  - `MEDICAL_ANONYMIZERS` - Strategie-Templates
  - `get_anonymizer_config()` - Config-Resolver

---

## 🔄 Deployment-Patterns

### Docker Compose (Development & Small Production)

**Vorteile:**
- Einfaches Setup
- Single-Host
- Gut für <50 User

**Services:**
```yaml
services:
  presidio-analyzer:
    build: ./analyzer-de
    ports: ["5002:3000"]
    resources:
      limits: {memory: 2G, cpus: '1.5'}

  presidio-anonymizer:
    image: mcr.microsoft.com/presidio-anonymizer
    ports: ["5001:3000"]
    resources:
      limits: {memory: 512M, cpus: '0.5'}

  klinikon-presidio-ui:
    build: ./klinikon-presidio-ui
    ports: ["8501:8501"]
    depends_on: [analyzer, anonymizer]
```

### Kubernetes (Large-Scale Production)

**Vorteile:**
- Auto-Scaling
- High-Availability
- Multi-Node
- Load-Balancing

**Beispiel-Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: presidio-analyzer
spec:
  replicas: 3  # Skalierbar
  template:
    spec:
      containers:
      - name: analyzer
        image: presidio-analyzer-de:latest
        resources:
          limits: {memory: 2Gi, cpu: 1500m}
---
apiVersion: v1
kind: Service
metadata:
  name: presidio-analyzer
spec:
  type: ClusterIP
  selector:
    app: presidio-analyzer
  ports:
  - port: 3000
```

---

## 🔐 Security-Architektur

### Schichten

```
┌─────────────────────────────────────────┐
│  Layer 4: Network (Firewall/NSG)       │ ← Port-Restriktionen
├─────────────────────────────────────────┤
│  Layer 3: TLS/HTTPS (Reverse-Proxy)    │ ← Verschlüsselung
├─────────────────────────────────────────┤
│  Layer 2: Authentication (SSO/LDAP)    │ ← Zugriffskontrolle
├─────────────────────────────────────────┤
│  Layer 1: Application (Stateless)      │ ← Keine persistenten Daten
└─────────────────────────────────────────┘
```

### Defense-in-Depth

1. **Netzwerk-Isolation:**
   - Analyzer & Anonymizer nur intern erreichbar
   - Nur UI-Port (8501) nach außen

2. **Container-Security:**
   - Non-Root User
   - Read-Only Filesystem (wo möglich)
   - Resource-Limits (DoS-Prevention)

3. **Data-Security:**
   - Keine persistente Speicherung
   - In-Memory Processing
   - Session-basierte Daten

4. **Audit-Trail:**
   - Structured Logging
   - Zentrales Log-Aggregation
   - SIEM-Integration möglich

---

## 📊 Performance-Charakteristiken

### Latenz-Budget

| Operation | Target | Worst-Case |
|-----------|--------|------------|
| spaCy Model Load | ~30s | 60s |
| Analyze (500 char) | <200ms | 500ms |
| Analyze (5000 char) | <1s | 2s |
| Anonymize | <100ms | 300ms |
| Total (Analyze + Anon) | <300ms | 800ms |

### Skalierungs-Metriken

**Single-Instance:**
- Concurrent Users: ~20
- Requests/sec: ~5
- RAM: 2GB (Analyzer) + 512MB (Anonymizer)

**3-Instance Cluster:**
- Concurrent Users: ~60
- Requests/sec: ~15
- RAM: 6GB + 1.5GB

### Bottlenecks

1. **spaCy NER** - CPU-intensiv
   - Lösung: Mehr Analyzer-Replicas
2. **Memory (spaCy Model)** - ~1.5GB per Instance
   - Lösung: Resource-Limits + Auto-Scaling

---

## 🧪 Testing-Strategie

### Unit-Tests (TODO)
```python
# tests/test_helpers.py
def test_analyze_text_valid_input():
    result = analyze_text("Max Mustermann", "de")
    assert len(result) > 0
    assert result[0]["entity_type"] == "PERSON"
```

### Integration-Tests
```bash
# tests/integration_test.sh
curl -X POST http://localhost:5002/analyze \
  -d '{"text": "Test", "language": "de"}' \
  | jq '.[] | select(.entity_type == "PERSON")'
```

### Load-Tests
```bash
# Apache Bench
ab -n 1000 -c 10 -T 'application/json' \
   -p test-payload.json \
   http://localhost:5002/analyze
```

---

## 🔧 Erweiterbarkeit

### Neue Custom-Recognizer hinzufügen

1. **YAML bearbeiten:**
```yaml
# analyzer-de/analyzer-config-medical-de.yml
recognizers:
  - name: DeCustomRecognizer
    supported_languages: [de]
    supported_entities: [MY_ENTITY]
    patterns:
      - name: my_pattern
        regex: '\bMY_REGEX\b'
        score: 0.8
```

2. **Rebuild:**
```bash
docker compose build presidio-analyzer
docker compose up -d
```

### Neue Anonymisierungs-Strategie

1. **helpers.py bearbeiten:**
```python
MEDICAL_ANONYMIZERS = {
    "custom_strategy": {
        "PERSON": {"type": "hash", "hash_type": "sha256"},
        # ...
    }
}
```

2. **UI aktualisieren:**
```python
# app.py
strategy = st.selectbox(
    options=["streng", "maskierung", "hash", "custom_strategy"]
)
```

---

## 📚 Technologie-Stack

| Komponente | Technologie | Version | Lizenz |
|------------|-------------|---------|--------|
| Analyzer | Presidio | latest | MIT |
| Anonymizer | Presidio | latest | MIT |
| NLP | spaCy | 3.7+ | MIT |
| DE Model | de_core_news_md | 3.7+ | MIT |
| UI | Streamlit | 1.39 | Apache 2.0 |
| Container | Docker | 24.0+ | Apache 2.0 |
| Orchestration | Docker Compose | 2.20+ | Apache 2.0 |

---

## 🔗 Externe Abhängigkeiten

- **Microsoft Presidio**: https://github.com/microsoft/presidio
- **spaCy**: https://spacy.io
- **Streamlit**: https://streamlit.io

---

**Fragen zur Architektur?** → GitHub Issues oder siehe README.md
