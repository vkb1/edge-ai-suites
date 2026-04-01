#!/usr/bin/env python3
"""Download HuggingFace models and convert them to OpenVINO IR format.

Downloads:
  - morsetechlab/yolov11-license-plate-detection (medium variant)
  - PaddlePaddle/PP-OCRv4_server_rec

Converts both to OpenVINO format in models_ov/ directory.
"""

import os
import shutil
import sys
import urllib.request
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download


BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
MODELS_OV_DIR = BASE_DIR / "models_ov"

# Model identifiers
YOLO_REPO = "morsetechlab/yolov11-license-plate-detection"
YOLO_FILENAME = "license-plate-finetune-v1m.pt"
YOLO_NATIVE_DIR = MODELS_DIR / "yolov11-license-plate"
YOLO_OV_DIR = MODELS_OV_DIR / "license-plate-finetune-v1m_openvino_model"

OCR_REPO = "PaddlePaddle/PP-OCRv4_server_rec"
OCR_NATIVE_DIR = MODELS_DIR / "PP-OCRv4_server_rec"
OCR_OV_DIR = MODELS_OV_DIR / "PP-OCRv4_server_rec"

# Character dictionary for CTC decoding (used by Stage 2)
PPOCR_KEYS_URL = (
    "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/"
    "main/ppocr/utils/ppocr_keys_v1.txt"
)


def download_yolo_model():
    """Download YOLOv11-m license plate detection model from HuggingFace."""
    pt_path = YOLO_NATIVE_DIR / YOLO_FILENAME
    if pt_path.exists():
        print(f"[YOLO] Model already exists: {pt_path}")
        return pt_path

    print(f"[YOLO] Downloading {YOLO_FILENAME} from {YOLO_REPO}...")
    YOLO_NATIVE_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = hf_hub_download(
        repo_id=YOLO_REPO,
        filename=YOLO_FILENAME,
        local_dir=str(YOLO_NATIVE_DIR),
    )
    print(f"[YOLO] Downloaded to: {downloaded}")
    return pt_path


def download_ocr_model():
    """Download PP-OCRv4_server_rec model from HuggingFace."""
    marker = OCR_NATIVE_DIR / "inference.pdiparams"
    if marker.exists():
        print(f"[OCR] Model already exists: {OCR_NATIVE_DIR}")
        return OCR_NATIVE_DIR

    print(f"[OCR] Downloading full model from {OCR_REPO}...")
    OCR_NATIVE_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=OCR_REPO,
        local_dir=str(OCR_NATIVE_DIR),
    )
    print(f"[OCR] Downloaded to: {OCR_NATIVE_DIR}")
    return OCR_NATIVE_DIR


def convert_yolo_to_openvino():
    """Convert YOLOv11 .pt model to OpenVINO IR format."""
    xml_candidates = list(YOLO_OV_DIR.glob("*.xml"))
    if xml_candidates:
        print(f"[YOLO-OV] OpenVINO model already exists: {YOLO_OV_DIR}")
        return YOLO_OV_DIR

    from ultralytics import YOLO

    pt_path = YOLO_NATIVE_DIR / YOLO_FILENAME
    if not pt_path.exists():
        print("[YOLO-OV] Native model not found. Run download first.")
        sys.exit(1)

    print(f"[YOLO-OV] Converting {pt_path} to OpenVINO format (static shapes)...")
    model = YOLO(str(pt_path))
    # Use dynamic=False for static input shapes — critical for OpenVINO performance.
    # OpenVINO pre-compiles optimized kernels for fixed shapes, avoiding
    # expensive on-the-fly compilation at first inference.
    export_path = model.export(format="openvino", half=False, dynamic=False, imgsz=640)

    # Move exported files to models_ov directory
    YOLO_OV_DIR.mkdir(parents=True, exist_ok=True)
    export_dir = Path(export_path)
    for f in export_dir.iterdir():
        dest = YOLO_OV_DIR / f.name
        shutil.move(str(f), str(dest))

    # Clean up the export directory left by ultralytics
    if export_dir.exists() and export_dir != YOLO_OV_DIR:
        shutil.rmtree(str(export_dir), ignore_errors=True)
    # Also clean up the .pt-adjacent export dir if different
    pt_adjacent = pt_path.parent / (pt_path.stem + "_openvino_model")
    if pt_adjacent.exists():
        shutil.rmtree(str(pt_adjacent), ignore_errors=True)

    print(f"[YOLO-OV] Converted to: {YOLO_OV_DIR}")
    return YOLO_OV_DIR


