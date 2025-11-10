# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [1.0.0] - 2024-03-15

### Hinzugefügt

#### Core-Funktionen
- Presidio Analyzer mit deutschem spaCy-Modell (`de_core_news_md`)
- Presidio Anonymizer Integration
- Streamlit-basierte Web-UI für medizinisches Personal
- Docker Compose Setup mit Health-Checks

#### Custom Recognizers (DE)
- `DE_KVNR` - Krankenversichertennummer
- `DE_PHONE_NUMBER` - Deutsche Telefonnummern (mobil & Festnetz)
- `DE_IBAN` - Deutsche Bankverbindungen
- `PATIENT_ID` - Patientennummern (verschiedene Formate)
- `DATE_OF_BIRTH` - Geburtsdaten im deutschen Format
- `DE_ZIP_CODE` - Postleitzahlen
- `DE_INSURANCE_NUMBER` - Versicherungsnummern

#### Anonymisierungs-Strategien
- **Streng**: Vollständiger Ersatz mit Platzhaltern
- **Maskierung**: Teilweise Maskierung sensibler Daten
- **Hash**: Kryptografische Hash-Funktionen

#### Sicherheit & Compliance
- Retry-Logic für robuste API-Kommunikation
- Audit-Logging für alle Operationen
- Resource-Limits zur Verhinderung von Memory-Leaks
- DSGVO-konforme stateless Architektur

#### Dokumentation
- Umfassende README mit Quick-Start Guide
- Production Deployment Guide
- API-Dokumentation & Beispiele
- Makefile für einfache Verwaltung
- Beispiel-Patiententexte für Tests

#### Development
- `.env.example` für Konfiguration
- `.gitignore` & `.dockerignore`
- Modulare Code-Struktur (KISS-Prinzip)

### Sicherheit
- Keine persistente Datenspeicherung (stateless)
- TLS-ready via Reverse-Proxy
- Health-Checks für alle Services
- Automatische Container-Neustarts bei Fehlern

---

## [Unreleased]

### Geplant
- Erweiterung um weitere medizinische Entities (ICD-Codes, Medikamente)
- Batch-Verarbeitung für große Dokumente
- REST-API-Dokumentation via OpenAPI/Swagger
- Multi-Language Support (EN, FR)
- Kubernetes Helm-Charts
- Prometheus-Metriken Export

---

## Versionierungs-Schema

- **MAJOR** (X.0.0): Breaking Changes (z.B. API-Änderungen)
- **MINOR** (1.X.0): Neue Features (rückwärtskompatibel)
- **PATCH** (1.0.X): Bugfixes & kleine Verbesserungen

---

[1.0.0]: https://github.com/your-org/presidio-medical-de/releases/tag/v1.0.0
