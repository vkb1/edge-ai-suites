# Copilot Instructions for Edge AI Suites

## Repository Overview

This is a monorepo containing industry-specific AI SDK sample applications organized into suites:
- **Manufacturing AI Suite** — Industrial Edge Insights (Time Series, Multimodal, Vision)
- **Metro AI Suite** — Smart city and traffic applications
- **Retail AI Suite** — Retail analytics
- **Robotics AI Suite** — Robotics components and pipelines
- **Education AI Suite** — Smart classroom
- **Health & Life Sciences AI Suite** — Patient monitoring

## License and Compliance

- All code is licensed under **Apache-2.0**. Every new source file must include the Apache v2 license header:
  ```
  # Apache v2 license
  # Copyright (C) <year> Intel Corporation
  # SPDX-License-Identifier: Apache-2.0
  ```
- Contributions require sign-off via the Developer Certificate of Origin (DCO). Commits must include `Signed-off-by:` lines.
- Do NOT introduce any third-party components incompatible with Apache-2.0.
- Do NOT commit credentials, passwords, API keys, or security tokens. Use environment variables (`.env` files) with randomized values in CI.
- `.env` and `helm/values.yaml` must have `chmod 600` permissions.

## Coding Standards

### Python
- Use Python 3.13+ for all new code (simulators use Python 3.13; CI linting uses 3.11).
- Follow PEP 8 style guidelines. The CI pipeline runs **Pylint** on all Python code.
- Static analysis is performed with **Bandit** (security) and **CodeQL** (SAST).
- Use `Intel Extension for Scikit-learn` (`sklearnex`) when applicable for ML workloads.
- Pin all dependency versions exactly in `requirements.txt` files (e.g., `pandas==2.2.3`).

### Docker and Containers
- Base images should use specific version tags, never `latest`.
- Containers must run as non-root users (UID 2999, user `timeseries_user`).
- Use read-only root filesystems where possible with `tmpfs` mounts for writable paths.
- Apply `no-new-privileges: true` and drop all Linux capabilities except those explicitly needed.
- All Docker images are scanned with **Trivy** (filesystem, image, config) and **ClamAV** (virus) in CI.
- **Docker Bench Security** is run against deployed containers.

### Helm Charts
- Helm charts reside in `helm/` directories within each project.
- Values files must include a JSON Schema (`values.schema.json`) for validation.
- Chart version must follow Semantic Versioning and match `appVersion` in `.env`.
- Trivy config scans are run against generated Helm charts.
- Network policies must be defined to restrict inter-pod communication.

### GitHub Actions Workflows
- All workflows are scanned with **Zizmor** for security issues.
- Use pinned action versions with commit SHAs (e.g., `actions/checkout@<sha> # v6.0.1`).
- Apply the principle of least privilege for `permissions` in every workflow and job.
- Use `concurrency` groups to prevent redundant workflow runs on the same PR.
- Upload all scan artifacts (HTML, CSV, SARIF, PDF) for auditability.

## Project Structure — Industrial Edge Insights Time Series

Located at `manufacturing-ai-suite/industrial-edge-insights-time-series/`:

```
├── .env                          # Environment config (credentials, ports, registry)
├── Makefile                      # Build/deploy automation
├── docker-compose.yml            # Docker Compose stack definition
├── generate-telegraf-config.py   # Multi-stream Telegraf config generator
├── apps/
│   ├── wind-turbine-anomaly-detection/
│   │   ├── telegraf-config/      # Telegraf input configurations (MQTT + OPC-UA)
│   │   ├── time-series-analytics-config/
│   │   │   ├── config.json       # UDF and alert configuration
│   │   │   ├── models/           # Trained ML model (.pkl)
│   │   │   ├── udfs/             # User-Defined Functions (Python)
│   │   │   └── tick_scripts/     # Kapacitor TICKscripts
│   │   ├── simulation-data/      # CSV test data
│   │   ├── training/             # Jupyter notebook for model training
│   │   └── grafana-dashboard.json
│   └── weld-defect-detection/    # Same structure as above, MQTT-only
├── configs/                      # Service configurations
│   ├── grafana/                  # Dashboard provisioning
│   ├── influxdb/                 # DB config and init scripts
│   ├── mqtt-broker/              # Mosquitto config
│   ├── nginx/                    # Reverse proxy and SSL cert generation
│   └── telegraf/                 # Telegraf entrypoint
├── helm/                         # Kubernetes Helm chart
├── simulator/
│   ├── mqtt-publisher/           # MQTT data simulator
│   └── opcua-server/             # OPC-UA data simulator
├── tests/
│   ├── functional/               # pytest functional tests (Docker + Helm)
│   └── utils/                    # Shared test utilities
└── docs/user-guide/              # Project documentation (Sphinx-based)
```

