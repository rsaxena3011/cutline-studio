"""Ingest stage.

Loads and validates the inputs of one comparison job: two takes of the
same scene (stills, or a short clip that is sampled into frames), the
script or brief text, and the target object named by the editor.
No model calls live here.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field

from PIL import Image


@dataclass
class Still:
    """One still image (an uploaded take, or one sampled frame of a clip)."""

    path: str
    width: int
    height: int
    frame_time_seconds: float | None = None

    @property
    def kind(self) -> str:
        return "sampled_frame" if self.frame_time_seconds is not None else "still"


@dataclass
class Job:
    """A normalized comparison job handed to the ledger stage."""

    scene_id: str
    take_a: Still
    take_b: Still
    brief_text: str
    target_object: str
    extra: dict = field(default_factory=dict)


def load_still(path: str, frame_time_seconds: float | None = None) -> Still:
    """Load one still and record its geometry. Raises on unreadable input."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"still not found: {path}")
    with Image.open(path) as img:
        img.verify()
    with Image.open(path) as img:
        width, height = img.size
    return Still(path=path, width=width, height=height,
                 frame_time_seconds=frame_time_seconds)


def sample_frames(clip_path: str, every_seconds: float, out_dir: str) -> list[Still]:
    """Sample frames from a short clip with ffmpeg.

    Each sampled frame is judged as a still downstream. No identity is
    tracked across frames anywhere in Cutline Studio.
    """
    if not os.path.isfile(clip_path):
        raise FileNotFoundError(f"clip not found: {clip_path}")
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, "frame_%04d.png")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", clip_path,
         "-vf", f"fps=1/{every_seconds}", pattern],
        check=True,
    )
    stills = []
    for index, name in enumerate(sorted(os.listdir(out_dir))):
        if name.endswith(".png"):
            stills.append(load_still(os.path.join(out_dir, name),
                                     frame_time_seconds=index * every_seconds))
    return stills


def build_job(scene_id: str, take_a_path: str, take_b_path: str,
              brief_text: str, target_object: str,
              take_a_time: float | None = None,
              take_b_time: float | None = None) -> Job:
    """Validate inputs and build the normalized job."""
    if not target_object.strip():
        raise ValueError("a target object must be named")
    return Job(
        scene_id=scene_id,
        take_a=load_still(take_a_path, take_a_time),
        take_b=load_still(take_b_path, take_b_time),
        brief_text=brief_text,
        target_object=target_object.strip(),
    )
