#!/usr/bin/env python3
"""
Build a custom spaCy model with ADDRESS EntityRuler + OpenPLZ street gazetteer.
This script loads the base de_core_news_md model and adds:
1. Tokenization fix for "str." abbreviations
2. EntityRuler patterns for common German address formats
3. Street gazetteer component using OpenPLZ street names for validation
4. Conflict resolver component to handle entity precedence (ADDRESS > PER/LOC/ORG)

Pipeline order: merge_str_abbrev → [default] → entity_ruler → ner → street_gazetteer → address_conflict_resolver
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

# Add tokenizer exceptions for common abbreviations (cleaner & faster than retokenization)
# Phase 2: Added "St." for streets like "St.-Brevin-Ring"
from spacy.symbols import ORTH
print("[build] Adding tokenizer exceptions for common abbreviations...")
abbrevs = ["Str.", "str.", "Allee.", "allee.", "St.", "st."]
for abbrev in abbrevs:
    nlp.tokenizer.add_special_case(abbrev, [{ORTH: abbrev}])

# merge_str_abbrev component is now defined in street_gazetteer.py (imported above)
# Add it to pipeline FIRST (before any other components)
if "merge_str_abbrev" not in nlp.pipe_names:
    print("[build] Adding merge_str_abbrev component...")
    nlp.add_pipe("merge_str_abbrev", first=True)

# Insert EntityRuler before NER (patterns work better on raw text)
# The conflict resolver will handle precedence later
if "entity_ruler" in nlp.pipe_names:
    ruler = nlp.get_pipe("entity_ruler")
else:
    ruler = nlp.add_pipe(
        "entity_ruler",
        before="ner",
        config={"overwrite_ents": False},  # keep NER entities too
    )

# Expanded suffix list from failure analysis
# Common: straße, str, weg, allee, platz, gasse, ring, ufer, damm, hof, chaussee, pfad
# Phase 2: garten, plan, redder, wiesen, flur, feld, berg, see, tal, blick, park, kamp, kamps
# Phase 3: gang, twiete, twieten, terrasse, terrassen, siedlung, winkel, äcker, acker, wald,
#          brink, rain, grund, höhe, hang, anger, bruch, heide, holz
# Phase 4: brücke, bruecke, tor, gässchen, gaesschen, gässle, gaessle, steige, lohe, höfe, hoefe,
#          reihe, umgehung, ortsumfahrung, bahnbogen, hügel, huegel, wegle
# IMPORTANT: Allow optional period at end to match merged tokens like "Hauffstr." (not just "Hauffstr")
STREET_SUFFIX_REGEX = r".*(straße|str|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse|steig|stieg|markt|garten|plan|redder|wiesen|flur|feld|berg|see|tal|blick|park|kamp|kamps|gang|twiete|twieten|terrasse|terrassen|siedlung|winkel|äcker|acker|wald|brink|rain|grund|höhe|hang|anger|bruch|heide|holz|brücke|bruecke|tor|gässchen|gaesschen|gässle|gaessle|steige|lohe|höfe|hoefe|reihe|umgehung|ortsumfahrung|bahnbogen|hügel|huegel|wegle)\.?$"

# Token-level patterns for typical German street addresses
# Note: German compound street names are single tokens (e.g., "Hauptstraße")
# Keep house number patterns simple - gazetteer handles range extension
patterns = [
    # 1) Single-token street names: "Hauptstraße 42", "Musterweg 7b", "Bismarckstr. 12-14"
    {
        "label": "ADDRESS",
        "pattern": [
            {
                "IS_TITLE": True,
                "LOWER": {"REGEX": STREET_SUFFIX_REGEX}
            },
            {"IS_PUNCT": True, "OP": "?"},  # optional period after street name
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
        ],
    },
    # 1b) Two-token suffix street: "<Title>+ <Suffix> [.] <Number>"
    # CRITICAL FIX: This catches "Berliner Str. 31", "Carl-Hesselmann Weg 107", etc.
    # Without this, EntityRuler only matches if street+suffix are in ONE token.
    # Examples: "Berliner Str. 31", "Carl-Hesselmann Weg 107", "Papiermühle 58"
    {
        "label": "ADDRESS",
        "pattern": [
            {"IS_TITLE": True, "OP": "+"},   # one or more title tokens (allows "Carl-Hesselmann")
            {"LOWER": {"IN": [
                "straße", "str", "str.", "weg", "allee", "platz", "gasse", "ring",
                "ufer", "damm", "hof", "chaussee", "pfad", "strasse", "markt",
                "steig", "stieg", "garten", "plan", "redder", "wiesen", "flur",
                "feld", "berg", "see", "tal", "blick", "park", "kamp", "kamps"
            ]}},
            {"IS_PUNCT": True, "OP": "?"},   # optional extra dot etc.
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
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
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
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
                "LOWER": {"REGEX": STREET_SUFFIX_REGEX}
            },
            {"IS_PUNCT": True, "OP": "?"},  # optional period after street name
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
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
                "LOWER": {"REGEX": STREET_SUFFIX_REGEX}
            },

            {"IS_PUNCT": True, "OP": "?"},

            # House number (simple pattern - gazetteer extends ranges)
            {
                "TEXT": {
                    "REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"
                }
            },
        ],
    },
    # 5) Phase 2/3/4: Multi-hyphen streets with suffix token
    # Examples: "Bertha-von-Suttner-Str. 198c", "Hans-im-Glück-Weg 153", "Franz-von-Kobell-Str. 19"
    #           "Viktor-von-Scheffel-Str.", "Christoph-von-Schmid-Str."
    # Conservative pattern: requires suffix token to avoid over-matching person names
    # Phase 3: Expanded particles to include "im", "am", "zum", "zur" for cases like "Hans-im-Glück"
    # Phase 4: Added "zu", "ob", "bei" for broader coverage
    {
        "label": "ADDRESS",
        "pattern": [
            {"IS_TITLE": True},                          # e.g., Bertha, Hans, Franz, Viktor
            {"ORTH": "-", "OP": "+"},                    # one or more hyphens
            {"LOWER": {"IN": ["von", "vom", "der", "den", "dem", "und", "im", "am", "zum", "zur", "zu", "ob", "bei"]}, "OP": "?"},  # optional particle
            {"IS_TITLE": True, "OP": "+"},              # Suttner, Glück, Kobell, Scheffel
            {"ORTH": "-", "OP": "?"},                   # hyphen before suffix
            {"LOWER": {"REGEX": r"^(straße|str|weg|allee|platz|gasse|ring|ufer|damm|hof|chaussee|landstraße|pfad|strasse)$"}},
            {"IS_PUNCT": True, "OP": "?"},              # dot after Str
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
    # 2b) Phase 3: Prepositional street names WITHOUT canonical suffix
    # Examples: "Im Grünen Winkel 164", "Im Kessler 26", "Zum Bildstöckle 126"
    # Safety: mandatory house number + Title casing
    {
        "label": "ADDRESS",
        "pattern": [
            {"LOWER": {"IN": ["im", "am", "an", "auf", "unter", "vor", "hinter", "bei", "zum", "zur"]}},
            {"IS_TITLE": True, "OP": "+"},         # one or more Title tokens (e.g., Grünen Winkel / Kessler)
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
    # 2c) Phase 4: Prepositional with lowercase adjectives
    # Examples: "Im alten Garten 58", "In der großen Harras 157", "Am alten Sägewerk 64"
    # Allows 0-2 lowercase tokens (adjectives/determiners) between prep/article and Title
    {
        "label": "ADDRESS",
        "pattern": [
            {"LOWER": {"IN": ["im", "am", "an", "auf", "unter", "vor", "hinter", "bei", "zum", "zur", "zu", "in"]}},
            {"LOWER": {"IN": ["der", "den", "dem"]}, "OP": "?"},
            {"IS_LOWER": True, "OP": "{0,2}"},           # e.g., alten / großen / neuen
            {"IS_TITLE": True, "OP": "+"},
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
    # 2d) Phase 4: DDR-style and "X der/des Y" roads
    # Examples: "Str. der Einheit 185", "Platz der Freiheit 57", "Str. des Fortschritts 183"
    {
        "label": "ADDRESS",
        "pattern": [
            {"LOWER": {"IN": ["straße", "str.", "str", "platz", "weg"]}},
            {"LOWER": {"IN": ["der", "des"]}},
            {"IS_TITLE": True, "OP": "+"},
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
    # 2e) Phase 4: Low German dialect openers
    # Examples: "Op de Lichten 148", "An de Kerkhoff 178", "Up de Hee 28", "Achtern Knick 188"
    {
        "label": "ADDRESS",
        "pattern": [
            {"LOWER": {"IN": ["op", "an", "achtern", "up", "auf'n", "auf'm"]}},
            {"LOWER": "de", "OP": "?"},
            {"IS_TITLE": True, "OP": "+"},
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
    # 2f) Phase 4: Broader prepositional families
    # Examples: "Hinter den Höfen 71f", "Vor dem Delftor 36f", "Ob der Schwalbenhälde 193"
    #           "Zu den Eichen 169a", "Zwischen den Höfen 71", "Nach der Wipse 176e"
    {
        "label": "ADDRESS",
        "pattern": [
            {"LOWER": {"IN": ["vor", "bei", "hinter", "nach", "ob", "zu", "unter", "unterm", "zwischen"]}},
            {"LOWER": {"IN": ["der", "den", "dem", "die"]}, "OP": "?"},
            {"IS_TITLE": True, "OP": "+"},
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
    # 1c) Phase 3/4: Composite phrase pattern (Adjective + suffix + short PP + Number)
    # Examples: "südlicher Serviceweg am Mittellandkanal 36", "Weg am Silo 73"
    #           "Hinterm kleinen Kamp 51", "Strandübergang 12 Ahrenshoop 175"
    # Phase 4: Broadened PP set, allow lowercase adjectives in landmark phrase
    {
        "label": "ADDRESS",
        "pattern": [
            {"IS_LOWER": True, "OP": "?"},                          # optional adjective like "südlicher"
            {"IS_TITLE": True, "OP": "+"},                          # e.g., Serviceweg / Strandübergang
            {"LOWER": {"REGEX": STREET_SUFFIX_REGEX}, "OP": "?"},  # allow both with/without suffix
            {"IS_PUNCT": True, "OP": "?"},                          # optional hyphen/dot
            {"LOWER": {"IN": ["am", "an", "im", "in", "bei", "hinter", "vor", "hinterm"]}, "OP": "?"},  # short PP
            {"IS_LOWER": True, "OP": "{0,2}"},                      # kleinen / alten
            {"IS_TITLE": True, "OP": "*"},                          # Mittellandkanal / Ahrenshoop (allow multi-token)
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
    # 6) Phase 3: Conservative oddball token + Number (e.g., "X-2s 199")
    # Last resort: requires capital letter AND digit/hyphen, followed by house number
    {
        "label": "ADDRESS",
        "pattern": [
            {"TEXT": {"REGEX": r"^(?=.*[A-ZÄÖÜ])(?=.*[-0-9])[A-Za-zÄÖÜäöü0-9-]+$"}},
            {"TEXT": {"REGEX": r"^[0-9]+[a-zA-Z]?(?:[-/–—][0-9]+[a-zA-Z]?)?[.,;:!?]?$"}}
        ],
    },
]

ruler.add_patterns(patterns)


# Add street gazetteer component after NER
# EntityRuler runs before NER, NER runs on patterns+raw text, then gazetteer validates
# Writes to doc.spans["gaz_address"] instead of doc.ents
if "street_gazetteer" not in nlp.pipe_names:
    print("[build] Adding street_gazetteer component...")
    nlp.add_pipe("street_gazetteer", after="ner")
else:
    print("[build] street_gazetteer already present in pipeline.")

# Add conflict resolver component to handle entity precedence
# This component reads from doc.spans["gaz_address"] and writes final doc.ents
if "address_conflict_resolver" not in nlp.pipe_names:
    print("[build] Adding address_conflict_resolver component...")
    nlp.add_pipe("address_conflict_resolver", after="street_gazetteer")
else:
    print("[build] address_conflict_resolver already present in pipeline.")

# Phase 2: Add universal ADDRESS normalizer AFTER conflict resolver
# This ensures ALL ADDRESS entities (including EntityRuler-only detections) get:
# - Full number range extension (e.g., "12-14" instead of just "12")
# - Letter suffix capture (e.g., "144g" instead of "144")
# - Preposition trimming (e.g., "Lilienweg" instead of "in der Lilienweg")
if "address_span_normalizer" not in nlp.pipe_names:
    print("[build] Adding address_span_normalizer component...")
    nlp.add_pipe("address_span_normalizer", after="address_conflict_resolver")
else:
    print("[build] address_span_normalizer already present in pipeline.")


# Save the complete model with all components
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
nlp.to_disk(OUTPUT_DIR)
print(f"[build] Saved custom model to {OUTPUT_DIR}")
print(f"[build] Pipeline components: {nlp.pipe_names}")
