"""Deterministic comparison: ledgers plus mask measurements in, verdicts out.

Rules, in plain words:
- An object the ledger says is present in one take and missing in the
  other is a BLOCK. The ledger lines are the evidence.
- An object one ledger does not record at all is a REVIEW: the ledger
  itself is incomplete, so the check cannot settle. It is never a
  silent pass.
- An object the ledger says is present in both takes, but for which
  segmentation finds no mask in one of them, is a REVIEW: cannot
  verify. It is never a silent pass.
- Mask measurements that move beyond the thresholds (area change,
  centroid shift on either axis) are a BLOCK with the measurements
  attached. Area is judged as a share of the frame, so two takes at
  different resolutions still compare honestly.
- A beat one ledger records as observed and the other does not is a
  REVIEW at scene level (beat_flags): a real disagreement, softer
  than a presence contradiction, so the human decides.
- A mask touching the frame edge is a REVIEW, a cropping warning. Edge
  contact is never treated as proof of cropping on its own.
- Anything the rules cannot settle is left for the judge layer or the
  human. The overall verdict is the most severe flag, or ALLOW when
  there are no flags.

No model calls live here.
"""

from __future__ import annotations

AREA_CHANGE_BLOCK = 0.35        # relative area change beyond this blocks
CENTROID_SHIFT_BLOCK = 0.10     # centroid shift (x over width, y over height) beyond this blocks

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

    if ledger_a.get("scene_id") != ledger_b.get("scene_id"):
        raise ValueError(
            "ledgers describe different scenes: "
            f"{ledger_a.get('scene_id')!r} vs {ledger_b.get('scene_id')!r}")

    flags: list[dict] = []
    objs_a = {o["name"]: o for o in ledger_a.get("objects", [])}
    objs_b = {o["name"]: o for o in ledger_b.get("objects", [])}
    present_a = objs_a.get(target_object, {}).get("present")
    present_b = objs_b.get(target_object, {}).get("present")

    ledger_diffs = [d for d in diff_ledgers(ledger_a, ledger_b)
                    if d.get("object") == target_object]

    if present_a is None or present_b is None:
        unrecorded = []
        if present_a is None:
            unrecorded.append(ledger_a["take_id"])
        if present_b is None:
            unrecorded.append(ledger_b["take_id"])
        flags.append(_flag(
            "REVIEW", "cannot_verify",
            f"{target_object} is not recorded in the ledger for: "
            f"{', '.join(unrecorded)}. The check cannot settle on an "
            f"incomplete ledger. Raised to the human.",
            {"recorded": {"take_a": present_a is not None,
                          "take_b": present_b is not None},
             "ledger_diffs": ledger_diffs},
        ))
    elif present_a != present_b:
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
            frac_a, frac_b = ma["area_fraction"], mb["area_fraction"]
            area_change = (abs(frac_b - frac_a) / frac_a) if frac_a else 0.0
            # Movement on either axis counts: x shift as a fraction of
            # frame width, y shift as a fraction of frame height. The
            # larger of the two is the shift the rule judges.
            if ma["centroid"] and mb["centroid"]:
                shift_fraction = max(
                    abs(mb["centroid"]["x"] - ma["centroid"]["x"]),
                    abs(mb["centroid"]["y"] - ma["centroid"]["y"]),
                )
            else:
                shift_fraction = 0.0
            # An area shrink in a take whose mask touches the frame edge
            # is explained by the object leaving the frame; it belongs to
            # the cropping warning below, not to a size-change block.
            area_explained_by_edge = (
                (mb["touches_edge"] and frac_b < frac_a)
                or (ma["touches_edge"] and frac_a < frac_b)
            )
            if area_change > AREA_CHANGE_BLOCK and not area_explained_by_edge:
                flags.append(_flag(
                    "BLOCK", "mask_area_change",
                    f"{target_object} mask area changed by "
                    f"{area_change:.0%} across takes.",
                    {"area_px": {"take_a": area_a, "take_b": area_b},
                     "area_fraction": {"take_a": round(frac_a, 6),
                                       "take_b": round(frac_b, 6)},
                     "area_change_fraction": round(area_change, 4)},
                ))
            if shift_fraction > CENTROID_SHIFT_BLOCK:
                flags.append(_flag(
                    "BLOCK", "mask_moved",
                    f"{target_object} mask centroid moved by "
                    f"{shift_fraction:.0%} of the frame across takes.",
                    {"centroid": {"take_a": ma["centroid"], "take_b": mb["centroid"]},
                     "shift_fraction": round(shift_fraction, 4)},
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


def beat_flags(ledger_a: dict, ledger_b: dict) -> list[dict]:
    """Scene-level flags for beats the two ledgers disagree on.

    diff_ledgers calls beat-observation differences verdict-grade;
    until review round 2 they never reached a verdict record at all.
    A beat mismatch is a REVIEW, not a BLOCK: the disagreement is
    real, but a beat observation is a softer signal than an object's
    presence contradiction, so the human decides what it means.
    """
    from ..ledger.ledger import diff_ledgers

    diffs = [d for d in diff_ledgers(ledger_a, ledger_b)
             if d.get("kind") == "beat"]
    if not diffs:
        return []
    detail = "; ".join(
        f"{d['beat']} (take_a observed={d['take_a']}, "
        f"take_b observed={d['take_b']})" for d in diffs)
    return [_flag(
        "REVIEW", "beat_mismatch",
        f"Beats the two ledgers disagree on: {detail}. Raised to "
        f"the human.",
        {"beat_diffs": diffs},
    )]


def overall_verdict(object_verdicts: list[dict]) -> str:
    verdict = "ALLOW"
    for record in object_verdicts:
        if SEVERITY_ORDER[record["verdict"]] > SEVERITY_ORDER[verdict]:
            verdict = record["verdict"]
    return verdict
