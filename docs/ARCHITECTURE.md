# Cutline Studio: architecture

## Pipeline

ingest -> ledger -> segment -> compare -> judge -> review

1. **Ingest** (`src/ingest/`): two takes of one scene (stills, or a short clip plus a frame-sampling rate), the script or brief text, and one target object named by the editor.
2. **Ledger** (`src/ledger/`): Muse Wonder writes one scene ledger per take against `scene_ledger.schema.json`. Same schema for every take, or the diff is meaningless.
3. **Segment** (`src/segment/`): SAM 3.1 segments the target object in each still and in each sampled frame of a clip. Output per frame: mask, mask area, mask centroid, edge-contact flags.
4. **Compare** (`src/compare/`): deterministic code diffs ledger fields and mask measurements across the two takes. Every difference it can prove becomes a candidate flag with the measurement attached.
5. **Judge** (`src/judge/`): Muse Spark reviews the differences measurement cannot settle (identity across lighting, restyle versus replacement). A Spark flag must cite ledger lines and frame identifiers.
6. **Review** (`src/ui/`): the editor sees each flag with its source frame, its mask, and its evidence, and accepts or rejects it. Two or three voice commands (accept, reject, next flag) drive the pass.

## Invariants

- No flag without a mask, a measurement, or a quoted ledger line behind it.
- An uncertain check is raised to the human, never passed silently.
- Clips are judged per sampled frame. No identity is tracked across frames and no drift is reported as a tracked event.
- Fixture mode is the default demo path. Every live call has a cached fixture fallback.

## Non-goals

No audio or dialogue checks. No long-form video. No generation of the takes being checked (repair edits on uploaded stills only). No accounts, billing, or SaaS wrapper.
