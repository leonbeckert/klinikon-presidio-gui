# /app/sitecustomize.py
"""
This module is auto-imported by Python on startup.

We import street_gazetteer here so that:
- the @Language.component decorators run
- spaCy registers all factories BEFORE any spacy.load() happens

Presidio analyzer then loads /app/models/de_with_address without knowing
anything about our custom components, and everything just works.
"""

import street_gazetteer  # noqa: F401

# Register merge_str_abbrev component
from spacy.language import Language

@Language.component("merge_str_abbrev")
def merge_str_abbrev(doc):
    """
    Merge 'str' + '.' into single token 'str.'
    This helps both EntityRuler patterns and gazetteer component.
    """
    with doc.retokenize() as retok:
        for i in range(1, len(doc)):
            if doc[i-1].lower_ == "str" and doc[i].text == ".":
                retok.merge(doc[i-1:i+1], attrs={"LEMMA": doc[i-1].lemma_ + "."})
    return doc
