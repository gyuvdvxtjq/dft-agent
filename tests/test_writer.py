"""Tests for the deterministic pw.x input writer and parameter patching."""

from dft_agent.engines.qe.writer import apply_parameter_patch, render_pw_input
from dft_agent.schemas import QEInputSpec


def _sample_spec() -> QEInputSpec:
    return QEInputSpec(
        calculation="scf",
        prefix="t",
        pseudo_dir="/root",
        outdir="/tmp/s",
        ibrav=2,
        celldm={"1": 10.2},
        nat=2,
        ntyp=1,
        ecutwfc=30.0,
        ecutrho=120.0,
        species=[("Si", 28.0855, "Si_r.upf")],
        positions=[("Si", 0.0, 0.0, 0.0), ("Si", 0.25, 0.25, 0.25)],
        kpoints=(2, 2, 2, 0, 0, 0),
    )


class TestRender:
    def test_renders_all_namelists(self):
        text = render_pw_input(_sample_spec())
        for marker in ("&CONTROL", "&SYSTEM", "&ELECTRONS", "ATOMIC_SPECIES",
                       "ATOMIC_POSITIONS alat", "K_POINTS automatic"):
            assert marker in text

    def test_species_line(self):
        text = render_pw_input(_sample_spec())
        assert "Si 28.0855 Si_r.upf" in text

    def test_two_positions(self):
        text = render_pw_input(_sample_spec())
        assert text.count("Si 0.0 0.0 0.0") == 1
        assert text.count("Si 0.25 0.25 0.25") == 1

    def test_kpoints_line(self):
        text = render_pw_input(_sample_spec())
        assert "2 2 2 0 0 0" in text

    def test_ecutrho_only_when_set(self):
        spec = _sample_spec()
        spec.ecutrho = None
        text = render_pw_input(spec)
        assert "ecutrho" not in text


class TestPatch:
    def test_low_risk_patch_allowed(self):
        spec = _sample_spec()
        assert apply_parameter_patch(spec, "ELECTRONS", "mixing_beta", 0.3) is True
        assert spec.mixing_beta == 0.3

    def test_maxstep_int_patch(self):
        spec = _sample_spec()
        assert apply_parameter_patch(spec, "ELECTRONS", "electron_maxstep", 200) is True
        assert spec.electron_maxstep == 200

    def test_high_risk_param_rejected(self):
        spec = _sample_spec()
        # ecutwfc is NOT in the low-risk whitelist: must be refused at writer level
        assert apply_parameter_patch(spec, "SYSTEM", "ecutwfc", 60.0) is False
        assert spec.ecutwfc == 30.0

    def test_unknown_section_rejected(self):
        spec = _sample_spec()
        assert apply_parameter_patch(spec, "FAKE", "mixing_beta", 0.3) is False

    def test_noop_returns_false(self):
        spec = _sample_spec()
        assert apply_parameter_patch(spec, "ELECTRONS", "mixing_beta", 0.7) is False
