# Presidio API Usage Guide

## Authentication

All API endpoints require HTTP Basic Authentication:
- **Username:** `presidio-extern`
- **Password:** (set during deployment)

## Making Requests

### From Command Line (curl)

```bash
# Health check (use -k to skip SSL verification if using self-signed certs)
curl -k -u presidio-extern:your-password https://analyzer.presidio.klinikon.com/health

# Analyze text
curl -k -u presidio-extern:your-password -X POST \
  https://analyzer.presidio.klinikon.com/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mein Name ist Max Mustermann und ich wohne in Berlin.",
    "language": "de"
  }'

# Anonymize text
curl -k -u presidio-extern:your-password -X POST \
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
auth = HTTPBasicAuth('presidio-extern', 'your-password')

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
  username: 'presidio-extern',
  password: 'your-password'
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
      - PRESIDIO_USERNAME=presidio-extern
      - PRESIDIO_PASSWORD=your-password
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
   htpasswd -nb presidio-extern YourNewPassword
   ```

2. Copy the output and replace `$` with `$$`:
   ```
   presidio-extern:$apr1$xyz$hash  →  presidio-extern:$$apr1$$xyz$$hash
   ```

3. Update the hash directly in `docker-compose.yaml` in the `traefik.http.middlewares.presidio-auth.basicauth.users` label

4. Commit and redeploy

## Security Notes

- Always use HTTPS in production (handled by Traefik)
- Store credentials securely (environment variables, secrets management)
- Change the default password before deploying to production
- Consider using API keys or OAuth for more granular access control
