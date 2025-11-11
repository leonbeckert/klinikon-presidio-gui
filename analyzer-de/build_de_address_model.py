#!/usr/bin/env python3
"""
Build a custom spaCy model with ADDRESS EntityRuler + OpenPLZ street gazetteer.
This script loads the base de_core_news_md model and adds:
1. EntityRuler patterns for common German address formats
2. Street gazetteer component using OpenPLZ street names for validation
"""
import spacy
from pathlib import Path

# Importing street_gazetteer ensures the component is registered
import street_gazetteer  # noqa: F401

BASE_MODEL = "de_core_news_md"
OUTPUT_DIR = "/app/models/de_with_address"

print("[build] Loading base model:", BASE_MODEL)
nlp = spacy.load(BASE_MODEL)

# Insert EntityRuler before NER so we keep spaCy NER + our rules
if "entity_ruler" in nlp.pipe_names:
    ruler = nlp.get_pipe("entity_ruler")
else:
    ruler = nlp.add_pipe(
        "entity_ruler",
        before="ner",
        config={"overwrite_ents": False},  # keep PERSON/ORG/LOC intact
    )

# Token-level patterns for typical German street addresses
# Note: German compound street names are single tokens (e.g., "Hauptstraße")
patterns = [
    # 1) Single-token street names: "Hauptstraße 42", "Musterweg 7b", "Bismarckstr. 12-14"
    {
        "label": "ADDRESS",
        "pattern": [
            {
                "IS_TITLE": True,
                "LOWER": {
                    "REGEX": r".*(straße|str\.|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse)$"
                }
            },
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
        ],
    },
    # 2) Multi-word addresses: "Am Bahnhof 3", "An der Kirche 12b"
    {
        "label": "ADDRESS",
        "pattern": [
            {"LOWER": {"IN": ["am", "an", "auf", "in"]}},
            {"LOWER": {"IN": ["der", "den", "dem"]}, "OP": "?"},
            {"IS_TITLE": True, "OP": "+"},
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
        ],
    },
    # 3) Full address with optional ZIP + city: "Hauptstraße 42, 10115 Berlin"
    {
        "label": "ADDRESS",
        "pattern": [
            {
                "IS_TITLE": True,
                "LOWER": {
                    "REGEX": r".*(straße|str\.|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse)$"
                }
            },
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
            {"IS_PUNCT": True, "OP": "?"},  # comma or other punctuation
            {"TEXT": {"REGEX": r"^[0-9]{5}$"}},  # ZIP
            {"IS_TITLE": True, "OP": "+"},      # City
        ],
    },
]

ruler.add_patterns(patterns)


# Add street gazetteer component at the end
if "street_gazetteer" not in nlp.pipe_names:
    print("[build] Adding street_gazetteer component...")
    nlp.add_pipe("street_gazetteer", last=True)
else:
    print("[build] street_gazetteer already present in pipeline.")


# Save the complete model with EntityRuler + Street Gazetteer
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
nlp.to_disk(OUTPUT_DIR)
print(f"[build] Saved custom model to {OUTPUT_DIR}")
print(f"[build] Pipeline components: {nlp.pipe_names}")
