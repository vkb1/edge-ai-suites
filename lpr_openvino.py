#!/usr/bin/env python3
"""Stage 2: License Plate Recognition using OpenVINO-optimized models.

Reads OpenVINO IR models from the models_ov/ directory.
Produces a side-by-side comparison of input image, detection result,
and recognized text with inference timing.

Usage:
    python lpr_openvino.py --image path/to/image.jpg [--output output/]
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import openvino as ov

from utils import (Timer, create_side_by_side_figure, crop_plate_region,
                   draw_detections, format_inference_stats)

BASE_DIR = Path(__file__).resolve().parent
YOLO_OV_DIR = BASE_DIR / "models_ov" / "license-plate-finetune-v1m_openvino_model"
OCR_OV_DIR = BASE_DIR / "models_ov" / "PP-OCRv4_server_rec"
OCR_XML = OCR_OV_DIR / "PP-OCRv4_server_rec.xml"
CHAR_DICT_PATH = OCR_OV_DIR / "ppocr_keys_v1.txt"


def load_char_dict():
    """Load PaddleOCR character dictionary for CTC decoding."""
    chars = ["blank"]  # CTC blank token at index 0
    with open(CHAR_DICT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            chars.append(line.strip())
    chars.append(" ")  # space token at the end
    return chars


def preprocess_ocr_image(crop, target_h=48, max_w=320):
    """Preprocess a cropped plate image for PP-OCRv4 recognition.

    Resizes to target_h while maintaining aspect ratio, pads to max_w,
    normalizes to [0,1], converts to NCHW float32.
    """
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return None

    # Resize maintaining aspect ratio
    ratio = target_h / h
    new_w = min(int(w * ratio), max_w)
    resized = cv2.resize(crop, (new_w, target_h))

    # Convert to grayscale → 3-channel (model expects RGB)
    if len(resized.shape) == 2:
        resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
    else:
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    # Pad to max_w
    padded = np.zeros((target_h, max_w, 3), dtype=np.float32)
    padded[:, :new_w, :] = resized.astype(np.float32)

    # Normalize to [0,1] and then to [-0.5, 0.5] / 0.5 → [-1, 1]
    padded = padded / 255.0
    padded = (padded - 0.5) / 0.5

    # HWC → CHW → NCHW
    padded = padded.transpose(2, 0, 1)
    padded = np.expand_dims(padded, axis=0)

    return padded


def ctc_greedy_decode(logits, char_dict):
    """Perform CTC greedy decoding on model output logits.

    Args:
        logits: numpy array of shape (1, seq_len, num_classes) or (seq_len, num_classes).
        char_dict: List of characters, index 0 = blank.

    Returns:
        Decoded text string.
    """
    if logits.ndim == 3:
        logits = logits[0]

    # Greedy: take argmax at each timestep
    indices = np.argmax(logits, axis=-1)

    # Remove consecutive duplicates and blanks
    decoded = []
    prev_idx = -1
    for idx in indices:
        if idx != prev_idx and idx != 0:  # 0 = blank
            if idx < len(char_dict):
                decoded.append(char_dict[idx])
        prev_idx = idx

    return "".join(decoded)


def detect_plates_openvino(image_path):
    """Run YOLOv11 license plate detection using Ultralytics OpenVINO backend.

    Returns:
        detections: List of dicts with 'box' and 'confidence'.
        elapsed_ms: Inference time in milliseconds.
    """
    from ultralytics import YOLO

    # Ultralytics detects OpenVINO format from directory name ending with _openvino_model
    model = YOLO(str(YOLO_OV_DIR), task="detect")

    # Warmup: first OpenVINO inference includes kernel compilation overhead.
    # Running a dummy inference ensures the timed run reflects true throughput.
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    model.predict(source=dummy, conf=0.25, verbose=False)

    with Timer() as t:
        results = model.predict(source=image_path, conf=0.25, verbose=False)

    detections = []
    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for i in range(len(boxes)):
                xyxy = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                detections.append({"box": xyxy, "confidence": conf})

    return detections, t.elapsed_ms


def recognize_plates_openvino(image, detections):
    """Run OCR on detected plates using OpenVINO compiled model.

    Returns:
        plates_info: List of dicts with 'crop', 'text', 'score'.
        elapsed_ms: Total OCR inference time in milliseconds.
    """
    core = ov.Core()
    # Enable model caching to avoid recompilation on subsequent runs
    core.set_property({"CACHE_DIR": str(BASE_DIR / "models_ov" / ".cache")})
    compiled_model = core.compile_model(str(OCR_XML), "CPU")
    output_layer = compiled_model.output(0)

    char_dict = load_char_dict()

    # PP-OCRv4 rec models use dynamic shapes; use standard defaults
    target_h = 48
    max_w = 320

    # Try to read static dimensions from input shape if available
    try:
        input_shape = compiled_model.input(0).get_partial_shape()
        if input_shape[2].is_static:
            target_h = input_shape[2].get_length()
        if input_shape[3].is_static:
            max_w = input_shape[3].get_length()
    except Exception:
        pass

    plates_info = []
    total_ms = 0.0

    for det in detections:
        crop = crop_plate_region(image, det["box"])
        if crop.size == 0:
            plates_info.append({"crop": crop, "text": "", "score": 0.0})
            continue

        preprocessed = preprocess_ocr_image(crop, target_h=target_h, max_w=max_w)
        if preprocessed is None:
            plates_info.append({"crop": crop, "text": "", "score": 0.0})
            continue

        with Timer() as t:
            result = compiled_model({0: preprocessed})[output_layer]

        total_ms += t.elapsed_ms

        text = ctc_greedy_decode(result, char_dict)
        # Compute confidence as mean of max softmax probabilities
        if result.ndim == 3:
            probs = np.exp(result[0]) / np.exp(result[0]).sum(axis=-1, keepdims=True)
        else:
            probs = np.exp(result) / np.exp(result).sum(axis=-1, keepdims=True)
        score = float(np.mean(np.max(probs, axis=-1)))

        plates_info.append({"crop": crop, "text": text.strip(), "score": score})

    return plates_info, total_ms


def main():
    parser = argparse.ArgumentParser(
        description="License Plate Recognition - OpenVINO Models (Stage 2)"
    )
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--output", default="output", help="Output directory (default: output/)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)

    # Validate model files
    yolo_xml = list(YOLO_OV_DIR.glob("*.xml"))
    if not yolo_xml:
        print(f"Error: YOLO OpenVINO model not found in: {YOLO_OV_DIR}")
        print("Run 'python download_models.py' first.")
        sys.exit(1)
    if not OCR_XML.exists():
        print(f"Error: OCR OpenVINO model not found: {OCR_XML}")
        print("Run 'python download_models.py' first.")
        sys.exit(1)
    if not CHAR_DICT_PATH.exists():
        print(f"Error: Character dictionary not found: {CHAR_DICT_PATH}")
        print("Run 'python download_models.py' first.")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load image
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Error: Could not read image: {image_path}")
        sys.exit(1)

    print("=" * 60)
    print("Stage 2: OpenVINO Optimized Pipeline")
    print("=" * 60)

    # Step 1: Detect license plates
    print("\n[1/3] Running license plate detection (YOLOv11-m OpenVINO)...")
    with Timer() as total_timer:
        detections, det_ms = detect_plates_openvino(str(image_path))
        print(f"      Found {len(detections)} plate(s) in {det_ms:.1f} ms")

        # Step 2: OCR on detected plates
        print("[2/3] Running OCR (PP-OCRv4_server_rec OpenVINO)...")
        plates_info, ocr_ms = recognize_plates_openvino(image, detections)
        for i, plate in enumerate(plates_info):
            print(f'      Plate {i+1}: "{plate["text"]}" (score: {plate["score"]:.3f})')

    total_ms = total_timer.elapsed_ms

    # Update detections with OCR text
    for det, plate in zip(detections, plates_info):
        det["text"] = plate["text"]

    # Step 3: Visualize
    print("[3/3] Generating visualization...")
    annotated = draw_detections(image, detections)
    stats_text = format_inference_stats(det_ms, ocr_ms, total_ms)

    save_path = output_dir / f"openvino_{image_path.stem}.png"
    fig = create_side_by_side_figure(
        original=image,
        detected=annotated,
        plates_info=plates_info,
        stats_text=stats_text,
        title="Stage 2: OpenVINO Optimized Pipeline (YOLOv11-m + PP-OCRv4)",
        save_path=str(save_path),
    )

    print(f"\n{stats_text}")
    print(f"Output saved to: {save_path}")

    # Display using OpenCV if a display is available
    try:
        img = cv2.imread(str(save_path))
        if img is not None:
            cv2.imshow("Stage 2: OpenVINO Pipeline", img)
            print("Press any key in the display window to close.")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
    except cv2.error:
        print("(No display available — view the saved image directly.)")


if __name__ == "__main__":
    main()
