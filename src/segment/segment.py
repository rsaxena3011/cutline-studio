"""Segmentation engines.

Two engines behind one interface:

- ColorKeySegmenter: the fixture engine, and the default demo path.
  Segments a named object in a still by the color key recorded in the
  fixture bundle, and computes the real mask from the real pixels.
  Used so a review never depends on a live API call.
- MetaSAMSegmenter: the live path. SAM 3.1 through the Meta Model API.
  See meta_api.py for the wire call; this class only adapts its result
  into the shared measurement record.

Every engine returns the same shape: whether the object was found, the
boolean mask, and the measurement record from measurements.py. Each
frame is segmented and judged on its own; no identity is tracked
across frames.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class Segmentation:
    object_name: str
    found: bool
    mask: np.ndarray | None
    measurement: dict | None


class ColorKeySegmenter:
    """Segments by color key: pixels within tolerance of a target color.

    This is the fixture-mode engine. The color keys live in the fixture
    bundle's targets.json, one per named object.
    """

    def __init__(self, targets: dict):
        self.targets = targets

    def segment(self, image_path: str, object_name: str) -> Segmentation:
        from .measurements import measure_mask

        if object_name not in self.targets:
            raise KeyError(f"no color key for object: {object_name}")
        spec = self.targets[object_name]
        target = np.array(spec["color"], dtype=np.int32)
        tolerance = float(spec.get("tolerance", 40))
        with Image.open(image_path) as img:
            pixels = np.asarray(img.convert("RGB"), dtype=np.int32)
        distance = np.sqrt(((pixels - target) ** 2).sum(axis=2))
        mask = distance <= tolerance
        found = bool(mask.any())
        return Segmentation(
            object_name=object_name,
            found=found,
            mask=mask if found else None,
            measurement=measure_mask(mask) if found else None,
        )


class MetaSAMSegmenter:
    """Live SAM 3.1 segmentation through the Meta Model API."""

    def __init__(self, api_key: str, base_url: str | None = None,
                 model: str | None = None):
        if not api_key:
            raise ValueError("live mode needs a Meta Model API key")
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def segment(self, image_path: str, object_name: str) -> Segmentation:
        from .measurements import measure_mask
        from .meta_api import segment_still_with_sam31

        mask = segment_still_with_sam31(
            image_path, object_name,
            api_key=self.api_key, base_url=self.base_url, model=self.model,
        )
        found = bool(mask is not None and mask.any())
        return Segmentation(
            object_name=object_name,
            found=found,
            mask=mask if found else None,
            measurement=measure_mask(mask) if found else None,
        )


def save_overlay(image_path: str, mask: np.ndarray, out_path: str,
                 color: tuple[int, int, int] = (255, 64, 64),
                 alpha: float = 0.45) -> str:
    """Write the evidence image: the frame with its mask blended on top."""
    with Image.open(image_path) as img:
        base = img.convert("RGB")
    overlay = Image.new("RGB", base.size, color)
    mask_img = Image.fromarray((mask.astype(np.uint8)) * 255, mode="L")
    blended = Image.composite(overlay, base, mask_img.point(lambda v: int(v * alpha)))
    blended.save(out_path)
    return out_path
