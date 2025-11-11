FROM python:3.11-slim

WORKDIR /app

# Installiere system dependencies (für Health-Checks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Kopiere requirements und installiere Python-Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere Anwendungs-Code
COPY helpers.py app.py ./

# Kopiere Streamlit-Konfiguration
COPY .streamlit /app/.streamlit

# Erstelle Verzeichnis für Logs (optional)
RUN mkdir -p /app/logs

EXPOSE 8501

# Health-Check (Streamlit läuft auf Port 8501)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --spider -q http://localhost:8501/_stcore/health || exit 1

# Starte Streamlit
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
