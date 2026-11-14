"""Compare the open-loop Webots measurements with the local linear model."""
import csv
from pathlib import Path
import numpy as np
from scipy.signal import StateSpace, lsim
from model import linear_model

root = Path(__file__).resolve().parents[1]
a, b = linear_model()
for case in ["open-force", "open-tilt"]:
    with (root / "evidence/model-check" / f"{case}.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    t, force, x, angle = np.array([[float(row[k]) for row in rows] for k in
                                   ["time_s", "force_N", "x_m", "theta_rad"]])
    system = StateSpace(a, b, np.eye(4), np.zeros((4, 1)))
    _, predicted, _ = lsim(system, force, t, X0=[x[0], 0, angle[0], 0], interp=False)
    dx = np.max(np.abs(predicted[:, 0] - x))
    dtheta = np.max(np.abs(predicted[:, 2] - angle))
    print(f"{case}: max |x error|={dx:.8f} m; max |theta error|={dtheta:.8f} rad")
    if (dx > .001 or dtheta > .003 or
        (case == "open-force" and not (x[-1] > 0 and angle[-1] < 0)) or
        (case == "open-tilt" and angle[-1] <= angle[0])):
        raise RuntimeError(f"{case} sign or trajectory does not match the linearization")
