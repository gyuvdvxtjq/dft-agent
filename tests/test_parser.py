"""Parser tests against a real QE 6.7 SCF log captured on the platform dev machine."""

from pathlib import Path

import pytest

from dft_agent.engines.qe.parser import diagnose_failure, load_log, parse_scf_output, parse_system_info

FIXTURE = Path(__file__).parent / "fixtures" / "si_scf_real.out"


@pytest.fixture(scope="module")
def real_log() -> str:
    return load_log(FIXTURE)


@pytest.fixture(scope="module")
def result(real_log: str):
    return parse_scf_output(real_log)


class TestParseSCFReal:
    def test_converged(self, result):
        assert result.converged is True

    def test_total_energy_matches_reference(self, result):
        # value captured from the actual run on dft-agent-dev
        assert result.total_energy_ry == pytest.approx(-16.73253375)
        assert result.total_energy_ev == pytest.approx(-16.73253375 * 13.6056980659, rel=1e-6)

    def test_iterations(self, result):
        assert result.iterations_used == 5

    def test_scf_accuracy_series_parsed(self, result):
        assert result.scf_accuracy_last == pytest.approx(0.00000015)

    def test_wall_time(self, result):
        assert result.wall_time_s is not None and result.wall_time_s > 0

    def test_no_errors(self, result):
        assert result.errors == []


class TestParseSystemInfo:
    def test_system_fields(self, real_log):
        info = parse_system_info(real_log)
        assert info.bravais_index == 2
        assert info.alat_bohr == pytest.approx(10.2)
        assert info.nat == 2
        assert info.n_elec == pytest.approx(8.0)
        assert info.ecutwfc == pytest.approx(30.0)


class TestFailureDiagnosis:
    def test_scf_not_converged(self):
        log = (
            "iteration # 50\n"
            "estimated scf accuracy    <       0.12345678 Ry\n"
            "convergence NOT achieved in 50 iterations\n"
        )
        etype, ev = diagnose_failure(log)
        assert etype == "scf_non_convergence"
        assert len(ev) >= 1
        assert ev[0][0] == 3  # line number of the NOT-achieved line

    def test_missing_pseudo(self):
        log = (
            "Error in routine  read_pseudo (1):\n"
            "file Si_r.upf not found\n"
            "MPI_ABORT was invoked on rank 0\n"
        )
        etype, _ = diagnose_failure(log)
        assert etype == "missing_pseudopotential"

    def test_incomplete_output(self):
        log = "Program PWSCF v.6.7MaX starts\nReading input from i\nstopping\n"
        etype, _ = diagnose_failure(log)
        assert etype == "incomplete_output"

    def test_unknown_returns_none_type(self):
        log = "completely unrelated text with no markers at all"
        etype, _ = diagnose_failure(log)
        assert etype in (None, "incomplete_output")


class TestOscillationHeuristic:
    def test_oscillation_detected(self):
        log = (
            "iteration #  1\nestimated scf accuracy    <       0.10000000 Ry\n"
            "iteration #  2\nestimated scf accuracy    <       0.05000000 Ry\n"
            "iteration #  3\nestimated scf accuracy    <       0.20000000 Ry\n"
            "iteration #  4\nestimated scf accuracy    <       0.06000000 Ry\n"
        )
        etype, _ = diagnose_failure(log)
        assert etype == "scf_oscillation"
