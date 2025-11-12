#!/usr/bin/env python3
"""
Build a custom spaCy model with ADDRESS EntityRuler + OpenPLZ street gazetteer.
This script loads the base de_core_news_md model and adds:
1. Tokenization fix for "str." abbreviations
2. EntityRuler patterns for common German address formats
3. Street gazetteer component using OpenPLZ street names for validation
"""
import spacy
from spacy.language import Language
from pathlib import Path

# Importing street_gazetteer ensures the component is registered
import street_gazetteer  # noqa: F401

BASE_MODEL = "de_core_news_md"
OUTPUT_DIR = "/app/models/de_with_address"

print("[build] Loading base model:", BASE_MODEL)
nlp = spacy.load(BASE_MODEL)

# Add tokenization fix for "str." abbreviation (merge "str" + "." into single token)
@Language.component("merge_str_abbrev")
def merge_str_abbrev(doc):
    """
    Merge 'str' + '.' into single token 'str.'
    This helps both EntityRuler patterns and gazetteer component.

    Example: "Bahnhofstr" "." → "Bahnhofstr."
    """
    with doc.retokenize() as retok:
        for i in range(1, len(doc)):
            if doc[i-1].lower_ == "str" and doc[i].text == ".":
                retok.merge(doc[i-1:i+1], attrs={"LEMMA": doc[i-1].lemma_ + "."})
    return doc

# Add to pipeline FIRST (before any other components)
if "merge_str_abbrev" not in nlp.pipe_names:
    print("[build] Adding merge_str_abbrev component...")
    nlp.add_pipe("merge_str_abbrev", first=True)

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
# Keep house number patterns simple - gazetteer handles range extension
patterns = [
    # 1) Single-token street names: "Hauptstraße 42", "Musterweg 7b", "Bismarckstr. 12-14"
    # Note: spaCy tokenizes "Str." as "Str" + ".", so we match "str" without period
    {
        "label": "ADDRESS",
        "pattern": [
            {
                "IS_TITLE": True,
                "LOWER": {
                    "REGEX": r".*(straße|str|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse|steig|stieg|markt)$"
                }
            },
            {"IS_PUNCT": True, "OP": "?"},  # optional period after street name
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
                    "REGEX": r".*(straße|str|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse|steig|stieg|markt)$"
                }
            },
            {"IS_PUNCT": True, "OP": "?"},  # optional period after street name
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
    # 4) P2a: Adjective/preposition-led streets WITH required suffix
    # Examples: "Unter den Eichen 64", "Zum Krückeberg 16", "Alte Landstraße 134"
    {
        "label": "ADDRESS",
        "pattern": [
            # Conservative opener set (most common prepositions + adjectives)
            {"LOWER": {"IN": ["unter", "zum", "zur", "alte", "alter", "neue", "neuer"]}},
            {"LOWER": {"IN": ["den", "der", "dem"]}, "OP": "?"},

            # Street name: one or more Title tokens ending with required suffix
            {"IS_TITLE": True, "OP": "+"},
            {
                "LOWER": {
                    "REGEX": r"(straße|str|strasse|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|steig|stieg|markt)$"
                }
            },

            {"IS_PUNCT": True, "OP": "?"},

            # House number (simple pattern - gazetteer extends ranges)
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
        ],
    },
]

ruler.add_patterns(patterns)


# Add street gazetteer component after entity_ruler but before NER
# This ensures ADDRESS entities are claimed early and filter_spans preserves them
if "street_gazetteer" not in nlp.pipe_names:
    print("[build] Adding street_gazetteer component...")
    nlp.add_pipe("street_gazetteer", after="entity_ruler")
else:
    print("[build] street_gazetteer already present in pipeline.")


# Save the complete model with EntityRuler + Street Gazetteer
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
nlp.to_disk(OUTPUT_DIR)
print(f"[build] Saved custom model to {OUTPUT_DIR}")
print(f"[build] Pipeline components: {nlp.pipe_names}")
