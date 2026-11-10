# Calcio Champagne — defense package

Everything in this archive is offline. Nothing here needs the database, Docker
or a network connection: open the files directly from the folder.

**The checkpoint is 12 November (a five-minute end-to-end demo). The final
defense is 20 or 26 November: 15 minutes plus five minutes of questions.**

## Open your own guide first

| You | Your guide | Your slot | You answer for | You hand over |
| --- | --- | --- | --- | --- |
| Neda | `Role-neda.pdf` | 00:00–03:45, slides 1–3 | where the data comes from, why a database, the licence | timings and memory → Atai · model quality → Gabriele |
| Gabriele | `Role-lill.pdf` | 03:45–06:30 and 09:15–10:15, slides 4, 5, 7 | the index, what the model predicts, how it is tested | timings and memory → Atai · data loading → Neda |
| Jacopo | `Role-jacopo.pdf` | 06:30–09:15 and 14:00–15:00, slides 6, 10 | the live demo, what the page shows, the API answers | timings and memory → Atai · model quality → Gabriele |
| Atai | `Role-atai.pdf` | 10:15–14:00, slides 8, 9 | startup, reproducibility, time, memory, disk, growth | model internals → Gabriele · sources → Neda |

Each guide is about ten pages: what to know, what to show, **three pictures of
your own part**, your exact slots on the clock, how to close the exam, a map of
the project files behind your part, the examiner questions for you, phrasings
to avoid, and the shared exam-day section.

Guides for Neda, Gabriele and Jacopo are in English and explain every technical
term in plain words. Atai's guide is in Russian. The content is the same.

**Nobody except Atai quotes a performance number out loud.** Startup time,
memory, the index speed-up and the data-growth experiment are his part. If one
of those comes up in your section, hand it over in one sentence — that is a
correct answer, not an evasion.

## Everything else in the archive

| File | What it is |
| --- | --- |
| `site/index.html` | the interactive study site: roles, the system, the evidence, a rehearsal timer and 39 examiner questions with answers |
| `site/presentation.html` | the live deck — arrow keys move, `N` shows speaker notes, `F` is fullscreen, with a 15-minute timer |
| `site/downloads/Project-Report.pdf` | the 26-page project report, including three architecture diagrams |
| `site/downloads/Team-Defense-Guide.pdf` | the full team guide: every track, all nine pictures, all questions, the running order |
| `site/downloads/Presentation.pdf` | the ten slides as a printable PDF |
| `materials/*.html` | the same documents as web pages, if you prefer reading in a browser |
| `curriculum.json` | the single source all of the above is generated from |

## Before you present

Read your own guide end to end once, then the examiner questions for your part,
then two questions from somebody else's part. Say the answers out loud: reading
them silently is not rehearsal.

## What the project claims, and what it does not

The system is reproducible on the measured setup. Transfer spending has almost
no linear relationship with the next season's change in attacking output, and
the model improves only modestly on predicting no change at all. Every result
is an association in historical records, never a cause. There is no xG in the
data and we do not invent it. The primary data source has no confirmed licence,
and we say so rather than calling it open.
