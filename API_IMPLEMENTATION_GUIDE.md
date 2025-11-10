# API Implementation Guide for PresidioGUI

## Overview

This guide explains how to use the OpenAPI specification (`openapi.yaml`) to deploy and integrate the PresidioGUI text anonymization services in clinical environments.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Deployment Scenarios](#deployment-scenarios)
3. [Security Implementation](#security-implementation)
4. [Client Integration Examples](#client-integration-examples)
5. [Monitoring and Logging](#monitoring-and-logging)
6. [Compliance Considerations](#compliance-considerations)

## Architecture Overview

The PresidioGUI system consists of two core microservices that clients can access directly:

```
┌─────────────────┐     ┌──────────────────┐
│                 │────▶│                  │
│  Analyzer       │     │  Anonymizer      │
│  Service        │     │  Service         │
│  (Port 5002)    │◀────│  (Port 5001)     │
└─────────────────┘     └──────────────────┘
        ▲                        ▲
        │                        │
        └────────┬───────────────┘
                 │
         ┌───────▼───────┐
         │               │
         │  Client Apps  │
         │               │
         └───────────────┘
```

**Direct Access Model**: External services communicate directly with the Presidio services, eliminating unnecessary complexity while maintaining security through service-level authentication and network policies.

### Benefits of Direct Access

- **Simplicity**: No additional API gateway layer to configure and maintain
- **Performance**: Reduced latency by eliminating an extra network hop
- **Transparency**: Direct communication makes debugging and monitoring easier
- **Security**: Service-level authentication and network policies provide adequate protection for internal deployments
- **Flexibility**: Each service can be scaled and secured independently

### When to Consider an API Gateway

While this guide focuses on direct access, you may want to add an API gateway (nginx, Kong, etc.) if you need:
- Complex routing logic across many microservices
- Centralized authentication/authorization for external (internet-facing) access
- Advanced features like API versioning, transformation, or aggregation
- Public API exposure with sophisticated rate limiting and throttling

## Deployment Scenarios

### 1. Single Clinic Deployment (Internal Network)

```yaml
# docker-compose.override.yml for single clinic
version: '3.8'

services:
  presidio-analyzer:
    ports:
      - "5002:3000"  # Expose analyzer on port 5002
    environment:
      - MAX_TEXT_LENGTH=50000
      - DEFAULT_SCORE_THRESHOLD=0.7
      - LOG_LEVEL=INFO
      - ALLOWED_IPS=10.0.0.0/8,172.16.0.0/12  # Internal network only
    networks:
      - clinic-internal

  presidio-anonymizer:
    ports:
      - "5001:3000"  # Expose anonymizer on port 5001
    environment:
      - ENABLE_DEANONYMIZE=false  # Disable for security
      - LOG_LEVEL=INFO
      - ALLOWED_IPS=10.0.0.0/8,172.16.0.0/12
    networks:
      - clinic-internal

networks:
  clinic-internal:
    internal: true
```

### 2. Multi-Clinic Deployment (Shared Infrastructure)

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: presidio-analyzer
  namespace: presidio-medical
spec:
  replicas: 3  # Scale based on load
  selector:
    matchLabels:
      app: presidio-analyzer
  template:
    metadata:
      labels:
        app: presidio-analyzer
    spec:
      containers:
      - name: analyzer
        image: presidio-medical/analyzer-de:1.0.0
        ports:
        - containerPort: 3000
        env:
        - name: CLINIC_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.labels['clinic-id']
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
          requests:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: presidio-analyzer
  namespace: presidio-medical
spec:
  selector:
    app: presidio-analyzer
  ports:
  - port: 5002
    targetPort: 3000
  type: ClusterIP
```

## Security Implementation

### JWT Authentication Setup

```python
# auth_middleware.py
import jwt
from functools import wraps
from flask import request, jsonify

SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
ALLOWED_AUDIENCES = ['presidio-medical-api', 'clinic-services']

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401

        if not token:
            return jsonify({'error': 'Token missing'}), 401

        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=['RS256'],
                audience=ALLOWED_AUDIENCES
            )
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidAudienceError:
            return jsonify({'error': 'Invalid audience'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)

    return decorated_function
```

### Network Security Configuration

**Firewall Rules** (using iptables or firewalld):

```bash
# Allow internal network access to Presidio services
iptables -A INPUT -p tcp --dport 5002 -s 10.0.0.0/8 -j ACCEPT     # Analyzer
iptables -A INPUT -p tcp --dport 5001 -s 10.0.0.0/8 -j ACCEPT     # Anonymizer
iptables -A INPUT -p tcp --dport 5002 -s 172.16.0.0/12 -j ACCEPT  # Analyzer
iptables -A INPUT -p tcp --dport 5001 -s 172.16.0.0/12 -j ACCEPT  # Anonymizer

# Deny all other access
iptables -A INPUT -p tcp --dport 5002 -j DROP
iptables -A INPUT -p tcp --dport 5001 -j DROP
```

**TLS Termination** (optional, using stunnel for HTTPS):

```conf
# /etc/stunnel/presidio.conf
[analyzer]
accept = 5003
connect = 5002
cert = /etc/ssl/certs/presidio.pem
key = /etc/ssl/private/presidio.key
TLSv1.2 = yes
TLSv1.3 = yes

[anonymizer]
accept = 5004
connect = 5001
cert = /etc/ssl/certs/presidio.pem
key = /etc/ssl/private/presidio.key
TLSv1.2 = yes
TLSv1.3 = yes
```

**Rate Limiting** (at service level or using fail2ban):

```python
# Add to Flask services for rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per minute", "5000 per hour"],
    storage_uri="memory://"
)

@app.route('/analyze', methods=['POST'])
@limiter.limit("100 per minute")
def analyze():
    # ... implementation
```

## Client Integration Examples

### Python Client

```python
# presidio_client.py
import requests
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

@dataclass
class PresidioClient:
    """Client for PresidioGUI Medical Text Anonymization API"""

    base_url: str
    api_key: Optional[str] = None
    bearer_token: Optional[str] = None
    timeout: int = 30

    def __post_init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

        # Set authentication
        if self.bearer_token:
            self.session.headers['Authorization'] = f'Bearer {self.bearer_token}'
        elif self.api_key:
            self.session.headers['X-API-Key'] = self.api_key

        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def analyze_text(
        self,
        text: str,
        language: str = 'de',
        score_threshold: float = 0.0,
        entities: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Analyze text for sensitive entities

        Args:
            text: Text to analyze
            language: Language code (default: 'de')
            score_threshold: Minimum confidence score (0.0-1.0)
            entities: Optional list of entity types to detect

        Returns:
            List of detected entities
        """
        url = f"{self.base_url}/analyze"

        payload = {
            'text': text,
            'language': language,
            'score_threshold': score_threshold
        }

        if entities:
            payload['entities'] = entities

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            self.logger.error(f"Request timeout after {self.timeout}s")
            raise
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            raise

    def anonymize_text(
        self,
        text: str,
        analyzer_results: List[Dict],
        anonymizers: Optional[Dict] = None,
        anonymizer_url: Optional[str] = None
    ) -> Dict:
        """
        Anonymize text based on analyzer results

        Args:
            text: Original text to anonymize
            analyzer_results: Results from analyze_text()
            anonymizers: Optional custom anonymization config
            anonymizer_url: URL of anonymizer service (if different from analyzer)

        Returns:
            Anonymized text and transformation details
        """
        # Use separate anonymizer URL if provided
        base = anonymizer_url or self.base_url
        url = f"{base}/anonymize"

        payload = {
            'text': text,
            'analyzer_results': analyzer_results
        }

        if anonymizers:
            payload['anonymizers'] = anonymizers

        response = self.session.post(
            url,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def process_medical_text(
        self,
        text: str,
        strategy: str = 'streng'
    ) -> Dict:
        """
        Complete pipeline: analyze and anonymize medical text

        Args:
            text: Medical text to process
            strategy: Anonymization strategy ('streng', 'maskierung', 'hash')

        Returns:
            Dict with original text, entities found, and anonymized text
        """
        # Define anonymization strategies
        strategies = {
            'streng': {
                'PERSON': {'type': 'replace', 'new_value': '<PATIENT>'},
                'DE_KVNR': {'type': 'replace', 'new_value': '<KVNR>'},
                'DE_PHONE_NUMBER': {'type': 'replace', 'new_value': '<TELEFON>'},
                'EMAIL_ADDRESS': {'type': 'replace', 'new_value': '<EMAIL>'},
                'DATE_OF_BIRTH': {'type': 'replace', 'new_value': '<GEBURTSDATUM>'},
                'PATIENT_ID': {'type': 'replace', 'new_value': '<PATIENTEN-ID>'},
                'DE_IBAN': {'type': 'replace', 'new_value': '<IBAN>'},
                'LOCATION': {'type': 'replace', 'new_value': '<ORT>'},
                'ORGANIZATION': {'type': 'replace', 'new_value': '<ORGANISATION>'}
            },
            'maskierung': {
                'PERSON': {'type': 'mask', 'masking_char': '*', 'chars_to_mask': 100, 'from_end': False},
                'DE_KVNR': {'type': 'mask', 'masking_char': 'X', 'chars_to_mask': 7, 'from_end': True},
                'DE_PHONE_NUMBER': {'type': 'mask', 'masking_char': '•', 'chars_to_mask': 6, 'from_end': True}
            },
            'hash': {
                'PERSON': {'type': 'hash', 'hash_type': 'md5'},
                'DE_KVNR': {'type': 'hash', 'hash_type': 'sha256'},
                'PATIENT_ID': {'type': 'hash', 'hash_type': 'sha256'}
            }
        }

        # Analyze text
        entities = self.analyze_text(text, score_threshold=0.7)

        # Anonymize with selected strategy
        anonymized = self.anonymize_text(
            text,
            entities,
            strategies.get(strategy, strategies['streng'])
        )

        return {
            'original_text': text,
            'entities_found': entities,
            'anonymized_text': anonymized['text'],
            'transformations': anonymized['items'],
            'strategy_used': strategy
        }

# Example usage
if __name__ == '__main__':
    # Initialize client - point directly to analyzer service
    # For production, use separate clients for analyzer and anonymizer
    analyzer_client = PresidioClient(
        base_url='http://presidio-analyzer.local:5002',
        bearer_token='your-jwt-token-here'
    )

    anonymizer_client = PresidioClient(
        base_url='http://presidio-anonymizer.local:5001',
        bearer_token='your-jwt-token-here'
    )

    # Example medical text
    medical_text = """
    Patient: Max Mustermann, geb. 15.03.1985
    KVNR: A123456789
    Diagnose: Hypertonie
    Behandelnder Arzt: Dr. Schmidt
    Kontakt: max.mustermann@email.de, Tel: 030-12345678
    """

    # Analyze with analyzer service
    entities = analyzer_client.analyze_text(medical_text, score_threshold=0.7)

    # Anonymize with anonymizer service
    anonymized = anonymizer_client.anonymize_text(
        medical_text,
        entities,
        anonymizers={
            'PERSON': {'type': 'replace', 'new_value': '<PATIENT>'},
            'DE_KVNR': {'type': 'replace', 'new_value': '<KVNR>'}
        }
    )

    print("Anonymized text:")
    print(anonymized['text'])
    print(f"\nFound {len(entities)} entities")
```

### Java Client (Spring Boot)

```java
// PresidioClient.java
package com.clinic.presidio.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.HttpClientErrorException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;

import java.util.*;

@Service
@Slf4j
public class PresidioClient {

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    @Value("${presidio.analyzer.url}")
    private String analyzerUrl;

    @Value("${presidio.anonymizer.url}")
    private String anonymizerUrl;

    @Value("${presidio.api.bearer-token}")
    private String bearerToken;

    public PresidioClient(RestTemplate restTemplate, ObjectMapper objectMapper) {
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
    }

    @Data
    public static class AnalyzeRequest {
        private String text;
        private String language = "de";
        private Double scoreThreshold = 0.0;
        private List<String> entities;
    }

    @Data
    public static class AnalysisResult {
        private String entityType;
        private Integer start;
        private Integer end;
        private Double score;
        private String text;
    }

    @Data
    public static class AnonymizeRequest {
        private String text;
        private List<AnalysisResult> analyzerResults;
        private Map<String, AnonymizerConfig> anonymizers;
    }

    @Data
    public static class AnonymizerConfig {
        private String type;
        private String newValue;
        private String maskingChar;
        private Integer charsToMask;
        private Boolean fromEnd;
        private String hashType;
    }

    @Data
    public static class AnonymizeResponse {
        private String text;
        private List<Map<String, Object>> items;
    }

    /**
     * Analyze text for sensitive entities
     */
    public List<AnalysisResult> analyzeText(String text, Double scoreThreshold) {
        String url = analyzerUrl + "/analyze";

        AnalyzeRequest request = new AnalyzeRequest();
        request.setText(text);
        request.setScoreThreshold(scoreThreshold != null ? scoreThreshold : 0.0);

        HttpHeaders headers = createHeaders();
        HttpEntity<AnalyzeRequest> entity = new HttpEntity<>(request, headers);

        try {
            ResponseEntity<AnalysisResult[]> response = restTemplate.exchange(
                url,
                HttpMethod.POST,
                entity,
                AnalysisResult[].class
            );

            return Arrays.asList(response.getBody());

        } catch (HttpClientErrorException e) {
            log.error("Error analyzing text: {} - {}", e.getStatusCode(), e.getMessage());
            throw new RuntimeException("Failed to analyze text", e);
        }
    }

    /**
     * Anonymize text based on analyzer results
     */
    public AnonymizeResponse anonymizeText(
        String text,
        List<AnalysisResult> analyzerResults,
        Map<String, AnonymizerConfig> anonymizers
    ) {
        String url = anonymizerUrl + "/anonymize";

        AnonymizeRequest request = new AnonymizeRequest();
        request.setText(text);
        request.setAnalyzerResults(analyzerResults);
        request.setAnonymizers(anonymizers);

        HttpHeaders headers = createHeaders();
        HttpEntity<AnonymizeRequest> entity = new HttpEntity<>(request, headers);

        ResponseEntity<AnonymizeResponse> response = restTemplate.exchange(
            url,
            HttpMethod.POST,
            entity,
            AnonymizeResponse.class
        );

        return response.getBody();
    }

    /**
     * Complete pipeline for medical text processing
     */
    public AnonymizeResponse processMedicalText(String text, String strategy) {
        // Analyze
        List<AnalysisResult> entities = analyzeText(text, 0.7);
        log.info("Found {} entities in text", entities.size());

        // Build anonymization config based on strategy
        Map<String, AnonymizerConfig> anonymizers = buildAnonymizers(strategy);

        // Anonymize
        return anonymizeText(text, entities, anonymizers);
    }

    private HttpHeaders createHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(bearerToken);
        headers.set("X-Request-ID", UUID.randomUUID().toString());
        return headers;
    }

    private Map<String, AnonymizerConfig> buildAnonymizers(String strategy) {
        Map<String, AnonymizerConfig> anonymizers = new HashMap<>();

        if ("streng".equals(strategy)) {
            AnonymizerConfig replace = new AnonymizerConfig();
            replace.setType("replace");

            replace.setNewValue("<PATIENT>");
            anonymizers.put("PERSON", replace);

            AnonymizerConfig kvnr = new AnonymizerConfig();
            kvnr.setType("replace");
            kvnr.setNewValue("<KVNR>");
            anonymizers.put("DE_KVNR", kvnr);

            // Add more entity types...
        } else if ("maskierung".equals(strategy)) {
            AnonymizerConfig mask = new AnonymizerConfig();
            mask.setType("mask");
            mask.setMaskingChar("*");
            mask.setCharsToMask(4);
            mask.setFromEnd(false);
            anonymizers.put("PERSON", mask);

            // Add more entity types...
        }

        return anonymizers;
    }
}
```

### JavaScript/TypeScript Client

```typescript
// presidio-client.ts
import axios, { AxiosInstance, AxiosError } from 'axios';

interface AnalyzeRequest {
  text: string;
  language?: string;
  score_threshold?: number;
  entities?: string[];
}

interface AnalysisResult {
  entity_type: string;
  start: number;
  end: number;
  score: number;
  text?: string;
}

interface AnonymizeRequest {
  text: string;
  analyzer_results: AnalysisResult[];
  anonymizers?: Record<string, AnonymizerConfig>;
}

interface AnonymizerConfig {
  type: 'replace' | 'mask' | 'hash' | 'redact' | 'keep';
  new_value?: string;
  masking_char?: string;
  chars_to_mask?: number;
  from_end?: boolean;
  hash_type?: 'md5' | 'sha256' | 'sha512';
}

interface AnonymizeResponse {
  text: string;
  items: Array<{
    operator: string;
    entity_type: string;
    start: number;
    end: number;
    old_text?: string;
    new_text?: string;
  }>;
}

export class PresidioClient {
  private analyzerClient: AxiosInstance;
  private anonymizerClient: AxiosInstance;

  constructor(
    private analyzerURL: string,
    private anonymizerURL: string,
    private bearerToken?: string,
    private apiKey?: string
  ) {
    const headers = {
      'Content-Type': 'application/json',
      ...(bearerToken && { 'Authorization': `Bearer ${bearerToken}` }),
      ...(apiKey && { 'X-API-Key': apiKey })
    };

    this.analyzerClient = axios.create({
      baseURL: analyzerURL,
      timeout: 30000,
      headers
    });

    this.anonymizerClient = axios.create({
      baseURL: anonymizerURL,
      timeout: 30000,
      headers
    });

    // Add request interceptor for logging to both clients
    const requestInterceptor = (config: any) => {
      config.headers['X-Request-ID'] = this.generateRequestId();
      console.log(`[${config.method?.toUpperCase()}] ${config.url}`);
      return config;
    };

    const errorInterceptor = (error: AxiosError) => {
      console.error(`API Error: ${error.response?.status} - ${error.message}`);
      return Promise.reject(error);
    };

    this.analyzerClient.interceptors.request.use(requestInterceptor, (error) => Promise.reject(error));
    this.analyzerClient.interceptors.response.use((response) => response, errorInterceptor);

    this.anonymizerClient.interceptors.request.use(requestInterceptor, (error) => Promise.reject(error));
    this.anonymizerClient.interceptors.response.use((response) => response, errorInterceptor);
  }

  async analyzeText(
    text: string,
    options: Partial<AnalyzeRequest> = {}
  ): Promise<AnalysisResult[]> {
    const response = await this.analyzerClient.post<AnalysisResult[]>(
      '/analyze',
      {
        text,
        language: 'de',
        score_threshold: 0.0,
        ...options
      }
    );

    return response.data;
  }

  async anonymizeText(
    text: string,
    analyzerResults: AnalysisResult[],
    anonymizers?: Record<string, AnonymizerConfig>
  ): Promise<AnonymizeResponse> {
    const response = await this.anonymizerClient.post<AnonymizeResponse>(
      '/anonymize',
      {
        text,
        analyzer_results: analyzerResults,
        ...(anonymizers && { anonymizers })
      }
    );

    return response.data;
  }

  async processMedicalText(
    text: string,
    strategy: 'streng' | 'maskierung' | 'hash' = 'streng'
  ): Promise<{
    originalText: string;
    anonymizedText: string;
    entitiesFound: AnalysisResult[];
    transformations: AnonymizeResponse['items'];
  }> {
    // Define strategies
    const strategies: Record<string, Record<string, AnonymizerConfig>> = {
      streng: {
        PERSON: { type: 'replace', new_value: '<PATIENT>' },
        DE_KVNR: { type: 'replace', new_value: '<KVNR>' },
        DE_PHONE_NUMBER: { type: 'replace', new_value: '<TELEFON>' },
        EMAIL_ADDRESS: { type: 'replace', new_value: '<EMAIL>' },
        DATE_OF_BIRTH: { type: 'replace', new_value: '<GEBURTSDATUM>' }
      },
      maskierung: {
        PERSON: { type: 'mask', masking_char: '*', chars_to_mask: 100, from_end: false },
        DE_KVNR: { type: 'mask', masking_char: 'X', chars_to_mask: 7, from_end: true }
      },
      hash: {
        PERSON: { type: 'hash', hash_type: 'md5' },
        DE_KVNR: { type: 'hash', hash_type: 'sha256' }
      }
    };

    // Analyze text
    const entities = await this.analyzeText(text, { score_threshold: 0.7 });

    // Anonymize with selected strategy
    const anonymized = await this.anonymizeText(
      text,
      entities,
      strategies[strategy]
    );

    return {
      originalText: text,
      anonymizedText: anonymized.text,
      entitiesFound: entities,
      transformations: anonymized.items
    };
  }

  private generateRequestId(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
}

// Example usage
async function example() {
  const client = new PresidioClient(
    'http://presidio-analyzer.local:5002',  // Analyzer service
    'http://presidio-anonymizer.local:5001', // Anonymizer service
    'your-bearer-token'
  );

  const medicalText = `
    Patient: Max Mustermann, geb. 15.03.1985
    KVNR: A123456789
    Diagnose: Hypertonie
  `;

  try {
    const result = await client.processMedicalText(medicalText, 'streng');
    console.log('Anonymized:', result.anonymizedText);
    console.log('Entities found:', result.entitiesFound.length);
  } catch (error) {
    console.error('Error processing text:', error);
  }
}
```

## Monitoring and Logging

### Prometheus Metrics

```yaml
# prometheus-config.yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'presidio-analyzer'
    static_configs:
      - targets: ['presidio-analyzer:3000']
    metrics_path: /metrics

  - job_name: 'presidio-anonymizer'
    static_configs:
      - targets: ['presidio-anonymizer:3000']
    metrics_path: /metrics

# Key metrics to monitor:
# - request_duration_seconds
# - request_count_total
# - entity_detection_count
# - anonymization_operations_count
# - error_rate
```

### ELK Stack Logging

```json
// logstash-pipeline.conf
input {
  tcp {
    port => 5000
    codec => json
  }
}

filter {
  if [service] == "presidio-analyzer" {
    mutate {
      add_field => { "[@metadata][index_prefix]" => "presidio-analyzer" }
    }

    # Extract entity types from log
    if [message] =~ /entities found:/ {
      grok {
        match => { "message" => "entities found: %{DATA:entities}" }
      }
    }
  }

  if [service] == "presidio-anonymizer" {
    mutate {
      add_field => { "[@metadata][index_prefix]" => "presidio-anonymizer" }
    }
  }

  # Add GDPR compliance fields
  mutate {
    add_field => {
      "gdpr_relevant" => true
      "data_category" => "PHI"
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "%{[@metadata][index_prefix]}-%{+YYYY.MM.dd}"
  }
}
```

### Audit Logging

```python
# audit_logger.py
import json
import logging
from datetime import datetime
from typing import Dict, Any

class AuditLogger:
    """GDPR-compliant audit logger for PHI access"""

    def __init__(self, service_name: str):
        self.service = service_name
        self.logger = logging.getLogger(f'audit.{service_name}')
        handler = logging.FileHandler(f'/var/log/presidio/{service_name}-audit.log')
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log_phi_access(
        self,
        request_id: str,
        user_id: str,
        action: str,
        entity_types: list,
        success: bool,
        client_ip: str,
        processing_time_ms: int
    ):
        """Log PHI access for compliance"""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'request_id': request_id,
            'service': self.service,
            'user_id': user_id,
            'action': action,
            'entity_types': entity_types,
            'success': success,
            'client_ip': client_ip,
            'processing_time_ms': processing_time_ms,
            'gdpr_relevant': True,
            'data_category': 'PHI'
        }

        self.logger.info(json.dumps(audit_entry))

    def log_anonymization(
        self,
        request_id: str,
        strategy: str,
        entities_count: int,
        text_length: int
    ):
        """Log anonymization operations"""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'request_id': request_id,
            'service': self.service,
            'operation': 'anonymization',
            'strategy': strategy,
            'entities_processed': entities_count,
            'text_length': text_length
        }

        self.logger.info(json.dumps(audit_entry))
```

## Compliance Considerations

### GDPR/DSGVO Requirements

1. **Data Minimization**
   - Process only necessary PHI
   - Implement text size limits
   - Auto-delete temporary data

2. **Purpose Limitation**
   - Log purpose of each PHI access
   - Enforce role-based access control
   - Audit all data processing

3. **Storage Limitation**
   - No persistent storage of PHI in services
   - Implement secure session management
   - Auto-cleanup of processing artifacts

4. **Integrity and Confidentiality**
   - TLS 1.2+ for all communications
   - Encryption at rest for any cached data
   - Regular security audits

5. **Accountability**
   - Comprehensive audit logging
   - Regular compliance reports
   - Incident response procedures

### Implementation Checklist

- [ ] Configure TLS certificates (optional, using stunnel or similar)
- [ ] Implement authentication at service level (JWT/OAuth)
- [ ] Configure network policies and firewall rules for service access
- [ ] Implement rate limiting at service level
- [ ] Implement audit logging
- [ ] Set up monitoring and alerting
- [ ] Configure backup and recovery
- [ ] Document data retention policies
- [ ] Implement RBAC (Role-Based Access Control)
- [ ] Set up regular security scans
- [ ] Create incident response plan
- [ ] Train staff on PHI handling

## Support and Documentation

For additional support and documentation:
- OpenAPI Specification: `openapi.yaml`
- Architecture Documentation: `ARCHITECTURE.md`
- Docker Compose Configuration: `docker-compose.yml`
- README: `README.md`

---

Last Updated: 2024-01-15
Version: 1.0.0