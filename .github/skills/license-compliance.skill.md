# License Compliance Skill — Edge AI Suites
# Provides guidance on license headers, third-party tracking, and compliance.

name: "license-compliance"
description: >
  Ensure license compliance for the Edge AI Suites project including
  Apache 2.0 headers, third-party license tracking, copyleft source
  handling, and Developer Certificate of Origin (DCO) requirements.

instructions: |
  ## License Compliance Skill

  This skill ensures all contributions meet Intel's licensing and compliance requirements.

  ### Apache 2.0 License Headers

  **Python files:**
  ```python
  #
  # Apache v2 license
  # Copyright (C) 2025 Intel Corporation
  # SPDX-License-Identifier: Apache-2.0
  #
  ```

  **YAML / workflow files:**
  ```yaml
  # SPDX-FileCopyrightText: (C) 2025 Intel Corporation
  # SPDX-License-Identifier: Apache-2.0
  ```

  **Dockerfile / Makefile / Shell scripts:**
  ```dockerfile
  #
  # Apache v2 license
  # Copyright (C) 2025 Intel Corporation
  # SPDX-License-Identifier: Apache-2.0
  #
  ```

  ### Third-Party License Tracking

  All third-party dependencies must be documented in `third-party-programs.txt`:

  **Docker images format:**
  ```
  Docker Image: <image:tag>
  License: <license-type>
  URL: <source-url>
  ```

  **Python packages format:**
  ```
  Package: <name>==<version>
  License: <license-type>
  ```

  ### Compatible Licenses

  The following licenses are compatible with Apache 2.0:
  - MIT
  - BSD (2-clause, 3-clause)
  - Apache 2.0
  - ISC
  - PSF (Python Software Foundation)
  - HPND (Historical Permission Notice and Disclaimer)
  - Unlicense

  ### Requires Review

  These licenses require additional review before inclusion:
  - EPL (Eclipse Public License) — May be compatible depending on usage
  - MPL (Mozilla Public License) — File-level copyleft, generally compatible
  - LGPL — Dynamic linking usually acceptable, static requires source sharing

  ### Incompatible Licenses

  These licenses are **NOT compatible** with Apache 2.0 for derived works:
  - GPL v2/v3 (unless the entire project relicenses)
  - AGPL
  - SSPL
  - Creative Commons NonCommercial/NoDerivatives

  Note: AGPLv3 dependencies (e.g., Grafana) are acceptable when used as
  separate services (not compiled/linked into Apache 2.0 code). The project
  does include Grafana (AGPLv3) as a standalone service container.

  ### Copyleft Source Download

  For copyleft-licensed dependencies, Dockerfiles support building with source:
  ```bash
  make build_copyleft_sources   # Builds with COPYLEFT_SOURCES=true
  ```

  This downloads source code for packages with MPL, GPL, LGPL, EPL, or CDDL licenses.

  ### Developer Certificate of Origin (DCO)

  All commits must be signed off:
  ```
  Signed-off-by: Your Name <your.name@email.com>
  ```

  Use: `git commit -s` to auto-sign.

  ### PR Checklist (from template)

  - [ ] I agree to use the APACHE-2.0 license for my code changes
  - [ ] I have not introduced any 3rd party components incompatible with APACHE-2.0
  - [ ] I have not included any company confidential information, trade secret, password or security token
  - [ ] I have performed a self-review of my code

  ### When Adding New Dependencies

  1. Check the dependency license compatibility
  2. Add entry to `third-party-programs.txt`
  3. Pin the exact version in requirements.txt
  4. If copyleft, ensure Dockerfile COPYLEFT_SOURCES block handles it
  5. Document in the PR under "Any Newly Introduced Dependencies"
