"""Beat-8 planted-case evaluation runner.

Reads the frozen labels in eval/cases.json, runs every case through
the real Cutline Studio pipeline (ledger validation, color-key
segmentation, deterministic compare, fixture judge), and scores the
verdicts with the TEST_SET_DESIGN.md rules:

- planted error: BLOCK is a catch, REVIEW is a half catch (sent to
  review), ALLOW is a miss.
- clean control or near miss: BLOCK is a false alarm, REVIEW is a
  soft alarm, ALLOW is a pass.
- contract case: the exact expected verdict must come back.

Also folds in the SAM 3.1 stills case from its saved live record
(SAM_TEST_2026-11-01/attempt3_mask_analysis.json, attempt 3,
2026-11-01): the recorded numbers are copied, and one derived number
(the box IoU against the ground truth recorded before that call) is
computed from the two recorded boxes and labelled as derived.

Everything here is fixture mode. No network call is made.

Run: python3 eval/run_beat8_eval.py
Writes: eval/results_2026-11-02.json
"""

from __future__ import annotations

import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from src.compare.compare import beat_flags, compare_target, overall_verdict
from src.judge.judge import FixtureJudge, settle
from src.ledger.ledger import validate_ledger
from src.segment.segment import ColorKeySegmenter

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
COMPETITION_DIR = os.path.dirname(REPO)
SAM_ANALYSIS = os.path.join(
    COMPETITION_DIR, "SAM_TEST_2026-11-01", "attempt3_mask_analysis.json")
# Ground-truth whole-lamp box, normalized 0..1000, recorded BEFORE the
# attempt-3 call in SAM_TEST_2026-11-01/attempt3_input_source.md.
SAM_GT_BOX = {"x_min": 0, "y_min": 40, "x_max": 905, "y_max": 1000}


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run_case(case: dict) -> dict:
    bundle = os.path.join(REPO, case["bundle"])
    ledger_a = load_json(os.path.join(bundle, "ledger_a.json"))
    ledger_b = load_json(os.path.join(bundle, "ledger_b.json"))
    for name, led in (("ledger_a", ledger_a), ("ledger_b", ledger_b)):
        errors = validate_ledger(led)
        if errors:
            raise SystemExit(f"{case['id']}: {name} fails schema: {errors}")
    targets = load_json(os.path.join(bundle, "targets.json"))["objects"]
    segmenter = ColorKeySegmenter(targets)
    obj = case["object"]
    seg_a = segmenter.segment(os.path.join(bundle, "take_a.png"), obj)
    seg_b = segmenter.segment(os.path.join(bundle, "take_b.png"), obj)
    record = compare_target(ledger_a, ledger_b, seg_a, seg_b, obj)
    verdict = record["verdict"]
    detail = {"object_verdict": verdict}
    if case.get("scene_level"):
        scene = beat_flags(ledger_a, ledger_b)
        records = [record]
        if scene:
            records.append({"verdict": "REVIEW", "flags": scene})
        verdict = overall_verdict(records)
        detail["scene_beat_flags"] = [f["rule"] for f in scene]
    judgment_info = None
    if case.get("judge"):
        judge = FixtureJudge(bundle)
        settled = settle(case["judge"], judge.answer(case["judge"]))
        judgment_info = {"question": case["judge"],
                         "verdict": settled["verdict"]}
        if settled["verdict"] != "ALLOW":
            verdict = settled["verdict"]
    result = {
        "id": case["id"],
        "group": case["group"],
        "kind": case["kind"],
        "object": obj,
        "bundle": case["bundle"],
        "expected": case["expected"],
        "actual": verdict,
        "rules_fired": [f["rule"] for f in record["flags"]],
        "measurements": record["measurements"],
        "object_verdict": detail["object_verdict"],
    }
    if "scene_beat_flags" in detail:
        result["scene_beat_flags"] = detail["scene_beat_flags"]
    if judgment_info is not None:
        result["judgment"] = judgment_info
    return result


