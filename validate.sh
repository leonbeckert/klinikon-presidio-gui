#!/bin/bash
# Klinikon Pseudonymisierer - Validierungs-Script
# Prüft ob alle Dateien vorhanden und Services konfiguriert sind

set -e

echo "🔍 Klinikon Pseudonymisierer - Validierung"
echo "======================================"
echo ""

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Helper-Funktionen
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1 vorhanden"
    else
        echo -e "${RED}✗${NC} $1 FEHLT"
        ((ERRORS++))
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} Verzeichnis $1 vorhanden"
    else
        echo -e "${RED}✗${NC} Verzeichnis $1 FEHLT"
        ((ERRORS++))
    fi
}

# 1. Struktur-Check
echo "1️⃣  Projektstruktur prüfen..."
echo "----------------------------"
check_file "docker-compose.yml"
check_file ".env.example"
check_file "README.md"
check_file "Makefile"

check_dir "analyzer-de"
check_file "analyzer-de/Dockerfile"
check_file "analyzer-de/analyzer-config-medical-de.yml"

check_dir "klinikon-presidio-ui"
check_file "klinikon-presidio-ui/Dockerfile"
check_file "klinikon-presidio-ui/requirements.txt"
check_file "klinikon-presidio-ui/helpers.py"
check_file "klinikon-presidio-ui/app.py"

echo ""

# 2. Docker-Check
echo "2️⃣  Docker-Verfügbarkeit prüfen..."
echo "--------------------------------"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker installiert: $(docker --version)"
else
    echo -e "${RED}✗${NC} Docker NICHT installiert"
    ((ERRORS++))
fi

if command -v docker compose &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker Compose verfügbar: $(docker compose version)"
elif command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Alte docker-compose Version (verwende 'docker compose')"
else
    echo -e "${RED}✗${NC} Docker Compose NICHT verfügbar"
    ((ERRORS++))
fi

echo ""

# 3. YAML-Syntax prüfen (analyzer config)
echo "3️⃣  YAML-Konfiguration validieren..."
echo "----------------------------------"
if command -v python3 &> /dev/null; then
    python3 -c "
import yaml
try:
    with open('analyzer-de/analyzer-config-medical-de.yml', 'r') as f:
        yaml.safe_load(f)
    print('${GREEN}✓${NC} analyzer-config-medical-de.yml ist valides YAML')
except Exception as e:
    print('${RED}✗${NC} YAML-Fehler:', str(e))
    exit(1)
" || ((ERRORS++))
else
    echo -e "${YELLOW}⚠${NC}  Python3 nicht verfügbar, YAML-Check übersprungen"
fi

echo ""

# 4. Port-Verfügbarkeit prüfen
echo "4️⃣  Port-Verfügbarkeit prüfen..."
echo "-----------------------------"
PORTS=(8501 5001 5002)
for PORT in "${PORTS[@]}"; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠${NC}  Port $PORT bereits belegt"
    else
        echo -e "${GREEN}✓${NC} Port $PORT verfügbar"
    fi
done

echo ""

# 5. .env-Datei prüfen
echo "5️⃣  Environment-Konfiguration..."
echo "------------------------------"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env Datei vorhanden"

    # Prüfe ob wichtige Variablen gesetzt sind
    if grep -q "LOG_LEVEL=" .env; then
        echo -e "${GREEN}✓${NC} LOG_LEVEL konfiguriert"
    else
        echo -e "${YELLOW}⚠${NC}  LOG_LEVEL nicht gesetzt (Standard wird verwendet)"
    fi
else
    echo -e "${YELLOW}⚠${NC}  .env fehlt (nutze: cp .env.example .env)"
fi

echo ""

# 6. Empfohlene System-Ressourcen
echo "6️⃣  System-Ressourcen prüfen..."
echo "-----------------------------"

# RAM-Check (Linux)
if [ -f /proc/meminfo ]; then
    TOTAL_RAM=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_GB=$((TOTAL_RAM / 1024 / 1024))

    if [ $TOTAL_RAM_GB -ge 6 ]; then
        echo -e "${GREEN}✓${NC} RAM: ${TOTAL_RAM_GB}GB (ausreichend)"
    else
        echo -e "${RED}✗${NC} RAM: ${TOTAL_RAM_GB}GB (min. 6GB empfohlen)"
        ((ERRORS++))
    fi
elif command -v sysctl &> /dev/null; then
    # macOS
    TOTAL_RAM_BYTES=$(sysctl -n hw.memsize)
    TOTAL_RAM_GB=$((TOTAL_RAM_BYTES / 1024 / 1024 / 1024))

    if [ $TOTAL_RAM_GB -ge 6 ]; then
        echo -e "${GREEN}✓${NC} RAM: ${TOTAL_RAM_GB}GB (ausreichend)"
    else
        echo -e "${YELLOW}⚠${NC}  RAM: ${TOTAL_RAM_GB}GB (min. 6GB empfohlen)"
    fi
else
    echo -e "${YELLOW}⚠${NC}  RAM-Check nicht möglich"
fi

# CPU-Check
if command -v nproc &> /dev/null; then
    CPUS=$(nproc)
    if [ $CPUS -ge 2 ]; then
        echo -e "${GREEN}✓${NC} CPUs: $CPUS (ausreichend)"
    else
        echo -e "${YELLOW}⚠${NC}  CPUs: $CPUS (min. 2 empfohlen)"
    fi
elif command -v sysctl &> /dev/null; then
    # macOS
    CPUS=$(sysctl -n hw.ncpu)
    if [ $CPUS -ge 2 ]; then
        echo -e "${GREEN}✓${NC} CPUs: $CPUS (ausreichend)"
    else
        echo -e "${YELLOW}⚠${NC}  CPUs: $CPUS (min. 2 empfohlen)"
    fi
else
    echo -e "${YELLOW}⚠${NC}  CPU-Check nicht möglich"
fi

echo ""

# 7. Zusammenfassung
echo "======================================"
echo "📊 Zusammenfassung"
echo "======================================"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Alle Checks bestanden!${NC}"
    echo ""
    echo "Nächste Schritte:"
    echo "  1. .env-Datei erstellen:  cp .env.example .env"
    echo "  2. Services starten:      make up"
    echo "  3. Browser öffnen:        http://localhost:8501"
    echo ""
    exit 0
else
    echo -e "${RED}❌ $ERRORS Fehler gefunden${NC}"
    echo ""
    echo "Bitte behebe die Fehler vor dem Start."
    echo ""
    exit 1
fi
