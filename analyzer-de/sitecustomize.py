# /app/sitecustomize.py
"""
This module is auto-imported by Python on startup.

We import street_gazetteer here so that:
- the @Language.component decorators run
- spaCy registers all factories BEFORE any spacy.load() happens

Presidio analyzer then loads /app/models/de_with_address without knowing
anything about our custom components, and everything just works.

IMPORTANT: The merge_str_abbrev component is now ONLY defined in street_gazetteer.py
as a factory. DO NOT register it here to avoid [E004] conflicts.
"""

import street_gazetteer  # noqa: F401

# Optional: Run self-test on startup if environment variable is set
import os
if os.environ.get("RUN_ADDRESS_SELFTEST") == "true":
    import sys
    try:
        import spacy
        nlp = spacy.load("/app/models/de_with_address")
        street_gazetteer.selftest_address_pipeline(nlp)
    except Exception as e:
        print(f"[selftest] WARNING: Could not run self-test: {e}", file=sys.stderr)
