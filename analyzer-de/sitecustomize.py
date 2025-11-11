# /app/sitecustomize.py
"""
This module is auto-imported by Python on startup.

We import street_gazetteer here so that:
- the @Language.component("street_gazetteer") decorator runs
- spaCy registers the factory BEFORE any spacy.load() happens

Presidio analyzer then loads /app/models/de_with_address without knowing
anything about our custom component, and everything just works.
"""

import street_gazetteer  # noqa: F401
