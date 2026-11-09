# Calcio Champagne — defense package

Prepared 9 November 2026 for the LUISS CIDS project defense. The checkpoint is
12 November (five-minute end-to-end demo) and the final defense is 20/26
November (15 minutes plus five minutes of questions). Start with these items:

1. `site/index.html` is the offline, interactive study site. It has role guides,
   a pipeline walkthrough, measured evidence, a rehearsal timer and examiner
   questions. Browser checkmarks remain in local browser storage.
2. `site/downloads/Project-Report.pdf` is the English technical report.
3. `site/downloads/Team-Defense-Guide.pdf` is the Russian team study guide with
   English rehearsal scripts and Q&A.
4. `site/downloads/Presentation.pdf` is a ten-slide, 15-minute deck.
5. `site/downloads/Role-*.pdf` are the four personal exam guides. Each one has
   what to know, what to show, the speaker's own slots on the 15-minute clock,
   how to close the exam, a map of the exact project files behind that role,
   the examiner questions for it, and the shared exam-day section: dates,
   machine preparation, how to answer, and direct answers to the four
   uncomfortable questions (licence, contributors, second laptop, xG).

## Run the presentation site

Open `site/index.html` in a browser. For the interactive deck, open
`site/presentation.html`. Arrow keys move between slides; `N` reveals speaker
notes, `F` requests fullscreen. The separate study site can run offline and
does not need project data or a database.

## Run the project

The complete software is in the sibling project root. Follow its README and
copy `.env.example` to `.env` before starting Compose. A fresh setup downloads
the pinned primary CSV sources through the project loader. The archive excludes
`.env`, credentials, raw datasets, model weights and built Docker images. Match
enrichment is optional and is not redistributed in this package.

## Data and metric note

League comparison shows completed-match goals for, goals against, goal
difference, and per-match attack/defense ranks within each league-season. xG
does not exist in the loaded match schema and is not estimated. In Serie A
24/25, Inter recorded 79/35/+44 (attack rank 1, defense rank 2); Milan
61/43/+18 (ranks 3 and 7). Head-to-head totals remain a separate view of their
two direct meetings.

## Evidence and open items

The PDF/site reflect checked local data and the dated measurements in
`../docs/MEASUREMENTS.md`. The primary upstream dataset's explicit reuse licence
is still unconfirmed; the report does not call it open-licensed. Role cards
organize study and speaking time but do not independently establish who wrote
or validated a change. Each participant should describe their real work.
