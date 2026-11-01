"""Mask measurements: the deterministic geometry behind every flag.

Pure math on boolean masks. A measurement is evidence: area, centroid,
bounding box, and edge contact, all computed from the mask itself.
"""

from __future__ import annotations

import numpy as np


def mask_area(mask: np.ndarray) -> int:
    return int(np.count_nonzero(mask))


def mask_centroid(mask: np.ndarray) -> tuple[float, float] | None:
    """Centroid in pixel coordinates (x, y); None for an empty mask."""
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return None
    return float(cols.mean()), float(rows.mean())


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Inclusive bounding box (x_min, y_min, x_max, y_max); None if empty."""
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return None
    return int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max())


def edge_contact(mask: np.ndarray) -> dict[str, bool]:
    """Which frame edges the mask touches, if any."""
    if mask.size == 0 or not mask.any():
        return {"left": False, "right": False, "top": False, "bottom": False}
    return {
        "left": bool(mask[:, 0].any()),
        "right": bool(mask[:, -1].any()),
        "top": bool(mask[0, :].any()),
        "bottom": bool(mask[-1, :].any()),
    }


def measure_mask(mask: np.ndarray) -> dict:
    """Full measurement record for one mask on one frame."""
    height, width = mask.shape
    area = mask_area(mask)
    centroid = mask_centroid(mask)
    contact = edge_contact(mask)
    return {
        "area_px": area,
        "area_fraction": area / float(width * height) if width * height else 0.0,
        "centroid": (
            {"x": centroid[0] / width, "y": centroid[1] / height}
            if centroid is not None else None
        ),
        "bbox": mask_bbox(mask),
        "edge_contact": contact,
        "touches_edge": any(contact.values()),
        "frame": {"width": width, "height": height},
    }
