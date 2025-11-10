# Production Deployment Guide - Klinikon Pseudonymisierer

Dieser Guide richtet sich an IT-Verantwortliche in Kliniken für das sichere Deployment in Produktionsumgebungen.

---

## 🔒 Sicherheits-Checkliste

### Vor dem Deployment

- [ ] **Netzwerk-Isolation**: Services in separatem VLAN/Subnet
- [ ] **Firewall-Regeln**: Nur Port 8501 (UI) nach außen, 5001+5002 intern
- [ ] **HTTPS**: Reverse-Proxy (nginx/Traefik) mit TLS-Zertifikat
- [ ] **Authentifizierung**: SSO/LDAP-Integration (siehe unten)
- [ ] **Audit-Logging**: Zentrales Logging (Syslog/ELK-Stack)
- [ ] **Backup**: Config-Files in Versionskontrolle
- [ ] **Updates**: Update-Strategie festgelegt
- [ ] **DSGVO-Prüfung**: Datenschutzbeauftragten informiert

---

## 🚀 Deployment-Optionen

### Option 1: Docker Compose (Empfohlen für kleine Installationen)

**Vorteile:**
- Einfaches Setup
- Wenig Overhead
- Gut für 1-50 gleichzeitige Nutzer

**Server-Anforderungen:**
- 4 CPU Cores (min. 2)
- 8 GB RAM (min. 6 GB)
- 20 GB Disk
- Ubuntu 22.04 LTS oder RHEL 8+

```bash
# Production-Setup
cd /opt/presidio-medical-de
cp .env.example .env

# .env anpassen:
LOG_LEVEL=WARNING
APP_ENV=production

# Starten
docker compose up -d
```

### Option 2: Kubernetes (Für größere Deployments)

**Vorteile:**
- Auto-Scaling
- High-Availability
- Load-Balancing
- Multi-Node

```yaml
# Beispiel: k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: presidio-analyzer
spec:
  replicas: 3  # Skalierbar
  selector:
    matchLabels:
      app: presidio-analyzer
  template:
    metadata:
      labels:
        app: presidio-analyzer
    spec:
      containers:
      - name: analyzer
        image: presidio-analyzer-de:latest
        resources:
          limits:
            memory: "2Gi"
            cpu: "1.5"
          requests:
            memory: "1Gi"
            cpu: "0.5"
```

---

## 🔐 Authentifizierung & Autorisierung

### Streamlit mit SSO (via nginx)

```nginx
# /etc/nginx/sites-available/presidio

upstream presidio_ui {
    server localhost:8501;
}

server {
    listen 443 ssl http2;
    server_name presidio.klinik.de;

    ssl_certificate /etc/ssl/certs/presidio.crt;
    ssl_certificate_key /etc/ssl/private/presidio.key;

    # SSO-Auth (z.B. via OpenID Connect)
    auth_request /auth;

    location /auth {
        internal;
        proxy_pass http://auth-server/validate;
    }

    location / {
        proxy_pass http://presidio_ui;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Nur für authentifizierte Nutzer
        if ($http_authorization = "") {
            return 401;
        }
    }
}
```

### LDAP-Integration (Active Directory)

```python
# klinikon-presidio-ui/auth_ldap.py (optional)
import ldap
import streamlit as st

def authenticate_ldap(username: str, password: str) -> bool:
    ldap_server = "ldap://ad.klinik.de"
    base_dn = "DC=klinik,DC=de"

    try:
        conn = ldap.initialize(ldap_server)
        user_dn = f"CN={username},OU=Users,{base_dn}"
        conn.simple_bind_s(user_dn, password)
        return True
    except ldap.INVALID_CREDENTIALS:
        return False
    finally:
        conn.unbind()

# In app.py integrieren:
if 'authenticated' not in st.session_state:
    username = st.text_input("Benutzername")
    password = st.text_input("Passwort", type="password")
    if st.button("Login"):
        if authenticate_ldap(username, password):
            st.session_state.authenticated = True
        else:
            st.error("Ungültige Zugangsdaten")
    st.stop()
```

