"""Deterministic comparison: ledgers plus mask measurements in, verdicts out.

Rules, in plain words:
- An object the ledger says is present in one take and missing in the
  other is a BLOCK. The ledger lines are the evidence.
- An object the ledger says is present in both takes, but for which
  segmentation finds no mask in one of them, is a REVIEW: cannot
  verify. It is never a silent pass.
- Mask measurements that move beyond the thresholds (area change,
  centroid shift) are a BLOCK with the measurements attached.
- A mask touching the frame edge is a REVIEW, a cropping warning. Edge
  contact is never treated as proof of cropping on its own.
- Anything the rules cannot settle is left for the judge layer or the
  human. The overall verdict is the most severe flag, or ALLOW when
  there are no flags.

No model calls live here.
"""

from __future__ import annotations

AREA_CHANGE_BLOCK = 0.35        # relative area change beyond this blocks
CENTROID_SHIFT_BLOCK = 0.10     # fraction of frame width beyond this blocks

SEVERITY_ORDER = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}


def _flag(severity: str, rule: str, message: str, evidence: dict) -> dict:
    return {"severity": severity, "rule": rule, "message": message,
            "evidence": evidence}


def compare_target(ledger_a: dict, ledger_b: dict,
                   seg_a, seg_b, target_object: str) -> dict:
    """Compare one target object across two takes.

    seg_a and seg_b are segment.Segmentation results for the target.
    Returns the verdict record for the object.
    """
    from ..ledger.ledger import diff_ledgers

    flags: list[dict] = []
    objs_a = {o["name"]: o for o in ledger_a.get("objects", [])}
    objs_b = {o["name"]: o for o in ledger_b.get("objects", [])}
    present_a = objs_a.get(target_object, {}).get("present")
    present_b = objs_b.get(target_object, {}).get("present")

    ledger_diffs = [d for d in diff_ledgers(ledger_a, ledger_b)
                    if d.get("object") == target_object]

    if present_a is not None and present_b is not None and present_a != present_b:
        missing_take = ledger_b["take_id"] if present_a else ledger_a["take_id"]
        flags.append(_flag(
            "BLOCK", "object_missing",
            f"{target_object} is present in one take and missing in {missing_take}.",
            {"ledger_diffs": ledger_diffs,
             "present": {"take_a": present_a, "take_b": present_b}},
        ))
    elif present_a and present_b:
        if not seg_a.found or not seg_b.found:
            missing = []
            if not seg_a.found:
                missing.append(ledger_a["take_id"])
            if not seg_b.found:
                missing.append(ledger_b["take_id"])
            flags.append(_flag(
                "REVIEW", "cannot_verify",
                f"Ledger lists {target_object} as present, but no mask was "
                f"found in: {', '.join(missing)}. Raised to the human.",
                {"mask_found": {"take_a": seg_a.found, "take_b": seg_b.found}},
            ))
        else:
            ma, mb = seg_a.measurement, seg_b.measurement
            area_a, area_b = ma["area_px"], mb["area_px"]
            area_change = (abs(area_b - area_a) / area_a) if area_a else 0.0
            shift_fraction = abs(mb["centroid"]["x"] - ma["centroid"]["x"]) \
                if ma["centroid"] and mb["centroid"] else 0.0
            # An area shrink in a take whose mask touches the frame edge
            # is explained by the object leaving the frame; it belongs to
            # the cropping warning below, not to a size-change block.
            area_explained_by_edge = (
                (mb["touches_edge"] and area_b < area_a)
                or (ma["touches_edge"] and area_a < area_b)
            )
            if area_change > AREA_CHANGE_BLOCK and not area_explained_by_edge:
                flags.append(_flag(
                    "BLOCK", "mask_area_change",
                    f"{target_object} mask area changed by "
                    f"{area_change:.0%} across takes.",
                    {"area_px": {"take_a": area_a, "take_b": area_b},
                     "area_change_fraction": round(area_change, 4)},
                ))
            if shift_fraction > CENTROID_SHIFT_BLOCK:
                flags.append(_flag(
                    "BLOCK", "mask_moved",
                    f"{target_object} mask centroid moved by "
                    f"{shift_fraction:.0%} of frame width across takes.",
                    {"centroid": {"take_a": ma["centroid"], "take_b": mb["centroid"]},
                     "shift_fraction_of_width": round(shift_fraction, 4)},
                ))
            if ma["touches_edge"] or mb["touches_edge"]:
                evidence = {"edge_contact": {"take_a": ma["edge_contact"],
                                             "take_b": mb["edge_contact"]}}
                if area_explained_by_edge:
                    evidence["area_px"] = {"take_a": area_a, "take_b": area_b}
                    evidence["note"] = ("Area is smaller in the take whose mask "
                                        "leaves the frame; consistent with "
                                        "cropping, not a size change.")
                flags.append(_flag(
                    "REVIEW", "cropping_warning",
                    f"{target_object} mask touches the frame edge. That is a "
                    f"cropping warning, not proof of cropping.",
                    evidence,
                ))

    verdict = "ALLOW"
    for flag in flags:
        if SEVERITY_ORDER[flag["severity"]] > SEVERITY_ORDER[verdict]:
            verdict = flag["severity"]
    return {
        "object": target_object,
        "verdict": verdict,
        "flags": flags,
        "measurements": {
            "take_a": seg_a.measurement if seg_a else None,
            "take_b": seg_b.measurement if seg_b else None,
        },
        "ledger_diffs": ledger_diffs,
    }


def overall_verdict(object_verdicts: list[dict]) -> str:
    verdict = "ALLOW"
    for record in object_verdicts:
        if SEVERITY_ORDER[record["verdict"]] > SEVERITY_ORDER[verdict]:
            verdict = record["verdict"]
    return verdict
