# Testing Skill — Edge AI Suites
# Provides guidance on writing and running functional tests.

name: "testing"
description: >
  Assist with writing pytest-based functional tests for Docker Compose
  and Helm deployments of Edge AI Suite applications.

instructions: |
  ## Testing Skill

  This skill helps write and run functional tests for Edge AI Suites.

  ### Test Framework

  - **Framework**: pytest with pytest-html for HTML reports
  - **Browser testing**: Playwright for Grafana dashboard validation
  - **MQTT testing**: paho-mqtt client for broker connectivity
  - **InfluxDB testing**: influxdb-client for data validation
  - **HTTP testing**: requests and aiohttp for API endpoints

  ### Test Structure

  ```
  tests/
  ├── requirements.txt                        # Test dependencies
  ├── README.md                               # Test instructions
  └── functional/
      ├── pytest.ini                           # pytest configuration
      ├── test_docker_deployment_multimodal.py # Docker Compose tests
      └── test_helm_deployment_multimodal.py   # Helm deployment tests
  ```

  ### Running Tests

  ```bash
  cd manufacturing-ai-suite/industrial-edge-insights-multimodal/tests
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt

  # Docker Compose deployment tests
  pytest -v -s --html=docker_multimodal_report.html functional/test_docker_deployment_multimodal.py

  # Helm deployment tests
  pytest -v -s --html=helm_multimodal_report.html functional/test_helm_deployment_multimodal.py
  ```

  ### Writing Tests

  **Test naming**: `test_<deployment_type>_<what_is_tested>`

  **Example test structure**:
  ```python
  #
  # Apache v2 license
  # Copyright (C) 2025 Intel Corporation
  # SPDX-License-Identifier: Apache-2.0
  #

  import pytest
  import subprocess
  import time
  import paho.mqtt.client as mqtt

  class TestDockerDeploymentMultimodal:
      """Functional tests for Docker Compose multimodal deployment."""

      @pytest.fixture(autouse=True)
      def setup(self):
          """Setup: ensure deployment is running."""
          # Verify all expected containers are healthy
          pass

      def test_containers_running(self):
          """Verify all 13+ containers are running."""
          result = subprocess.run(
              ["docker", "ps", "--format", "{{.Names}}"],
              capture_output=True, text=True
          )
          expected = ["ia-telegraf", "ia-influxdb", "ia-mqtt-broker",
                       "ia-grafana", "ia-fusion-analytics", "nginx"]
          for name in expected:
              assert name in result.stdout

      def test_mqtt_broker_connectivity(self):
          """Verify MQTT broker accepts connections."""
          client = mqtt.Client()
          client.connect("localhost", 1883, 60)
          client.disconnect()

      def test_influxdb_data_ingestion(self):
          """Verify data flows into InfluxDB."""
          # Query InfluxDB for expected measurements
          pass

      def test_grafana_dashboard(self):
          """Verify Grafana dashboard is accessible via nginx proxy."""
          import requests
          resp = requests.get("https://localhost:15443", verify=False)
          assert resp.status_code == 200

      def test_fusion_mode_or(self):
          """Verify OR fusion mode triggers on single source anomaly."""
          pass

      def test_s3_storage(self):
          """Verify SeaweedFS S3 bucket is created and accessible."""
          pass
  ```

  ### Test Dependencies (tests/requirements.txt)

  ```
  pytest==9.0.2
  pytest-html==4.2.0
  pytest-env==1.6.0
  requests==2.33.0
  playwright==1.58.0
  aiohttp==3.13.3
  paho-mqtt==2.1.0
  influxdb-client==1.50.0
  ruamel.yaml==0.19.1
  PyYAML==6.0.3
  pandas==2.2.3
  ```

  ### Best Practices

  - Tests must be independent and idempotent
  - Use generous timeouts for container startup (30-60 seconds)
  - Clean up resources in teardown fixtures
  - Test both positive and negative scenarios
  - Include tests for credential validation (invalid passwords should fail)
  - Generate HTML reports with `--html` flag
  - Use `pytest.mark.parametrize` for testing multiple configurations
  - Mark long-running tests (1+ hour) with `@pytest.mark.slow`
