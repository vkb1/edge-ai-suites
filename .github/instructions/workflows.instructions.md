# GitHub Actions Workflows — Copilot Instructions

applyTo:
  - ".github/workflows/**"

## Workflow Standards

### Action Pinning

All GitHub Actions **must** be pinned by full commit SHA with a version comment:

```yaml
uses: actions/checkout@8e8c483db84b4bee98b60c0593521ed34d9990e8 # v6.0.1
```

Never use tag-only references like `actions/checkout@v4`. Zizmor scanning will flag unpinned actions as HIGH severity findings.

### Credentials & Secrets

- Set `persist-credentials: false` on all `actions/checkout` steps
- Never log or echo secrets in workflow steps
- Generate random credentials in CI using `/dev/urandom` and `openssl rand` — never use static test credentials
- Use `${{ secrets.GITHUB_TOKEN }}` only where required and with minimal scope

### Permissions

Follow the principle of least privilege. Always declare explicit permissions:

```yaml
permissions:
  contents: read
  packages: read
  pull-requests: read
  security-events: write   # only if uploading SARIF results
```

Use `permissions: {}` at the workflow level and override per-job when possible.

### Concurrency

Use concurrency controls to prevent duplicate runs:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event_name == 'pull_request' && github.event.pull_request.number || github.sha }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

### Runner

Use `ubuntu-24.04` as the standard runner for all jobs unless a specific OS is required.

### Naming Conventions

- Workflow name: `"[Suite Name Component] Action Type"` (e.g., `"[Industrial Edge Insights Multimodal and Time Series] SDLe Scans"`)
- Run name: Include actor and event: `"... (by @${{ github.actor }} via ${{ github.event_name }})"` 
- File naming: `component-name-action.yaml` or `component-name-action.yml`

### Triggers

Standard trigger patterns used in this repository:

```yaml
# PR workflow — trigger on path changes
on:
  pull_request:
    paths:
      - 'manufacturing-ai-suite/industrial-edge-insights-multimodal/**'
  workflow_call:
  workflow_dispatch:

# Scan workflow — dispatch with scan selection
on:
  workflow_dispatch:
    inputs:
      target:
        description: 'Which Scans to run'
        type: choice
        options:
          - all-scans
          - trivy-fs-scan
          - trivy-image-scan
          # ...

# Scheduled test workflow
on:
  schedule:
    - cron: '0 14 * * *'  # 14:00 UTC daily
  workflow_dispatch:
```

### Required Scans

Every application must have these security scans configured:

| Scan | Tool | Purpose |
|------|------|---------|
| Filesystem scan | Trivy | Scan repo files for vulnerabilities |
| Image scan | Trivy | Scan built Docker images |
| Config scan | Trivy | Scan IaC configurations |
| Dockerfile scan | Trivy | Lint and scan Dockerfiles |
| Helm scan | Trivy | Scan Helm chart templates |
| Python static analysis | Bandit | Security-focused Python linting |
| Code quality | CodeQL | GitHub's semantic code analysis |
| Python lint | Pylint | Code quality and style |
| Workflow security | Zizmor | GitHub Actions security analysis |
| Virus scan | ClamAV or equivalent | Malware detection |

### Docker Build Patterns in CI

When building Docker images in CI:

```yaml
- name: Building Multimodal Sample App
  run: |
    cd ./path/to/app
    make down
    # Generate random credentials - NEVER use static values
    INFLUXDB_USERNAME=$(cat /dev/urandom | tr -dc 'a-zA-Z' | head -c 8)
    base=$(tr -dc 'a-zA-Z' </dev/urandom | head -c9)
    digit=$(tr -dc '0-9' </dev/urandom | head -c1)
    pos=$((RANDOM % 10))
    INFLUXDB_PASSWORD=${base:0:$pos}${digit}${base:$pos}
    # Update .env with generated values
    sed -i "s/INFLUXDB_USERNAME=.*/INFLUXDB_USERNAME=${INFLUXDB_USERNAME}/g" .env
    make build
```

### Reusable Workflows

Use `workflow_call` for shared scan/test logic:

```yaml
# In the calling workflow
jobs:
  scans:
    uses: ./.github/workflows/component-scans.yml
    with:
      target: all-scans
```

### Artifacts

Upload test reports and scan results as artifacts:

```yaml
- uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
  with:
    name: test-reports
    path: '*.html'
    retention-days: 30
```

## Workflow Types in This Repository

1. **PR Workflows** (`*-pull-request.yml`): Build and deploy validation on pull requests
2. **Scan Workflows** (`*-scans.yml`): Security scanning (Trivy, Bandit, CodeQL, Pylint, Zizmor)
3. **Test Workflows** (`*-tests.yml`): Functional tests (Docker Compose and Helm deployments)
4. **Documentation Workflows** (`documentation-check.yaml`): Docs build validation
5. **Weekly Packaging** (`*-weekly-package-helm.yaml`): Periodic Helm chart packaging
6. **Tag Workflows** (`*-weekly-tag.yaml`): Release tagging

## When Creating New Workflows

1. Add the SPDX license header at the top of the file
2. Pin all actions by commit SHA
3. Set `persist-credentials: false` on all checkout steps
4. Declare minimal `permissions` at workflow and job level
5. Add concurrency control for PR workflows
6. Include `workflow_dispatch` for manual triggering
7. Use `continue-on-error: true` only for scans that should not block the pipeline
8. Clean up Docker resources at the start of jobs to avoid runner disk issues
9. Update `.github/CODEOWNERS` if adding component-specific workflows
