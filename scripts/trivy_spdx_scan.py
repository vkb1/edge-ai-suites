# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Trivy SPDX-JSON image scanner.

Runs ``trivy image --list-all-pkgs --format spdx-json`` for one or more
container images and writes the results to individual JSON files named
``trivy-spdx-<sanitized-image-name>.json``.

When a Dockerfile or explicit base image is supplied the script also produces
a *delta* SPDX file (``trivy-spdx-<name>-delta.json``) that contains only the
packages present in the scanned image but **not** in the base image.  Any
packages downloaded via ``curl``/``wget`` inside Dockerfile ``RUN`` layers are
extracted from the Dockerfile and injected into both SPDX outputs.

Usage examples
--------------
Scan a single image::

    python trivy_spdx_scan.py ubuntu:22.04

Scan multiple images::

    python trivy_spdx_scan.py ubuntu:22.04 nginx:1.27-alpine

Read images from a plain-text or YAML config file::

    python trivy_spdx_scan.py --conf-file images.txt
    python trivy_spdx_scan.py --conf-file images.yaml  # must have 'images:' list key

Read images from a docker-compose file::

    python trivy_spdx_scan.py --compose-file docker-compose.yml

Supply a Dockerfile to extract the base image and curl/wget downloads::

    python trivy_spdx_scan.py myapp:latest --dockerfile path/to/Dockerfile

Provide an explicit base image for the delta report::

    python trivy_spdx_scan.py myapp:latest --base-image ubuntu:22.04

Specify a custom output directory (default: current working directory)::

    python trivy_spdx_scan.py --output-dir ./security-results ubuntu:22.04
