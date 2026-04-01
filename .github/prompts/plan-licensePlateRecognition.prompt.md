## Plan: License Plate Recognition Multi-Stage Application

Build a license plate recognition (LPR) application with three variants — native models, OpenVINO-optimized models, and DL Streamer video pipeline — using YOLOv11-m for plate detection and PP-OCRv4 for text recognition.

---

### Directory Structure

```
oep-developer-guides/
├── requirements.txt
├── setup_prerequisites.md       # DL Streamer install guide
├── download_models.py           # Pre-req: download & convert models
├── utils.py                     # Shared visualization/timing helpers
├── lpr_native.py                # Stage 1: Native models
├── lpr_openvino.py              # Stage 2: OpenVINO optimized
├── lpr_dlstreamer.py            # Stage 3: DL Streamer pipeline
├── .gitignore
├── models/                      # Native weights (gitignored)
│   ├── yolov11-license-plate/
│   │   └── license-plate-finetune-v1m.pt
│   └── PP-OCRv4_server_rec/
│       ├── inference.pdiparams, inference.json, ...
├── models_ov/                   # OpenVINO IR (gitignored)
│   ├── yolov11-license-plate/
│   │   ├── *.xml, *.bin
│   └── PP-OCRv4_server_rec/
│       ├── *.xml, *.bin, char_dict.txt
└── output/
```

---

### Phase 0 — Prerequisites

**Step 0a.** Create `setup_prerequisites.md` documenting DL Streamer 2026.0.0 installation:
   1. Run Intel's `DLS_install_prerequisites.sh` for GPU/NPU drivers
   2. Add APT repos (Ubuntu 22.04 or 24.04 specific commands)
   3. `sudo apt update && sudo apt-get install intel-dlstreamer`
   4. `source /opt/intel/dlstreamer/scripts/setup_dls_env.sh`
   5. Verify: `gst-inspect-1.0 gvadetect`

**Step 0b.** Create `requirements.txt` with: `ultralytics>=8.4.7`, `openvino>=2026.0.0`, `paddlepaddle>=3.0.0`, `paddleocr`, `huggingface-hub`, `opencv-python`, `matplotlib`, `numpy`

---

### Phase 1 — Model Download & Conversion (`download_models.py`)

1. Download **YOLOv11-m** `.pt` from `morsetechlab/yolov11-license-plate-detection` via `huggingface_hub.hf_hub_download()` → `models/yolov11-license-plate/`
2. Download **PP-OCRv4_server_rec** full model from `PaddlePaddle/PP-OCRv4_server_rec` via `huggingface_hub.snapshot_download()` → `models/PP-OCRv4_server_rec/`
3. Convert YOLO to OpenVINO: `YOLO(pt_path).export(format='openvino', half=False, dynamic=True)` → move output to `models_ov/yolov11-license-plate/`
4. Convert PP-OCRv4 to OpenVINO: `openvino.convert_model('models/PP-OCRv4_server_rec/inference.json')` + `save_model()` → `models_ov/PP-OCRv4_server_rec/`
   - *Fallback*: If PaddlePaddle 3.x format isn't directly supported, use PaddleOCR API to re-export as v2 format first, then convert
5. Download OCR character dictionary (`ppocr_keys_v1.txt`) from PaddleOCR GitHub repo → `models_ov/PP-OCRv4_server_rec/` (needed for Stage 2 CTC decoding)
6. Validate all output files exist, print summary

---

### Phase 2 — Native Image Pipeline (`lpr_native.py`)

1. Parse CLI: `--image` (required), `--output` (default: `output/`)
2. Load `YOLO('models/yolov11-license-plate/license-plate-finetune-v1m.pt')`, run `model.predict()`, time it
3. Crop detected plate regions; run each through `paddleocr.TextRecognition(model_dir='models/PP-OCRv4_server_rec/')`, time it
4. Render **3-panel matplotlib figure**: original image | image with detection boxes + confidence | cropped plates with OCR text — plus inference timing stats bar
5. Save figure + display

---

### Phase 3 — OpenVINO Image Pipeline (`lpr_openvino.py`)

1. Same CLI interface as Stage 1
2. Load YOLO via: `YOLO('models_ov/yolov11-license-plate/')` — Ultralytics auto-detects OpenVINO format and uses OV runtime
3. OCR with OpenVINO: load `ov.Core().compile_model('models_ov/.../PP-OCRv4_server_rec.xml', 'CPU')`, manually preprocess plates (resize h=48, normalize, CHW), run inference, CTC-greedy-decode using character dict
4. Same 3-panel visualization + side-by-side timing comparison vs native

---

### Phase 4 — DL Streamer Video Pipeline (`lpr_dlstreamer.py`)

1. Parse CLI: `--video` (required), `--device` (CPU/GPU), `--output` (display/file/both)
2. Build GStreamer pipeline using Python GI bindings:
   ```
   filesrc ! decodebin3 ! tee name=t
     t. ! queue ! compositor.sink_0              # original stream
     t. ! queue ! gvadetect model=YOLO_OV
              ! gvaclassify model=OCR_OV
              ! gvawatermark ! compositor.sink_1 # annotated stream
   compositor ! gvafpscounter ! autovideosink    # side-by-side display
   ```
   - *If `compositor` unavailable*: fallback to `appsink` → OpenCV compositing → display
3. Attach pad probes on `gvaclassify` src pad for per-frame metadata extraction (detection count, recognized text, latency)
4. For "file" output: tee after compositor to `vah264enc ! h264parse ! mp4mux ! filesink`
5. Handle EOS, GPU fallback to CPU if `/dev/dri/renderD128` absent

---

### Shared Utilities (`utils.py`)

- `create_side_by_side_figure()` — matplotlib 3-panel layout
- `draw_detections()` — OpenCV bounding box + label drawing
- `format_inference_stats()` — format timing as display text
- `crop_plate_region()` — crop plate with padding

---

### Verification

1. Run `python download_models.py` — confirm `models/` and `models_ov/` have all expected files; load `.xml` with `ov.Core().read_model()` to validate
2. Run `python lpr_native.py --image <plate_image>` — confirm 3-panel figure saved, OCR text extracted
3. Run `python lpr_openvino.py --image <plate_image>` — confirm output matches Stage 1 qualitatively; OpenVINO should be faster
4. Run `python lpr_dlstreamer.py --video <video_file>` — confirm side-by-side window renders with FPS counter; confirm MP4 output written
5. Verify `gst-inspect-1.0 gvadetect` returns valid output before Stage 3

---

### Decisions
- **YOLO variant**: `m` (medium, ~40MB) per user choice
- **Stage 3 output**: Both display window and MP4 file
- **Sample media**: User provides own (no sample downloads)
- **OCR approach**: Native PaddleOCR API (Stage 1) → raw OpenVINO + CTC decode (Stage 2) → DL Streamer `gvaclassify` (Stage 3)
- **PaddlePaddle model format**: 3.x (`.json` + `.pdiparams`); conversion via `openvino.convert_model()`

### Further Considerations
1. **PP-OCRv4 conversion fallback**: If `openvino.convert_model()` doesn't handle PaddlePaddle 3.x `.json` directly, the script will use PaddleOCR's export to save as v2 format (`.pdmodel` + `.pdiparams`) first, then convert. Both paths should be implemented.
2. **DL Streamer `compositor` availability**: The `compositor` GStreamer element may not ship in all GStreamer builds. The fallback (`appsink` + OpenCV compositing) should be implemented as a safety net.
3. **GPU support for Stage 3**: Default to CPU; auto-detect GPU via `/dev/dri/renderD128` and switch to VA-API decode + GPU inference when available.
