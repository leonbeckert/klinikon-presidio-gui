"""
Klinikon Pseudonymisierer - Pseudonymisierungs-Tool für Patientendaten
Streamlit Web-Interface für deutsche Kliniken
"""

import streamlit as st
import logging
import json
from typing import Dict, Any, List
from helpers import (
    analyze_text,
    anonymize_text,
    check_service_health,
    get_anonymizer_config,
    MEDICAL_ANONYMIZERS
)

# Logging
logger = logging.getLogger(__name__)

# Page-Konfiguration
st.set_page_config(
    page_title="Klinikon Pseudonymisierer - Patiententext-Pseudonymisierung",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS für bessere Lesbarkeit
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .entity-box {
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.5rem 0;
        background-color: #f0f2f6;
    }
    .success-box {
        padding: 1rem;
        border-radius: 5px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialisiere Session State für Persistenz"""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'anonymized_text' not in st.session_state:
        st.session_state.anonymized_text = None
    if 'input_text' not in st.session_state:
        st.session_state.input_text = ""


def render_sidebar():
    """Rendert Sidebar mit Einstellungen und Health-Status"""
    with st.sidebar:
        st.header("⚙️ Einstellungen")

        # Health-Check
        st.subheader("Service-Status")
        if st.button("Status prüfen"):
            with st.spinner("Prüfe Services..."):
                health = check_service_health()
                if health["analyzer"]:
                    st.success("✅ Analyzer aktiv")
                else:
                    st.error("❌ Analyzer nicht erreichbar")

                if health["anonymizer"]:
                    st.success("✅ Anonymizer aktiv")
                else:
                    st.error("❌ Anonymizer nicht erreichbar")

        st.divider()

        # Anonymisierungs-Strategie
        st.subheader("Anonymisierungs-Strategie")
        strategy = st.selectbox(
            "Methode wählen",
            options=[
                "Vollständig (Platzhalter)",
                "Teilweise (Maskierung)",
                "Konsistent (Hash)"
            ],
            help=(
                "**Vollständig (Platzhalter)**: Alle identifizierenden Angaben werden komplett durch Platzhalter "
                "ersetzt (z.B. `<PERSON>`, `<IBAN>`). Für Weitergabe nach außen, Publikationen. "
                "Kein Rückbezug möglich.\n\n"
                "**Teilweise (Maskierung)**: Teile sensibler Angaben bleiben zur Orientierung sichtbar "
                "(z.B. Max M******, 089 ****123). Für interne Qualitätssicherung.\n\n"
                "**Konsistent (Hash)**: Daten werden durch stabile Codes ersetzt (gleicher Patient ⇒ gleicher Code). "
                "Geeignet für Längsschnitt-Analysen. Hinweis: Keine echte Anonymisierung im DSGVO-Sinne."
            )
        )

        st.divider()

        # Erweiterte Optionen
        with st.expander("🔧 Erweiterte Optionen"):
            score_threshold = st.slider(
                "Min. Konfidenz-Score",
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.05,
                help="Nur Entitäten über diesem Score werden erkannt"
            )

            show_json = st.checkbox(
                "JSON-Ausgabe anzeigen",
                value=False,
                help="Zeigt technische Details im JSON-Format"
            )

        st.divider()

        # Info
        st.subheader("ℹ️ Erkannte Entitäten")
        st.markdown("""
        **Personen & Orte:**
        - `PERSON` - Namen
        - `LOCATION` - Orte, Städte
        - `ORGANIZATION` - Einrichtungen

        **Medizinische Daten:**
        - `DE_KVNR` - Krankenversichertennummer
        - `PATIENT_ID` - Patientennummer
        - `DATE_OF_BIRTH` - Geburtsdatum

        **Kontaktdaten:**
        - `DE_PHONE_NUMBER` - Telefon
        - `EMAIL_ADDRESS` - E-Mail
        - `DE_IBAN` - Bankverbindung
        - `DE_ZIP_CODE` - PLZ
        """)

        return strategy, score_threshold, show_json


def render_entity_table(entities: List[Dict[str, Any]]):
    """Rendert Tabelle mit erkannten Entitäten"""
    if not entities:
        st.info("Keine personenbezogenen Daten erkannt.")
        return

    # Gruppiere nach Entity-Typ
    entity_groups = {}
    for entity in entities:
        entity_type = entity.get("entity_type", "UNKNOWN")
        if entity_type not in entity_groups:
            entity_groups[entity_type] = []
        entity_groups[entity_type].append(entity)

    # Zeige gruppiert an
    for entity_type, items in sorted(entity_groups.items()):
        with st.expander(f"**{entity_type}** ({len(items)} gefunden)", expanded=True):
            for item in items:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    # Extrahiere Original-Text (falls verfügbar)
                    start = item.get("start", 0)
                    end = item.get("end", 0)
                    original = st.session_state.input_text[start:end] if start and end else "N/A"
                    st.markdown(f"**Text:** `{original}`")
                with col2:
                    score = item.get("score", 0)
                    st.markdown(f"**Score:** {score:.2f}")
                with col3:
                    st.markdown(f"**Pos:** {start}-{end}")


def main():
    """Hauptanwendung"""
    init_session_state()

    # Header
    st.markdown('<h1 class="main-header">🏥 Klinikon Presidio Pseudonymisierer</h1>', unsafe_allow_html=True)
    st.markdown(
        "**Pseudonymisierung von Patiententexten** nach DSGVO-Anforderungen. "
        "Erkennt und anonymisiert personenbezogene Daten in deutschen medizinischen Dokumenten."
    )

    # Sidebar
    strategy, score_threshold, show_json = render_sidebar()

    st.divider()

    # Hauptbereich: Eingabe
    st.subheader("📝 Eingabe: Patiententext")

    # Beispieltext-Button
    if st.button("📋 Beispieltext laden"):
        st.session_state.input_text = (
            "Patientenbericht vom 15.03.2024\n\n"
            "Patient: Max Mustermann, geboren am 12.05.1978\n"
            "Adresse: Hauptstraße 42, 10115 Berlin\n"
            "Kontakt: 030-12345678, max.mustermann@email.de\n"
            "KVNR: M987654321\n"
            "Patientennummer: PAT-1234567\n\n"
            "Anamnese: Der Patient klagt über chronische Rückenschmerzen. "
            "Behandlung in der Charité Berlin. "
            "Versichert bei der AOK Nordost.\n\n"
            "Überweisender Arzt: Dr. med. Anna Schmidt, Praxis am Alexanderplatz\n"
            "Telefon: 030-98765432\n"
            "IBAN: DE89370400440532013000"
        )

    # Text-Eingabefeld
    input_text = st.text_area(
        label="Text hier eingeben",
        value=st.session_state.input_text,
        height=300,
        placeholder="Geben Sie hier den zu pseudonymisierenden Text ein...",
        help="Patiententext mit personenbezogenen Daten"
    )
    st.session_state.input_text = input_text

    st.divider()

    # Aktionen
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        analyze_btn = st.button("🔍 Analysieren", type="primary", use_container_width=True)

    with col2:
        anonymize_btn = st.button("🔒 Anonymisieren", type="secondary", use_container_width=True)

    with col3:
        if st.button("🗑️ Löschen", use_container_width=True):
            st.session_state.input_text = ""
            st.session_state.analysis_results = None
            st.session_state.anonymized_text = None
            st.rerun()

    # Analyse
    if analyze_btn:
        if not input_text.strip():
            st.error("❌ Bitte geben Sie einen Text ein.")
        else:
            try:
                with st.spinner("🔍 Analysiere Text..."):
                    results = analyze_text(
                        text=input_text,
                        language="de",
                        score_threshold=score_threshold
                    )
                    st.session_state.analysis_results = results
                    st.success(f"✅ Analyse abgeschlossen: **{len(results)}** Entitäten erkannt")

            except Exception as e:
                st.error(f"❌ Fehler bei der Analyse: {str(e)}")
                logger.error(f"Analyse fehlgeschlagen: {e}", exc_info=True)

    # Anonymisierung
    if anonymize_btn:
        if not input_text.strip():
            st.error("❌ Bitte geben Sie einen Text ein.")
        elif not st.session_state.analysis_results:
            st.warning("⚠️ Bitte führen Sie zuerst eine Analyse durch.")
        else:
            try:
                with st.spinner("🔒 Anonymisiere Text..."):
                    anonymizers = get_anonymizer_config(strategy)
                    result = anonymize_text(
                        text=input_text,
                        analyzer_results=st.session_state.analysis_results,
                        anonymizers=anonymizers
                    )
                    st.session_state.anonymized_text = result
                    st.success("✅ Anonymisierung erfolgreich")

            except Exception as e:
                st.error(f"❌ Fehler bei der Anonymisierung: {str(e)}")
                logger.error(f"Anonymisierung fehlgeschlagen: {e}", exc_info=True)

    st.divider()

    # Ergebnisse anzeigen
    if st.session_state.analysis_results:
        st.subheader("📊 Erkannte Entitäten")
        render_entity_table(st.session_state.analysis_results)

        if show_json:
            with st.expander("🔧 JSON-Details (Entwickler)"):
                st.json(st.session_state.analysis_results)

    if st.session_state.anonymized_text:
        st.divider()
        st.subheader("✅ Anonymisierter Text")

        anonymized = st.session_state.anonymized_text.get("text", "")

        # Ausgabe-Box
        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.text_area(
            label="Pseudonymisiertes Ergebnis",
            value=anonymized,
            height=300,
            help="Kopieren Sie diesen Text für die weitere Verarbeitung"
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # Download-Button
        st.download_button(
            label="📥 Als Textdatei herunterladen",
            data=anonymized,
            file_name="pseudonymisiert.txt",
            mime="text/plain"
        )

        if show_json:
            with st.expander("🔧 JSON-Details (Entwickler)"):
                st.json(st.session_state.anonymized_text)

    # Footer
    st.divider()
    st.markdown(
        "<small>🏥 **Klinikon Pseudonymisierer** | "
        "Powered by Microsoft Presidio | "
        "Keine Daten werden gespeichert</small>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
