# OpenPLZ Street Gazetteer Integration

## Current Status

The OpenPLZ street list (`data/streets.csv`) is available in the repository with **1.2M German street names** from [openplzapi.data](https://github.com/openpotato/openplzapi.data).

**Current Implementation**: EntityRuler patterns provide robust address recognition without the gazetteer.

**Why not integrated yet?**: spaCy 3.x component serialization requires custom components to be registered at model load time, which complicates Presidio integration.

## What Works Now

The current EntityRuler-based ADDRESS recognition handles:
- ✅ Single-token streets: `Hauptstraße 42`, `Musterweg 7b`
- ✅ Multi-word addresses: `Am Bahnhof 3`, `An der Kirche 12b`
- ✅ Full addresses with ZIP: `Hauptstraße 42, 10115 Berlin`
- ✅ Trailing punctuation: `Bismarckstraße 100.`

## Future Enhancement: Gazetteer Integration

### Approach 1: Custom Presidio Recognizer (Recommended)

Create a dedicated Presidio recognizer that uses the OpenPLZ data:

```python
# analyzer-de/custom_recognizers/de_street_recognizer.py
from presidio_analyzer import Pattern, PatternRecognizer
import csv

class DeStreetRecognizer(PatternRecognizer):
    def __init__(self):
        self.street_names = self._load_streets()
        patterns = [Pattern("street_with_number", r"\b[A-Z][\w\s]+\d+[a-z]?\b", 0.5)]
        super().__init__(
            supported_entity="DE_STREET_ADDRESS",
            patterns=patterns,
            supported_language="de"
        )

    def _load_streets(self):
        # Load and normalize street names from CSV
        pass

    def analyze(self, text, entities, nlp_artifacts=None):
        results = super().analyze(text, entities, nlp_artifacts)
        # Validate against street_names set
        return [r for r in results if self._is_valid_street(r.entity_type)]
```

Then register in `recognizers-de.yml`:

```yaml
recognizers:
  - name: DeStreetRecognizer
    type: custom
    supported_language: de
    supported_entity: DE_STREET_ADDRESS
```

### Approach 2: Runtime spaCy Component Registration

Modify Presidio analyzer startup to register the component:

```python
# In Presidio analyzer startup hook
from spacy.language import Language
from spacy.tokens import Span

@Language.component("street_gazetteer")
def street_gazetteer(doc):
    # Implementation from build_de_address_model.py
    pass

# Register before loading model
nlp = spacy.load("/app/models/de_with_address")
```

### Approach 3: PhraseMatcher (High Performance)

Use spaCy's PhraseMatcher for O(1) lookups:

```python
from spacy.matcher import PhraseMatcher

matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
patterns = [nlp.make_doc(street) for street in STREET_NAMES]
matcher.add("STREETS", patterns)
```

## Data Format

**File**: `analyzer-de/data/streets.csv`
**Size**: 53MB, ~1.2M entries
**Columns**: `Name,PostalCode,Locality,RegionalKey,Borough,Suburb`

**Sample**:
```csv
Name,PostalCode,Locality,RegionalKey,Borough,Suburb
"Ütterlingser Str.",58791,Werdohl,05962060,,
"Hauptstraße",10115,Berlin,11000000,,
```

## Normalization Function

Already implemented in `build_de_address_model.py`:

```python
def normalize_street_name(name: str) -> str:
    """Normalize for comparison: strip quotes, unify Str./Straße, lowercase"""
    # Handles: "Str." → "straße", removes quotes, NFC normalize
```

## License

OpenPLZ data is under **ODbL-1.0**. For internal hospital/SaaS usage (detection only, not republishing), this is typically acceptable. See [LICENSE](https://github.com/openpotato/openplzapi.data/blob/main/LICENSE).

## Testing

To test gazetteer integration locally:

```python
from build_de_address_model import load_street_names, normalize_street_name

streets = load_street_names("data/streets.csv")
print(f"Loaded {len(streets):,} streets")

# Test normalization
assert normalize_street_name("Ütterlingser Str.") == "ütterlingser straße"
```

## Implementation Timeline

- **Phase 1** (Current): EntityRuler patterns ✅
- **Phase 2** (Future): Custom Presidio recognizer with gazetteer validation
- **Phase 3** (Optional): ZIP code + locality validation for higher confidence scores

## References

- [OpenPLZ API Data](https://github.com/openpotato/openplzapi.data)
- [Presidio Custom Recognizers](https://microsoft.github.io/presidio/analyzer/adding_recognizers/)
- [spaCy Custom Components](https://spacy.io/usage/processing-pipelines#custom-components)
