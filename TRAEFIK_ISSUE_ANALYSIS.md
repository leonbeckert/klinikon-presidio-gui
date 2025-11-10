# Traefik Routing Issue Analysis - Presidio Services

## Executive Summary

The Presidio analyzer and anonymizer services are running successfully in Docker containers but are not accessible through Traefik reverse proxy via their configured domains. The main UI service works correctly through Traefik, but API services return "no available server" error.

## Current Status

### Working ✅
- **Main UI** (`https://presidio.klinikon.com`) - Fully functional
- **Container Health** - All three containers running and healthy
- **Internal Communication** - UI can communicate with analyzer/anonymizer internally
- **DNS Resolution** - All domains resolve correctly to server IP (176.9.82.82)
- **Direct Port Access** - Services accessible via localhost:5001 and localhost:5002 on server

### Not Working ❌
- **Analyzer API** (`https://analyzer.presidio.klinikon.com`) - Returns "no available server"
- **Anonymizer API** (`https://anonymizer.presidio.klinikon.com`) - Returns "no available server"
- **Basic Auth** - Cannot be tested due to routing failure

## Environment Details

### Infrastructure
- **Platform**: Coolify v4.0.0-beta.428
- **Server**: Hetzner dedicated server
- **Reverse Proxy**: Traefik (managed by Coolify)
- **Container Runtime**: Docker with docker-compose
- **Network**: External network named `coolify` shared across services

### Service Configuration

#### Container Names (as deployed by Coolify)
```
presidio-analyzer-v4wcc8woo4k0c04ogg8kc0w8-[timestamp]
presidio-anonymizer-v4wcc8woo4k0c04ogg8kc0w8-[timestamp]
klinikon-presidio-ui-v4wcc8woo4k0c04ogg8kc0w8-[timestamp]
```

**Note**: Coolify overrides the `container_name` directive and adds unique suffixes.

#### Networks
```yaml
networks:
  presidio-network:    # Internal network for service communication
    driver: bridge
  coolify:            # External network for Traefik discovery
    external: true
```

## Attempted Solutions

### 1. Initial Configuration
Added Traefik labels following the pattern from a working service:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.presidio-analyzer-https.rule=Host(`analyzer.presidio.klinikon.com`)"
  - "traefik.http.routers.presidio-analyzer-https.entrypoints=https"
  - "traefik.http.routers.presidio-analyzer-https.tls=true"
  - "traefik.http.services.presidio-analyzer-service.loadbalancer.server.port=3000"
```

### 2. Network Configuration
- Added both services to `coolify` network
- Specified `traefik.docker.network=coolify` label
- Ensured services are on same network as Traefik

### 3. Authentication Setup
- Implemented Basic Auth middleware (hardcoded due to env var interpolation issues)
- Synchronized auth configuration across both services
- Fixed middleware naming conflicts

### 4. Service Discovery
- Added explicit network specification for Traefik
- Tried various service naming patterns
- Verified port configurations (internal port 3000)

## Technical Analysis

### Symptoms
1. **Error Message**: "no available server" from Traefik
2. **HTTP Status**: Returns immediately (no timeout)
3. **Behavior**: Consistent across both analyzer and anonymizer
4. **Logs**: No errors in container logs, services starting successfully

### Key Observations

1. **Container Name Mismatch**:
   - Defined: `presidio-analyzer-de`
   - Actual: `presidio-analyzer-v4wcc8woo4k0c04ogg8kc0w8-[timestamp]`
   - This may prevent Traefik from finding the service

2. **Working UI Service**:
   - The UI service works through Traefik
   - Uses identical label pattern
   - Key difference: UI is the main service, APIs are additional

3. **Network Connectivity**:
   - Services are on `coolify` network (verified in logs)
   - Can communicate internally via `presidio-network`
   - Direct port access works (5001, 5002)

4. **Traefik Configuration**:
   - Labels appear correct syntactically
   - Similar pattern works for other projects
   - "no available server" indicates Traefik can't find backend

## Possible Root Causes

### 1. Service Discovery Issue
Traefik may not be able to discover the services due to:
- Container name override by Coolify
- Missing or incorrect service selector
- Label parsing issues with Coolify's deployment

### 2. Network Isolation
Despite being on `coolify` network:
- Traefik might not have access to the containers
- Network policies or firewall rules blocking communication
- Docker network driver compatibility issues

### 3. Coolify-Specific Behavior
- Coolify might handle multiple services in docker-compose differently
- Only the "main" service gets proper Traefik integration
- Additional services need special configuration

### 4. Label Processing
- Labels might not be applied correctly during Coolify deployment
- Coolify might override or ignore certain Traefik labels
- Timing issue with label application

## Diagnostic Commands

### On the Server

```bash
# 1. Verify containers are on coolify network
docker network inspect coolify | grep -A5 presidio