def score(result: dict) -> str:
    actual = result["actual"]
    if result["group"] == "planted":
        return {"BLOCK": "catch", "REVIEW": "half catch (sent to review)",
                "ALLOW": "miss"}[actual]
    if result["group"] in ("clean", "near_miss"):
        return {"BLOCK": "false alarm", "REVIEW": "soft alarm",
                "ALLOW": "pass"}[actual]
    return "pass" if actual == result["expected"] else "FAIL"


def sam_stills_section() -> dict:
    analysis = load_json(SAM_ANALYSIS)
    pred = analysis["bbox_normalized_1000"]
    inter_w = max(0, min(pred["x_max"], SAM_GT_BOX["x_max"])
                  - max(pred["x_min"], SAM_GT_BOX["x_min"]))
    inter_h = max(0, min(pred["y_max"], SAM_GT_BOX["y_max"])
                  - max(pred["y_min"], SAM_GT_BOX["y_min"]))
    inter = inter_w * inter_h
    pred_area = ((pred["x_max"] - pred["x_min"])
                 * (pred["y_max"] - pred["y_min"]))
    gt_area = ((SAM_GT_BOX["x_max"] - SAM_GT_BOX["x_min"])
               * (SAM_GT_BOX["y_max"] - SAM_GT_BOX["y_min"]))
    iou = inter / (pred_area + gt_area - inter)
    return {
        "source": "SAM_TEST_2026-11-01/attempt3_mask_analysis.json "
                  "(live attempt 3, 2026-11-01; recorded numbers copied)",
        "mask_pixels": analysis["mask_pixels"],
        "frame_coverage_fraction": analysis["coverage_fraction"],
        "mask_mass_inside_gt_lamp_bbox": analysis[
            "mask_mass_inside_gt_lamp_bbox"],
        "gt_shade_bbox_covered": analysis["gt_shade_covered"],
        "gt_lamp_bbox_covered": analysis["gt_lamp_bbox_covered"],
        "mask_bbox_normalized_1000": pred,
        "gt_lamp_bbox_normalized_1000": SAM_GT_BOX,
        "bbox_iou_derived_from_recorded_boxes": round(iou, 4),
    }


def main() -> None:
    cases = load_json(os.path.join(EVAL_DIR, "cases.json"))["cases"]
    started = time.perf_counter()
    results = []
    for case in cases:
        result = run_case(case)
        result["outcome"] = score(result)
        results.append(result)
        print(f"{result['id']:>3} {result['group']:<9} "
              f"{result['kind']:<52} expected {result['expected']:<6} "
              f"actual {result['actual']:<6} {result['outcome']}")
    wall = time.perf_counter() - started

    def count(group: str, outcome: str) -> int:
        return sum(1 for r in results
                   if r["group"] == group and r["outcome"] == outcome)

    summary = {
        "planted_errors": sum(1 for r in results if r["group"] == "planted"),
        "caught_block": count("planted", "catch"),
        "sent_to_review": count("planted", "half catch (sent to review)"),
        "missed": count("planted", "miss"),
        "clean_controls": sum(1 for r in results if r["group"] == "clean"),
        "near_misses": sum(1 for r in results
                            if r["group"] == "near_miss"),
        "false_alarms_block_on_clean_or_near_miss": (
            count("clean", "false alarm")
            + count("near_miss", "false alarm")),
        "soft_alarms_review_on_clean_or_near_miss": (
            count("clean", "soft alarm") + count("near_miss", "soft alarm")),
        "contract_cases": sum(1 for r in results
                              if r["group"] == "contract"),
        "contract_passed": count("contract", "pass"),
        "wall_seconds_all_cases": round(wall, 3),
    }
    out = {
        "suite": "Cutline Studio planted-case evaluation, beat 8",
        "run_date": "2026-11-02",
        "mode": "fixture (color-key segmentation, deterministic "
                "compare); no network calls",
        "labels": "eval/cases.json, frozen before the run",
        "scoring": "TEST_SET_DESIGN.md",
        "summary": summary,
        "cases": results,
        "sam_stills_live_case": sam_stills_section(),
    }
    out_path = os.path.join(EVAL_DIR, "results_2026-11-02.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("\nsummary:", json.dumps(summary, indent=2))
    print("wrote", out_path)


if __name__ == "__main__":
    main()