---

## 📊 Monitoring & Observability

### Health-Checks (Kubernetes)

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 60
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 30
  periodSeconds: 10
```

### Prometheus-Metriken

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'presidio-analyzer'
    static_configs:
      - targets: ['presidio-analyzer:3000']
```

### Centralized Logging (ELK-Stack)

```yaml
# docker-compose.logging.yml
services:
  filebeat:
    image: docker.elastic.co/beats/filebeat:8.10.0
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml
    depends_on:
      - elasticsearch

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"

  kibana:
    image: docker.elastic.co/kibana/kibana:8.10.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

---

## 🔄 Backup & Disaster Recovery

### Config-Backup (täglich)

```bash
#!/bin/bash
# /opt/scripts/backup-presidio.sh

BACKUP_DIR="/backup/presidio"
DATE=$(date +%Y%m%d)

# Config-Files sichern
tar -czf "$BACKUP_DIR/config-$DATE.tar.gz" \
    /opt/presidio-medical-de/analyzer-de/analyzer-config-medical-de.yml \
    /opt/presidio-medical-de/klinikon-presidio-ui/*.py \
    /opt/presidio-medical-de/docker-compose.yml \
    /opt/presidio-medical-de/.env

# Alte Backups löschen (>30 Tage)
find "$BACKUP_DIR" -name "config-*.tar.gz" -mtime +30 -delete
```

```bash
# Cronjob einrichten
0 2 * * * /opt/scripts/backup-presidio.sh
```

### Disaster-Recovery-Plan

1. **RPO (Recovery Point Objective)**: 24 Stunden (tägl. Backup)
2. **RTO (Recovery Time Objective)**: 2 Stunden

**Recovery-Schritte:**
```bash
# 1. Backup einspielen
cd /opt/presidio-medical-de
tar -xzf /backup/presidio/config-YYYYMMDD.tar.gz

# 2. Container neu bauen
docker compose build

# 3. Services starten
docker compose up -d

# 4. Health-Check
curl http://localhost:5002/health
```

---

## 📈 Skalierung & Performance

### Load-Balancing (nginx)

```nginx
upstream presidio_analyzer {
    least_conn;  # Load-Balancing-Algorithmus
    server analyzer1:3000 max_fails=3 fail_timeout=30s;
    server analyzer2:3000 max_fails=3 fail_timeout=30s;
    server analyzer3:3000 max_fails=3 fail_timeout=30s;
}

server {
    listen 5002;
    location / {
        proxy_pass http://presidio_analyzer;
    }
}
```

### Auto-Scaling (Kubernetes HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: presidio-analyzer-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: presidio-analyzer
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Performance-Tuning

**Analyzer-Optimierung:**
```yaml
# docker-compose.yml
services:
  presidio-analyzer:
    environment:
      # spaCy-Pipeline optimieren
      SPACY_PREFER_GPU: "false"  # CPU-optimiert
      OMP_NUM_THREADS: "4"       # Parallel-Threads
    deploy:
      resources:
        limits:
          memory: 3G  # Mehr RAM = weniger GC-Pausen
          cpus: '2.0'
```

---

## 🧪 Update-Strategie

### Zero-Downtime-Update

```bash
# 1. Neue Version bauen
docker compose build

# 2. Rolling-Update (ein Service nach dem anderen)
docker compose up -d --no-deps --build presidio-analyzer
sleep 30  # Warten auf Health-Check
docker compose up -d --no-deps --build klinikon-presidio-ui

# 3. Alte Images aufräumen
docker image prune -f
```

### Rollback-Prozedur

```bash
# 1. Letzte funktionierende Version identifizieren
docker images | grep presidio-analyzer

# 2. Auf alte Version zurück
docker tag presidio-analyzer:old presidio-analyzer:latest
docker compose up -d

# 3. Verify
curl http://localhost:5002/health
```

---

## 🔍 Compliance & Audit

### DSGVO-Dokumentation

**Erforderliche Dokumente:**
- [ ] Verarbeitungsverzeichnis (Art. 30 DSGVO)
- [ ] TOM (Technisch-organisatorische Maßnahmen)
- [ ] Datenschutz-Folgenabschätzung (bei Bedarf)
- [ ] Einwilligung der Patienten (falls erforderlich)

**Beispiel-TOM:**
```markdown
## Technisch-organisatorische Maßnahmen (TOM)

### Zutrittskontrolle
- Zugang nur für autorisiertes Personal (LDAP)
- Logging aller Zugriffe

### Zugangskontrolle
- SSO/MFA für alle Nutzer
- Rollenbasierte Berechtigungen

### Zugriffskontrolle
- Keine persistente Speicherung
- Session-basierte Verarbeitung

### Weitergabekontrolle
- Verschlüsselte Übertragung (TLS 1.3)
- Keine Weitergabe an Dritte

### Eingabekontrolle
- Audit-Logs für alle Operationen
- Protokollierung von Anonymisierungen

### Auftragskontrolle
- Nur Verarbeitung im Auftrag der Klinik
- Keine externe Datenverarbeitung

### Verfügbarkeitskontrolle
- Health-Checks & Monitoring
- Backup & Disaster Recovery

### Trennungskontrolle
- Dedizierte Instanz pro Klinik
- Keine Mandantenfähigkeit
```

### Audit-Logging aktivieren

```python
# klinikon-presidio-ui/audit_logger.py
import logging
from datetime import datetime

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Log-Handler (z.B. Syslog)
handler = logging.handlers.SysLogHandler(address=('syslog-server', 514))
audit_logger.addHandler(handler)

def log_anonymization(user: str, text_length: int, entities_found: int):
    """Loggt Anonymisierungs-Operationen für Compliance"""
    audit_logger.info(
        f"ANONYMIZATION | User={user} | TextLength={text_length} | "
        f"Entities={entities_found} | Timestamp={datetime.utcnow().isoformat()}"
    )
```

---

## 📞 Support & Eskalation

### Incident-Response

**Severity-Level:**

| Level | Beschreibung | Response-Zeit |
|-------|--------------|---------------|
| P1 | Service komplett ausgefallen | 15 Min. |
| P2 | Teilausfall, kritische Funktion fehlt | 1 Std. |
| P3 | Degraded Performance | 4 Std. |
| P4 | Kosmetische Fehler | Next Business Day |

**Eskalationspfad:**
1. IT-Support Klinik
2. Docker/Container-Experten
3. Presidio-Community (GitHub Issues)

### Kontakte

- **Microsoft Presidio**: https://github.com/microsoft/presidio/issues
- **spaCy Support**: https://github.com/explosion/spaCy/discussions

---

## ✅ Go-Live Checkliste

### Vor dem Go-Live

- [ ] Alle Sicherheits-Checks durchgeführt
- [ ] HTTPS & Authentifizierung aktiv
- [ ] Monitoring & Alerting eingerichtet
- [ ] Backup-Strategie getestet
- [ ] Rollback-Prozedur dokumentiert
- [ ] Load-Tests durchgeführt (siehe unten)
- [ ] Datenschutzbeauftragten informiert
- [ ] Anwender geschult
- [ ] Support-Prozesse definiert
- [ ] Dokumentation vollständig

### Load-Test (Apache Bench)

```bash
# Test: 1000 Requests, 10 concurrent
ab -n 1000 -c 10 -T 'application/json' \
   -p test-payload.json \
   http://localhost:5002/analyze

# test-payload.json:
# {"text": "Test-Patient Max Mustermann", "language": "de"}
```

---

**Bei Fragen: Siehe README.md oder eröffne ein GitHub Issue.**
