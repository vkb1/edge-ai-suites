# License Plate Recognition Application

Multi-stage license plate recognition (LPR) application using **YOLOv11-m** for plate detection and **PP-OCRv4** for text recognition. Demonstrates three inference approaches: native models, OpenVINO-optimized models, and Intel DL Streamer video pipeline.

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Download models and convert to OpenVINO format
python download_models.py

# 3. Run Stage 1: Native model inference on an image
python lpr_native.py --image path/to/plate_image.jpg

# 4. Run Stage 2: OpenVINO optimized inference on an image
python lpr_openvino.py --image path/to/plate_image.jpg

# 5. Run Stage 3: DL Streamer video pipeline (requires DL Streamer installation)
python lpr_dlstreamer.py --video path/to/video.mp4 --device CPU --output both
```

## Prerequisites

- Python 3.10+
- For Stage 3: Intel DL Streamer 2026.0.0 — see [setup_prerequisites.md](setup_prerequisites.md)

## Project Structure

| File | Description |
|------|-------------|
| `download_models.py` | Downloads HuggingFace models and converts to OpenVINO IR |
| `lpr_native.py` | Stage 1: Image LPR with native YOLO + PaddleOCR |
| `lpr_openvino.py` | Stage 2: Image LPR with OpenVINO runtime |
| `lpr_dlstreamer.py` | Stage 3: Video LPR with DL Streamer pipeline |
| `utils.py` | Shared visualization and timing utilities |
| `requirements.txt` | Python dependencies |
| `setup_prerequisites.md` | DL Streamer installation guide |

## Models

| Model | Source | Purpose |
|-------|--------|---------|
| [YOLOv11-m License Plate](https://huggingface.co/morsetechlab/yolov11-license-plate-detection) | HuggingFace | License plate detection |
| [PP-OCRv4_server_rec](https://huggingface.co/PaddlePaddle/PP-OCRv4_server_rec) | HuggingFace | Text recognition (OCR) |

Models are downloaded to `models/` (native) and `models_ov/` (OpenVINO IR) by `download_models.py`.

## Stages

### Stage 1: Native Pipeline (`lpr_native.py`)

Uses native YOLO `.pt` weights via Ultralytics and PaddleOCR Python API. Produces a 3-panel visualization: input image, detection overlay, and recognized plate text with inference timing.

### Stage 2: OpenVINO Pipeline (`lpr_openvino.py`)

Uses OpenVINO IR models for both detection and OCR. YOLO runs through Ultralytics' OpenVINO backend; OCR uses the OpenVINO runtime directly with CTC greedy decoding.

### Stage 3: DL Streamer Pipeline (`lpr_dlstreamer.py`)

Builds a GStreamer pipeline using DL Streamer elements (`gvadetect`, `gvaclassify`, `gvawatermark`) for real-time video processing. Displays input and annotated streams side by side with FPS metrics. Supports both display and MP4 file output.

```
--output display  # Live window only
--output file     # MP4 file only
--output both     # Window + MP4 (default)
```

## License

See [LICENSE](LICENSE).