"""Cutline Studio command line.

Run from the repository root:

  python3 -m src.cli check-still --image still.png --object "brass lamp" \
      --color 212,160,23 --tolerance 50

  python3 -m src.cli compare --bundle fixtures/studio_desk \
      --object "brass lamp" --judge jacket_identity

Modes: fixture (default, color-key segmentation from the bundle's
targets.json) and live (SAM 3.1 through the Meta Model API). Live
mode is unverified; see the Status section of the README before
relying on it. In this workspace the credential is held by the
registered Meta Model API connector, not in a file; the .env key
route below is the standalone fallback for other runners. A live
call that fails produces a REVIEW, never a silent pass, and never
a traceback. Verdicts are printed as a report and written as JSON
when --out is given. Evidence overlays are written when --out-dir
is given.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests
from PIL import UnidentifiedImageError

from .compare.compare import compare_target, overall_verdict
from .ingest.ingest import build_job, load_still
from .judge.judge import FixtureJudge, settle
from .ledger.ledger import validate_ledger
from .segment.segment import (ColorKeySegmenter, MetaSAMSegmenter,
                              Segmentation, save_overlay)
from .ui.review import render_report, run_review


def _load_env() -> dict:
    env = {}
    path = os.path.join(os.getcwd(), ".env")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
    return env


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _segmenter(mode: str, targets: dict | None):
    if mode == "live":
        env = _load_env()
        key = env.get("META_API_KEY") or env.get("META_MODEL_API_KEY") \
            or os.environ.get("META_API_KEY") or os.environ.get("META_MODEL_API_KEY")
        if not key:
            raise SystemExit("live mode needs META_API_KEY (or META_MODEL_API_KEY) "
                             "in the repo .env")
        return MetaSAMSegmenter(key)
    if targets is None:
        raise SystemExit("fixture mode needs color targets (--color or a bundle)")
    return ColorKeySegmenter(targets)


def _segment_or_review(segmenter, image_path: str, object_name: str,
                       mode: str):
    """Run one segmentation.

    In live mode a failed call is data, not a crash: it returns a
    not-found segmentation plus the error, so the verdict layer can
    raise a REVIEW. In fixture mode errors propagate to the clean
    error path in main(); a local bug must not dress up as a verdict.
    """
    try:
        return segmenter.segment(image_path, object_name), None
    except requests.RequestException as exc:
        if mode != "live":
            raise
        return Segmentation(object_name=object_name, found=False,
                            mask=None, measurement=None), str(exc)


def cmd_check_still(args) -> int:
    still = load_still(args.image)
    targets = None
    if args.color:
        rgb = tuple(int(v) for v in args.color.split(","))
        targets = {args.object: {"color": list(rgb),
                                 "tolerance": args.tolerance}}
    segmenter = _segmenter(args.mode, targets)
    seg, live_error = _segment_or_review(segmenter, args.image,
                                         args.object, args.mode)
    if live_error is not None:
        verdict = {"object": args.object, "verdict": "REVIEW",
                   "reason": "Live segmentation call failed "
                             f"({live_error}). Cannot verify; raised "
                             "to the human.",
                   "measurement": None}
        print(json.dumps({"still": args.image,
                          "size": [still.width, still.height],
                          **verdict}, indent=2))
        return 0
    if not seg.found:
        verdict = {"object": args.object, "verdict": "REVIEW",
                   "reason": "No mask found. Cannot verify; raised to the human.",
                   "measurement": None}
    else:
        measurement = seg.measurement
        verdict = {"object": args.object,
                   "verdict": "REVIEW" if measurement["touches_edge"] else "ALLOW",
                   "reason": ("Mask touches the frame edge: cropping warning, "
                              "not proof." if measurement["touches_edge"]
                              else "Mask measured, inside the frame."),
                   "measurement": measurement}
        if args.out_dir:
            os.makedirs(args.out_dir, exist_ok=True)
            save_overlay(args.image, seg.mask,
                         os.path.join(args.out_dir, "overlay.png"))
    print(json.dumps({"still": args.image, "size": [still.width, still.height],
                      **verdict}, indent=2))
    return 0


def cmd_compare(args) -> int:
    bundle = args.bundle
    take_a = os.path.join(bundle, "take_a.png")
    take_b = os.path.join(bundle, "take_b.png")
    ledger_a = _read_json(os.path.join(bundle, "ledger_a.json"))
    ledger_b = _read_json(os.path.join(bundle, "ledger_b.json"))
    for name, ledger in (("ledger_a", ledger_a), ("ledger_b", ledger_b)):
        errors = validate_ledger(ledger)
        if errors:
            raise SystemExit(f"{name} fails the ledger schema: {errors}")
    targets = _read_json(os.path.join(bundle, "targets.json"))["objects"]
    brief_path = os.path.join(bundle, "brief.txt")
    brief_text = ""
    if os.path.isfile(brief_path):
        with open(brief_path, encoding="utf-8") as fh:
            brief_text = fh.read()
    job = build_job(ledger_a["scene_id"], take_a, take_b, brief_text, args.object)
    segmenter = _segmenter(args.mode, targets)
    seg_a, err_a = _segment_or_review(segmenter, take_a, args.object,
                                      args.mode)
    seg_b, err_b = _segment_or_review(segmenter, take_b, args.object,
                                      args.mode)
    for take_id, err in (("take_a", err_a), ("take_b", err_b)):
        if err is not None:
            print(f"warning: live segmentation failed for {take_id} "
                  f"({err}); treated as no mask found.", file=sys.stderr)
    record = compare_target(ledger_a, ledger_b, seg_a, seg_b, args.object)
    judgments = []
    if args.judge:
        judge = FixtureJudge(bundle)
        judgments.append(settle(args.judge, judge.answer(args.judge)))
    result = {
        "scene_id": job.scene_id,
        "verdict": overall_verdict([record] + [
            {"verdict": j["verdict"]} for j in judgments]),
        "objects": [record],
        "judgments": judgments,
    }
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        if seg_a.found:
            save_overlay(take_a, seg_a.mask,
                         os.path.join(args.out_dir, "take_a_overlay.png"))
        if seg_b.found:
            save_overlay(take_b, seg_b.mask,
                         os.path.join(args.out_dir, "take_b_overlay.png"))
        with open(os.path.join(args.out_dir, "verdict.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
    print(render_report(result))
    if args.interactive:
        decisions = run_review(result)
        print("Editor decisions:", json.dumps(decisions, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cutline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_still = sub.add_parser("check-still", help="segment one still, verdict out")
    p_still.add_argument("--image", required=True)
    p_still.add_argument("--object", required=True)
    p_still.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    p_still.add_argument("--color", help="fixture color key as R,G,B")
    p_still.add_argument("--tolerance", type=float, default=40)
    p_still.add_argument("--out-dir")
    p_still.set_defaults(fn=cmd_check_still)

    p_cmp = sub.add_parser("compare", help="compare two takes from a bundle")
    p_cmp.add_argument("--bundle", required=True)
    p_cmp.add_argument("--object", required=True)
    p_cmp.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    p_cmp.add_argument("--judge", help="judgment question key from the bundle")
    p_cmp.add_argument("--out-dir")
    p_cmp.add_argument("--interactive", action="store_true")
    p_cmp.set_defaults(fn=cmd_compare)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError,
            UnidentifiedImageError) as exc:
        # Malformed or missing inputs get a clean error, not a
        # traceback: these are the inputs a judge will actually feed
        # the tool. SystemExit (schema failures, missing keys) keeps
        # its own message and is not caught here.
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
