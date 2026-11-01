"""Evidence review: the human pass over the flags.

Renders one verdict record as a readable report: every flag with the
evidence behind it (mask measurements, ledger citations, judgment
citations). The editor accepts or rejects each flag; the interface
never auto-fixes and never exports. The editor's decision is final.
"""

from __future__ import annotations

import json


def render_report(result: dict) -> str:
    lines = []
    lines.append(f"Scene: {result['scene_id']}")
    lines.append(f"Overall verdict: {result['verdict']}")
    lines.append("")
    for record in result["objects"]:
        lines.append(f"Object: {record['object']}  Verdict: {record['verdict']}")
        if not record["flags"]:
            measurements = record.get("measurements") or {}
            if measurements.get("take_a") and measurements.get("take_b"):
                lines.append("  No flags. Measurements within tolerance.")
            else:
                lines.append("  No flags.")
        for flag in record["flags"]:
            lines.append(f"  [{flag['severity']}] {flag['rule']}: {flag['message']}")
            lines.append(f"    evidence: {json.dumps(flag['evidence'], default=str)}")
        lines.append("")
    for item in result.get("judgments", []):
        lines.append(f"Judgment: {item['question']}  Verdict: {item['verdict']}")
        if item.get("decision"):
            lines.append(f"  decision: {item['decision']}")
        if item.get("reason"):
            lines.append(f"  reason: {item['reason']}")
        if item.get("citations"):
            lines.append(f"  citations: {json.dumps(item['citations'], default=str)}")
        lines.append("")
    return "\n".join(lines)


def run_review(result: dict, input_fn=input, output_fn=print) -> dict:
    """Interactive accept / reject pass. Returns the editor's decisions.

    decisions maps "object:rule" to "accepted" or "rejected".
    """
    decisions: dict[str, str] = {}
    output_fn(render_report(result))
    for record in result["objects"]:
        for flag in record["flags"]:
            key = f"{record['object']}:{flag['rule']}"
            while True:
                answer = input_fn(
                    f"Flag {key} [{flag['severity']}]: accept (a) or reject (r)? "
                ).strip().lower()
                if answer in ("a", "accept"):
                    decisions[key] = "accepted"
                    break
                if answer in ("r", "reject"):
                    decisions[key] = "rejected"
                    break
                output_fn("Please answer a or r.")
    return decisions
