# puzdrop

Automatically downloads my favourite daily crossword and converts it to a valid .puz file for use in my preferred solving app.

[![Daily](https://github.com/abrahammenendez/puzdrop/actions/workflows/daily.yaml/badge.svg)](https://github.com/abrahammenendez/puzdrop/actions/workflows/daily.yaml)

A scheduled GitHub Action fetches the day's puzzle from a JSON API, converts
it to [Across Lite (`.puz`)](https://en.wikipedia.org/wiki/Crossword_puzzle#Software),
validates the result, and leaves it as a short-lived build artifact with a
ready-to-tap link for sharing it. `.puz` is the closest thing crosswords have
to a universal format, most solving apps on any platform can open one.

## Getting started

Requires Python 3.13, the version pinned in
[`.python-version`](./.python-version) and installed by CI.

```sh
pip install --group dev
pytest
ruff check .
ruff format --check .
```

Running `fetch.py` locally needs three environment variables set, matching
the repository variables below:

```sh
PUZZLE_API_URL_TEMPLATE="..." PUZZLE_API_ORIGIN="..." PUZZLE_TITLE="..." \
  python fetch.py --date 2026-08-20
```

Omit `--date` to fetch the current day (in the `Europe/Madrid` timezone,
regardless of where the command runs). The file is written to `output/`,
which is gitignored; pass `--output` to write it elsewhere.

## Configuration

| Variable | Purpose |
| --- | --- |
| `PUZZLE_API_URL_TEMPLATE` | Fetch URL, with `{date}` as a placeholder |
| `PUZZLE_API_ORIGIN` | Value sent as the `Origin` header |
| `PUZZLE_TITLE` | Title written into the generated `.puz`'s metadata |

Set as repository variables (Settings → Secrets and variables → Actions →
Variables) rather than secrets: they're configuration, not credentials. The
workflow masks them from its logs anyway, since this repository is public and
so are its Actions logs.

## Workflow

`daily.yaml` runs on a schedule and also accepts a manual trigger
(`workflow_dispatch`) with an optional `date` input, for recovering a single
day that a scheduled run missed. Re-running a past workflow run does **not**
recover that day; it re-runs the code now, against today's date. Use the
manual trigger with an explicit date instead.

A failed run emails the repository owner via GitHub's default notifications;
no separate alerting is set up.

## License

Copyright (C) 2026 Abraham Menéndez

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version. The full text is in [`LICENSE`](./LICENSE).
