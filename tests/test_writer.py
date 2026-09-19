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


class TestLineLevelRepair:
    def test_line_patch_preserves_cards(self, tmp_path):
        """The critical regression: repairing must NOT drop ATOMIC_POSITIONS."""
        from dft_agent.tools.qe_tools import apply_repair_to_input
        src = (
            "&CONTROL\ncalculation='scf'\n/\n&SYSTEM\nibrav=2\nnat=2\n/\n"
            "&ELECTRONS\nconv_thr=1e-6\nelectron_maxstep=3\n/\n"
            "ATOMIC_SPECIES\nSi 28.0855 Si_r.upf\nATOMIC_POSITIONS alat\n"
            "Si 0 0 0\nSi .25 .25 .25\nK_POINTS automatic\n2 2 2 0 0 0\n"
        )
        f = tmp_path / "si.in"
        f.write_text(src)
        rep = apply_repair_to_input(str(f), [
            {"type": "set_parameter", "section": "ELECTRONS",
             "parameter": "electron_maxstep", "new_value": 200},
            {"type": "set_parameter", "section": "ELECTRONS",
             "parameter": "mixing_beta", "new_value": 0.3},
        ])
        assert rep["applied"] == ["ELECTRONS.electron_maxstep=200", "ELECTRONS.mixing_beta=0.3"]
        out = f.read_text()
        # cards preserved verbatim
        assert "Si 0 0 0" in out and "Si .25 .25 .25" in out
        assert "Si 28.0855 Si_r.upf" in out and "2 2 2 0 0 0" in out
        assert "nat=2" in out
        # patched values present
        assert "electron_maxstep = 200" in out and "mixing_beta = 0.3" in out

    def test_line_patch_inserts_missing_param(self, tmp_path):
        from dft_agent.tools.qe_tools import apply_repair_to_input
        f = tmp_path / "x.in"
        f.write_text("&ELECTRONS\nconv_thr=1e-6\n/\n")
        apply_repair_to_input(str(f), [
            {"type": "set_parameter", "section": "ELECTRONS",
             "parameter": "mixing_beta", "new_value": 0.3}])
        out = f.read_text()
        assert "mixing_beta = 0.3" in out and "conv_thr=1e-6" in out
