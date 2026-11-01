"""Scene ledger validation and deterministic diff.

One ledger per take, written against scene_ledger.schema.json in this
folder. The validator here enforces the same contract (required fields,
enums) with no third-party dependency, so the diff never runs on a
ledger that does not meet the schema.

The diff is plain code. It reports field-level differences between two
takes of the same scene; it never invents a difference it cannot point
at, and it returns the exact values from both ledgers as evidence.
"""

from __future__ import annotations

CATEGORIES = {"wardrobe", "prop", "logo", "set", "other"}
SOURCE_KINDS = {"still", "sampled_frame"}


def validate_ledger(ledger: dict) -> list[str]:
    """Return a list of schema violations; empty means valid."""
    errors: list[str] = []
    if not isinstance(ledger, dict):
        return ["ledger is not an object"]
    for key in ("scene_id", "take_id", "source", "objects", "beats"):
        if key not in ledger:
            errors.append(f"missing required field: {key}")
    source = ledger.get("source")
    if isinstance(source, dict):
        if source.get("kind") not in SOURCE_KINDS:
            errors.append("source.kind must be one of: still, sampled_frame")
    elif "source" in ledger:
        errors.append("source must be an object")
    objects = ledger.get("objects")
    if isinstance(objects, list):
        for i, obj in enumerate(objects):
            if not isinstance(obj, dict):
                errors.append(f"objects[{i}] is not an object")
                continue
            if "name" not in obj:
                errors.append(f"objects[{i}] missing required field: name")
            if "present" not in obj:
                errors.append(f"objects[{i}] missing required field: present")
            elif not isinstance(obj["present"], bool):
                errors.append(f"objects[{i}].present must be a boolean")
            if "category" in obj and obj["category"] not in CATEGORIES:
                errors.append(f"objects[{i}].category is not a known category")
    elif "objects" in ledger:
        errors.append("objects must be an array")
    beats = ledger.get("beats")
    if isinstance(beats, list):
        for i, beat in enumerate(beats):
            if not isinstance(beat, dict):
                errors.append(f"beats[{i}] is not an object")
                continue
            if "beat" not in beat:
                errors.append(f"beats[{i}] missing required field: beat")
            if "observed" not in beat:
                errors.append(f"beats[{i}] missing required field: observed")
    elif "beats" in ledger:
        errors.append("beats must be an array")
    return errors


def _objects_by_name(ledger: dict) -> dict[str, dict]:
    return {obj["name"]: obj for obj in ledger.get("objects", [])}


def diff_ledgers(ledger_a: dict, ledger_b: dict) -> list[dict]:
    """Field-by-field diff of two ledgers for the same scene.

    Presence and beat-observation differences are verdict-grade diffs.
    Other field changes (description, screen region) are returned as
    notes: visible evidence, but not by themselves a verdict.
    """
    diffs: list[dict] = []
    objs_a = _objects_by_name(ledger_a)
    objs_b = _objects_by_name(ledger_b)
    for name in sorted(set(objs_a) | set(objs_b)):
        in_a = name in objs_a
        in_b = name in objs_b
        if in_a and in_b:
            a, b = objs_a[name], objs_b[name]
            if a.get("present") != b.get("present"):
                diffs.append({
                    "kind": "presence",
                    "object": name,
                    "take_a": a.get("present"),
                    "take_b": b.get("present"),
                    "citation": f"{ledger_a['take_id']}.objects[{name}] vs "
                                f"{ledger_b['take_id']}.objects[{name}]",
                })
            for field_name in ("description", "screen_region", "category"):
                if a.get(field_name) != b.get(field_name):
                    diffs.append({
                        "kind": "note",
                        "object": name,
                        "field": field_name,
                        "take_a": a.get(field_name),
                        "take_b": b.get(field_name),
                        "citation": f"{ledger_a['take_id']}.objects[{name}].{field_name} vs "
                                    f"{ledger_b['take_id']}.objects[{name}].{field_name}",
                    })
        else:
            present_in = ledger_a["take_id"] if in_a else ledger_b["take_id"]
            diffs.append({
                "kind": "presence",
                "object": name,
                "take_a": objs_a[name].get("present") if in_a else None,
                "take_b": objs_b[name].get("present") if in_b else None,
                "citation": f"object listed only in {present_in}",
            })
    beats_a = {b["beat"]: b for b in ledger_a.get("beats", [])}
    beats_b = {b["beat"]: b for b in ledger_b.get("beats", [])}
    for beat in sorted(set(beats_a) | set(beats_b)):
        if beat in beats_a and beat in beats_b:
            if beats_a[beat].get("observed") != beats_b[beat].get("observed"):
                diffs.append({
                    "kind": "beat",
                    "beat": beat,
                    "take_a": beats_a[beat].get("observed"),
                    "take_b": beats_b[beat].get("observed"),
                    "citation": f"beats[{beat}] observed differs across takes",
                })
    return diffs
