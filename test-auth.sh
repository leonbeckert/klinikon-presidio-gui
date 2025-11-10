#!/bin/bash
# Test script for authenticated Presidio API endpoints

echo "Testing Analyzer API with auth..."
curl -u presidio:SecurePass123 https://analyzer.presidio.klinikon.com/health

echo -e "\n\nTesting Analyzer API without auth (should fail)..."
curl https://analyzer.presidio.klinikon.com/health

echo -e "\n\nTesting Anonymizer API with auth..."
curl -u presidio:SecurePass123 https://anonymizer.presidio.klinikon.com/health

echo -e "\n\nTesting Anonymizer API without auth (should fail)..."
curl https://anonymizer.presidio.klinikon.com/health

echo -e "\n\nTesting Analyzer analyze endpoint with auth..."
curl -u presidio:SecurePass123 -X POST \
  https://analyzer.presidio.klinikon.com/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mein Name ist Max Mustermann und ich wohne in Berlin.",
    "language": "de"
  }'