def convert_ocr_to_openvino():
    """Convert PP-OCRv4_server_rec PaddlePaddle model to OpenVINO IR format."""
    xml_path = OCR_OV_DIR / "PP-OCRv4_server_rec.xml"
    if xml_path.exists():
        print(f"[OCR-OV] OpenVINO model already exists: {xml_path}")
        return OCR_OV_DIR

    OCR_OV_DIR.mkdir(parents=True, exist_ok=True)

    # PaddlePaddle 3.x format uses .json + .pdiparams (not .pdmodel)
    # Convert via paddle2onnx first, then to OpenVINO IR
    json_model = OCR_NATIVE_DIR / "inference.json"
    pdmodel = OCR_NATIVE_DIR / "inference.pdmodel"
    pdiparams = OCR_NATIVE_DIR / "inference.pdiparams"

    # Try direct OpenVINO conversion for legacy .pdmodel format
    if pdmodel.exists():
        print(f"[OCR-OV] Converting {pdmodel} to OpenVINO format (direct)...")
        try:
            import openvino as ov
            ov_model = ov.convert_model(str(pdmodel))
            ov.save_model(ov_model, str(xml_path))
            print(f"[OCR-OV] Converted to: {xml_path}")
            _download_char_dict()
            return OCR_OV_DIR
        except Exception as e:
            print(f"[OCR-OV] Direct conversion failed: {e}")

    # PaddlePaddle 3.x format (.json + .pdiparams) → ONNX → OpenVINO
    if json_model.exists() and pdiparams.exists():
        print("[OCR-OV] Detected PaddlePaddle 3.x format. Converting via paddle2onnx...")
        onnx_path = OCR_OV_DIR / "PP-OCRv4_server_rec.onnx"
        _convert_paddle3x_to_onnx(json_model, pdiparams, onnx_path)

        print("[OCR-OV] Converting ONNX to OpenVINO IR via ovc...")
        _convert_onnx_to_openvino_with_ovc(onnx_path, xml_path)

        # Clean up intermediate ONNX file
        onnx_path.unlink(missing_ok=True)
        print(f"[OCR-OV] Converted to: {xml_path}")
        _download_char_dict()
        return OCR_OV_DIR

    print("[OCR-OV] ERROR: No convertible model found in", OCR_NATIVE_DIR)
    print("[OCR-OV] Expected inference.json + inference.pdiparams or inference.pdmodel")
    sys.exit(1)