## Key Technologies

| Component | Technology | Version |
|-----------|-----------|---------|
| Data Collection | Telegraf | 1.38.0 |
| Time-Series DB | InfluxDB | 1.12.2 |
| Stream Processing | Kapacitor (TSAM) | Intel custom |
| Visualization | Grafana | 12.4.0 |
| MQTT Broker | Eclipse Mosquitto | 2.0.22 |
| Reverse Proxy | nginx | 1.29.5 |
| ML Framework | scikit-learn + Intel Extension | — |
| Container Orchestration | Docker Compose / Helm + k3s | — |

## Build and Deploy Commands

```bash
# Build all Docker images
make build

# Deploy with MQTT ingestion (default: wind-turbine-anomaly-detection)
make up_mqtt_ingestion app=wind-turbine-anomaly-detection

# Deploy with OPC-UA ingestion (wind-turbine only)
make up_opcua_ingestion app=wind-turbine-anomaly-detection

# Deploy weld defect detection (MQTT only)
make up_mqtt_ingestion app=weld-defect-detection

# Multi-stream deployment
make up_mqtt_ingestion app=wind-turbine-anomaly-detection num_of_streams=3

# Check container status
make status

# Stop and clean up
make down

# Generate Helm chart packages
make gen_helm_charts app=wind-turbine-anomaly-detection

# Validate environment variables
make check_env_variables
```

## Testing

Tests use **pytest** with HTML and JUnit XML reporting. Test infrastructure includes both Docker Compose and Helm (k3s) deployments.

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run functional tests
cd tests/functional
pytest test_docker_deployment_wind_turbine.py --html=report.html --self-contained-html
```

### Test Categories
- `test_docker_deployment_wind_turbine` — Wind turbine via Docker
- `test_docker_deployment_weld_anomaly` — Weld defect via Docker
- `test_docker_deployment_stability` — Deployment stability
- `test_docker_influxdb_retention` — InfluxDB retention policies
- `test_docker_helm_deployment_security` — Security compliance
- `test_helm_deployment_wind_turbine` — Wind turbine via Helm/k3s
- `test_helm_deployment_weld_anomaly` — Weld defect via Helm/k3s
- `test_helm_influxdb_retention` — Helm InfluxDB retention

Tests marked with `@pytest.mark.longrun` can be skipped with `--skip-long-tests`.

## CI/CD Pipelines

### Pull Request Workflow
Triggers on changes to `manufacturing-ai-suite/industrial-edge-insights-time-series/**`:
1. Builds Time Series Analytics microservices (from `edge-ai-libraries`)
2. Builds sample app Docker images
3. Deploys and validates Wind Turbine app (MQTT + OPC-UA)
4. Deploys and validates Weld Defect Detection app (MQTT)
5. Runs full security scan suite

### Security Scans Workflow
- **Trivy FS Scan** — Repository vulnerability scanning
- **Trivy Image Scan** — Docker image CVE scanning with SPDX SBOMs
- **Trivy Config/Helm Scan** — Infrastructure-as-code scanning
- **Bandit** — Python security analysis
- **ClamAV** — Virus/malware scanning
- **Docker Bench Security** — Container runtime security
- **CodeQL** — Static application security testing
- **Pylint** — Python code quality

### Tests Workflow
- Runs daily at 14:00 UTC and on-demand
- Deploys both Docker and Helm (k3s) test environments
- Generates HTML and JUnit XML test reports

### Documentation
- Sphinx-based documentation in `docs/user-guide/`
- Triggered on PR changes to docs directories
- Uses a shared template from Intel's documentation platform

## Security Requirements

1. **No hardcoded credentials** — Use `.env` files with environment variable substitution.
2. **Container hardening** — Non-root, read-only FS, dropped capabilities, `no-new-privileges`.
3. **Network isolation** — Docker bridge networks and Helm NetworkPolicies.
4. **SSL/TLS** — nginx generates self-signed certs; OPC-UA supports TLS encryption.
5. **Input validation** — Environment variables are validated (length, character set, not `admin`).
6. **Dependency pinning** — All Python packages and Docker base images use exact versions.

## Pull Request Guidelines

Follow the [PR template](.github/PULL_REQUEST_TEMPLATE.md):
1. Describe changes and link to related issues.
2. List any new third-party dependencies with license information.
3. Describe how changes were tested.
4. Confirm: Apache-2.0 license agreement, no incompatible dependencies, no confidential information, self-review completed.

## Documentation Standards

- All user-facing docs go in `docs/user-guide/`.
- Use Markdown format compatible with Sphinx documentation builder.
- Include diagrams/screenshots in `docs/user-guide/_assets/`.
- Update `CHANGELOG.md` for every release with categorized entries (Added, Changed, Fixed, Security).
