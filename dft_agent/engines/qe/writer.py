"""pw.x input writer: renders a QEInputSpec into a pw.x input file (deterministic)."""

from __future__ import annotations

from dft_agent.schemas import QEInputSpec


def render_pw_input(spec: QEInputSpec) -> str:
    lines: list[str] = ["&CONTROL", f"  calculation = '{spec.calculation}'", f"  prefix = '{spec.prefix}'",
                        f"  pseudo_dir = '{spec.pseudo_dir}'", f"  outdir = '{spec.outdir}'", "/"]
    lines += ["&SYSTEM", f"  ibrav = {spec.ibrav}"]
    for k, v in spec.celldm.items():
        lines.append(f"  celldm({k}) = {v}")
    lines += [f"  nat = {spec.nat}", f"  ntyp = {spec.ntyp}", f"  ecutwfc = {spec.ecutwfc}"]
    if spec.ecutrho is not None:
        lines.append(f"  ecutrho = {spec.ecutrho}")
    lines += ["/", "&ELECTRONS", f"  conv_thr = {spec.conv_thr}",
              f"  electron_maxstep = {spec.electron_maxstep}",
              f"  mixing_beta = {spec.mixing_beta}",
              f"  mixing_mode = '{spec.mixing_mode}'",
              f"  diagonalization = '{spec.diagonalization}'",
              f"  occupations = '{spec.occupations}'", "/"]
    lines.append("ATOMIC_SPECIES")
    for name, mass, upf in spec.species:
        lines.append(f"{name} {mass} {upf}")
    lines.append("ATOMIC_POSITIONS alat")
    for name, x, y, z in spec.positions:
        lines.append(f"{name} {x} {y} {z}")
    kp = spec.kpoints
    lines += ["K_POINTS automatic", f"{kp[0]} {kp[1]} {kp[2]} {kp[3]} {kp[4]} {kp[5]}"]
    return "\n".join(lines) + "\n"


def apply_parameter_patch(spec: QEInputSpec, section: str, parameter: str, new_value) -> bool:
    """Apply a validated low-risk parameter patch. Returns True if changed."""
    allowed = {
        "ELECTRONS": {"electron_maxstep", "mixing_beta", "mixing_mode", "diagonalization",
                       "startingpot", "startingwfc"},
        "CONTROL": {"restart_mode"},
    }
    if section not in allowed or parameter not in allowed[section]:
        return False
    if not hasattr(spec, parameter):
        return False
    old = getattr(spec, parameter)
    if parameter == "electron_maxstep" or parameter == "restart_mode":
        new_value = int(new_value) if parameter == "electron_maxstep" else str(new_value)
    else:
        new_value = float(new_value) if isinstance(old, float) else str(new_value)
    if new_value == old:
        return False
    setattr(spec, parameter, new_value)
    return True