def _convert_paddle3x_to_onnx(json_model, pdiparams, onnx_path):
    """Convert PaddlePaddle 3.x format (.json + .pdiparams) to ONNX via paddle2onnx."""
    try:
        import paddle2onnx
        print(f"[OCR-OV] paddle2onnx version: {paddle2onnx.__version__}")
    except ImportError:
        print("[OCR-OV] ERROR: paddle2onnx not installed. Install with: pip install paddle2onnx")
        sys.exit(1)

    # Use the Python API: export(model_filename, params_filename, save_file, ...)
    # In paddle2onnx >= 2.x, these are file path strings, not bytes.
    try:
        paddle2onnx.export(
            model_filename=str(json_model),
            params_filename=str(pdiparams),
            save_file=str(onnx_path),
            opset_version=14,
            enable_onnx_checker=True,
        )
        if onnx_path.exists():
            print(f"[OCR-OV] ONNX model saved to: {onnx_path}")
            return
        raise RuntimeError("ONNX file was not created")
    except Exception as e:
        print(f"[OCR-OV] paddle2onnx.export() failed: {e}")
        print("[OCR-OV] Trying CLI fallback...")

    # CLI fallback
    import subprocess
    cmd = [
        sys.executable, "-m", "paddle2onnx",
        "--model_dir", str(json_model.parent),
        "--model_filename", json_model.name,
        "--params_filename", pdiparams.name,
        "--save_file", str(onnx_path),
        "--opset_version", "14",
    ]
    print(f"[OCR-OV] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not onnx_path.exists():
        print(f"[OCR-OV] CLI output: {result.stdout.strip()}")
        print(f"[OCR-OV] CLI error: {result.stderr.strip()}")
        print("[OCR-OV] ERROR: paddle2onnx conversion failed.")
        sys.exit(1)
    print(f"[OCR-OV] ONNX model saved to: {onnx_path}")


def _convert_onnx_to_openvino_with_ovc(onnx_path, xml_path):
    """Convert ONNX to OpenVINO IR via ovc with static OCR input shape."""
    import subprocess

    cmd = [
        "ovc",
        str(onnx_path),
        "--output_model",
        str(xml_path),
        "--input",
        "x[1,3,48,320]",
    ]
    print(f"[OCR-OV] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[OCR-OV] ovc stdout: {result.stdout.strip()}")
        print(f"[OCR-OV] ovc stderr: {result.stderr.strip()}")
        print("[OCR-OV] ERROR: ovc conversion failed.")
        sys.exit(1)

    bin_path = xml_path.with_suffix(".bin")
    if not xml_path.exists() or not bin_path.exists():
        print("[OCR-OV] ERROR: ovc did not generate expected .xml/.bin files")
        sys.exit(1)


def _download_char_dict():
    """Download the PaddleOCR character dictionary for CTC decoding."""
    dict_path = OCR_OV_DIR / "ppocr_keys_v1.txt"
    if dict_path.exists():
        print(f"[OCR-OV] Character dictionary already exists: {dict_path}")
        return

    print("[OCR-OV] Downloading character dictionary...")
    urllib.request.urlretrieve(PPOCR_KEYS_URL, str(dict_path))
    print(f"[OCR-OV] Dictionary saved to: {dict_path}")


def validate_models():
    """Validate that all required model files exist."""
    print("\n" + "=" * 60)
    print("Model Validation Summary")
    print("=" * 60)

    all_ok = True

    # Native models
    checks = {
        "YOLO native (.pt)": YOLO_NATIVE_DIR / YOLO_FILENAME,
        "OCR native (pdiparams)": OCR_NATIVE_DIR / "inference.pdiparams",
    }

    # OpenVINO models
    yolo_xml = list(YOLO_OV_DIR.glob("*.xml"))
    ocr_xml = OCR_OV_DIR / "PP-OCRv4_server_rec.xml"
    char_dict = OCR_OV_DIR / "ppocr_keys_v1.txt"

    for name, path in checks.items():
        exists = path.exists()
        status = "OK" if exists else "MISSING"
        size = f"({path.stat().st_size / 1e6:.1f} MB)" if exists else ""
        print(f"  [{status}] {name}: {path} {size}")
        if not exists:
            all_ok = False

    if yolo_xml:
        xml = yolo_xml[0]
        print(f"  [OK] YOLO OpenVINO: {xml} ({xml.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"  [MISSING] YOLO OpenVINO: {YOLO_OV_DIR}/*.xml")
        all_ok = False

    for name, path in [("OCR OpenVINO", ocr_xml), ("Char dictionary", char_dict)]:
        exists = path.exists()
        status = "OK" if exists else "MISSING"
        size = f"({path.stat().st_size / 1e6:.1f} MB)" if exists else ""
        print(f"  [{status}] {name}: {path} {size}")
        if not exists:
            all_ok = False

    # Validate OpenVINO models load correctly
    if all_ok:
        try:
            import openvino as ov
            core = ov.Core()
            if yolo_xml:
                core.read_model(str(yolo_xml[0]))
                print("  [OK] YOLO OpenVINO model loads successfully")
            core.read_model(str(ocr_xml))
            print("  [OK] OCR OpenVINO model loads successfully")
        except Exception as e:
            print(f"  [WARN] OpenVINO validation failed: {e}")

    print("=" * 60)
    if all_ok:
        print("All models ready!")
    else:
        print("Some models are missing. Re-run this script to download them.")
    return all_ok


def main():
    print("License Plate Recognition - Model Setup")
    print("=" * 60)

    # Phase 1: Download native models
    print("\n--- Phase 1: Downloading native models ---")
    download_yolo_model()
    download_ocr_model()

    # Phase 2: Convert to OpenVINO
    print("\n--- Phase 2: Converting to OpenVINO format ---")
    convert_yolo_to_openvino()
    convert_ocr_to_openvino()

    # Phase 3: Validate
    validate_models()


if __name__ == "__main__":
    main()
