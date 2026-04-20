# GitHub Copilot Instructions — Edge AI Suites

## Project Overview

Edge AI Suites is an Intel Open Edge Platform repository containing production-ready AI application suites for manufacturing, metro/smart-city, retail, robotics, education, and health & life sciences. Each suite contains sample applications that run on edge hardware using Docker Compose or Helm chart deployments.

## Repository Structure

```
edge-ai-suites/
├── manufacturing-ai-suite/          # Industrial defect detection, asset tracking, vision, time-series, GenAI
│   ├── industrial-edge-insights-multimodal/   # Vision + time-series fusion for weld defect detection
│   ├── industrial-edge-insights-time-series/  # Time-series anomaly detection
│   ├── industrial-edge-insights-vision/       # Vision-based defect detection
│   └── hmi-augmented-worker/                  # HMI augmented worker app
├── metro-ai-suite/                  # Smart city, traffic, video analytics
├── retail-ai-suite/                 # Self-checkout, loss prevention
├── robotics-ai-suite/              # Perception, navigation, simulation
├── education-ai-suite/             # Education AI applications
├── health-and-life-sciences-ai-suite/  # Healthcare monitoring (preview)
└── .github/
    ├── workflows/                   # CI/CD pipelines
    ├── CODEOWNERS                   # Code ownership for review routing
    ├── PULL_REQUEST_TEMPLATE.md     # PR template
    └── ISSUE_TEMPLATE/              # Bug and feature request templates
```

## Tech Stack

- **Languages**: Python 3.13, Bash, YAML, JSON
- **Container Orchestration**: Docker Compose, Kubernetes (Helm charts)
- **Time-Series**: InfluxDB 1.12.x, Kapacitor, Telegraf 1.38.x
- **Message Broker**: Eclipse Mosquitto (MQTT) 2.0.x
- **Visualization**: Grafana 12.x
- **Video Processing**: Intel DL Streamer Pipeline Server, MediaMTX, RTSP/WebRTC
- **Object Storage**: SeaweedFS (S3-compatible)
- **Networking**: nginx (reverse proxy/TLS), Coturn (TURN/WebRTC)
- **ML/AI**: CatBoost, DeiT models, OpenCV, OpenTelemetry
- **Testing**: pytest, Playwright, pytest-html
- **Security Scanning**: Trivy, Bandit, CodeQL, Zizmor, Pylint
- **CI/CD**: GitHub Actions on ubuntu-24.04 runners

## Coding Standards

### License Headers

Every source file **must** include the Apache 2.0 license header:

```python
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
```

For YAML files use the SPDX form:
```yaml
# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
```

### Python Code

- Target Python 3.13 (base image: `python:3.13-slim`)
- Use type hints for function signatures (`from typing import Dict, Optional, Any, Literal`)
- Use `logging` module with configurable `LOG_LEVEL` environment variable — never use bare `print()` for application output
- Use `os.getenv()` with sensible defaults for all configuration
- Follow PEP 8 naming conventions; use meaningful variable and function names
- Pin all dependency versions exactly in `requirements.txt` (e.g., `paho-mqtt==2.1.0`)
- Document modules and functions with docstrings

### Docker / Container Standards

- Base images: Use official slim variants (e.g., `python:3.13-slim`)
- Always create a non-root user (`TIMESERIES_UID` / `TIMESERIES_USER_NAME`) and switch to it with `USER`
- Set `read_only: true`, `security_opt: [no-new-privileges:true]`, and `seccomp:unconfined` where appropriate
- Use `tmpfs` volumes for runtime data rather than persistent bind mounts
- Include `HEALTHCHECK` directives in Dockerfiles
- Support `COPYLEFT_SOURCES` build arg for license compliance
- Remove unnecessary packages (e.g., `perl-base`) to reduce attack surface
- Never embed secrets in images — use environment variables injected at runtime

### Docker Compose

