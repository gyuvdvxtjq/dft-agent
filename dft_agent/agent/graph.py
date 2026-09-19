"""Agent graph: the constrained state machine (LangGraph).

Lifecycle: inspect -> plan -> validate -> execute -> observe -> (diagnose ->
reflect -> repair) -> verify -> report. High-risk repairs stop at
WAITING_APPROVAL and require `approve()` before continuing.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from dft_agent.agent import planner
from dft_agent.agent.llm import LLMError
from dft_agent.agent.state import AgentState, initial_state
from dft_agent.storage.events import EventStore
from dft_agent.tools import qe_tools

LOW_RISK_PARAMS = {"electron_maxstep", "mixing_beta", "mixing_mode", "diagonalization",
                   "startingpot", "startingwfc", "restart_mode"}
HIGH_RISK_PARAMS = {"ecutwfc", "ecutrho", "occupations", "nspin", "hubbard_u", "input_dft",
                    "pseudo_dir", "tot_charge"}
RANGE_CHECKS = {"mixing_beta": (0.0, 1.0), "electron_maxstep": (1, 5000)}


def _emit(store: EventStore, state: AgentState, kind: str, payload: dict) -> None:
    store.emit(kind, payload)
    state["observations"].append({"kind": kind, **payload}) if kind == "observation" else None


class DFTAgentGraph:
    def __init__(self, run_dir: str, approve_callback=None, runner="local"):
        self.store = EventStore(run_dir)
        self.approve_callback = approve_callback  # callable(question) -> bool
        self.runner = runner

    # ---- nodes ------------------------------------------------------------

    def inspect(self, state: AgentState) -> dict:
        state["status"] = "INSPECTING"
        found = qe_tools.inspect_job(state["job_dir"])
        _emit(self.store, state, "observation", found)
        state["observations"].append({"step": "inspect", **found})
        return {"status": "INSPECTING", "observations": state["observations"],
                "tool_calls": state["tool_calls"] + [{"tool": "inspect_job", "out": found}]}

    def plan(self, state: AgentState, reason: str = "") -> dict:
        state["status"] = "PLANNING"
        try:
            plan = planner.make_plan(state, reason)
        except (LLMError, Exception) as e:  # deterministic fallback keeps agent alive
            plan = [
                {"version": state["plan_version"] + 1, "step": "validate_input", "why": f"fallback ({e})"},
                {"version": state["plan_version"] + 1, "step": "run_calculation", "why": "fallback"},
                {"version": state["plan_version"] + 1, "step": "observe_log", "why": "fallback"},
            ]
        state["plan"] = plan
        state["plan_version"] = plan[0]["version"] if plan else state["plan_version"]
        self.store.save_plan_versions(plan)
        self.store.emit("plan", {"version": state["plan_version"], "plan": plan})
        return {"status": "PLANNING", "plan": plan, "plan_version": state["plan_version"]}

    def validate(self, state: AgentState) -> dict:
        state["status"] = "VALIDATING"
        job = Path(state["job_dir"])
        inputs = list(job.glob("*.in")) + list(job.glob("*.pwi"))
        if not inputs:
            return {"status": "FAILED", "finished": True,
                    "final_summary": "no pw.x input file found in job dir"}
        problems = qe_tools.validate_parameters(qe_tools.parse_qe_input_file(str(inputs[0])) or __import__("dft_agent.schemas", fromlist=["QEInputSpec"]).QEInputSpec())
        return {"status": "READY" if not problems else "VALIDATING",
                "observations": state["observations"] + [{"step": "validate", "problems": problems}]}

    def execute(self, state: AgentState) -> dict:
        state["status"] = "RUNNING"
        state["attempt"] += 1
        job = Path(state["job_dir"])
        inputs = sorted(job.glob("*.in")) + sorted(job.glob("*.pwi"))
        input_file = inputs[0]
        res = qe_tools.run_pw_local(str(job), input_file.name, timeout_s=600)
        out_file = res["output_file"]
        state["artifacts"].append(out_file)
        self.store.emit("execution", {"attempt": state["attempt"], "output_file": out_file,
                                      "returncode": res["returncode"]})
        return {"status": "OBSERVING", "last_result": {"output_file": out_file,
                                                       "returncode": res["returncode"]}}

    def observe(self, state: AgentState) -> dict:
        state["status"] = "OBSERVING"
        out_file = state["last_result"]["output_file"]
        obs = qe_tools.observe_log(out_file)
        state["last_result"]["observation"] = obs
        self.store.emit("observation", {"attempt": state["attempt"], **obs})
        state["observations"].append({"attempt": state["attempt"], **obs})
        return {"status": "OBSERVING", "last_result": state["last_result"]}

    # ---- repair loop ------------------------------------------------------

    def policy_gate(self, state: AgentState, repair: dict) -> tuple[str, dict]:
        """Classify a repair plan. Returns (verdict, record).
        verdict: auto | approval | rejected"""
        for a in repair.get("actions", []):
            p = a["parameter"]
            if p in HIGH_RISK_PARAMS:
                return "approval", {"verdict": "approval", "param": p,
                                    "why": "high-risk parameter"}
            rng = RANGE_CHECKS.get(p)
            if rng:
                lo, hi = rng
                v = a["new_value"]
                if not (lo < float(v) <= hi):
                    return "rejected", {"verdict": "rejected", "param": p,
                                        "why": f"value {v} outside allowed range {rng}"}
            if p not in LOW_RISK_PARAMS:
                return "rejected", {"verdict": "rejected", "param": p,
                                    "why": "parameter not whitelisted"}
        return "auto", {"verdict": "auto"}

    def diagnose_and_reflect(self, state: AgentState) -> dict:
        state["status"] = "DIAGNOSING"
        obs = state["last_result"].get("observation", {})
        prelim, evidence = obs.get("failure_type"), obs.get("evidence", [])

        # rule-based first
        if prelim is None:
            state["status"] = "VERIFYING"
            return {"status": "VERIFYING", "diagnosis_ok": True}

        # LLM refinement (best effort; rule result stands on failure)
        refined = {"error_type": prelim, "confidence": 0.6, "reasoning": "rule-based"}
        try:
            refined = planner.refine_diagnosis(prelim, evidence)
        except Exception as e:
            refined["reasoning"] = f"llm unavailable: {e}"
        refined["evidence"] = evidence
        state["diagnoses"].append(refined)
        self.store.save_diagnoses(state["diagnoses"])
        self.store.emit("diagnosis", refined)

        # reflection
        try:
            refl = planner.reflect(refined, state["attempt"], state["max_attempts"])
        except Exception as e:
            refl = {"what_failed": refined["error_type"], "should_repair": True,
                    "repair_hint": "", "root_cause_hypothesis": f"llm unavailable: {e}"}
        state["observations"].append({"step": "reflect", **refl})
        self.store.emit("reflection", refl)
        return {"status": "DIAGNOSING", "reflection": refl,
                "diagnosis": refined, "diagnosis_ok": False}

    def propose_and_gate(self, state: AgentState, reflection: dict) -> dict:
        """Turn the reflection hint into a whitelist-constrained repair plan."""
        state["status"] = "REPAIRING"
        hint = reflection.get("repair_hint", "")
        actions = _hint_to_actions(hint)
        repair = {"attempt": state["attempt"], "hint": hint, "actions": actions}
        verdict, record = self.policy_gate(state, repair)
        repair.update(record)
        state["repair_history"].append(repair)
        self.store.save_repair_history(state["repair_history"])
        self.store.emit("repair_plan", repair)

        if verdict == "rejected":
            return {"status": "FAILED", "finished": True,
                    "final_summary": f"repair rejected: {record}"}
        if verdict == "approval":
            question = (f"High-risk change requested: {actions}. Approve?")
            approved = bool(self.approve_callback and self.approve_callback(question))
            state["approvals"].append({"question": question, "approved": approved})
            self.store.emit("approval", {"approved": approved, "actions": actions})
            if not approved:
                return {"status": "FAILED", "finished": True,
                        "final_summary": "human rejected high-risk repair"}
        return {"status": "REPAIRING", "repair": repair}

    def apply_repair(self, state: AgentState, repair: dict) -> dict:
        job = Path(state["job_dir"])
        # snapshot original attempt dir on first repair
        attempts = job / "attempts"
        attempts.mkdir(exist_ok=True)
        snap = attempts / f"attempt_{state['attempt']:02d}"
        snap.mkdir(parents=True, exist_ok=True)
        for f in job.glob("*.in"):
            shutil.copy2(f, snap / f.name)
        inputs = sorted(job.glob("*.in"))
        report = qe_tools.apply_repair_to_input(str(inputs[0]), repair.get("actions", []))
        self.store.emit("repair_applied", report)
        return {"status": "REPAIRING", "repair_report": report,
                "last_result": {"output_file": "", "returncode": None}}

    # ---- report -----------------------------------------------------------

    def report(self, state: AgentState) -> str:
        state["status"] = "SUCCEEDED" if state.get("final_summary", "").startswith("ok") or \
            state["last_result"].get("observation", {}).get("result", {}).get("converged") else state["status"]
        obs = state["last_result"].get("observation", {})
        lines = [
            f"# DFT-Agent run {state['run_id']}",
            f"goal: {state['user_goal']}",
            f"attempts: {state['attempt']}  status: {state['status']}",
            "",
            "## Final result",
            json.dumps(obs.get("result", {}), indent=1),
            "",
            "## Diagnoses",
            json.dumps(state["diagnoses"], ensure_ascii=False, indent=1),
            "",
            "## Repairs",
            json.dumps(state["repair_history"], ensure_ascii=False, indent=1),
        ]
        text = "\n".join(lines)
        (Path(state["job_dir"]) / "final_report.md").write_text(text, encoding="utf-8")
        self.store.save_state(state)
        return text


def _hint_to_actions(hint: str) -> list[dict]:
    """Very conservative hint parser: maps known keywords to whitelisted actions."""
    actions = []
    h = hint.lower()
    if "mixing_beta" in h or "mixing" in h and "0.3" in h:
        actions.append({"type": "set_parameter", "section": "ELECTRONS",
                        "parameter": "mixing_beta", "new_value": 0.3})
    if "maxstep" in h or "iterations" in h or "electron_maxstep" in h:
        actions.append({"type": "set_parameter", "section": "ELECTRONS",
                        "parameter": "electron_maxstep", "new_value": 200})
    if "diagonalization" in h and "davidson" not in h:
        actions.append({"type": "set_parameter", "section": "ELECTRONS",
                        "parameter": "diagonalization", "new_value": "cg"})
    return actions
