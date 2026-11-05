"""Regenerate human-readable evidence from executed benchmark JSON."""
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]


def n(value, digits=2):
    return "not recorded" if value is None else f"{value:,.{digits}f}"


def main():
    data = json.loads((ROOT / "measure/results/results.json").read_text())
    assert data.get("repeats") == 3, "Run the three-repeat query benchmark first"
    assert len(data.get("system_runs", [])) == 3, "Run the three-repeat system measurement first"
    runs = data["system_runs"]
    hardware = data["hardware"]
    system_time = data.get("system_measured_at") or runs[-1]["pipeline"]["measured_at"]
    speed = data["query_without_index_seconds"] / data["query_with_index_seconds"]
    loader_mean = statistics.mean(r["loader"]["full_seconds"] for r in runs)
    pipeline_mean = statistics.mean(r["pipeline"]["full_seconds"] for r in runs)
    hardware_line = (f"Laptop: **{hardware['processor']}**, {n(hardware['host_ram_gb'],0)} GiB RAM, "
                     f"{hardware['logical_cpus']} logical CPUs. Docker VM: {hardware['docker_cpus']} CPUs, "
                     f"{n(hardware['docker_ram_gb'],2)} GiB memory. Three repetitions; arithmetic means below. "
                     f"Query benchmark: {data['measured_at']}; final system pipeline completed: {system_time}.")
    rows = [
        ("Complete cached-source startup → API ready", f"{n(data['system_run_seconds'])} s"),
        ("Loader: source checks, COPY, indices, enrichment", f"{n(loader_mean)} s"),
        ("Pipeline: aggregation, fitting, saved outputs", f"{n(pipeline_mean)} s"),
        ("300 club lookups, without index", f"{n(data['query_without_index_seconds'],3)} s"),
        ("300 identical club lookups, with index", f"{n(data['query_with_index_seconds'],3)} s ({n(speed,1)}× faster)"),
        ("Database footprint, including indices", f"{n(data['db_size_mb'],1)} MiB"),
        ("Original local CSVs, including enrichment", f"{n(data['raw_csv_mb'],1)} MiB"),
    ]
    for service, value in data["peak_memory_mb"].items():
        rows.append((f"{service}: highest observed working-set RAM", f"{n(value,1)} MiB" if value is not None else "not observed"))
    table = "| Measurement | Result |\n| --- | ---: |\n" + "\n".join(f"| {label} | {value} |" for label, value in rows)
    growth = "| Largest-table share | Rows | Load mean | Query mean |\n| --- | ---: | ---: | ---: |\n" + "\n".join(
        f"| {r['pct']}% | {r['rows']:,} | {n(r['load_seconds'])} s | {n(r['query_seconds'],3)} s |" for r in data["growth_test"])
    limits = ("Sources were already downloaded; images were already built. Each full run recreates containers, "
              "reimports source rows and retrains the model, retaining the database volume. OS/database caches are "
              "not flushed. Other host/Docker workloads were not controlled. Memory is the maximum sampled "
              "`docker stats` working set across the three runs, not a guaranteed instantaneous peak. "
              "Query and full-system protocols ran separately. This snapshot uses the preserved legacy metadata table.")
    summary = hardware_line + "\n\n" + table + "\n\n" + growth + "\n\n" + limits
    readme = ROOT / "README.md"
    before, tail = readme.read_text().split("<!-- MEASUREMENTS:START -->", 1)
    _, after = tail.split("<!-- MEASUREMENTS:END -->", 1)
    readme.write_text(before + "<!-- MEASUREMENTS:START -->\n" + summary + "\n<!-- MEASUREMENTS:END -->" + after)
    details = "# Executed infrastructure measurements\n\n" + summary
    details += "\n\n## Individual repetitions\n\n| Run | Full system | Loader | Pipeline |\n| --- | ---: | ---: | ---: |\n"
    details += "\n".join(f"| {r['repeat']} | {n(r['seconds'])} s | {n(r['loader']['full_seconds'])} s | {n(r['pipeline']['full_seconds'])} s |" for r in runs)
    details += "\n\nIndex lookup runs (seconds):\n\n```json\n" + json.dumps(data["lookup_runs"], indent=2) + "\n```\n"
    details += "\n## Interpretation\n\n"
    first, last = data["growth_test"][0], data["growth_test"][-1]
    details += (f"Four times the largest-table rows took {n(last['load_seconds']/first['load_seconds'])}× "
                f"the loading time and {n(last['query_seconds']/first['query_seconds'])}× the aggregation time. "
                "The load includes CSV subset preparation and COPY. Index lookup is a selective raw-table "
                "aggregation, not the frontend endpoint, which reads precomputed outputs. The index changes "
                f"that access pattern by {n(speed,1)}× for this sample. These results do not imply every query "
                "gets the same speedup or that a future laptop has the same latency.\n\n")
    details += "## Resource observations\n\n" + data["memory_method"] + "\n\n"
    details += "| Run | db MiB | loader MiB | pipeline MiB | app MiB | Sample counts |\n| --- | ---: | ---: | ---: | ---: | --- |\n"
    details += "\n".join("| " + " | ".join([str(r["repeat"])] + [n(r["observed_peak_memory_mb"].get(k),1) for k in ["db","loader","pipeline","app"]] + [str(r["memory_samples"])]) + " |" for r in runs)
    details += "\n\nRaw JSON: `measure/results/results.json` (ignored runtime artifact). "
    details += "Startup logs and browser evidence: ignored `artifacts/`. "
    details += "An aborted diagnostic run with an inadequate DISTINCT plan is excluded from all means.\n"
    (ROOT / "docs/MEASUREMENTS.md").write_text(details)
    print("Updated README and docs/MEASUREMENTS.md from executed results")


if __name__ == "__main__":
    main()
