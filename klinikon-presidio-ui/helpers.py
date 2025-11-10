"""
Hilfs-Funktionen für Klinikon Pseudonymisierer
Kommunikation mit Analyzer und Anonymizer APIs
"""

import os
import logging
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Logging-Konfiguration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API-Endpunkte aus Umgebungsvariablen
ANALYZER_API = os.environ.get("ANALYZER_API", "http://presidio-analyzer:3000")
ANONYMIZER_API = os.environ.get("ANONYMIZER_API", "http://presidio-anonymizer:3000")

# Retry-Strategie für robuste API-Calls
def get_session_with_retry() -> requests.Session:
    """Erstellt Session mit automatischem Retry bei Netzwerkfehlern"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def analyze_text(
    text: str,
    language: str = "de",
    entities: Optional[List[str]] = None,
    score_threshold: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Analysiert Text mit Presidio Analyzer (deutsche medizinische Entitäten).

    Args:
        text: Zu analysierender Text
        language: Sprache (Standard: "de")
        entities: Liste spezifischer Entitäten oder None für alle
        score_threshold: Min. Konfidenz-Score (0.0 - 1.0)

    Returns:
        Liste der erkannten Entitäten mit Metadaten

    Raises:
        requests.exceptions.RequestException: Bei API-Fehlern
    """
    payload = {
        "text": text,
        "language": language,
        "score_threshold": score_threshold
    }

    if entities:
        payload["entities"] = entities

    logger.info(f"Analysiere Text (Länge: {len(text)} Zeichen)")

    try:
        session = get_session_with_retry()
        response = session.post(
            f"{ANALYZER_API}/analyze",
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        results = response.json()
        logger.info(f"Analyse erfolgreich: {len(results)} Entitäten gefunden")
        return results

    except requests.exceptions.Timeout:
        logger.error("Timeout beim Analyzer-API Call")
        raise Exception("Analyzer-Service antwortet nicht (Timeout)")
    except requests.exceptions.ConnectionError:
        logger.error(f"Verbindungsfehler zu Analyzer: {ANALYZER_API}")
        raise Exception("Analyzer-Service nicht erreichbar")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP-Fehler vom Analyzer: {e.response.status_code}")
        raise Exception(f"Analyzer-Fehler: {e.response.text}")
    except Exception as e:
        logger.error(f"Unerwarteter Fehler bei Analyse: {str(e)}")
        raise


def anonymize_text(
    text: str,
    analyzer_results: List[Dict[str, Any]],
    anonymizers: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Anonymisiert Text basierend auf Analyzer-Ergebnissen.

    Args:
        text: Original-Text
        analyzer_results: Ergebnisse von analyze_text()
        anonymizers: Custom Anonymizers pro Entity-Typ

    Returns:
        Dict mit "text" (anonymisiert) und "items" (Details)

    Raises:
        requests.exceptions.RequestException: Bei API-Fehlern
    """
    payload = {
        "text": text,
        "analyzer_results": analyzer_results
    }

    if anonymizers:
        payload["anonymizers"] = anonymizers

    logger.info(f"Anonymisiere Text mit {len(analyzer_results)} Entitäten")

    try:
        session = get_session_with_retry()
        response = session.post(
            f"{ANONYMIZER_API}/anonymize",
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        result = response.json()
        logger.info("Anonymisierung erfolgreich")
        return result

    except requests.exceptions.Timeout:
        logger.error("Timeout beim Anonymizer-API Call")
        raise Exception("Anonymizer-Service antwortet nicht (Timeout)")
    except requests.exceptions.ConnectionError:
        logger.error(f"Verbindungsfehler zu Anonymizer: {ANONYMIZER_API}")
        raise Exception("Anonymizer-Service nicht erreichbar")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP-Fehler vom Anonymizer: {e.response.status_code}")
        raise Exception(f"Anonymizer-Fehler: {e.response.text}")
    except Exception as e:
        logger.error(f"Unerwarteter Fehler bei Anonymisierung: {str(e)}")
        raise


def check_service_health() -> Dict[str, bool]:
    """
    Prüft Health-Status der Presidio-Services.

    Returns:
        Dict mit Status für analyzer und anonymizer
    """
    health = {"analyzer": False, "anonymizer": False}

    try:
        resp = requests.get(f"{ANALYZER_API}/health", timeout=5)
        health["analyzer"] = resp.status_code == 200
    except Exception as e:
        logger.warning(f"Analyzer Health-Check fehlgeschlagen: {e}")

    try:
        resp = requests.get(f"{ANONYMIZER_API}/health", timeout=5)
        health["anonymizer"] = resp.status_code == 200
    except Exception as e:
        logger.warning(f"Anonymizer Health-Check fehlgeschlagen: {e}")

    return health


# Vordefinierte Anonymisierungs-Strategien für medizinischen Kontext
MEDICAL_ANONYMIZERS = {
    "Vollständig (Platzhalter)": {
        "DEFAULT": {"type": "replace", "new_value": "<ENTFERNT>"},
        "PERSON": {"type": "replace", "new_value": "<PATIENT>"},
        "LOCATION": {"type": "replace", "new_value": "<ORT>"},
        "ORGANIZATION": {"type": "replace", "new_value": "<EINRICHTUNG>"},
        "DE_KVNR": {"type": "replace", "new_value": "<KVNR>"},
        "PATIENT_ID": {"type": "replace", "new_value": "<PID>"},
        "DE_PHONE_NUMBER": {"type": "replace", "new_value": "<TELEFON>"},
        "EMAIL_ADDRESS": {"type": "replace", "new_value": "<EMAIL>"},
        "DE_IBAN": {"type": "replace", "new_value": "<IBAN>"},
        "DATE_OF_BIRTH": {"type": "replace", "new_value": "<GEBURTSDATUM>"},
    },
    "Teilweise (Maskierung)": {
        "DEFAULT": {"type": "mask", "masking_char": "X", "chars_to_mask": 8, "from_end": False},
        "PERSON": {"type": "mask", "masking_char": "*", "chars_to_mask": 6, "from_end": False},
        "DE_KVNR": {"type": "mask", "masking_char": "X", "chars_to_mask": 7, "from_end": True},
        "PATIENT_ID": {"type": "mask", "masking_char": "X", "chars_to_mask": 5, "from_end": True},
        "DE_PHONE_NUMBER": {"type": "mask", "masking_char": "•", "chars_to_mask": 6, "from_end": True},
        "EMAIL_ADDRESS": {"type": "mask", "masking_char": "*", "chars_to_mask": 5, "from_end": False},
        "DE_IBAN": {"type": "mask", "masking_char": "X", "chars_to_mask": 12, "from_end": True},
    },
    "Konsistent (Hash)": {
        "DEFAULT": {"type": "hash", "hash_type": "sha256"},
        "PERSON": {"type": "hash", "hash_type": "md5"},
        "DE_KVNR": {"type": "hash", "hash_type": "sha256"},
        "PATIENT_ID": {"type": "hash", "hash_type": "sha256"},
    }
}


def get_anonymizer_config(strategy: str = "Vollständig (Platzhalter)") -> Dict[str, Dict[str, Any]]:
    """
    Gibt vordefinierte Anonymisierungs-Konfiguration zurück.

    Args:
        strategy: "Vollständig (Platzhalter)", "Teilweise (Maskierung)", oder "Konsistent (Hash)"

    Returns:
        Anonymizer-Konfiguration für anonymize_text()
    """
    return MEDICAL_ANONYMIZERS.get(strategy, MEDICAL_ANONYMIZERS["Vollständig (Platzhalter)"])
