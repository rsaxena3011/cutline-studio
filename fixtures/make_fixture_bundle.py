"""Generate the studio_desk fixture bundle: two synthetic takes of one scene.

Take A is the clean reference. Take B plants two continuity errors,
one near miss, and one unverifiable case:
- the brass lamp is gone from the desk (a BLOCK: missing object),
- the sponsor logo board has drifted so its mask touches the right
  frame edge (a REVIEW: cropping warning, not proof),
- the presenter's jacket is a lighter shade under changed lighting
  (a judgment case: same jacket, cited, ALLOW),
- the desk plant is drawn in take A only, while both ledgers record
  it as present (a REVIEW: cannot verify; the ledger claims it, no
  mask can settle it, added in review round 2 for demo beat 6).

The drawings are deliberately simple so the color keys in targets.json
segment them exactly; the pipeline still computes every mask and
measurement from the real pixels.

Run: python3 fixtures/make_fixture_bundle.py
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
PLANT_GREEN = (46, 139, 87)
PLANT_POT = (170, 80, 50)


def draw_scene(jacket, with_lamp: bool, logo_x: int,
               with_plant: bool = False) -> Image.Image:
    img = Image.new("RGB", (W, H), WALL)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 270, W, H], fill=FLOOR)
    d.rectangle([120, 250, 560, 320], fill=DESK)          # desk
    d.ellipse([80, 70, 130, 120], fill=SKIN)              # head
    d.rectangle([60, 120, 150, 280], fill=jacket)         # jacket / torso
    if with_plant:
        d.ellipse([472, 196, 508, 232], fill=PLANT_GREEN)  # plant leaves
        d.rectangle([480, 230, 500, 252], fill=PLANT_POT)  # plant pot
    if with_lamp:
        d.rectangle([425, 195, 435, 255], fill=GOLD)      # lamp stem
        d.polygon([(405, 195), (455, 195), (443, 162), (417, 162)], fill=GOLD)
        d.ellipse([422, 176, 438, 192], fill=(250, 230, 150))
    d.rectangle([logo_x, 30, logo_x + 150, 80], fill=LOGO_WHITE)
    d.text((logo_x + 12, 48), "ACME", fill=INK)
    return img


def main() -> None:
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio_desk")
    os.makedirs(out_dir, exist_ok=True)
    draw_scene(JACKET_A, with_lamp=True, logo_x=470, with_plant=True).save(
        os.path.join(out_dir, "take_a.png"))
    draw_scene(JACKET_B, with_lamp=False, logo_x=545).save(
        os.path.join(out_dir, "take_b.png"))

    base_objects = [
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
    beats = [{"beat": "presenter introduces the sponsor", "observed": True}]

    def ledger(take_id: str, lamp_present: bool) -> dict:
        objects = []
        for obj in base_objects:
            entry = dict(obj)
            if entry["name"] == "brass lamp":
                entry["present"] = lamp_present
            objects.append(entry)
        return {"scene_id": "studio-desk-01", "take_id": take_id,
                "source": {"kind": "still", "frame_time_seconds": None},
                "objects": objects, "beats": beats}

    with open(os.path.join(out_dir, "ledger_a.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger("take_a", True), fh, indent=2)
    with open(os.path.join(out_dir, "ledger_b.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger("take_b", False), fh, indent=2)

    targets = {"objects": {
        "brass lamp": {"color": list(GOLD), "tolerance": 50},
        "sponsor logo": {"color": list(LOGO_WHITE), "tolerance": 40},
        "presenter jacket": {"color": [58, 104, 216], "tolerance": 70},
        "desk plant": {"color": list(PLANT_GREEN), "tolerance": 40},
    }}
    with open(os.path.join(out_dir, "targets.json"), "w", encoding="utf-8") as fh:
        json.dump(targets, fh, indent=2)

    judgments = {"jacket_identity": {
        "question": "Is the jacket in take_b the same jacket as in take_a?",
        "decision": "same_item",
        "verdict_effect": "allow",
        "rationale": "Both ledgers describe the same blue jacket. The shade "
                     "shift is consistent with a lighting change, and the "
                     "mask position and size are stable across takes.",
        "citations": {
            "ledger_lines": ["take_a.objects[presenter jacket]",
                             "take_b.objects[presenter jacket]"],
            "frames": ["take_a.png", "take_b.png"],
        },
    }}
    with open(os.path.join(out_dir, "judgments.json"), "w", encoding="utf-8") as fh:
        json.dump(judgments, fh, indent=2)

    with open(os.path.join(out_dir, "brief.txt"), "w", encoding="utf-8") as fh:
        fh.write("Studio desk scene. The presenter introduces the sponsor. "
                 "The brass lamp stays on the desk. The sponsor logo board "
                 "stays fully inside the frame. The presenter wears the "
                 "blue jacket throughout. A small desk plant sits to the "
                 "right of the lamp.\n")
    print(f"bundle written to {out_dir}")


if __name__ == "__main__":
    main()
