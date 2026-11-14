"""Run a real Webots world for each selected case (project-root relative paths)."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from world import write_world

ROOT = Path(__file__).resolve().parents[1]
WEBOTS = Path(os.environ.get("WEBOTS_HOME", "D:/Webots")) / "msys64/mingw64/bin/webots.exe"


def run_case(case, output, port, movie=False):
    case_id = case["id"]
    csv_path = output / f"{case_id}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    world = ROOT / "worlds" / f".generated-{token}.wbt"
    # A unique destination prevents accidental reuse of a previous run.
    fresh_csv = csv_path.with_name(f".{token}.csv")
    args = [f"--algorithm={case['algorithm']}", f"--scenario={case['scenario']}",
            f"--duration={case['duration']}", f"--csv={fresh_csv.as_posix()}", "--batch=1"]
    movie_path = csv_path.with_suffix(".mp4")
    fresh_movie = movie_path.with_name(f".{token}.mp4")
    if movie:
        args.append(f"--movie={fresh_movie.as_posix()}")
    write_world(world, case["cart_mass"], case["rod_mass"], case["length"], case["initial_angle_deg"], args)
    command = [str(WEBOTS), "--batch", "--mode=fast", "--stdout", "--stderr", f"--port={port}"]
    if not movie:
        command += ["--no-rendering", "--minimize"]
    command.append(str(world))
    try:
        child = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            raw, _ = child.communicate(timeout=240 if movie else 90)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
            raw, _ = child.communicate()
            raise RuntimeError(f"Webots timed out in {case_id}: {raw.decode(errors='replace')[-1800:]}")
        console = raw.decode(errors="replace")
        if child.returncode or not fresh_csv.is_file() or "ERROR:" in console:
            raise RuntimeError(f"Webots failed in {case_id}: {child.returncode}\n{console}")
        with fresh_csv.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) < 2:
            raise ValueError(f"Missing samples: {case_id}")
        last = rows[-1]
        failed = any(not math.isfinite(float(n)) for n in last.values()) or abs(float(last["x_m"])) >= 1.5 or abs(float(last["theta_rad"])) >= math.radians(30)
        if not failed and float(last["time_s"]) < case["duration"] - .0041:
            raise ValueError(f"Incomplete trace: {case_id} {last['time_s']}")
        if movie:
            if not fresh_movie.exists() or fresh_movie.stat().st_size < 1000:
                raise ValueError(f"Missing Webots recording: {fresh_movie}")
            fresh_movie.replace(movie_path)
        fresh_csv.replace(csv_path)
        print(f"{case_id}: {len(rows)} rows; t={last['time_s']}; x={last['x_m']}; theta={last['theta_rad']}", flush=True)
    finally:
        world.unlink(missing_ok=True)
        world.with_name("." + world.stem + ".wbproj").unlink(missing_ok=True)
        fresh_csv.unlink(missing_ok=True)
        fresh_movie.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Case ID (repeatable); default: entire manifest")
    parser.add_argument("--open", action="store_true", help="Run two short open-loop sign checks")
    parser.add_argument("--movie", choices=["pid", "lqr"], help="Record a 14 s Webots demo")
    parser.add_argument("--out", type=Path, help="CSV output directory")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--port", type=int, default=12580)
    opts = parser.parse_args()
    if sum(bool(v) for v in [opts.case, opts.open, opts.movie]) > 1:
        parser.error("choose one of --case, --open, --movie")
    if not WEBOTS.is_file():
        parser.error(f"Missing Webots executable: {WEBOTS}")
    if opts.open or opts.movie:
        scenarios = ["open-force", "open-tilt"] if opts.open else ["demo"]
        cases = [dict(id=f"demo-{opts.movie}" if opts.movie else name, scenario=name, algorithm=opts.movie or "open",
                      initial_angle_deg=5 if name != "open-force" else 0, cart_mass=1, rod_mass=.2,
                      length=.6, duration=14 if opts.movie else .12) for name in scenarios]
    else:
        cases = json.loads((ROOT / "experiments/manifest.json").read_text(encoding="utf-8"))
        if opts.case:
            missing = set(opts.case) - {case["id"] for case in cases}
            if missing:
                parser.error(f"Unknown cases: {missing}")
            cases = [case for case in cases if case["id"] in opts.case]
    output = opts.out or (ROOT / ("evidence/model-check" if opts.open else "evidence/video" if opts.movie else "evidence/raw"))
    def worker(slot):
        for case in cases[slot::opts.jobs]:
            run_case(case, output.resolve(), opts.port + slot, bool(opts.movie))
    with ThreadPoolExecutor(max_workers=opts.jobs) as pool:
        list(pool.map(worker, range(opts.jobs)))


if __name__ == "__main__":
    main()
