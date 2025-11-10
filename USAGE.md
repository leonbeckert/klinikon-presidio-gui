# Presidio API Usage Guide

## Authentication

All API endpoints require HTTP Basic Authentication:
- **Username:** `presidio`
- **Password:** `SecurePass123`

## Making Requests

### From Command Line (curl)

```bash
# Health check
curl -u presidio:SecurePass123 https://analyzer.presidio.klinikon.com/health

# Analyze text
curl -u presidio:SecurePass123 -X POST \
  https://analyzer.presidio.klinikon.com/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mein Name ist Max Mustermann und ich wohne in Berlin.",
    "language": "de"
  }'

# Anonymize text
curl -u presidio:SecurePass123 -X POST \
  https://anonymizer.presidio.klinikon.com/anonymize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mein Name ist Max Mustermann",
    "anonymizers": {
      "DEFAULT": {"type": "replace", "new_value": "ANONYMIZED"}
    },
    "analyzer_results": [
      {"start": 13, "end": 27, "entity_type": "PERSON", "score": 0.85}
    ]
  }'
```

### From Python

```python
import requests
from requests.auth import HTTPBasicAuth

# Configure auth
auth = HTTPBasicAuth('presidio', 'SecurePass123')

# Analyze
response = requests.post(
    'https://analyzer.presidio.klinikon.com/analyze',
    auth=auth,
    json={
        "text": "Mein Name ist Max Mustermann",
        "language": "de"
    }
)
print(response.json())

# Anonymize
response = requests.post(
    'https://anonymizer.presidio.klinikon.com/anonymize',
    auth=auth,
    json={
        "text": "Mein Name ist Max Mustermann",
        "anonymizers": {
            "DEFAULT": {"type": "replace", "new_value": "ANONYMIZED"}
        },
        "analyzer_results": [
            {"start": 13, "end": 27, "entity_type": "PERSON", "score": 0.85}
        ]
    }
)
print(response.json())
```

### From JavaScript/Node.js

```javascript
const axios = require('axios');

const auth = {
  username: 'presidio',
  password: 'SecurePass123'
};

// Analyze
const analyzeResponse = await axios.post(
  'https://analyzer.presidio.klinikon.com/analyze',
  {
    text: "Mein Name ist Max Mustermann",
    language: "de"
  },
  { auth }
);
console.log(analyzeResponse.data);

// Anonymize
const anonymizeResponse = await axios.post(
  'https://anonymizer.presidio.klinikon.com/anonymize',
  {
    text: "Mein Name ist Max Mustermann",
    anonymizers: {
      DEFAULT: { type: "replace", new_value: "ANONYMIZED" }
    },
    analyzer_results: [
      { start: 13, end: 27, entity_type: "PERSON", score: 0.85 }
    ]
  },
  { auth }
);
console.log(anonymizeResponse.data);
```

### From Docker Container (Environment Variables)

In your other Coolify project's docker-compose.yaml:

```yaml
services:
  your-app:
    image: your-image
    environment:
      - ANALYZER_URL=https://analyzer.presidio.klinikon.com
      - ANONYMIZER_URL=https://anonymizer.presidio.klinikon.com
      - PRESIDIO_USERNAME=presidio
      - PRESIDIO_PASSWORD=SecurePass123
    networks:
      - coolify

networks:
  coolify:
    external: true
```

Then in your application code, use these environment variables for authentication.

## Changing the Password

1. Generate new hash:
   ```bash
   htpasswd -nb presidio YourNewPassword
   ```

2. Copy the output and replace `$` with `$$`:
   ```
   presidio:$apr1$xyz$hash  →  presidio:$$apr1$$xyz$$hash
   ```

3. Update `PRESIDIO_BASIC_AUTH` in Coolify environment variables

4. Redeploy

## Security Notes

- Always use HTTPS in production (handled by Traefik)
- Store credentials securely (environment variables, secrets management)
- Change the default password before deploying to production
- Consider using API keys or OAuth for more granular access control
