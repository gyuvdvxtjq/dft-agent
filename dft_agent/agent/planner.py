"""Planner + diagnoser + reflector: the LLM-reasoning layer (strict JSON out)."""

from __future__ import annotations

import json

from pydantic import BaseModel

from dft_agent.agent import llm
from dft_agent.agent.prompts import DIAGNOSER_SYSTEM, PLANNER_SYSTEM, REFLECTION_SYSTEM
from dft_agent.schemas import ErrorType


class _Plan(BaseModel):
    plan_version: int
    steps: list[dict]


class _Diagnosis(BaseModel):
    error_type: str
    confidence: float
    reasoning: str


class _Reflection(BaseModel):
    what_failed: str
    root_cause_hypothesis: str
    should_repair: bool
    repair_hint: str = ""


def make_plan(state: dict, force_replan_reason: str = "") -> list[dict]:
    """Ask the LLM for an ordered plan adapted to the current state."""
    view = {
        "goal": state["user_goal"],
        "calculation_type": state["calculation_type"],
        "attempt": state["attempt"],
        "has_input_file": bool(state.get("observations")),
        "last_result": state.get("last_result", {}),
        "diagnoses": state.get("diagnoses", [])[-2:],
        "force_replan_reason": force_replan_reason,
    }
    out = llm.structured(
        [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": json.dumps(view, ensure_ascii=False)},
        ],
        schema=_Plan,
    )
    version = state["plan_version"] + 1
    return [{"version": version, **step} for step in out.model_dump()["steps"]]


def refine_diagnosis(preliminary: str, evidence: list[dict]) -> dict:
    """Confirm/refine the rule-based classification with LLM reasoning."""
    out = llm.structured(
        [
            {"role": "system", "content": DIAGNOSER_SYSTEM},
            {"role": "user", "content": json.dumps({
                "preliminary_class": preliminary,
                "evidence": evidence[:6],
            }, ensure_ascii=False)},
        ],
        schema=_Diagnosis,
    )
    d = out.model_dump()
    valid = {e.value for e in ErrorType}
    if d["error_type"] not in valid:
        d["error_type"] = preliminary or ErrorType.UNKNOWN.value
    return d


def reflect(diagnosis: dict, attempt: int, max_attempts: int) -> dict:
    """Why did the attempt fail and should we repair?"""
    out = llm.structured(
        [
            {"role": "system", "content": REFLECTION_SYSTEM},
            {"role": "user", "content": json.dumps({
                "diagnosis": diagnosis,
                "attempt": attempt,
                "max_attempts": max_attempts,
            }, ensure_ascii=False)},
        ],
        schema=_Reflection,
    )
    return out.model_dump()
