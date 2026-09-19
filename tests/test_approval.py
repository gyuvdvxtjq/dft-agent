"""Phase 3: high-risk repair must stop at WAITING_APPROVAL and honor human decision."""

import json
from pathlib import Path

import pytest

from dft_agent.agent.graph import DFTAgentGraph, _hint_to_actions
from dft_agent.agent.state import initial_state
from dft_agent.storage.events import EventStore


def _state_with_failure(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "si.in").write_text(
        "&CONTROL\ncalculation='scf'\npseudo_dir='/data/probe'\noutdir='/tmp/s'\n/\n"
        "&SYSTEM\nibrav=2\ncelldm(1)=10.2\nnat=2\nntyp=1\necutwfc=12\n/\n"
        "&ELECTRONS\nconv_thr=1e-6\n/\nATOMIC_SPECIES\nSi 28.0855 Si_r.upf\n"
        "ATOMIC_POSITIONS alat\nSi 0 0 0\nSi .25 .25 .25\nK_POINTS automatic\n2 2 2 0 0 0\n"
    )
    state = initial_state(str(job), "demo", "scf", max_attempts=2)
    state["attempt"] = 1
    state["last_result"] = {"output_file": str(job / "si.out"), "returncode": 1}
    return state


def _hint_with_ecutwfc():
    return {"what_failed": "cutoff too low", "should_repair": True,
            "repair_hint": "increase ecutwfc to 40 and rerun"}


class TestHighRiskGate:
    def test_hint_maps_to_ecutwfc_action(self):
        actions = _hint_to_actions("increase ecutwfc to 40 and rerun")
        assert any(a["parameter"] == "ecutwfc" for a in actions)

    def test_gate_flags_ecutwfc_as_approval(self, tmp_path):
        graph = DFTAgentGraph(tmp_path)
        repair = {"actions": [{"type": "set_parameter", "section": "SYSTEM",
                               "parameter": "ecutwfc", "new_value": 40.0}]}
        verdict, record = graph.policy_gate({}, repair)
        assert verdict == "approval"
        assert record["param"] == "ecutwfc"

    def test_approval_denied_blocks_repair(self, tmp_path):
        state = _state_with_failure(tmp_path)
        graph = DFTAgentGraph(str(tmp_path), approve_callback=lambda q: False)
        pg = graph.propose_and_gate(state, _hint_with_ecutwfc())
        state.update(pg)
        assert state["finished"] is True
        assert "human rejected" in state["final_summary"]
        # approval was recorded in state AND event store
        assert state["approvals"][-1]["approved"] is False
        ev = (tmp_path / "events.jsonl").read_text()
        assert '"approved": false' in ev

    def test_approval_granted_applies_repair(self, tmp_path):
        state = _state_with_failure(tmp_path)
        graph = DFTAgentGraph(str(tmp_path), approve_callback=lambda q: True)
        pg = graph.propose_and_gate(state, _hint_with_ecutwfc())
        state.update(pg)
        assert state["finished"] is not True
        assert state["approvals"][-1]["approved"] is True
        # approval grants permission; apply is a separate explicit step
        ap = graph.apply_repair(state, state["repair_history"][-1])
        assert ap["repair_report"]["applied"] == ["SYSTEM.ecutwfc=40.0"]
        out = (tmp_path / "job" / "si.in").read_text()
        assert "ecutwfc = 40.0" in out

    def test_out_of_range_auto_rejected(self, tmp_path):
        graph = DFTAgentGraph(str(tmp_path))
        repair = {"actions": [{"type": "set_parameter", "section": "ELECTRONS",
                               "parameter": "mixing_beta", "new_value": 5.0}]}
        verdict, record = graph.policy_gate({}, repair)
        assert verdict == "rejected"
        assert "range" in record["why"]
