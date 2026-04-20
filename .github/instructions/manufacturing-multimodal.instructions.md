# Industrial Edge Insights Multimodal — Copilot Instructions

applyTo:
  - "manufacturing-ai-suite/industrial-edge-insights-multimodal/**"

## Component Overview

This sample application performs **multimodal weld defect detection** by fusing vision-based defect classification with time-series anomaly detection. It uses MQTT for data ingestion, InfluxDB for storage, Grafana for visualization, and SeaweedFS for S3-compatible object storage.

## Architecture

```
RTSP Camera Feed → DL Streamer Pipeline Server → MQTT (vision_weld_defect_classification)
                                                          ↓
Sensor Data → Weld Data Simulator → MQTT (ts_weld_anomaly_detection)
                                                          ↓
                                              Fusion Analytics Module
                                                   (AND/OR logic)
                                                          ↓
                                               InfluxDB + Grafana
```

### Key Services (13+ containers)

| Service | Image/Base | Purpose |
|---------|-----------|---------|
| `ia-telegraf` | telegraf:1.38.0 | MQTT→InfluxDB data bridge |
| `ia-influxdb` | influxdb:1.12.2 | Time-series database |
| `ia-time-series-analytics-microservice` | Intel custom | Kapacitor-based anomaly detection |
| `ia-grafana` | grafana-oss:12.4.0-ubuntu | Visualization dashboards |
| `ia-mqtt-broker` | eclipse-mosquitto:2.0.22 | MQTT message broker |
| `ia-weld-data-simulator` | Intel custom | RTSP + MQTT data publisher |
| `nginx` | nginx:1.29.5-trixie-perl | Reverse proxy (HTTPS on 15443) |
| `ia-fusion-analytics` | Intel custom | Vision + TS fusion module |
| `dlstreamer-pipeline-server` | Intel DL Streamer | Video processing pipeline |
| `mediamtx` | mediamtx:1.16.3 | RTSP/WebRTC media server |
| `seaweedfs-*` | seaweedfs:4.15 | S3-compatible object storage |
| `coturn` | coturn:4.9.0 | TURN server for WebRTC |

## Development Patterns

### Fusion Analytics Module (`fusion-analytics/`)

- **Entry point**: `fusion.py` — subscribes to MQTT topics, performs timestamp-based message matching, writes fused results to InfluxDB
- **Fusion modes**: `AND` (both vision + TS must detect anomaly) or `OR` (either triggers alert)
- **Timestamp tolerance**: Configurable via `TOLERANCE_NS` (default 50ms = 50e6 ns)
- **Buffer management**: Rolling deque of 100/1000 messages per source
- **Dependencies**: paho-mqtt, pandas, numpy, influxdb (all pinned in `requirements.txt`)

### Weld Data Simulator (`weld-data-simulator/`)

- **Entry point**: `publisher.py` — publishes RTSP video streams and MQTT time-series data
- **Data source**: Intel Robotic Welding Multimodal Dataset
- **Modes**: Continuous (`CONTINUOUS_SIMULATOR_INGESTION=true`) or one-time ingestion
- **Dependencies**: opencv-python, paho-mqtt, pandas

### Configuration (`configs/`)

- `time-series-analytics-microservice/`: Pipeline config, UDF scripts, ML models (DeiT), Kapacitor tick scripts
- `grafana/`: Dashboard provisioning, data sources, weld defect detection dashboard JSON
- `dlstreamer-pipeline-server/`: Video pipeline configuration
- `mqtt-broker/`: Mosquitto configuration
- `telegraf/`: Input plugin configuration and entrypoint scripts
- `nginx/`: Reverse proxy and TLS certificate generation
- `seaweedfs-s3/`: S3 bucket configuration and initialization

### Environment Variables (`.env`)

Critical credentials that must be set before deployment:
- `INFLUXDB_USERNAME` / `INFLUXDB_PASSWORD` — InfluxDB credentials
- `VISUALIZER_GRAFANA_USER` / `VISUALIZER_GRAFANA_PASSWORD` — Grafana credentials
- `MTX_WEBRTCICESERVERS2_0_USERNAME` / `MTX_WEBRTCICESERVERS2_0_PASSWORD` — MediaMTX WebRTC
- `S3_STORAGE_USERNAME` / `S3_STORAGE_PASSWORD` — SeaweedFS S3 credentials
- `HOST_IP` — Must be set to a valid IPv4 address

**Validation rules** (enforced by Makefile):
- Usernames: 5+ alphabetic chars only; InfluxDB username must not be "admin"
- Passwords: 10+ alphanumeric chars with at least one digit and one letter

### Makefile Targets

| Target | Description |
|--------|-------------|
| `make build` | Build Docker containers with `--pull` |
| `make up` | Validate env, start containers, upload UDF config |
| `make down` | Stop containers, remove volumes |
| `make status` | Check container health and error logs |
| `make push_images` | Push images to Docker registry |
| `make gen_helm_charts` | Generate Helm packages |
| `make push_helm_charts` | Package and push Helm charts to OCI registry |

### Testing (`tests/`)

- **Docker tests**: `pytest -v -s --html=docker_multimodal_report.html test_docker_deployment_multimodal.py`
- **Helm tests**: `pytest -v -s --html=helm_multimodal_report.html test_helm_deployment_multimodal.py`
- Install test deps in venv: `pip install -r tests/requirements.txt`
- Tests validate: container health, MQTT connectivity, InfluxDB writes, Grafana dashboards, S3 storage

### Helm Deployment (`helm/`)

- Chart versioning follows date-based format: `2026.0`
- Templates for all 13+ services including network policies
- `values.yaml` contains all configurable parameters
- `values.schema.json` validates Helm values

## When Making Changes

1. **Add SPDX license headers** to every new file
2. **Pin dependency versions exactly** in requirements.txt
3. **Use non-root user** (UID 2999) in any new Dockerfile
4. **Set `read_only: true`** and `no-new-privileges` for new Docker Compose services
5. **Update `third-party-programs.txt`** if adding new dependencies
6. **Update `CHANGELOG.md`** for user-visible changes
7. **Update `docker-compose.yml`** service definitions if adding new containers
8. **Never commit credentials** — use `.env` variables and Makefile validation
9. **Test with both Docker Compose and Helm** deployment methods
10. **Ensure GPU fallback** works (DRI_MOUNT_PATH auto-detection for `/dev/dri` or `/dev/null`)
