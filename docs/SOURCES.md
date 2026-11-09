# Dataset provenance and reproducibility

## Primary source

The earlier README linked `davidcariboo/player-scores` on Kaggle. That link did
not identify the schema actually loaded here. The matching source is
[salimt/football-datasets](https://github.com/salimt/football-datasets), revision
[`da9227e1f42baf74561324290dbf1ad2e3c00edd`](https://github.com/salimt/football-datasets/tree/da9227e1f42baf74561324290dbf1ad2e3c00edd).

On 4 November 2026, ten of the eleven local CSVs were verified against that
revision: Git blob hashes for ordinary files, and SHA-256 object IDs for the two
Git LFS files. Exact SHA-256 checksums, URLs, sizes and ordered headers are stored
in `loader/sources.json`. LFS objects are fetched through GitHub's media endpoint,
not mistaken for 133/134-byte pointer files. No credentials are required.

**Licence gap:** the revision's recursive tree did not contain an explicit
LICENCE/LICENSE file. Publicly downloadable is not the same as openly licensed.
The old “open licence” claim was removed. The course asks for a clear licence;
upstream permission/licence confirmation or a clearly licensed replacement is
still needed before claiming this aspect of course compliance. No redistribution
of raw data is added to this repository.

## The metadata-table difference

The existing `team_competitions_seasons.csv` has 196,378 rows and seven fields.
The pinned upstream file has 58,247 rows and 29 fields. Its history exposes only
the initial commit for that path; the exact provenance of the existing derived
file could not be reconstructed. It is preserved, not silently replaced.

For a fresh checkout, the downloader projects the upstream table onto the seven
schema fields and leaves the unavailable `_last_modified_at` blank. Both the
upstream and normalized checksums are pinned. The existing local derivative's
checksum is explicitly labeled `legacy_local_sha256` so verification does not
misrepresent it as an upstream byte match.

This metadata table does **not** feed Champagne Index, transfer spend, the
RandomForest or league standings. Therefore those outputs are reproducible from
the ten identical inputs. Metadata exploration query 2, raw row counts, database
size and loading measurements may differ on a fresh normalized source snapshot.
The recorded benchmark belongs to the existing local snapshot. Do not promise
identical timings or metadata counts for the normalized variant.

## Acquisition

The loader checks all eleven headers before any database COPY. Missing files are
downloaded automatically at startup and atomically renamed only after checksum
and header validation. Existing valid CSVs can be reused entirely offline.

```bash
# Verify the prepared local snapshot without downloading it.
python3 loader/get_data.py --data-dir data --verify

# Or use the loader's pinned Python environment.
docker compose run --rm --no-deps loader python get_data.py --verify
```

`DOWNLOAD_DATA=0` disables downloads and gives an explicit error for missing
files. Existing files are never overwritten by automatic acquisition.

## Match enrichment

[football-data.co.uk](https://www.football-data.co.uk/data.php): 25 manually
downloaded match CSVs for five leagues, 21/22–25/26, 8,908 completed matches in
this local snapshot. Names are resolved with `sql/team_name_map.sql`. Both two-
and four-digit date years are accepted. Unplayed fixtures are excluded. This
source remains optional and is not scraped by the loader.

Football-Data's [current fair-data usage policy](https://www.football-data.co.uk/contact.php)
states that its free CSV/Excel data is intended for personal betting or academic
research, downloaded manually or with light automation (at most twice weekly).
These optional files were manually downloaded for this academic project and are
not redistributed. This stated use policy is not a general open-data licence and
does not change the separate unresolved licence status of the primary
Transfermarkt-derived dataset above.

Completed rows require valid dates, nonnegative whole-number goals and a result
consistent with the score. Unexpected season filenames are skipped with a
warning. Duplicate fixtures are imported once; contradictory scores stop the
replacement before existing matches are changed. Removing optional match input
clears its previous stored rows on the next loader run, so stale standings or
head-to-head results are not presented as current enrichment.

The loaded snapshot currently has all 25 league-season CSVs (five leagues ×
five seasons), totaling 8,908 completed matches. These scorelines support actual
GF, GA, GD and per-match scoring/conceding ranks in season comparisons. The
source schema has no expected-goals (xG) field, so xG is not reported. The
match CSVs also contain shots, shots on target, corners, cards and half-time
scores for 8,907 of 8,908 completed matches. The comparison presents these as
observed match statistics. A separate SOT-based estimate applies the league's
overall goals-per-shot-on-target rate; it is explicitly an experimental proxy,
not provider xG or a shot-location model. A two-parameter Poisson fit reports
descriptive attack/defence ratings for complete league seasons; those ratings
are fitted to the same season scores and are not out-of-sample forecasts.
Bookmaker odds are stored as source fields but are not treated as team
performance measures in the comparison.
primary Transfermarkt player table includes `goals_conceded` and `clean_sheets`
at player level. Pipeline totals are retained as a distinct cross-check, not
substituted for complete club match totals. On 388 adequately covered top-five
club-seasons, Transfermarkt goalkeeper goals-conceded totals exactly match the
independent scoreline totals in 366 cases (94.3%); clean-sheet totals match in
269 (69.3%). The lower clean-sheet agreement is why that field is not used for a
league defensive ranking. This cross-check is descriptive; the interface's
head-to-head and league ranks use actual match scores.

Final positions are calculated using points and goal difference; official
deductions and league-specific tie-break rules are not represented. Transfermarkt
25/26 is a partial snapshot. Its index is never correlated with full final
standings; adequate coverage requires at least 80% of the match-result count and
30 games played.
