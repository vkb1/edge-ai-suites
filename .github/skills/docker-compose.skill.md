# Docker & Compose Skill — Edge AI Suites
# Provides guidance on Docker and Docker Compose development patterns.

name: "docker-compose"
description: >
  Assist with Docker Compose service definitions, Dockerfile best practices,
  and container deployment for the Edge AI Suites multimodal application.

instructions: |
  ## Docker & Compose Skill

  This skill helps with Docker and Docker Compose development for Edge AI Suites.

  ### Dockerfile Conventions

  **Base Image:**
  ```dockerfile
  FROM python:3.13-slim
  ```

  **Non-Root User Setup:**
  ```dockerfile
  ARG TIMESERIES_UID
  ARG TIMESERIES_USER_NAME
  RUN groupadd $TIMESERIES_USER_NAME -g $TIMESERIES_UID && \
      useradd -r -u $TIMESERIES_UID -g $TIMESERIES_USER_NAME $TIMESERIES_USER_NAME
  USER $TIMESERIES_USER_NAME
  ```

  **Copyleft Source Support:**
  ```dockerfile
  ARG COPYLEFT_SOURCES=false
  RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        # Download sources for packages with copyleft licenses
        mkdir -p /python-licenses && cd /python-licenses && \
        pip3 freeze | cut -d= -f1 | while read pkg; do \
          meta=$(pip3 show $pkg 2>/dev/null); \
          lic=$(echo "$meta" | grep -i '^License:' | grep -Ei 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
          if [ ! -z "$lic" ]; then pip3 download --no-binary :all: $pkg || true; fi; \
        done; \
      fi
  ```

  **Health Check:**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:8080/health || exit 1
  ```

  ### Docker Compose Service Template

  ```yaml
  services:
    ia-new-service:
      image: ${NEW_SERVICE_IMAGE}:${IMAGE_SUFFIX}
      container_name: ia-new-service
      hostname: ia-new-service
      build:
        context: ./new-service
        args:
          TIMESERIES_UID: ${TIMESERIES_UID}
          TIMESERIES_USER_NAME: ${TIMESERIES_USER_NAME}
      read_only: true
      security_opt:
        - no-new-privileges:true
      user: "${TIMESERIES_UID}:${TIMESERIES_UID}"
      environment:
        - MQTT_BROKER=ia-mqtt-broker
        - LOG_LEVEL=${LOG_LEVEL:-INFO}
      depends_on:
        ia-mqtt-broker:
          condition: service_healthy
      networks:
        - timeseries_network
      volumes:
        - new_service_data:/data:rw
      restart: unless-stopped

  volumes:
    new_service_data:
      driver_opts:
        type: tmpfs
        device: tmpfs
  ```

  ### Key Environment Variables

  | Variable | Default | Description |
  |----------|---------|-------------|
  | `COMPOSE_PROJECT_NAME` | timeseriessoftware | Docker Compose project name |
  | `TIMESERIES_UID` | 2999 | Non-root user ID |
  | `TIMESERIES_USER_NAME` | timeseries_user | Non-root username |
  | `IMAGE_SUFFIX` | 2026.1.0 | Docker image tag suffix |
  | `HOST_IP` | (must be set) | Host machine IPv4 address |
  | `DRI_MOUNT_PATH` | auto-detected | GPU device path |
  | `FUSION_MODE` | OR | Fusion logic: AND or OR |
  | `TOLERANCE_NS` | 50000000 | Timestamp matching tolerance (ns) |

  ### Network Configuration

  All services join `timeseries_network` (bridge driver):
  ```yaml
  networks:
    timeseries_network:
      driver: bridge
  ```

  ### Common Troubleshooting

  **Container won't start:**
  ```bash
  docker compose logs ia-service-name
  docker compose ps -a
  ```

  **MQTT connectivity:**
  ```bash
  docker exec ia-mqtt-broker mosquitto_sub -t '#' -v
  ```

  **InfluxDB data check:**
  ```bash
  docker exec ia-influxdb influx -username $USER -password $PASS -database datain -execute "SHOW MEASUREMENTS"
  ```

  **Rebuild single service:**
  ```bash
  docker compose build --no-cache ia-service-name
  docker compose up -d ia-service-name
  ```
