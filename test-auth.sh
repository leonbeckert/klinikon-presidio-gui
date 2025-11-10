#!/bin/bash
# Test script for authenticated Presidio API endpoints
# Note: Uses -k flag to skip SSL cert verification (remove in production with valid certs)

# Get credentials from .env file
USERNAME="presidio-extern"
PASSWORD="your-password-here"  # Replace with actual password

echo "Testing Analyzer API with auth..."
curl -k -u ${USERNAME}:${PASSWORD} https://analyzer.presidio.klinikon.com/health

echo -e "\n\nTesting Analyzer API without auth (should fail with 401)..."
curl -k https://analyzer.presidio.klinikon.com/health

echo -e "\n\nTesting Anonymizer API with auth..."
curl -k -u ${USERNAME}:${PASSWORD} https://anonymizer.presidio.klinikon.com/health

echo -e "\n\nTesting Anonymizer API without auth (should fail with 401)..."
curl -k https://anonymizer.presidio.klinikon.com/health

echo -e "\n\nTesting Analyzer analyze endpoint with auth..."
curl -k -u ${USERNAME}:${PASSWORD} -X POST \
  https://analyzer.presidio.klinikon.com/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mein Name ist Max Mustermann und ich wohne in Berlin.",
    "language": "de"
  }'