"""

import argparse
import copy
import json
import logging
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image-list helpers
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
        import yaml  # optional – only needed for YAML sources
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


def _images_from_conf_file(conf_file: str) -> list[str]:
    """Read an image list from a plain-text or YAML config file.

    *Plain-text* files (any extension other than ``.yaml``/``.yml``): one
    Docker image reference per line.  Blank lines and lines starting with
    ``#`` are ignored.

    *YAML* files (``.yaml``/``.yml``): must contain a top-level ``images``
    key whose value is a list of image reference strings, e.g.::

        images:
          - ubuntu:22.04
          - nginx:1.27-alpine
    """
    conf_path = Path(conf_file)
    if not conf_path.is_file():
        logger.error("Config file not found: %s", conf_file)
        sys.exit(1)

    if conf_path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            logger.error(
                "PyYAML is required for YAML config files. "
                "Install it with: pip install pyyaml"
            )
            sys.exit(1)
        with conf_path.open() as fh:
            data = yaml.safe_load(fh)
        if not data or "images" not in data:
            logger.warning(
                "Config file '%s' has no 'images' key – no images loaded.",
                conf_file,
            )
            return []
        entries = data["images"]
        if not isinstance(entries, list):
            logger.error("'images' key in '%s' must be a YAML list.", conf_file)
            sys.exit(1)
        return [str(e) for e in entries if e]
    else:
        # Plain-text: one image per line, # starts a comment
        images: list[str] = []
        with conf_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    images.append(line)
        return images


# ---------------------------------------------------------------------------
# Dockerfile parsing
# ---------------------------------------------------------------------------

# Matches http(s):// and ftp:// URLs; stops at whitespace and shell metacharacters.
# The character class deliberately excludes quotes, backslash, semicolons,
# pipe/redirect/grouping characters and square brackets so the regex
# naturally terminates before shell operands without needing post-strip heuristics.
_URL_RE = re.compile(r"(?:https?|ftp)://[^\s\"'\\;|&><)([\]]+")


def _extract_urls_from_run(run_body: str) -> list[str]:
    """Return URLs that appear as arguments to ``curl`` or ``wget`` commands
    inside a single (already joined) RUN instruction body."""
    urls: list[str] = []
    # Split on common shell operators to isolate individual commands
    for cmd in re.split(r"&&|;|\|\||\|", run_body):
        tokens = cmd.split()
        if not tokens:
            continue
        # Skip leading sudo / env / variable assignments
        idx = 0
        while idx < len(tokens) and (
            "=" in tokens[idx] or tokens[idx] in ("sudo", "env", "time")
        ):
            idx += 1
        if idx >= len(tokens):
            continue
        if tokens[idx].lower() not in ("curl", "wget"):
            continue
        for m in _URL_RE.finditer(cmd):
            url = m.group(0).rstrip(",.")  # strip only unambiguous trailing punctuation
            if url not in urls:
                urls.append(url)
    return urls


def _parse_dockerfile(dockerfile_path: str) -> tuple[str | None, list[str]]:
    """Parse a Dockerfile and return ``(base_image, downloaded_urls)``.

    ``base_image`` is the image reference from the *first* ``FROM`` instruction
    that is not an ARG substitution (``$...``) and not ``scratch``.

    ``downloaded_urls`` is a deduplicated list of URLs found in ``curl`` or
    ``wget`` commands inside ``RUN`` instructions.
    """
    path = Path(dockerfile_path)
    if not path.is_file():
        logger.error("Dockerfile not found: %s", dockerfile_path)
        sys.exit(1)

    text = path.read_text()

    # Join line-continuation backslashes so each logical instruction is one line
    logical_lines: list[str] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.rstrip()
        if stripped.endswith("\\"):
            current.append(stripped[:-1])
        else:
            current.append(stripped)
            logical_lines.append(" ".join(current))
            current = []
    if current:
        logical_lines.append(" ".join(current))

    base_image: str | None = None
    downloaded_urls: list[str] = []

    for line in logical_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        upper = line.upper()

        # FROM – capture first non-ARG, non-scratch image
        if upper.startswith("FROM ") and base_image is None:
            parts = line.split()
            if len(parts) >= 2:
                candidate = parts[1]
                if not candidate.startswith("$") and candidate.lower() != "scratch":
                    base_image = candidate
                    logger.info("Dockerfile base image: %s", base_image)

        # RUN – look for curl/wget invocations
        if upper.startswith("RUN "):
            for url in _extract_urls_from_run(line[4:]):
                if url not in downloaded_urls:
                    downloaded_urls.append(url)

    if downloaded_urls:
        logger.info(
            "Dockerfile: found %d URL(s) downloaded via curl/wget: %s",
            len(downloaded_urls),
            downloaded_urls,
        )

    return base_image, downloaded_urls


def _build_extra_spdx_packages(urls: list[str]) -> list[dict]:
    """Convert a list of downloaded URLs into SPDX package entry dicts.

    Each URL becomes a package whose ``downloadLocation`` is set to the URL
    and whose ``name`` is derived from the URL's filename component.
    """
    packages: list[dict] = []
    for i, url in enumerate(urls):
        parsed = urllib.parse.urlparse(url)
        filename = Path(parsed.path).name or "unknown"
        # Strip common archive extensions to get a cleaner package name.
        # The leading `\.` anchors the match to a literal period (not any char).
        pkg_name = re.sub(
            r"[.](?:tar[.](gz|bz2|xz|zst)|tgz|zip|whl|deb|rpm)$",
            "",
            filename,
            flags=re.IGNORECASE,
        )
        packages.append({
            "SPDXID": f"SPDXRef-Downloaded-{i:04d}",
            "name": pkg_name or filename,
            "versionInfo": "NOASSERTION",
            "downloadLocation": url,
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "comment": f"Downloaded via curl/wget in Dockerfile RUN layer: {url}",
        })
    return packages


# ---------------------------------------------------------------------------
# SPDX post-processing helpers
# ---------------------------------------------------------------------------

def _inject_extra_packages(spdx: dict, extra_packages: list[dict]) -> dict:
    """Return a copy of *spdx* with *extra_packages* appended to the package list.

    A ``CONTAINS`` relationship is added from the first
    ``SPDXRef-ContainerImage-*`` package (if any) to each injected package so
    that the new entries are properly connected in the SPDX graph.
    """
    if not extra_packages:
        return spdx

    result = copy.deepcopy(spdx)

    # Find the container-image package to use as the parent in relationships
    container_id: str | None = None
    for pkg in result.get("packages", []):
        spdx_id = pkg.get("SPDXID", "")
        if spdx_id.startswith("SPDXRef-ContainerImage-"):
            container_id = spdx_id
            break

    result.setdefault("packages", []).extend(extra_packages)

    if container_id:
        new_rels = [
            {
                "spdxElementId": container_id,
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": pkg["SPDXID"],
            }
            for pkg in extra_packages
        ]
        result.setdefault("relationships", []).extend(new_rels)

    return result


def _compute_delta_spdx(full_spdx: dict, base_spdx: dict) -> dict:
    """Return a copy of *full_spdx* with packages that appear in *base_spdx* removed.

    Matching is performed by ``(name, versionInfo)`` pair.  Packages whose
    ``SPDXID`` starts with ``SPDXRef-ContainerImage-`` or ``SPDXRef-OS-`` are
    always retained because they describe the image / OS layer rather than
    individual software packages.

    ``relationships`` entries that reference removed packages are pruned so the
    resulting document is self-consistent.  The document ``name`` and
    ``documentNamespace`` are suffixed with ``" (delta)"`` / ``"-delta"`` to
    distinguish the file from the full-image report.
    """
    # Build a set of (name, versionInfo) keys present in the base image
    base_keys: set[tuple[str, str]] = set()
    for pkg in base_spdx.get("packages", []):
        name = pkg.get("name", "")
        version = pkg.get("versionInfo", "")
        if name:
            base_keys.add((name, version))

    # Decide which packages survive into the delta
    kept_ids: set[str] = {"SPDXRef-DOCUMENT"}
    kept_packages: list[dict] = []
    for pkg in full_spdx.get("packages", []):
        spdx_id = pkg.get("SPDXID", "")
        name = pkg.get("name", "")
        version = pkg.get("versionInfo", "")
        # Always keep image/OS descriptor meta-packages
        if spdx_id.startswith(("SPDXRef-ContainerImage-", "SPDXRef-OS-")):
            kept_packages.append(pkg)
            kept_ids.add(spdx_id)
        elif (name, version) not in base_keys:
            kept_packages.append(pkg)
            kept_ids.add(spdx_id)
        else:
            logger.debug("Delta: removing base-image package %s@%s (%s)", name, version, spdx_id)

    # Prune relationships so both endpoints are in the kept set
    kept_relationships: list[dict] = []
    for rel in full_spdx.get("relationships", []):
        src = rel.get("spdxElementId", "")
        dst = rel.get("relatedSpdxElement", "")
        if src in kept_ids and dst in kept_ids:
            kept_relationships.append(rel)

    delta = copy.deepcopy(full_spdx)
    delta["name"] = full_spdx.get("name", "") + " (delta)"
    ns = delta.get("documentNamespace", "")
    delta["documentNamespace"] = (ns + "-delta") if ns else "delta"
    delta["packages"] = kept_packages
    delta["relationships"] = kept_relationships

    removed = len(full_spdx.get("packages", [])) - len(kept_packages)
    logger.info(
        "Delta SPDX: kept %d / %d package(s); removed %d base-image package(s).",
        len(kept_packages),
        len(full_spdx.get("packages", [])),
        removed,
    )
    return delta


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Matches standard Docker image reference format:
#   [registry/][namespace/]name[:tag][@digest]
# Hyphen is placed at the end of the character class to avoid ambiguity.
_VALID_IMAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/:@-]*$")


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

def _run_trivy_scan(image: str, output_path: Path) -> bool:
    """Invoke ``trivy image`` and write the SPDX-JSON result to *output_path*.

    Returns ``True`` on success.
    """
    cmd = [
        "trivy",
        "image",
        "--list-all-pkgs",
        "--format", "spdx-json",
        "--output", str(output_path),
        image,
    ]
    logger.info("Command: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=False)  # nosec B603 – list cmd, image validated
    if result.returncode != 0:
        logger.error(
            "trivy scan FAILED for '%s' (exit code %d).", image, result.returncode
        )
        return False
    return True


def scan_image(
    image: str,
    output_dir: Path,
    base_image: str | None = None,
    extra_packages: list[dict] | None = None,
) -> bool:
    """Scan *image* with trivy and write SPDX-JSON output(s) to *output_dir*.

    Always produces:
      ``trivy-spdx-<sanitized-image-name>.json``  – full SPDX for the image.

    When *base_image* is provided also produces:
      ``trivy-spdx-<sanitized-image-name>-delta.json``  – SPDX with base-image
      packages removed.

    When *extra_packages* is provided (packages extracted from Dockerfile
    ``curl``/``wget`` commands) those entries are injected into both outputs.

    Returns ``True`` if the scan(s) succeeded.
    """
    try:
        _validate_image_name(image)
    except ValueError as exc:
        logger.error("%s", exc)
        return False

    safe_name = _sanitize_image_name(image)
    full_path = output_dir / f"trivy-spdx-{safe_name}.json"

    logger.info("Scanning image : %s", image)
    logger.info("Full SPDX file : %s", full_path)

    if not _run_trivy_scan(image, full_path):
        return False

    # Load the trivy output so we can post-process it
    try:
        with full_path.open() as fh:
            full_spdx = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load trivy output '%s': %s", full_path, exc)
        return False

    # Inject curl/wget-downloaded packages (if any)
    if extra_packages:
        logger.info(
            "Injecting %d extra package(s) from Dockerfile into full SPDX.",
            len(extra_packages),
        )
        full_spdx = _inject_extra_packages(full_spdx, extra_packages)
        with full_path.open("w") as fh:
            json.dump(full_spdx, fh, indent=2)

    # Generate delta SPDX (full image minus base image)
    if base_image:
        try:
            _validate_image_name(base_image)
        except ValueError as exc:
            logger.error("Invalid base image name – skipping delta: %s", exc)
        else:
            import tempfile
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, dir=output_dir
            ) as tmp:
                base_tmp = Path(tmp.name)
            try:
                logger.info("Scanning base image for delta: %s", base_image)
                if _run_trivy_scan(base_image, base_tmp):
                    with base_tmp.open() as fh:
                        base_spdx = json.load(fh)
                    delta_spdx = _compute_delta_spdx(full_spdx, base_spdx)
                    if extra_packages:
                        delta_spdx = _inject_extra_packages(delta_spdx, extra_packages)
                    delta_path = output_dir / f"trivy-spdx-{safe_name}-delta.json"
                    with delta_path.open("w") as fh:
                        json.dump(delta_spdx, fh, indent=2)
                    logger.info("Delta SPDX file: %s", delta_path)
                else:
                    logger.warning(
                        "Base image scan failed – delta SPDX will not be generated."
                    )
            finally:
                base_tmp.unlink(missing_ok=True)

    logger.info("Scan PASSED for '%s' -> %s", image, full_path)
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run 'trivy image --list-all-pkgs --format spdx-json' for one or "
            "more container images.  Optionally generates a delta SPDX (image "
            "minus base-image packages) and injects packages downloaded via "
            "curl/wget in a Dockerfile."
        )
    )
    parser.add_argument(
        "images",
        nargs="*",
        metavar="IMAGE",
        help="Container image(s) to scan, e.g. ubuntu:22.04",
    )
    parser.add_argument(
        "--conf-file",
        metavar="FILE",
        help=(
            "Plain-text file (one image per line) or YAML file with an "
            "'images:' list key containing the images to scan."
        ),
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
        "--dockerfile",
        metavar="FILE",
        help=(
            "Path to a Dockerfile.  The script will extract the base image "
            "from the FROM instruction (used for the delta report unless "
            "--base-image is also given) and parse RUN layers for packages "
            "downloaded via curl or wget."
        ),
    )
    parser.add_argument(
        "--base-image",
        metavar="IMAGE",
        help=(
            "Explicit base image to use when computing the delta SPDX report. "
            "Overrides the base image detected from --dockerfile."
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

    if args.conf_file:
        conf_images = _images_from_conf_file(args.conf_file)
        logger.info(
            "Found %d image(s) in conf file '%s': %s",
            len(conf_images),
            args.conf_file,
            conf_images,
        )
        images.extend(conf_images)

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
            "No images to scan. Provide IMAGE argument(s), --conf-file, "
            "or --compose-file."
        )
        return 1

    # Parse Dockerfile (if supplied)
    extra_packages: list[dict] = []
    base_image: str | None = args.base_image  # explicit override takes precedence

    if args.dockerfile:
        df_base, downloaded_urls = _parse_dockerfile(args.dockerfile)
        if df_base and base_image is None:
            base_image = df_base
            logger.info("Using Dockerfile base image for delta: %s", base_image)
        elif df_base and base_image != df_base:
            logger.info(
                "Dockerfile FROM (%s) overridden by --base-image (%s).",
                df_base,
                base_image,
            )
        extra_packages = _build_extra_spdx_packages(downloaded_urls)

    if base_image:
        logger.info(
            "Delta SPDX reports will be generated using base image: %s", base_image
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, bool] = {}
    for image in unique_images:
        results[image] = scan_image(
            image,
            output_dir,
            base_image=base_image,
            extra_packages=extra_packages or None,
        )

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
