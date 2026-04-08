# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Trivy SPDX-JSON image scanner.

Runs ``trivy image --list-all-pkgs --format spdx-json`` for one or more
container images and writes the results to individual JSON files named
``trivy-spdx-<sanitized-image-name>.json``.

Usage examples
--------------
Scan a single image::

    python trivy_spdx_scan.py ubuntu:22.04

Scan multiple images::

    python trivy_spdx_scan.py ubuntu:22.04 nginx:1.27-alpine

Read images from a docker-compose file and scan them::

    python trivy_spdx_scan.py --compose-file docker-compose.yml

Combine both sources::

    python trivy_spdx_scan.py ubuntu:22.04 --compose-file docker-compose.yml

Specify a custom output directory (default: current working directory)::

    python trivy_spdx_scan.py --output-dir ./security-results ubuntu:22.04
"""

import argparse
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_image_name(image: str) -> str:
    """Return a filesystem-safe version of *image* suitable for use in a filename.

    Slashes, colons and other special characters are replaced with underscores.
    Leading/trailing underscores are stripped so the result looks tidy.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", image)
    sanitized = sanitized.strip("_")
    return sanitized


def _images_from_compose(compose_file: str) -> list[str]:
    """Parse *compose_file* and return the list of concrete image names.

    Images whose value starts with ``$`` (environment variable references) are
    skipped with a warning because they cannot be resolved without a running
    environment.
    """
    try:
        import yaml  # optional – only needed for --compose-file
    except ImportError:
        logger.error(
            "PyYAML is required to parse docker-compose files. "
            "Install it with: pip install pyyaml"
        )
        sys.exit(1)

    compose_path = Path(compose_file)
    if not compose_path.is_file():
        logger.error("Compose file not found: %s", compose_file)
        sys.exit(1)

    with compose_path.open() as fh:
        data = yaml.safe_load(fh)

    services = data.get("services", {}) if data else {}
    images: list[str] = []
    for service_name, service_cfg in services.items():
        if not isinstance(service_cfg, dict):
            continue
        image = service_cfg.get("image")
        if not image:
            continue
        if image.startswith("$"):
            logger.warning(
                "Skipping service '%s' – image value is an unresolved "
                "environment variable: %s",
                service_name,
                image,
            )
            continue
        images.append(image)

    return images


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Matches standard Docker image reference format:
#   [registry/][namespace/]name[:tag][@digest]
# where each component uses only alphanumeric characters, dots, hyphens,
# underscores, slashes, colons and the '@' for digest references.
_VALID_IMAGE_RE = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9._\-/:@]*$"
)


def _validate_image_name(image: str) -> None:
    """Raise ``ValueError`` if *image* does not look like a valid Docker image reference."""
    if not _VALID_IMAGE_RE.match(image):
        raise ValueError(
            f"Invalid image name {image!r}. "
            "Image names must match the pattern: "
            "[registry/][namespace/]name[:tag][@digest]"
        )


# ---------------------------------------------------------------------------
# Core scan logic
# ---------------------------------------------------------------------------

def scan_image(image: str, output_dir: Path) -> bool:
    """Run a trivy SPDX-JSON scan for *image*.

    The output file is written to *output_dir* and named
    ``trivy-spdx-<sanitized-image-name>.json``.

    Returns ``True`` on success, ``False`` if the scan failed.
    """
    try:
        _validate_image_name(image)
    except ValueError as exc:
        logger.error("%s", exc)
        return False

    output_filename = f"trivy-spdx-{_sanitize_image_name(image)}.json"
    output_path = output_dir / output_filename

    cmd = [
        "trivy",
        "image",
        "--list-all-pkgs",
        "--format", "spdx-json",
        "--output", str(output_path),
        image,
    ]

    logger.info("Scanning image: %s", image)
    logger.info("Output file   : %s", output_path)
    logger.info("Command       : %s", " ".join(cmd))

    result = subprocess.run(cmd, check=False)  # nosec B603 – cmd is a list (no shell), image validated above

    if result.returncode != 0:
        logger.error(
            "Trivy scan FAILED for image '%s' (exit code %d)",
            image,
            result.returncode,
        )
        return False

    logger.info("Trivy scan PASSED for image '%s' -> %s", image, output_path)
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run 'trivy image --list-all-pkgs --format spdx-json' for one or "
            "more container images and save the results as JSON files."
        )
    )
    parser.add_argument(
        "images",
        nargs="*",
        metavar="IMAGE",
        help="Container image(s) to scan, e.g. ubuntu:22.04",
    )
    parser.add_argument(
        "--compose-file",
        metavar="FILE",
        help=(
            "Path to a docker-compose YAML file. All services that specify a "
            "concrete 'image' value will be scanned."
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=".",
        help=(
            "Directory where the SPDX JSON report files are written "
            "(default: current working directory)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    images: list[str] = list(args.images)

    if args.compose_file:
        compose_images = _images_from_compose(args.compose_file)
        logger.info(
            "Found %d image(s) in compose file '%s': %s",
            len(compose_images),
            args.compose_file,
            compose_images,
        )
        images.extend(compose_images)

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique_images: list[str] = []
    for img in images:
        if img not in seen:
            seen.add(img)
            unique_images.append(img)

    if not unique_images:
        logger.error(
            "No images to scan. Provide at least one IMAGE argument or use "
            "--compose-file."
        )
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, bool] = {}
    for image in unique_images:
        results[image] = scan_image(image, output_dir)

    # Summary
    passed = [img for img, ok in results.items() if ok]
    failed = [img for img, ok in results.items() if not ok]

    logger.info("=" * 60)
    logger.info("Scan summary: %d passed, %d failed", len(passed), len(failed))
    for img in passed:
        logger.info("  PASS: %s", img)
    for img in failed:
        logger.error("  FAIL: %s", img)
    logger.info("=" * 60)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
