"""Shared utilities for license plate recognition pipelines."""

import time
import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


def crop_plate_region(image, box, padding=10):
    """Crop a license plate region from the image with optional padding.

    Args:
        image: BGR image (numpy array).
        box: Bounding box as [x1, y1, x2, y2].
        padding: Pixels to expand the crop region.

    Returns:
        Cropped BGR image.
    """
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    return image[y1:y2, x1:x2]


def draw_detections(image, detections):
    """Draw bounding boxes and labels on an image.

    Args:
        image: BGR image (numpy array). Will be modified in-place.
        detections: List of dicts with keys 'box' [x1,y1,x2,y2],
                    'confidence' (float), and optionally 'text' (str).

    Returns:
        The annotated image.
    """
    annotated = image.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["box"]]
        conf = det["confidence"]
        text = det.get("text", "")

        # Draw box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Label
        label = f"{conf:.2f}"
        if text:
            label = f"{text} ({conf:.2f})"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw, y1), (0, 255, 0), -1)
        cv2.putText(annotated, label, (x1, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    return annotated


def format_inference_stats(detection_ms, ocr_ms, total_ms, extra=None):
    """Format inference timing as a display string.

    Args:
        detection_ms: Detection inference time in milliseconds.
        ocr_ms: OCR inference time in milliseconds.
        total_ms: Total pipeline time in milliseconds.
        extra: Optional dict of additional stats to display.

    Returns:
        Formatted string.
    """
    lines = [
        f"Detection: {detection_ms:.1f} ms",
        f"OCR: {ocr_ms:.1f} ms",
        f"Total: {total_ms:.1f} ms",
    ]
    if extra:
        for k, v in extra.items():
            lines.append(f"{k}: {v}")
    return " | ".join(lines)


def create_side_by_side_figure(original, detected, plates_info, stats_text,
                               title="License Plate Recognition", save_path=None):
    """Create a 3-panel matplotlib figure with inference stats.

    Args:
        original: Original BGR image.
        detected: Image with detection bounding boxes drawn.
        plates_info: List of dicts with 'crop' (BGR image) and 'text' (str).
        stats_text: Formatted inference stats string.
        title: Figure title.
        save_path: If set, save figure to this path.

    Returns:
        The matplotlib figure.
    """
    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    detected_rgb = cv2.cvtColor(detected, cv2.COLOR_BGR2RGB)

    fig = plt.figure(figsize=(18, 7))
    gs = gridspec.GridSpec(2, 3, height_ratios=[6, 1], hspace=0.3, wspace=0.3)

    # Panel 1: Original image
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.imshow(original_rgb)
    ax1.set_title("Input Image", fontsize=12, fontweight="bold")
    ax1.axis("off")

    # Panel 2: Detection result
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.imshow(detected_rgb)
    ax2.set_title("License Plate Detection", fontsize=12, fontweight="bold")
    ax2.axis("off")

    # Panel 3: OCR results
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.axis("off")
    ax3.set_title("Recognized Text", fontsize=12, fontweight="bold")

    if plates_info:
        n_plates = len(plates_info)
        plate_gs = gridspec.GridSpecFromSubplotSpec(
            max(n_plates, 1), 1, subplot_spec=gs[0, 2], hspace=0.4
        )
        for i, plate in enumerate(plates_info):
            ax_plate = fig.add_subplot(plate_gs[i, 0])
            if plate["crop"] is not None and plate["crop"].size > 0:
                crop_rgb = cv2.cvtColor(plate["crop"], cv2.COLOR_BGR2RGB)
                ax_plate.imshow(crop_rgb)
            ax_plate.set_title(
                f'Plate {i+1}: "{plate["text"]}"', fontsize=10, color="darkgreen"
            )
            ax_plate.axis("off")
    else:
        ax3.text(0.5, 0.5, "No plates detected", ha="center", va="center",
                 fontsize=14, color="red", transform=ax3.transAxes)

    # Stats bar
    ax_stats = fig.add_subplot(gs[1, :])
    ax_stats.axis("off")
    ax_stats.text(0.5, 0.5, stats_text, ha="center", va="center",
                  fontsize=12, fontweight="bold",
                  bbox=dict(boxstyle="round,pad=0.5", facecolor="#e0f0ff", edgecolor="#4a90d9"),
                  transform=ax_stats.transAxes)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {save_path}")

    return fig


class Timer:
    """Simple context-manager timer that records elapsed milliseconds."""

    def __init__(self):
        self.elapsed_ms = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
