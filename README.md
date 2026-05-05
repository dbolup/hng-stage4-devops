# hng-stage4-devops

A DevOps automation project that builds infrastructure deployment tools. This task focuses on creating a declarative manifest-driven deployment system where `manifest.yaml` is the single source of truth for your entire infrastructure. The `swiftdeploy` CLI tool generates all configurations programmatically, manages container lifecycles, and ensures your stack runs reliably.

## Project Objectives

By completing this task, you will:

- Write a declarative YAML manifest that describes a complete service deployment
- Build a CLI tool with multiple subcommands that manages infrastructure lifecycle
- Generate Nginx and Docker Compose configurations programmatically from templates
- Implement industry best practices for containerized deployments

## What You're Building

### 1. The Manifest (`manifest.yaml`)

The manifest is the **single source of truth** - the only file you're allowed to edit manually. All other configurations are generated from it. The grader will delete generated files and re-run `swiftdeploy init` to verify regeneration.

**Base Requirements** (must include):

```yaml
services:
  image: swift-deploy-1-node:latest
  port: 3000

nginx:
  image: nginx:latest
  port: 8080

network:
  name: swiftdeploy-net
  driver_type: bridge
```

You can extend the manifest with additional fields, but do not change these base requirements.

### 2. The API Service

A single HTTP service (Python implementation) running in `stable` or `canary` mode via the `MODE` environment variable.

**Endpoints**:

