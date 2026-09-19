"""Event persistence: append-only events.jsonl + state.json snapshots per run."""

from __future__ import annotations

import json
import time
from pathlib import Path


class EventStore:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"

    def emit(self, kind: str, payload: dict) -> None:
        event = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "payload": payload}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def save_state(self, state: dict) -> None:
        (self.run_dir / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )

    def save_plan_versions(self, plan: list[dict]) -> None:
        path = self.run_dir / "plan_versions.json"
        plans = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if plan and (not plans or plans[-1] != plan):
            plans.append(plan)
        path.write_text(json.dumps(plans, ensure_ascii=False, indent=1), encoding="utf-8")

    def save_diagnoses(self, diagnoses: list[dict]) -> None:
        (self.run_dir / "diagnoses.json").write_text(
            json.dumps(diagnoses, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def save_repair_history(self, repairs: list[dict]) -> None:
        (self.run_dir / "repair_history.json").write_text(
            json.dumps(repairs, ensure_ascii=False, indent=1), encoding="utf-8"
        )
