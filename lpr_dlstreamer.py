#!/usr/bin/env python3
"""Stage 3: License Plate Recognition using Intel DL Streamer pipeline.

Builds a GStreamer pipeline with DL Streamer elements (gvadetect, gvaclassify)
for video-based license plate recognition. Saves annotated output to a file.

Requires: DL Streamer 2026.0.0 installed (see setup_prerequisites.md)

Usage:
    python lpr_dlstreamer.py --video path/to/video.mp4 [--device CPU]
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
YOLO_OV_DIR = BASE_DIR / "models_ov" / "license-plate-finetune-v1m_openvino_model"
OCR_OV_DIR = BASE_DIR / "models_ov" / "PP-OCRv4_server_rec"
OCR_XML = OCR_OV_DIR / "PP-OCRv4_server_rec.xml"
OUTPUT_DIR = BASE_DIR / "output"
DLS_ENV_SCRIPT = "/opt/intel/dlstreamer/scripts/setup_dls_env.sh"


def find_model_xml(model_dir):
    """Find the .xml model file in a directory."""
    xml_files = list(Path(model_dir).glob("*.xml"))
    if not xml_files:
        return None
    return str(xml_files[0])


def main():
    parser = argparse.ArgumentParser(
        description="License Plate Recognition - DL Streamer Pipeline (Stage 3)"
    )
    parser.add_argument("--video", required=True, help="Path to input video file or URL")
    parser.add_argument("--device", default="CPU", choices=["CPU", "GPU"],
                        help="Inference device (default: CPU)")
    args = parser.parse_args()

    video_path = args.video
    device = args.device

    if not video_path.startswith(("http://", "https://", "rtsp://", "/dev/video")):
        if not Path(video_path).exists():
            print(f"Error: Video file not found: {video_path}")
            sys.exit(1)

    # Validate models
    yolo_xml = find_model_xml(YOLO_OV_DIR)
    if not yolo_xml:
        print(f"Error: YOLO OpenVINO model not found in {YOLO_OV_DIR}")
        print("Run 'python download_models.py' first.")
        sys.exit(1)
    if not OCR_XML.exists():
        print(f"Error: OCR OpenVINO model not found: {OCR_XML}")
        print("Run 'python download_models.py' first.")
        sys.exit(1)
    ocr_xml = str(OCR_XML)

    # Determine source element
    if video_path.startswith(("http://", "https://", "rtsp://")):
        source = f"urisourcebin buffer-size=4096 uri={video_path}"
    elif video_path.startswith("/dev/video"):
        source = f"v4l2src device={video_path}"
    else:
        source = f"filesrc location={video_path}"

    # Device-specific decode and preprocessing
    if device == "GPU" and os.path.exists("/dev/dri/renderD128"):
        decode = "decodebin3 ! vapostproc ! video/x-raw\\(memory:VAMemory\\)"
        preproc = "pre-process-backend=va-surface-sharing"
    else:
        if device == "GPU" and not os.path.exists("/dev/dri/renderD128"):
            print("Warning: GPU requested but /dev/dri/renderD128 not found. Falling back to CPU.")
            device = "CPU"
        decode = "decodebin3"
        preproc = "pre-process-backend=opencv"

    # Output file path
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    video_stem = Path(video_path).stem
    output_path = str(OUTPUT_DIR / f"lpr_{video_stem}_{device}.avi")

    # Sink: watermark annotations, count FPS, encode to file
    sink = (f"gvawatermark ! videoconvert ! gvafpscounter ! "
            f"filesink location={output_path}")

    pipeline_str = (
        f"gst-launch-1.0 "
        f"{source} ! {decode} ! videoconvert ! "
        f"gvadetect model={yolo_xml} device={device} {preproc} ! queue ! "
        f"gvaclassify model={ocr_xml} device={device} {preproc} ! queue ! "
        f"{sink}"
    )

    # Prepend DL Streamer environment setup
    full_cmd = f"source {DLS_ENV_SCRIPT} && {pipeline_str}"

    print("=" * 60)
    output_path = str(OUTPUT_DIR / f"lpr_{video_stem}_{device}.avi")
    print("=" * 60)
    print(f"  Video:  {video_path}")
    sink = (f"gvawatermark ! videoconvert ! gvafpscounter ! avimux ! filesink location={output_path}")
    print(f"  YOLO:   {yolo_xml}")
    print(f"  OCR:    {ocr_xml}")
    print(f"\nPipeline:\n{pipeline_str}\n")

    start_time = time.time()
    try:
        subprocess.run(full_cmd, shell=True, executable="/bin/bash", check=True)
    except subprocess.CalledProcessError as e:
        print(f"\nPipeline failed with return code {e.returncode}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user.")

    elapsed = time.time() - start_time
    print(f"\nDone. Output saved to: {output_path}")
    print(f"Total time: {elapsed:.1f} s")


if __name__ == "__main__":
    main()