# 2. Check actual labels on running containers
docker inspect $(docker ps -q -f name=presidio-analyzer) | jq '.[0].Config.Labels'

# 3. Test from Traefik container
docker exec $(docker ps -q -f name=traefik) wget -O- http://presidio-analyzer:3000/health

# 4. Check Traefik routing table
curl http://localhost:8080/api/http/routers | jq '.[] | select(.rule | contains("presidio"))'

# 5. Verify service discovery
docker exec $(docker ps -q -f name=traefik) nslookup presidio-analyzer
```

## Recommendations for Resolution

### Option 1: Single Service Approach
Instead of exposing analyzer/anonymizer separately, proxy requests through the UI:
- Add API proxy endpoints in UI application
- Keep analyzer/anonymizer internal only
- Simplifies Traefik configuration

### Option 2: Manual Traefik Configuration
- Create separate Traefik configuration file
- Mount as volume in Coolify
- Bypass docker-compose labels entirely

### Option 3: Use Coolify's Internal Proxy
- Check if Coolify has specific methods for multi-service exposure
- May need to create separate "services" in Coolify UI
- Consult Coolify documentation for multi-container applications

### Option 4: Direct Container Reference
- Try using full container name pattern in labels
- Or use service discovery with Coolify-specific syntax
- May need to reference by project/service ID

## Current docker-compose.yaml (Relevant Sections)

```yaml
services:
  presidio-analyzer:
    build: ./analyzer-de
    container_name: presidio-analyzer-de  # Overridden by Coolify
    ports:
      - "5002:3000"
    networks:
      - presidio-network
      - coolify
    labels:
      - "traefik.enable=true"
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
      - "traefik.http.middlewares.presidio-auth.basicauth.users=presidio-extern:$$apr1$$ySmKU4uq$$GpschtTYbsP3hWuIvb84O."
      - "traefik.http.routers.presidio-analyzer-http.entryPoints=http"
      - "traefik.http.routers.presidio-analyzer-http.rule=Host(`analyzer.presidio.klinikon.com`)"
      - "traefik.http.routers.presidio-analyzer-http.middlewares=redirect-to-https"
      - "traefik.http.routers.presidio-analyzer-http.service=presidio-analyzer-service"
      - "traefik.http.routers.presidio-analyzer-https.entryPoints=https"
      - "traefik.http.routers.presidio-analyzer-https.rule=Host(`analyzer.presidio.klinikon.com`)"
      - "traefik.http.routers.presidio-analyzer-https.tls=true"
      - "traefik.http.routers.presidio-analyzer-https.middlewares=presidio-auth"
      - "traefik.http.routers.presidio-analyzer-https.service=presidio-analyzer-service"
      - "traefik.http.services.presidio-analyzer-service.loadbalancer.server.port=3000"
      - "traefik.docker.network=coolify"
```

## Files for Reference

- `/docker-compose.yaml` - Full service configuration
- `/TROUBLESHOOTING.md` - Basic troubleshooting guide
- `/USAGE.md` - API usage documentation
- `/.env.example` - Environment configuration template

## Next Steps for Developer

1. **Verify Coolify's Multi-Service Support**
   - Check if Coolify supports multiple publicly exposed services in one docker-compose
   - Review Coolify documentation for proper multi-service configuration

2. **Inspect Traefik Configuration**
   - Access Traefik dashboard/API to see actual routing configuration
   - Verify if service discovery is working correctly
   - Check for any conflicting routes or middlewares

3. **Test Alternative Approaches**
   - Try deploying analyzer/anonymizer as separate Coolify projects
   - Test with simplified labels (remove auth, just basic routing)
   - Use Traefik file provider instead of Docker labels

4. **Contact Coolify Support**
   - This might be a known limitation or require specific configuration
   - Check Coolify GitHub issues for similar problems
   - Ask in Coolify Discord/community

## Contact Information

- **Repository**: https://github.com/leonbeckert/klinikon-presidio-gui
- **Latest Commit**: 5309d8c - "Add Traefik network specification for service discovery"
- **Domains Configured**:
  - analyzer.presidio.klinikon.com
  - anonymizer.presidio.klinikon.com
  - presidio.klinikon.com (working)

## Conclusion

The issue appears to be specific to how Coolify handles multiple services within a single docker-compose deployment when those services need to be publicly accessible through Traefik. The main service (UI) works correctly, but additional services cannot be reached despite appearing to have correct configuration.

The most likely cause is that Coolify has specific requirements or limitations for multi-service deployments that aren't documented or differ from standard Traefik + Docker Compose setups. A developer familiar with Coolify's internals or someone with access to Traefik's running configuration would be best positioned to diagnose and resolve this issue.