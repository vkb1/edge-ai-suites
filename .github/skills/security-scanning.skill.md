# Security Scanning Skill — Edge AI Suites
# Provides guidance on running and interpreting security scans.

name: "security-scanning"
description: >
  Run and interpret security scans for Edge AI Suite applications including
  Trivy, Bandit, CodeQL, Pylint, and Zizmor.

instructions: |
  ## Security Scanning Skill

  This skill helps run and interpret security scans for the Edge AI Suites project.

  ### Trivy Scans

  **Filesystem Scan** — Scans the repository source code for vulnerabilities:
  ```bash
  trivy fs --severity HIGH,CRITICAL --format table <path>
  ```

  **Docker Image Scan** — Scans built container images:
  ```bash
  trivy image --severity HIGH,CRITICAL --format table <image:tag>
  ```

  **Dockerfile Scan** — Lints and scans Dockerfiles for misconfigurations:
  ```bash
  trivy config --file-patterns "Dockerfile" --severity HIGH,CRITICAL <path>
  ```

  **Helm Chart Scan** — Scans Helm chart templates:
  ```bash
  trivy config --severity HIGH,CRITICAL <helm-chart-path>
  ```

  **Configuration Scan** — Scans IaC configuration files:
  ```bash
  trivy config --severity HIGH,CRITICAL <path>
  ```

  ### Bandit (Python Static Security Analysis)

  ```bash
  bandit -r <python-source-path> -f json -o bandit-report.json
  ```

  Common findings to address:
  - B101: Use of assert (remove from production code)
  - B105/B106/B107: Hardcoded passwords
  - B108: Insecure temporary file/directory
  - B301: pickle usage
  - B608: SQL injection
  - B602: subprocess with shell=True

  ### CodeQL

  CodeQL analysis runs in CI via GitHub's built-in integration. To set up:
  ```yaml
  - uses: github/codeql-action/init@v3
    with:
      languages: python
  - uses: github/codeql-action/analyze@v3
  ```

  ### Pylint (Python Code Quality)

  ```bash
  pylint --output-format=json <python-files> > pylint-report.json
  ```

  ### Zizmor (GitHub Actions Security)

  Zizmor scans workflow files for security issues:
  - Unpinned actions (use commit SHA instead of tags)
  - Missing `persist-credentials: false`
  - Overly broad permissions
  - Script injection via untrusted inputs

  ### Interpreting Results

  **Severity Levels:**
  - CRITICAL: Must fix before merge
  - HIGH: Must fix before merge (for PR scans)
  - MEDIUM: Should fix; create a follow-up issue if deferred
  - LOW: Best effort; informational on scheduled scans

  ### Key Docker Images to Scan

  For the multimodal application:
  - `intel/ia-time-series-analytics-microservice:<tag>`
  - `intel/ia-weld-data-simulator:<tag>`
  - `intel/ia-multimodal-fusion-analytics:<tag>`
  - `intel/dlstreamer-pipeline-server:2026.0.0-ubuntu24`
  - `grafana/grafana-oss:12.4.0-ubuntu`
  - `influxdb:1.12.2`
  - `eclipse-mosquitto:2.0.22`
  - `nginx:1.29.5-trixie-perl`
  - `chrislusf/seaweedfs:4.15`
  - `coturn/coturn:4.9.0`
  - `bluenviron/mediamtx:1.16.3`
