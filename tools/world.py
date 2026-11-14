"""Generate a self-contained Webots world using the GUI demo as the nominal model."""

import json
import math
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / "worlds" / "balance.wbt"


def write_world(path, cart_mass, rod_mass, length, initial_angle_deg, args):
    """Replace the marked fields of the nominal world; Webots computes box inertias from geometry."""
    if any(not math.isfinite(v) or v <= 0 for v in (cart_mass, rod_mass, length)):
        raise ValueError("mass and length must be finite and positive")
    if not math.isfinite(initial_angle_deg):
        raise ValueError("initial angle must be finite")
    angle = math.radians(initial_angle_deg)
    x = length * math.sin(angle) / 2
    z = 0.065 + length * math.cos(angle) / 2
    arguments = " ".join(json.dumps(arg, ensure_ascii=False) for arg in args)
    fields = {
        "arguments": f"controllerArgs [ {arguments} ]",
        "angle": f"position {angle:.14g}",
        "rod_center": f"translation {x:.14g} 0 {z:.14g}",
        "rotation": f"rotation 0 1 0 {angle:.14g}",
        "rod_box": f"geometry DEF ROD Box {{ size 0.02 0.02 {length:.14g} }}",
        "rod_mass": f"mass {rod_mass:.14g}",
        "cart_mass": f"mass {cart_mass:.14g}",
    }
    lines = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        if " # @" in line:
            _, key = line.split(" # @")
            indent = line[: len(line) - len(line.lstrip())]
            line = f"{indent}{fields.pop(key)} # @{key}"
        lines.append(line)
    if fields:
        raise ValueError(f"world template is missing fields: {', '.join(fields)}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
