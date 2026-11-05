# Executed infrastructure measurements

Laptop: **Apple M3 Pro**, 18 GiB RAM, 12 logical CPUs. Docker VM: 12 CPUs, 7.70 GiB memory. Three repetitions; arithmetic means below. Query benchmark: 2026-11-04T18:48:23.854996+00:00; final system pipeline completed: 2026-11-04T18:46:23.540122+00:00.

| Measurement | Result |
| --- | ---: |
| Complete cached-source startup → API ready | 31.10 s |
| Loader: source checks, COPY, indices, enrichment | 12.53 s |
| Pipeline: aggregation, fitting, saved outputs | 9.70 s |
| 300 club lookups, without index | 10.872 s |
| 300 identical club lookups, with index | 0.075 s (145.4× faster) |
| Database footprint, including indices | 695.5 MiB |
| Original local CSVs, including enrichment | 356.6 MiB |
| db: highest observed working-set RAM | 250.6 MiB |
| loader: highest observed working-set RAM | 17.9 MiB |
| pipeline: highest observed working-set RAM | 500.9 MiB |
| app: highest observed working-set RAM | 107.3 MiB |

| Largest-table share | Rows | Load mean | Query mean |
| --- | ---: | ---: | ---: |
| 25% | 469,679 | 1.40 s | 0.297 s |
| 50% | 939,359 | 2.94 s | 0.552 s |
| 100% | 1,878,719 | 6.18 s | 0.998 s |

Sources were already downloaded; images were already built. Each full run recreates containers, reimports source rows and retrains the model, retaining the database volume. OS/database caches are not flushed. Other host/Docker workloads were not controlled. Memory is the maximum sampled `docker stats` working set across the three runs, not a guaranteed instantaneous peak. Query and full-system protocols ran separately. This snapshot uses the preserved legacy metadata table.

## Individual repetitions

| Run | Full system | Loader | Pipeline |
| --- | ---: | ---: | ---: |
| 1 | 30.54 s | 12.08 s | 9.57 s |
| 2 | 31.62 s | 13.12 s | 9.72 s |
| 3 | 31.14 s | 12.40 s | 9.80 s |

Index lookup runs (seconds):

```json
{
  "without_index": [
    11.058830754001974,
    10.78572417200121,
    10.77276654600064
  ],
  "with_index": [
    0.08705433399882168,
    0.0648399169986078,
    0.07243083299908903
  ]
}
```

## Interpretation

Four times the largest-table rows took 4.40× the loading time and 3.35× the aggregation time. The load includes CSV subset preparation and COPY. Index lookup is a selective raw-table aggregation, not the frontend endpoint, which reads precomputed outputs. The index changes that access pattern by 145.4× for this sample. These results do not imply every query gets the same speedup or that a future laptop has the same latency.

## Resource observations

Maximum docker stats working-set observation across three complete starts; refreshed container IDs, approximately 2 s samples. Brief unsampled peaks may be higher. Source cache and persistent DB volume retained; sources reimported and pipeline retrained each run.

| Run | db MiB | loader MiB | pipeline MiB | app MiB | Sample counts |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 212.9 | 17.9 | 500.7 | 107.2 | {'db': 17, 'loader': 6, 'pipeline': 6, 'app': 2} |
| 2 | 211.9 | 17.3 | 500.9 | 107.1 | {'db': 18, 'loader': 6, 'pipeline': 6, 'app': 2} |
| 3 | 250.6 | 16.8 | 457.0 | 107.3 | {'db': 17, 'loader': 6, 'pipeline': 5, 'app': 2} |

Raw JSON: `measure/results/results.json` (ignored runtime artifact). Startup logs and browser evidence: ignored `artifacts/`. An aborted diagnostic run with an inadequate DISTINCT plan is excluded from all means.
