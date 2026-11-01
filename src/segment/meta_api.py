"""SAM 3.1 stills call through the Meta Model API.

Wire facts, from Meta's developer documentation and the SAM 3.1
protocol description (checked 2026-11-01):
- Base URL: https://api.meta.ai/v1, OpenAI-compatible. Auth is a
  Bearer key (the docs name it MODEL_API_KEY).
- SAM 3.1 model id: sam-3.1. Input: an image plus a short noun-phrase
  text prompt naming one thing. Output: a box and a mask per match.
- The mask output travels as streamed text records in the Responses
  API: box records and mask records whose payload is a base85-encoded
  compressed raster. The meta-sam-parser package implements that
  protocol (strict raster decoding, image and video formats) and is
  used here to decode; nothing in this module hand-rolls the encoding.

Scope: stills only. Cutline Studio makes no tracking claim, and this
module only ever segments one still per call.
"""

from __future__ import annotations

import base64
import json
import os

import numpy as np
import requests

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "sam-3.1"


def _image_data_url(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp"}.get(ext, "image/png")
    with open(image_path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _collect_stream_text(response: requests.Response) -> str:
    """Collect the text payload of a streamed Responses API call."""
    chunks: list[str] = []
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "response.output_text.delta":
                chunks.append(event.get("delta", ""))
            elif event.get("type") == "response.output_text.done":
                text = event.get("text")
                if text and not chunks:
                    chunks.append(text)
        else:
            # Non-SSE fallback: a plain JSON body.
            try:
                body = json.loads(line)
            except json.JSONDecodeError:
                chunks.append(line)
                continue
            for item in body.get("output", []):
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        chunks.append(part.get("text", ""))
    return "".join(chunks)


def _mask_from_protocol_text(text: str) -> np.ndarray | None:
    """Decode the first mask record of a SAM 3.1 image response.

    Uses meta-sam-parser, the protocol's reference parser. Returns a
    boolean numpy array at the mask's own raster size, or None when the
    response carries no mask.
    """
    from meta_sam_parser import CompletedOutcome, image_segmentation_format

    parser = image_segmentation_format().create_parser()
    for snapshot in parser.push(text):
        _ = snapshot  # cumulative snapshots; the finish result is authoritative
    finished = parser.finish(CompletedOutcome())
    records = getattr(finished.result, "records", None) or []
    for record in records:
        raster = getattr(record, "raster", None)
        if raster is not None:
            return np.asarray(raster).astype(bool)
    return None


def segment_still_with_sam31(image_path: str, prompt: str, api_key: str,
                             base_url: str | None = None,
                             model: str | None = None,
                             timeout: int = 120) -> np.ndarray | None:
    """Segment one still with SAM 3.1. Returns a boolean mask or None.

    Raises on transport or HTTP failure; the caller decides what an
    unreachable live call means (the pipeline falls back to a REVIEW,
    never a silent pass).
    """
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    payload = {
        "model": model or DEFAULT_MODEL,
        "stream": True,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": _image_data_url(image_path)},
                {"type": "input_text", "text": prompt},
            ],
        }],
    }
    with requests.post(
        f"{base}/responses",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json=payload, timeout=timeout, stream=True,
    ) as response:
        response.raise_for_status()
        text = _collect_stream_text(response)
    if os.environ.get("CUTLINE_DEBUG_RAW"):
        with open(os.environ["CUTLINE_DEBUG_RAW"], "w", encoding="utf-8") as fh:
            fh.write(text)
    if not text.strip():
        return None
    return _mask_from_protocol_text(text)
