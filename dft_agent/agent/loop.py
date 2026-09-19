"""The agent loop driver: wires the graph nodes into the observe-plan-act cycle.

This is plain Python (no LangGraph dependency at runtime) implementing the same
constrained lifecycle; LangGraph wiring lands in graph_langgraph.py in phase 2b.
"""

from __future__ import annotations

import json
from pathlib import Path

from dft_agent.agent.graph import DFTAgentGraph
from dft_agent.agent.state import initial_state
from dft_agent.storage.events import EventStore
from dft_agent.tools import qe_tools


def run_agent(job_dir: str, goal: str, calculation_type: str = "scf",
              max_attempts: int = 2, approve_callback=None, quiet: bool = False) -> dict:
    state = initial_state(job_dir, goal, calculation_type, max_attempts=max_attempts)
    store = EventStore(job_dir)
    graph = DFTAgentGraph(job_dir, approve_callback=approve_callback)

    def say(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    say(f"[run {state['run_id']}] goal: {goal}")

    # 1. inspect
    graph.inspect(state)
    say(f"[inspect] inputs found: {[o for o in state['observations'] if 'input_files' in o]}")

    # 2. plan (LLM)
    graph.plan(state)
    say(f"[plan v{state['plan_version']}] " + " -> ".join(s['step'] for s in state['plan']))

    # 3. validate
    v = graph.validate(state)
    state.update(v)
    say(f"[validate] status: {state['status']}")
    if state["status"] == "FAILED":
        store.save_state(state)
        return state

    # 4. attempt loop: execute -> observe -> (diagnose -> reflect -> repair -> re-execute)
    while state["attempt"] < state["max_attempts"] and not state.get("finished"):
        ex = graph.execute(state)
        state.update(ex)
        say(f"[execute] attempt {state['attempt']} -> {state['last_result']['output_file']}")

        ob = graph.observe(state)
        state.update(ob)
        obs = state["last_result"].get("observation", {})
        r = obs.get("result", {})
        say(f"[observe] converged={r.get('converged')} energy={r.get('total_energy_ry')} Ry "
            f"failure={obs.get('failure_type')}")

        if obs.get("failure_type") is None:
            state["status"] = "VERIFYING"
            ok, _ = qe_tools.verify_convergence(state["last_result"]["output_file"])
            state["final_summary"] = "ok: converged" if ok else "verification failed"
            state["finished"] = True
            break

        # diagnose + reflect (LLM)
        dg = graph.diagnose_and_reflect(state)
        state.update(dg)
        if dg.get("diagnosis_ok"):
            break
        refl = dg.get("reflection", {})
        say(f"[reflect] {refl.get('what_failed')} | repair: {refl.get('should_repair')}")

        if not refl.get("should_repair"):
            state["status"] = "FAILED"
            state["finished"] = True
            state["final_summary"] = f"no repair possible: {refl.get('what_failed')}"
            break

        pg = graph.propose_and_gate(state, refl)
        state.update(pg)
        say(f"[policy] {state['repair_history'][-1].get('verdict')} "
            f"({state['repair_history'][-1].get('why', 'ok')})")
        if state.get("finished"):
            break

        ap = graph.apply_repair(state, state["repair_history"][-1])
        state.update(ap)
        say(f"[repair applied] {ap['repair_report']}")

    # 5. final verification & report
    if not state.get("finished"):
        state["status"] = "FAILED"
        state["finished"] = True
        state["final_summary"] = f"max attempts ({state['max_attempts']}) exhausted"

    out_file = state["last_result"].get("output_file")
    if out_file and Path(out_file).exists():
        ok, _ = qe_tools.verify_convergence(out_file)
        state["final_summary"] = ("ok: converged" if ok else
                                  state.get("final_summary") or "not converged")

    report = graph.report(state)
    say(f"[report] {state['final_summary']}")
    say(f"[report written] {Path(job_dir) / 'final_report.md'}")
    return state
