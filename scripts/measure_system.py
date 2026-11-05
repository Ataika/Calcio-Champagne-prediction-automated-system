"""Measure three complete local Compose starts and sample container RAM.

Runs on the host: python3 scripts/measure_system.py
Recreates containers, reimports the prepared source CSVs, and retrains models.
The named database volume and source files are retained. Query/growth tests are
separate: docker compose run --rm measure. Never run both measurements together.
"""
import json
import os
import pathlib
import platform
import re
import statistics
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "measure/results/results.json"
ARTIFACTS = ROOT / "artifacts"


def command(args):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def hardware():
    if platform.system() == "Darwin":
        processor = command(["sysctl", "-n", "machdep.cpu.brand_string"])
        ram = int(command(["sysctl", "-n", "hw.memsize"]))
    else:
        processor = platform.processor() or platform.machine()
        ram = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    docker = json.loads(command(["docker", "info", "--format", "{{json .}} "]))
    return {"host_os": platform.platform(), "processor": processor,
            "logical_cpus": os.cpu_count(), "host_ram_gb": round(ram / 1024**3, 1),
            "docker_cpus": docker["NCPU"], "docker_ram_gb": round(docker["MemTotal"] / 1024**3, 1)}


def memory_mb(text):
    match = re.match(r"([\d.]+)\s*([KMGT]?i?B)", text.strip())
    if not match:
        return None
    value, unit = float(match[1]), match[2]
    factor = {"B": 1/1024**2, "KiB": 1/1024, "MiB": 1, "GiB": 1024, "TiB": 1024**2,
              "kB": 1000/1024**2, "KB": 1000/1024**2, "MB": 1e6/1024**2, "GB": 1e9/1024**2}
    return value * factor[unit] if unit in factor else None


def sample_resources(prefix, stop, maxima, samples):
    # Refresh IDs: a single streaming `docker stats` process can retain the old
    # container set when Compose recreates services, missing every new process.
    while not stop.is_set():
        try:
            ids = command(["docker", "compose", "ps", "-q", "--status", "running"]).split()
            if ids:
                snapshot = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}", *ids],
                                          cwd=ROOT, capture_output=True, text=True, timeout=10)
                for line in snapshot.stdout.splitlines():
                    row = json.loads(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line))
                    name = row.get("Name", "")
                    if not name.startswith(prefix + "-"):
                        continue
                    service = name[len(prefix)+1:].split("-")[0]
                    if service not in {"db", "loader", "pipeline", "app"}:
                        continue
                    value = memory_mb(row["MemUsage"].split("/")[0])
                    if value is not None:
                        maxima[service] = max(maxima.get(service, 0), value)
                        samples[service] = samples.get(service, 0) + 1
        except (ValueError, KeyError, subprocess.SubprocessError):
            pass
        stop.wait(.25)


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    prefix = json.loads(command(["docker", "compose", "config", "--format", "json"]))["name"]
    runs = []
    for repeat in range(1, 4):
        subprocess.run(["docker", "compose", "stop"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        stop = threading.Event()
        maxima, samples = {}, {}
        sampler = threading.Thread(target=sample_resources, args=(prefix, stop, maxima, samples), daemon=True)
        sampler.start()
        started = time.perf_counter()
        try:
            with (ARTIFACTS / f"system-run-{repeat}.log").open("w") as log:
                subprocess.run(["docker", "compose", "up", "-d", "--force-recreate"], cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
                for _ in range(120):
                    try:
                        with urllib.request.urlopen("http://localhost:8502/api/health", timeout=2) as response:
                            if json.load(response).get("ready"):
                                break
                    except (OSError, ValueError):
                        pass
                    time.sleep(.5)
                else:
                    raise RuntimeError("Application did not become ready")
            elapsed = time.perf_counter() - started
            # Observe the app serving its heaviest overview, model and source requests.
            for endpoint in ("/api/meta", "/api/season?competition=IT1&season=24%2F25", "/api/project"):
                with urllib.request.urlopen("http://localhost:8502" + endpoint, timeout=20) as response:
                    response.read()
            time.sleep(3)
        finally:
            stop.set()
            sampler.join(timeout=10)
        run = {"repeat": repeat, "seconds": round(elapsed, 3), "observed_peak_memory_mb":
               {key: round(value, 2) for key, value in maxima.items()}, "memory_samples": samples}
        if any(service not in maxima for service in ("db", "loader", "pipeline", "app")):
            raise RuntimeError(f"Incomplete memory observations; repeat the run. Observed: {samples}")
        for step in ("loader", "pipeline"):
            artifact = ROOT / "measure/results" / (step + ".json")
            if artifact.exists():
                run[step] = json.loads(artifact.read_text())
        runs.append(run)
        print(json.dumps(run), flush=True)
    existing = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    existing.update(system_runs=runs, system_run_seconds=round(statistics.mean(r["seconds"] for r in runs), 3),
                    hardware=hardware(), memory_method="Maximum docker stats working-set observation across three complete starts; refreshed container IDs, approximately 2 s samples. Brief unsampled peaks may be higher. Source cache and persistent DB volume retained; sources reimported and pipeline retrained each run.",
                    peak_memory_mb={key: max((r["observed_peak_memory_mb"].get(key, 0) for r in runs), default=0) or None for key in ("db", "loader", "pipeline", "app")},
                    system_measured_at=datetime.now(timezone.utc).isoformat())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(existing, indent=2))
    temporary.replace(OUTPUT)
    print("Saved full-system measurements to", OUTPUT, flush=True)


if __name__ == "__main__":
    main()
