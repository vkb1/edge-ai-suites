# Helm and Docker Operations Skill

## Description

This skill provides knowledge for building, deploying, and managing containerized applications using Docker Compose and Helm charts in the Edge AI Suites project, with a focus on the Industrial Edge Insights Time Series application.

## Instructions

### Docker Compose Stack

The `docker-compose.yml` defines these services:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `ia-telegraf` | telegraf:1.38.0 | Internal | Data collection from MQTT/OPC-UA |
| `ia-influxdb` | influxdb:1.12.2 | Internal | Time-series data storage |
| `ia-time-series-analytics-microservice` | Intel TSAM | 9092 | Kapacitor-based stream processing |
| `ia-grafana` | grafana-oss:12.4.0-ubuntu | 3000 | Visualization |
| `ia-mqtt-broker` | eclipse-mosquitto:2.0.22 | 1883 | MQTT message broker |
| `ia-opcua-server` | Custom (Python 3.13) | 4840 | OPC-UA data simulator |
| `ia-mqtt-publisher` | Custom (Python 3.13) | Internal | MQTT data simulator |
| `nginx` | nginx:1.29.5-trixie-perl | 15443 | Reverse proxy with SSL |

### Building Docker Images

```bash
# Standard build
make build

# Build with copyleft sources included
make build_copyleft_sources

# Push images to registry (configure DOCKER_REGISTRY in .env)
make push_images
```

**Build requirements:**
- Docker and Docker Compose installed
- Access to base images (Docker Hub)
- `edge-ai-libraries` repository checked out at `../edge-ai-libraries` for TSAM builds

### Docker Compose Deployment

```bash
# MQTT ingestion (wind turbine - default)
make up_mqtt_ingestion

# MQTT ingestion (weld defect detection)
make up_mqtt_ingestion app=weld-defect-detection

# OPC-UA ingestion (wind turbine only)
make up_opcua_ingestion app=wind-turbine-anomaly-detection

# Multi-stream deployment
make up_mqtt_ingestion app=wind-turbine-anomaly-detection num_of_streams=3

# With system metrics validation
make up_mqtt_ingestion INCLUDE=validation

# With benchmarking
make up_mqtt_ingestion number_of_data_points_per_stream=1000

# Stop and clean up
make down
```

### Docker Container Security

All containers follow these security practices:

```yaml
# Required security settings in docker-compose.yml
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
read_only: true
user: "2999:2999"  # timeseries_user
tmpfs:
  - /tmp
  - /run
```

**Volumes and filesystems:**
- `tmpfs` for performance-sensitive paths (InfluxDB config, Grafana, nginx)
- Named volumes only for persistent data (`grafana_data`)
- Read-only mounts for configuration files
- Network: `timeseries_network` (bridge mode)

### Helm Chart Operations

#### Chart Structure

```
helm/
├── Chart.yaml              # Chart metadata (name, version, appVersion)
├── values.yaml             # Configurable values
├── values.schema.json      # JSON Schema for values validation
├── README.md               # Deployment guide
└── templates/
    ├── NOTES.txt           # Post-install notes
    ├── broker.yaml         # MQTT broker deployment
    ├── grafana.yaml        # Grafana deployment
    ├── influxdb.yaml       # InfluxDB deployment
    ├── mqtt-publisher.yaml # MQTT publisher deployment
    ├── network-policy.yaml # Network policy rules
    ├── nginx.yaml          # nginx reverse proxy
    ├── opcua.yaml          # OPC-UA server deployment
    ├── provision-configmap.yaml  # Config provisioning
    ├── telegraf.yaml       # Telegraf deployment
    └── time-series-analytics-microservice.yaml  # TSAM deployment
```

#### Generate Helm Charts

```bash
# Generate chart for wind turbine app
make gen_helm_charts app=wind-turbine-anomaly-detection

# Generate chart for weld defect detection
make gen_helm_charts app=weld-defect-detection

# Package and push to registry
make push_helm_charts app=wind-turbine-anomaly-detection
```

**What `gen_helm_charts` does:**
1. Copies Grafana dashboard configs to `helm/`
2. Copies app-specific simulation data to `helm/simulation-data/`
3. Copies Telegraf, InfluxDB, MQTT, nginx configs to `helm/`
4. Updates `Chart.yaml` with app name and version
5. Updates `values.yaml` with app name and weekly build date

#### Deploy with Helm (k3s)

```bash
# Install k3s
curl -sfL https://get.k3s.io | sh -

# Load Docker images into k3s
docker save <image> | k3s ctr images import -

# Install the chart
helm install <release-name> ./helm \
  --set influxdbUsername=<user> \
  --set influxdbPassword=<pass> \
  --set grafanaUser=<user> \
  --set grafanaPassword=<pass>

# Check deployment
kubectl get pods
kubectl get svc
```

#### Helm Values Configuration

Key values in `values.yaml`:
- `SAMPLE_APP` — Application to deploy
- `influxdbUsername` / `influxdbPassword` — InfluxDB credentials
- `grafanaUser` / `grafanaPassword` — Grafana credentials
- `imageRegistry` — Docker image registry
- `imageSuffix` — Docker image version tag
- `continuousSimulatorIngestion` — Data loop mode
- `influxdbRetentionDuration` — Data retention period

### Networking

**Docker Compose:**
- All services on `timeseries_network` (bridge)
- nginx proxies: HTTPS (:15443) → Grafana (:3000), TSAM API
- nginx MQTT proxy: (:1883) → MQTT broker

**Helm/Kubernetes:**
- `network-policy.yaml` restricts traffic between pods
- Services expose ports via ClusterIP (internal) or NodePort (external)

### SSL/TLS Configuration

nginx generates self-signed certificates automatically:
- Script: `configs/nginx/nginx-cert-gen.sh`
- Certificates stored in nginx container
- HSTS and security headers configured in `nginx.conf`
- OPC-UA supports TLS encryption for secure connections

### Troubleshooting Docker/Helm Deployments

```bash
# Check all container statuses
make status

# View specific container logs
docker logs ia-time-series-analytics-microservice
docker logs ia-telegraf
docker logs ia-influxdb

# Check for port conflicts
ss -tlnp | grep -E '3000|1883|9092|15443'

# Verify Docker Compose config
docker compose config

# Helm debugging
helm template ./helm --debug
helm lint ./helm
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

### Common Issues and Solutions

| Issue | Solution |
|-------|---------|
| TSAM not starting | Check `docker logs ia-time-series-analytics-microservice` for errors |
| "Kapacitor Tasks Enabled Successfully" not appearing | Verify UDF tar upload and config.json POST succeeded |
| InfluxDB authentication failure | Ensure `INFLUXDB_USERNAME` ≠ `admin` and ≥ 5 chars |
| No data in Grafana | Check Telegraf → InfluxDB connection and data source config |
| Helm install fails | Run `helm lint ./helm` and check `values.schema.json` |
| Multi-stream not working | Verify `generate-telegraf-config.py` ran and `Telegraf_multi_stream.conf` exists |
| Permission denied on .env | Run `chmod 600 .env helm/values.yaml` |
