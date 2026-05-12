# Helm Chart Skill — Edge AI Suites
# Provides guidance on Helm chart development and deployment.

name: "helm-charts"
description: >
  Assist with Helm chart development, packaging, and deployment
  for the Edge AI Suites Kubernetes deployments.

instructions: |
  ## Helm Chart Skill

  This skill helps with Helm chart development for Edge AI Suites.

  ### Chart Structure

  ```
  helm/
  ├── Chart.yaml              # Chart metadata with date-based versioning
  ├── values.yaml             # Default configuration values
  ├── values.schema.json      # JSON Schema for values validation
  ├── README.md               # Deployment instructions
  └── templates/
      ├── NOTES.txt            # Post-install instructions
      ├── broker.yaml          # MQTT broker (Mosquitto)
      ├── coturn.yaml          # WebRTC TURN server
      ├── dlstreamer-pipeline-server.yaml
      ├── fusion-analytics.yaml
      ├── grafana.yaml         # Visualization
      ├── influxdb.yaml        # Time-series database
      ├── mediamtx.yaml        # RTSP/WebRTC server
      ├── network-policy.yaml  # Network security
      ├── nginx.yaml           # Reverse proxy
      ├── provision-configmap.yaml
      ├── seaweedfs-filer.yaml
      ├── seaweedfs-master.yaml
      ├── seaweedfs-s3.yaml    # S3 storage
      ├── seaweedfs-volume.yaml
      ├── telegraf.yaml        # Data collection
      ├── time-series-analytics-microservice.yaml
      └── weld-data-simulator.yaml
  ```

  ### Versioning

  Date-based versioning format: `2026.0`, `2026.1.0`

  For weekly builds: `2026.1.0-YYYYMMDD-weekly`

  Update in Chart.yaml:
  ```yaml
  version: 2026.1.0
  appVersion: "2026.1.0"
  ```

  ### Generating Helm Packages

  ```bash
  # Generate Helm chart with config files
  make gen_helm_charts

  # Package and push to registry
  make push_helm_charts
  ```

  The `gen_helm_charts` target copies configuration files into the helm directory
  and updates version strings in Chart.yaml and values.yaml.

  ### Values Schema Validation

  All user-facing values should be validated in `values.schema.json`:
  ```json
  {
    "properties": {
      "influxdb": {
        "properties": {
          "username": {
            "type": "string",
            "minLength": 5,
            "pattern": "^[A-Za-z]+$"
          },
          "password": {
            "type": "string",
            "minLength": 10,
            "pattern": "^[A-Za-z0-9]+$"
          }
        }
      }
    }
  }
  ```

  ### Deployment

  ```bash
  # Install chart
  helm install multimodal-weld ./helm -f helm/values.yaml

  # Upgrade existing release
  helm upgrade multimodal-weld ./helm -f helm/values.yaml

  # Validate templates
  helm template multimodal-weld ./helm -f helm/values.yaml

  # Lint chart
  helm lint ./helm
  ```

  ### Security Considerations

  - Use Kubernetes security contexts (non-root, read-only root filesystem)
  - Configure network policies to restrict inter-pod communication
  - Use Kubernetes secrets for credentials (not ConfigMaps)
  - Set resource limits on all containers
  - Use image pull policies appropriate for the environment
