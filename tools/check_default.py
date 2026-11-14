"""Start the unchanged default world and check its 14 s state in the Webots console."""
import argparse
import math
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=12681, type=int)
    port = parser.parse_args().port
    world = ROOT / "worlds/balance.wbt"
    executable = Path(os.environ.get("WEBOTS_HOME", "D:/Webots")) / "msys64/mingw64/bin/webots.exe"
    launch = [str(executable), "--batch", "--no-rendering", "--minimize", "--mode=fast",
              "--stdout", "--stderr", f"--port={port}", str(world)]
    # The normal GUI demo keeps balancing past 14 s. Request a graceful exit after its checkpoint.
    env = {**os.environ, "BALANCE_VERIFY_DEFAULT": "1"}
    child = subprocess.Popen(launch, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=ROOT, env=env)
    try:
        raw, _ = child.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
        child.wait(timeout=10)
        raise RuntimeError("Default world did not terminate at its 14 s checkpoint")
    console = raw.decode(errors="replace")
    match = re.search(r"BALANCE_DEMO algorithm=(\w+) time=(\S+) target=(\S+) x=(\S+) theta=(\S+)", console)
    if child.returncode or "ERROR:" in console or not match:
        raise RuntimeError(f"Webots default demo failed: {console[-2000:]}")
    algorithm, seconds, target, pos, angle = match.groups()
    if not (algorithm == "lqr" and float(seconds) == 14 and float(target) == 0.2 and
            abs(float(pos) - .2) <= .01 and abs(float(angle)) <= math.radians(.5)):
        raise ValueError(f"Default world did not settle: {match.group()}")
    print(match.group())


if __name__ == "__main__":
    main()
