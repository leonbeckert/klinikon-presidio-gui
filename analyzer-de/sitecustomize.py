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

# Self-test: Run on startup in production to fail-fast if ADDRESS pipeline breaks
# Set RUN_ADDRESS_SELFTEST=false to disable (e.g., for debugging)
import os
if os.environ.get("RUN_ADDRESS_SELFTEST", "true").lower() != "false":
    import sys
    try:
        import spacy
        nlp = spacy.load("/app/models/de_with_address")
        street_gazetteer.selftest_address_pipeline(nlp)
    except Exception as e:
        # FAIL FAST: Self-test failure means ADDRESS pipeline is broken
        print(f"[selftest] FATAL: ADDRESS pipeline self-test failed: {e}", file=sys.stderr)
        sys.exit(1)  # Container will restart, alerting ops team
