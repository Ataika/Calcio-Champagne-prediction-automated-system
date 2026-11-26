# Primary-source licence: evidence and the decision to take

The course requires a data source with a clear licence. This project does not
have one yet. This file records what was actually checked, when, and the three
options that can close the requirement. It does not claim the item is closed.

## What was verified on 9 November 2026

| Check | Result |
| --- | --- |
| `GET api.github.com/repos/salimt/football-datasets/license` | `404 Not Found` — GitHub detects no licence on the default branch |
| `LICENSE`, `LICENCE`, `LICENSE.md`, `COPYING` at pinned revision `da9227e1f42baf74561324290dbf1ad2e3c00edd` | HTTP 404 for every name |
| `LICENSE` on the default branch | HTTP 404 |
| Upstream README | Describes raw Transfermarkt-derived data for educational use; states no reuse terms, no attribution requirement and no licence |

The earlier note in `SOURCES.md` therefore still holds, and it is not a
formality: without a licence, "publicly downloadable" gives no reuse right.
Transfermarkt's own terms apply to the upstream data in every option below.
A repackager's licence declaration covers their compilation work; it cannot
grant rights the original site never gave.

## Option A — ask the owner for permission

Open an issue on `salimt/football-datasets` or write to the owner. Draft:

> Hello — I am a student at LUISS using this dataset for a university data
> engineering project (no commercial use, no redistribution of the raw CSVs).
> The repository does not include a LICENSE file, so I cannot tell what reuse
> is permitted. Would you be willing to state the terms — for example adding a
> LICENSE file, or confirming in writing that academic use with attribution is
> allowed? I pin revision `da9227e1` and cite the repository in my report.

Cost: one message. Risk: there may be no reply before the defense, and a reply
cannot fix Transfermarkt's own terms upstream.

## Option B — replace the primary source with a CC0 dataset

`dcaribou/transfermarkt-datasets` is published under **CC0-1.0** (verified
through the GitHub licence API on 9 November 2026). It contains twelve joinable
tables including `appearances`, `transfers`, `player_valuations`, `games`,
`clubs` and `players` — everything this project consumes, and `appearances`
gives real per-match rows instead of our match-count proxy. The dataset is
current to 6 July 2026; automated updates are paused, which is acceptable for
seasons up to 2025/26.

Cost, honestly stated: this is not a configuration change. It means a new
manifest and checksums, a new schema mapping, rewritten aggregation SQL, a
re-run of every measurement and a rewrite of every number in the report and the
slides. Do not start it in the week of a checkpoint.

## Option C — narrow the question to the data we may already use

Football-Data.co.uk states its files are free for personal and academic use.
Dropping the transfer-spend question and keeping only match-derived analysis
would make the project licence-clean immediately, at the cost of the research
question that gives the project its name.

## Recommendation

1. Send Option A today: it costs one message and may close the item outright.
2. Keep the current source for the 12 November checkpoint and state the gap out
   loud, as the report and the role guides already do.
3. Decide between A and B before the final defense. Option B is the only path
   that closes the requirement without depending on someone else's reply.

Whatever is chosen, do not describe the current source as open-licensed, and do
not add raw data to this repository.
