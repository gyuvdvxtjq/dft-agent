"""Agent state: single source of truth flowing through the LangGraph state machine."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal, TypedDict

Status = Literal[
    "CREATED", "INSPECTING", "PLANNING", "VALIDATING", "READY", "RUNNING",
    "OBSERVING", "DIAGNOSING", "WAITING_APPROVAL", "REPAIRING", "VERIFYING",
    "SUCCEEDED", "FAILED", "STOPPED",
]


def new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


class AgentState(TypedDict, total=False):
    # identity / inputs
    run_id: str
    job_dir: str
    user_goal: str
    engine: str
    calculation_type: str
    user_constraints: list[str]

    # lifecycle
    status: Status
    plan_version: int
    plan: list[dict[str, Any]]
    current_step: int

    # observations & bookkeeping
    observations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    diagnoses: list[dict[str, Any]]
    repair_history: list[dict[str, Any]]
    approvals: list[dict[str, Any]]
    artifacts: list[str]

    # attempt management
    attempt: int
    max_attempts: int
    token_usage: int
    started_at: str
    last_result: dict[str, Any]

    # control
    pending_approval: dict[str, Any] | None
    finished: bool
    final_summary: str


def initial_state(job_dir: str, user_goal: str, calculation_type: str,
                  max_attempts: int = 2, engine: str = "qe") -> AgentState:
    return AgentState(
        run_id=new_run_id(),
        job_dir=str(job_dir),
        user_goal=user_goal,
        engine=engine,
        calculation_type=calculation_type,
        user_constraints=[],
        status="CREATED",
        plan_version=0,
        plan=[],
        current_step=0,
        observations=[],
        tool_calls=[],
        diagnoses=[],
        repair_history=[],
        approvals=[],
        artifacts=[],
        attempt=0,
        max_attempts=max_attempts,
        token_usage=0,
        started_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        last_result={},
        pending_approval=None,
        finished=False,
        final_summary="",
    )