- **GET /**: Welcome message including current mode, version, and server timestamp
- **GET /healthz**: Liveness check returning status and process uptime in seconds
- **POST /chaos**: Chaos injection endpoint (canary mode only)

**Modes**:
- `stable`: Standard operation
- `canary`: Adds `X-Mode: canary` header to all responses and activates chaos endpoint

**Chaos Operations** (POST /chaos):
```json
{ "operation": "slow", "duration": 2 }     // Sleep N seconds before responding
{ "operation": "error", "rate": 0.5 }      // Return 500 on ~50% of requests
{ "operation": "recover" }                 // Cancel active chaos
```

### 3. The CLI Tool (`swiftdeploy`)

An executable Python script with the following subcommands:

#### `init`
Parses manifest.yaml and generates `nginx.conf` and `docker-compose.yml` from templates.

#### `validate`
Runs 5 pre-flight checks, exits non-zero on failure:
1. `manifest.yaml` exists and is valid YAML
2. All required fields are present and non-empty
3. Docker image referenced in manifest exists locally
4. Nginx port is not already bound on host
5. Generated `nginx.conf` is syntactically valid

#### `deploy`
Runs `init`, brings up the stack, and blocks until health checks pass or 60s timeout.

#### `promote [stable|canary]`
Switches deployment mode with rolling service restart:
- Updates `mode` field in `manifest.yaml` in-place
- Regenerates `docker-compose.yml` with new `MODE` env var
- Restarts service container only
- Confirms new mode is active via `/healthz`

#### `teardown [--clean]`
Removes all containers, networks, and volumes. `--clean` also deletes generated configs.

## Architecture

```
Internet → Nginx (nginx.port) → API Service (services.port)
```

- **API Service**: Python HTTP server with chaos engineering capabilities
- **Nginx**: Reverse proxy with custom error handling and logging
- **Docker Compose**: Orchestrates services with health checks and networking
- **SwiftDeploy**: CLI tool for declarative infrastructure management

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for swiftdeploy tool)
- Linux/Unix environment

## Quick Start

1. **Clone and navigate**:
   ```bash
   git clone https://github.com/Dbolup/hng-stage4-devops.git
   cd hng-stage4-devops
   ```

2. **Initialize from manifest**:
   ```bash
   python3 swiftdeploy init
   ```

3. **Deploy the stack**:
   ```bash
   python3 swiftdeploy deploy
   ```

4. **Access the application**:
   - API: http://localhost:8080
   - Health: http://localhost:8080/healthz

## Configuration

### Manifest Structure

```yaml
services:
  image: swift-deploy-1-node:latest
  port: 3000
  mode: stable          # "stable" or "canary"
  version: "1.0.0"      # Application version
  restart_policy: unless-stopped

nginx:
  image: nginx:latest
  port: 8080
  proxy_timeout: 30     # Timeout in seconds

network:
  name: swiftdeploy-net
  driver_type: bridge

volumes:
  logs: swiftdeploy-logs
```

### Environment Variables (Injected)

- `MODE`: Deployment mode
- `APP_VERSION`: Application version
- `APP_PORT`: Service port

## API Endpoints

### GET /
**Response**:
```json
{
  "message": "Welcome! Running in stable mode",
  "mode": "stable",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00.000000+00:00"
}
```

### GET /healthz
**Response**:
```json
{
  "status": "ok",
  "mode": "stable",
  "version": "1.0.0",
  "uptime_seconds": 123.45
}
```

### POST /chaos (Canary Mode Only)
**Request Body Examples**:
```json
{ "operation": "slow", "duration": 2 }
{ "operation": "error", "rate": 0.5 }
{ "operation": "recover" }
```

## CLI Usage

### Initialize Configuration
```bash
python3 swiftdeploy init
```

### Validate Setup
```bash
python3 swiftdeploy validate
```

### Deploy Stack
```bash
python3 swiftdeploy deploy
```

### Promote to Canary
```bash
python3 swiftdeploy promote canary
```

### Promote to Stable
```bash
python3 swiftdeploy promote stable
```

### Teardown Stack
```bash
python3 swiftdeploy teardown
```

### Teardown with Clean
```bash
python3 swiftdeploy teardown --clean
```

## Infrastructure Requirements

### Nginx Configuration
- Listens on `nginx.port`
- Sets timeouts from `nginx.proxy_timeout`
- Returns JSON error bodies for 502/503/504:
  ```json
  {
    "error": "Bad Gateway",
    "code": 502,
    "service": "api",
    "contact": "ops@swiftdeploy.io"
  }
  ```
- Adds `X-Deployed-By: swiftdeploy` header
- Forwards `X-Mode` from upstream
- Access logs format: `$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request`

### Docker & Docker Compose
- Containers run as non-root user with dropped Linux capabilities
- Images are lightweight (< 300MB)
- Injects `MODE`, `APP_VERSION`, `APP_PORT` into service container
- Uses defined network and restart policy
- Mounts named volume for logs
- Defines health check on `/healthz`
- Never exposes service port directly (all traffic through Nginx)

## Chaos Engineering

Canary mode enables chaos testing:

- **Slow Mode**: Artificial delays before responses
- **Error Mode**: Random HTTP 500 errors at specified rate
- **Recovery**: Return to normal operation

Control via POST /chaos endpoint.

## File Structure

```
hng-stage4-devops/
├── app/                    # Python API service
│   ├── main.py            # HTTP server implementation
│   └── requirements.txt   # Dependencies
├── templates/             # Jinja2-style templates
│   ├── docker-compose.yml.j2
│   └── nginx.conf.j2
├── manifest.yaml          # Declarative configuration (single source of truth)
├── swiftdeploy            # CLI deployment tool
├── Dockerfile             # Container build (generated from manifest)
├── docker-compose.yml     # Service orchestration (generated)
├── nginx.conf             # Nginx config (generated)
└── README.md              # This documentation
```

## Development

### Building Images
```bash
docker build -t swift-deploy-1-node:latest .
```

### Testing Validation
```bash
python3 swiftdeploy validate
```

### Viewing Logs
```bash
docker-compose logs api
docker-compose logs nginx
```

## Industry Best Practices Implemented

- **Declarative Configuration**: Single manifest as source of truth
- **Immutable Infrastructure**: All configs generated, nothing handwritten
- **Security**: Non-root execution, capability dropping
- **Observability**: Health checks, structured logging
- **Reliability**: Chaos engineering for testing
- **Automation**: CLI-driven lifecycle management
- **Lightweight**: Images under 300MB
- **Network Security**: No direct service port exposure

## Troubleshooting

### Validation Failures
- Check `manifest.yaml` syntax
- Ensure Docker images exist locally
- Verify ports are available
- Confirm Nginx config syntax

### Deployment Issues
- Run `swiftdeploy validate` first
- Check Docker daemon status
- Review service logs

### Mode Switching
- Use `promote` command for safe mode transitions
- Health checks confirm successful switches

## Contributing

1. Edit only `manifest.yaml`
2. Test with `swiftdeploy validate`
3. Deploy with `swiftdeploy deploy`
4. Verify chaos features in canary mode

This project demonstrates modern DevOps practices through automated, declarative infrastructure management.
docker build -t swift-deploy-1-node:latest .
```

### Running Tests

```bash
python3 swiftdeploy validate
```

### Logs

View application logs:
```bash
docker-compose logs api
```

View Nginx logs:
```bash
docker-compose logs nginx
```

## Security Considerations

- Services run as non-root user (UID 1000)
- Capabilities are dropped except for NET_BIND_SERVICE
- Health checks ensure service availability
- Custom error pages prevent information leakage

## Troubleshooting

### Common Issues

1. **Port already in use**: Change ports in `manifest.yaml`
2. **Permission denied**: Ensure Docker daemon is running
3. **Health check failures**: Check service logs with `docker-compose logs`

### Debug Mode

Set `MODE=canary` in manifest for additional chaos testing endpoints.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run validation: `python3 swiftdeploy validate`
5. Submit a pull request

## License

This project is part of the HNG Internship program. See repository for licensing details.