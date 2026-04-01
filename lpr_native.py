#!/usr/bin/env python3
"""Stage 1: License Plate Recognition using native YOLO and PaddleOCR models.

Reads native model weights from the models/ directory.
Produces a side-by-side comparison of input image, detection result,
and recognized text with inference timing.

Usage:
    python lpr_native.py --image path/to/image.jpg [--output output/]
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from utils import (Timer, create_side_by_side_figure, crop_plate_region,
                   draw_detections, format_inference_stats)

BASE_DIR = Path(__file__).resolve().parent
YOLO_MODEL_PATH = BASE_DIR / "models" / "yolov11-license-plate" / "license-plate-finetune-v1m.pt"
OCR_MODEL_DIR = BASE_DIR / "models" / "PP-OCRv4_server_rec"


def detect_plates(image_path):
    """Run YOLOv11 license plate detection on an image.

    Returns:
        results: Ultralytics Results object.
        detections: List of dicts with 'box' and 'confidence'.
        elapsed_ms: Inference time in milliseconds.
    """
    from ultralytics import YOLO

    model = YOLO(str(YOLO_MODEL_PATH))

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

    return results, detections, t.elapsed_ms


def recognize_plates(image, detections):
    """Run PaddleOCR text recognition on detected plate regions.

    Returns:
        plates_info: List of dicts with 'crop', 'text', 'score'.
        elapsed_ms: Total OCR inference time in milliseconds.
    """
    from paddleocr import TextRecognition

    model = TextRecognition(model_name="PP-OCRv4_server_rec")

    plates_info = []
    total_ms = 0.0

    for det in detections:
        crop = crop_plate_region(image, det["box"])
        if crop.size == 0:
            plates_info.append({"crop": crop, "text": "", "score": 0.0})
            continue

        # Save crop to temp file for PaddleOCR
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        cv2.imwrite(tmp.name, crop)

        with Timer() as t:
            output = model.predict(input=tmp.name, batch_size=1)

        os.unlink(tmp.name)
        total_ms += t.elapsed_ms

        text = ""
        score = 0.0
        for res in output:
            if hasattr(res, "rec_text"):
                text = res.get("rec_text", "")
                score = res.get("rec_score", 0.0)
            elif isinstance(res, dict):
                res_data = res.get("res", res)
                text = res_data.get("rec_text", "")
                score = res_data.get("rec_score", 0.0)
            else:
                # Try accessing result attributes
                try:
                    result_dict = res.to_dict() if hasattr(res, "to_dict") else {}
                    text = result_dict.get("rec_text", "")
                    score = result_dict.get("rec_score", 0.0)
                except Exception:
                    pass

        plates_info.append({"crop": crop, "text": text.strip(), "score": score})

    return plates_info, total_ms


def main():
    parser = argparse.ArgumentParser(
        description="License Plate Recognition - Native Models (Stage 1)"
    )
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--output", default="output", help="Output directory (default: output/)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)

    if not YOLO_MODEL_PATH.exists():
        print(f"Error: YOLO model not found: {YOLO_MODEL_PATH}")
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
    print("Stage 1: Native Model Pipeline")
    print("=" * 60)

    # Step 1: Detect license plates
    print("\n[1/3] Running license plate detection (YOLOv11-m native)...")
    with Timer() as total_timer:
        _, detections, det_ms = detect_plates(str(image_path))
        print(f"      Found {len(detections)} plate(s) in {det_ms:.1f} ms")

        # Step 2: OCR on detected plates
        print("[2/3] Running OCR (PP-OCRv4_server_rec native)...")
        plates_info, ocr_ms = recognize_plates(image, detections)
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

    save_path = output_dir / f"native_{image_path.stem}.png"
    fig = create_side_by_side_figure(
        original=image,
        detected=annotated,
        plates_info=plates_info,
        stats_text=stats_text,
        title="Stage 1: Native Model Pipeline (YOLOv11-m + PP-OCRv4)",
        save_path=str(save_path),
    )

    print(f"\n{stats_text}")
    print(f"Output saved to: {save_path}")

    # Display using OpenCV if a display is available
    try:
        img = cv2.imread(str(save_path))
        if img is not None:
            cv2.imshow("Stage 1: Native Model Pipeline", img)
            print("Press any key in the display window to close.")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
    except cv2.error:
        print("(No display available — view the saved image directly.)")


if __name__ == "__main__":
    main()
