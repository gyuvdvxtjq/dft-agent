"""Pydantic schemas: every tool I/O and LLM output is validated through these models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    CREATED = "CREATED"
    INSPECTING = "INSPECTING"
    PLANNING = "PLANNING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    RUNNING = "RUNNING"
    OBSERVING = "OBSERVING"
    DIAGNOSING = "DIAGNOSING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    REPAIRING = "REPAIRING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class ErrorType(str, Enum):
    INPUT_PARSE_ERROR = "input_parse_error"
    MISSING_PSEUDOPOTENTIAL = "missing_pseudopotential"
    SPECIES_PSEUDOPOTENTIAL_MISMATCH = "species_pseudopotential_mismatch"
    INVALID_KPOINTS = "invalid_kpoints"
    ATOMIC_OVERLAP = "atomic_overlap"
    SCF_NON_CONVERGENCE = "scf_non_convergence"
    SCF_OSCILLATION = "scf_oscillation"
    IONIC_NON_CONVERGENCE = "ionic_non_convergence"
    WALLTIME_INTERRUPTED = "walltime_interrupted"
    PROCESS_CRASHED = "process_crashed"
    INCOMPLETE_OUTPUT = "incomplete_output"
    SCIENTIFIC_QUALITY_RISK = "scientific_quality_risk"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FORBIDDEN = "forbidden"


class LogEvidence(BaseModel):
    file: str
    line_start: int
    line_end: int
    summary: str


class Diagnosis(BaseModel):
    error_type: ErrorType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[LogEvidence]
    alternative_causes: list[str] = []
    additional_information_needed: list[str] = []


class RepairAction(BaseModel):
    type: Literal["set_parameter"]
    section: str
    parameter: str
    old_value: Any
    new_value: Any


class RepairPlan(BaseModel):
    diagnosis_id: str
    reason: str
    risk: RiskLevel
    actions: list[RepairAction]
    expected_effect: str
    rollback_available: bool = True


class QEInputSpec(BaseModel):
    """Structured representation of a pw.x input file."""

    calculation: str = "scf"
    prefix: str = "dft"
    pseudo_dir: str = "./pseudo"
    outdir: str = "./out"
    ibrav: int = 2
    celldm: dict[str, float] = Field(default_factory=lambda: {"1": 10.2})
    nat: int = 1
    ntyp: int = 1
    ecutwfc: float = 30.0
    ecutrho: float | None = None
    conv_thr: float = 1e-6
    electron_maxstep: int = 100
    mixing_beta: float = 0.7
    mixing_mode: str = "plain"
    diagonalization: str = "david"
    occupations: str = "fixed"
    species: list[tuple[str, float, str]] = Field(default_factory=list)
    positions: list[tuple[str, float, float, float]] = Field(default_factory=list)
    kpoints: tuple[int, int, int, int, int, int] = (2, 2, 2, 0, 0, 0)
    raw_lines: list[str] = Field(default_factory=list)


class SCFResult(BaseModel):
    converged: bool
    total_energy_ry: float | None = None
    total_energy_ev: float | None = None
    fermi_ev: float | None = None
    iterations_used: int | None = None
    scf_accuracy_last: float | None = None
    wall_time_s: float | None = None
    errors: list[str] = Field(default_factory=list)


class SystemInfo(BaseModel):
    """System-level info parsed from pw.x startup output."""

    bravais_index: int | None = None
    alat_bohr: float | None = None
    nat: int | None = None
    n_elec: float | None = None
    nkstot: int | None = None
    ecutwfc: float | None = None
    unit_cell_volume: float | None = None
