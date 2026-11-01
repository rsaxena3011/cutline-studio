"""Generate the extra eval bundles for the beat-8 planted-case suite.

Each bundle plants exactly the difference its label in cases.json
records, drawn with the same palette and layout as the studio_desk
fixture so the pipeline reads them the same way. Images only: this
script contains no verdict logic, and the labels live in cases.json,
frozen before the run.

Bundles: moved_lamp, vertical_lamp, grown_lamp, colour_drift,
identical, half_res, near_edge, unrecorded, beat_mismatch.

Run: python3 eval/make_eval_bundles.py
"""

from __future__ import annotations

import json
import os

from PIL import Image, ImageDraw

W, H = 640, 360
WALL = (91, 107, 122)
FLOOR = (60, 52, 44)
DESK = (122, 74, 33)
SKIN = (222, 184, 150)
GOLD = (212, 160, 23)
LOGO_WHITE = (245, 245, 245)
INK = (30, 30, 30)
JACKET_A = (36, 86, 200)
JACKET_B = (91, 132, 224)
JACKET_RED = (200, 40, 40)
PLANT_GREEN = (46, 139, 87)
PLANT_POT = (170, 80, 50)

BASE_OBJECTS = [
    {"name": "brass lamp", "category": "prop", "present": True,
     "description": "Brass lamp on the desk, right of the presenter",
     "screen_region": "center-right"},
    {"name": "sponsor logo", "category": "logo", "present": True,
     "description": "Sponsor logo board, top right",
     "screen_region": "top-right"},
    {"name": "presenter jacket", "category": "wardrobe", "present": True,
     "description": "Blue jacket", "screen_region": "left"},
    {"name": "desk plant", "category": "prop", "present": True,
     "description": "Small plant on the desk, right of the lamp",
     "screen_region": "center-right"},
]
BEATS = [{"beat": "presenter introduces the sponsor", "observed": True}]

TARGETS = {"objects": {
    "brass lamp": {"color": list(GOLD), "tolerance": 50},
    "sponsor logo": {"color": list(LOGO_WHITE), "tolerance": 40},
    "presenter jacket": {"color": [58, 104, 216], "tolerance": 70},
    "desk plant": {"color": list(PLANT_GREEN), "tolerance": 40},
}}
BRIEF = ("Studio desk scene. The presenter introduces the sponsor. "
         "The brass lamp stays on the desk. The sponsor logo board "
         "stays fully inside the frame. The presenter wears the "
         "blue jacket throughout. A small desk plant sits to the "
         "right of the lamp.\n")


def draw_lamp(d: ImageDraw.ImageDraw, dx: int = 0, dy: int = 0,
              scale: float = 1.0) -> None:
    """Lamp drawn around its base anchor (430, 255), as in studio_desk."""
    def px(x: float) -> int:
        return int(round(430 + (x - 430) * scale)) + dx

    def py(y: float) -> int:
        return int(round(255 + (y - 255) * scale)) + dy

    d.rectangle([px(425), py(195), px(435), py(255)], fill=GOLD)
    d.polygon([(px(405), py(195)), (px(455), py(195)),
               (px(443), py(162)), (px(417), py(162))], fill=GOLD)
    d.ellipse([px(422), py(176), px(438), py(192)], fill=(250, 230, 150))


def draw_scene(jacket, lamp: bool = True, lamp_dx: int = 0,
               lamp_dy: int = 0, lamp_scale: float = 1.0,
               logo_x: int = 470, plant: bool = True) -> Image.Image:
    img = Image.new("RGB", (W, H), WALL)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 270, W, H], fill=FLOOR)
    d.rectangle([120, 250, 560, 320], fill=DESK)
    d.ellipse([80, 70, 130, 120], fill=SKIN)
    d.rectangle([60, 120, 150, 280], fill=jacket)
    if plant:
        d.ellipse([472, 196, 508, 232], fill=PLANT_GREEN)
        d.rectangle([480, 230, 500, 252], fill=PLANT_POT)
    if lamp:
        draw_lamp(d, dx=lamp_dx, dy=lamp_dy, scale=lamp_scale)
    d.rectangle([logo_x, 30, logo_x + 150, 80], fill=LOGO_WHITE)
    d.text((logo_x + 12, 48), "ACME", fill=INK)
    return img


def ledger(take_id: str, lamp_present: bool = True,
           drop_lamp: bool = False, beat_observed: bool = True) -> dict:
    objects = []
    for obj in BASE_OBJECTS:
        if drop_lamp and obj["name"] == "brass lamp":
            continue
        entry = dict(obj)
        if entry["name"] == "brass lamp":
            entry["present"] = lamp_present
        objects.append(entry)
    beats = [dict(b, observed=beat_observed) for b in BEATS]
    return {"scene_id": "studio-desk-01", "take_id": take_id,
            "source": {"kind": "still", "frame_time_seconds": None},
            "objects": objects, "beats": beats}


def write_bundle(root: str, name: str, take_a: Image.Image,
                 take_b: Image.Image, ledger_a: dict,
                 ledger_b: dict) -> None:
    out = os.path.join(root, name)
    os.makedirs(out, exist_ok=True)
    take_a.save(os.path.join(out, "take_a.png"))
    take_b.save(os.path.join(out, "take_b.png"))
    with open(os.path.join(out, "ledger_a.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger_a, fh, indent=2)
    with open(os.path.join(out, "ledger_b.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger_b, fh, indent=2)
    with open(os.path.join(out, "targets.json"), "w", encoding="utf-8") as fh:
        json.dump(TARGETS, fh, indent=2)
    with open(os.path.join(out, "brief.txt"), "w", encoding="utf-8") as fh:
        fh.write(BRIEF)
    print("bundle:", name)


def main() -> None:
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bundles")
    clean_a = draw_scene(JACKET_A)
    clean_b = draw_scene(JACKET_B)

    write_bundle(root, "moved_lamp", clean_a,
                 draw_scene(JACKET_B, lamp_dx=160),
                 ledger("take_a"), ledger("take_b"))
    write_bundle(root, "vertical_lamp", clean_a,
                 draw_scene(JACKET_B, lamp_dy=90),
                 ledger("take_a"), ledger("take_b"))
    write_bundle(root, "grown_lamp", clean_a,
                 draw_scene(JACKET_B, lamp_scale=1.5),
                 ledger("take_a"), ledger("take_b"))
    write_bundle(root, "colour_drift", clean_a,
                 draw_scene(JACKET_RED),
                 ledger("take_a"), ledger("take_b"))
    write_bundle(root, "identical", clean_a, draw_scene(JACKET_A),
                 ledger("take_a"), ledger("take_b"))
    half_b = clean_b.resize((320, 180), Image.NEAREST)
    write_bundle(root, "half_res", clean_a, half_b,
                 ledger("take_a"), ledger("take_b"))
    write_bundle(root, "near_edge", clean_a,
                 draw_scene(JACKET_B, logo_x=480),
                 ledger("take_a"), ledger("take_b"))
    write_bundle(root, "unrecorded", clean_a, clean_b,
                 ledger("take_a"), ledger("take_b", drop_lamp=True))
    write_bundle(root, "beat_mismatch", clean_a, clean_b,
                 ledger("take_a"), ledger("take_b", beat_observed=False))


if __name__ == "__main__":
    main()