- Name services with `ia-` prefix for Intel Application containers
- Use bridge networks (e.g., `timeseries_network`)
- Use `depends_on` with `condition: service_healthy` for startup ordering
- Environment variables sourced from `.env` files — never hardcode credentials
- Include `deploy.resources.limits` for memory/CPU where applicable

### Helm Charts

- Follow the structure: `Chart.yaml`, `values.yaml`, `values.schema.json`, `templates/`
- Version charts using date-based versioning (e.g., `2026.0`)
- Validate all user inputs with `values.schema.json`
- Templates must support configurable resource limits, image tags, and credentials

### Makefile Conventions

- Use `.PHONY` for all non-file targets
- Include validation targets (`validate_host_ip`, `check_env_variables`) called before deployment
- Set `chmod 600` on files containing credentials (`.env`, `helm/values.yaml`)
- Support `help` target listing all available commands

### Commit Messages

- Use present tense: "Add feature" not "Added feature"
- Capitalize the first letter
- Keep under 50 characters
- Include `Signed-off-by:` line (Developer Certificate of Origin required)

## Security Requirements

- **No secrets in code**: Credentials must be injected via environment variables, never hardcoded
- **Password rules**: Minimum 10 alphanumeric characters with at least one digit for passwords; minimum 5 alphabetic characters for usernames
- **Container hardening**: Read-only filesystems, non-root users (UID 2999), no privilege escalation, seccomp profiles
- **TLS everywhere**: nginx proxies Grafana over HTTPS (port 15443); auto-generated self-signed certificates for development
- **Dependency pinning**: All Python packages, Docker images, and GitHub Actions must be version-pinned (actions pinned by SHA)
- **Security scanning**: Trivy (filesystem, image, config, Dockerfile, Helm), Bandit (Python), CodeQL, Zizmor (GitHub Actions), Pylint
- Report vulnerabilities per Intel's [vulnerability handling guidelines](https://www.intel.com/content/www/us/en/security-center/vulnerability-handling-guidelines.html)

## Testing

- Use `pytest` with `pytest-html` for HTML test reports
- Test files follow naming: `test_docker_deployment_*.py`, `test_helm_deployment_*.py`
- Tests validate Docker Compose and Helm deployments end-to-end
- Run tests in a virtual environment with dependencies from `tests/requirements.txt`
- Functional tests check container health, MQTT connectivity, InfluxDB data flow, Grafana dashboards

## CI/CD Workflows

- Workflows trigger on `pull_request` to specific paths and on `workflow_dispatch`
- Use `ubuntu-24.04` runners
- Concurrency: one workflow per PR (`cancel-in-progress: true`)
- Pin all action versions by commit SHA (e.g., `actions/checkout@8e8c483...`)
- Permissions follow least privilege: declare only needed `contents: read`, `packages: read`, etc.
- Security scans run as part of PR workflow (Trivy, Bandit, CodeQL, Zizmor)
- Functional tests run daily at 14:00 UTC and on demand

## PR and Contribution Guidelines

When creating or reviewing PRs, ensure:

1. **License compliance**: Apache 2.0 headers on all new files; no incompatible 3rd party licenses
2. **No secrets**: No passwords, tokens, or confidential data committed
3. **Self-review**: Code reviewed before submission
4. **Testing**: Changes tested locally; describe test setup in PR
5. **Dependencies**: Any new 3rd party dependency must be listed with name, license, and usage
6. **DCO sign-off**: All commits signed with `Signed-off-by: Name <email>`
7. **Documentation**: Update relevant docs, README, CHANGELOG when applicable

## Third-Party License Tracking

All third-party dependencies (Docker images, Python packages) are tracked in `third-party-programs.txt` with:
- Package name and version
- License type (Apache 2.0, MIT, BSD, EPL, AGPLv3, etc.)
- For copyleft dependencies (GPL, LGPL, MPL, EPL, CDDL): source download support via `COPYLEFT_SOURCES=true` build arg
