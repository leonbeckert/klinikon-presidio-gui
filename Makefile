# Klinikon Pseudonymisierer - Makefile
# Vereinfachte Kommandos für Entwicklung und Deployment

.PHONY: help build up down restart logs clean test health

# Default target
help:
	@echo "Klinikon Pseudonymisierer - Verfügbare Kommandos:"
	@echo ""
	@echo "  make build    - Docker-Images bauen"
	@echo "  make up       - Services starten"
	@echo "  make down     - Services stoppen"
	@echo "  make restart  - Services neustarten"
	@echo "  make logs     - Logs anzeigen (live)"
	@echo "  make health   - Health-Status prüfen"
	@echo "  make test     - API-Tests durchführen"
	@echo "  make clean    - Container und Images löschen"
	@echo ""

# Docker-Images bauen
build:
	@echo "🔨 Baue Docker-Images..."
	docker compose build --no-cache

# Services starten
up:
	@echo "🚀 Starte Services..."
	docker compose up -d
	@echo "✅ Services gestartet!"
	@echo "   UI:         http://localhost:8501"
	@echo "   Analyzer:   http://localhost:5002"
	@echo "   Anonymizer: http://localhost:5001"

# Services stoppen
down:
	@echo "🛑 Stoppe Services..."
	docker compose down

# Services neustarten
restart:
	@echo "🔄 Starte Services neu..."
	docker compose restart

# Logs anzeigen
logs:
	@echo "📋 Zeige Logs (Ctrl+C zum Beenden)..."
	docker compose logs -f

# Health-Check
health:
	@echo "🏥 Prüfe Service-Status..."
	@echo ""
	@echo "Analyzer:"
	@curl -s http://localhost:5002/health && echo "✅ OK" || echo "❌ Fehler"
	@echo ""
	@echo "Anonymizer:"
	@curl -s http://localhost:5001/health && echo "✅ OK" || echo "❌ Fehler"
	@echo ""

# API-Tests
test:
	@echo "🧪 Führe API-Tests durch..."
	@echo ""
	@echo "Test 1: Analyzer mit deutschem Text"
	@curl -s -X POST http://localhost:5002/analyze \
		-H "Content-Type: application/json" \
		-d '{"text": "Max Mustermann, KVNR M123456789", "language": "de"}' | jq .
	@echo ""
	@echo "✅ Test abgeschlossen"

# Cleanup
clean:
	@echo "🧹 Räume auf..."
	docker compose down -v
	docker system prune -f
	@echo "✅ Cleanup abgeschlossen"

# Quick-Start (Build + Start)
quickstart: build up
	@echo ""
	@echo "⏳ Warte 60 Sekunden auf Service-Start..."
	@sleep 60
	@make health
