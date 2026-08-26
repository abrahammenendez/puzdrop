# puzdrop

Automatically downloads my favourite daily crossword, converts it to a valid
.puz file for use in my preferred solving app, and delivers it to my phone.

[![Daily](https://github.com/abrahammenendez/puzdrop/actions/workflows/daily.yaml/badge.svg)](https://github.com/abrahammenendez/puzdrop/actions/workflows/daily.yaml)

A scheduled GitHub workflow fetches the day's puzzle from a **secret** JSON
API, converts it to [Across Lite (`.puz`)](https://en.wikipedia.org/wiki/Crossword_puzzle#Software),
validates the result, sends it to Telegram, and leaves it as a short-lived
build artifact with a ready-to-tap WhatsApp link.

`.puz` is the closest thing
crosswords have to a universal format, most solving apps on any platform can
open one.

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

`notify.py` takes it from there, and prints the run summary:

```sh
python notify.py --file output/2026-08-20.puz --date 2026-08-20
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `PUZZLE_API_URL_TEMPLATE` | Fetch URL, with `{date}` as a placeholder |
| `PUZZLE_API_ORIGIN` | Value sent as the `Origin` header |
| `PUZZLE_TITLE` | Title written into the generated `.puz`'s metadata |
| `PUZZLE_FILE_PREFIX` | Optional prefix for the filename, `<prefix>-YYYY-MM-DD.puz` |
| `TELEGRAM_CHAT_ID` | Optional chat to deliver to, see "Delivery" below |

These are repository variables, not secrets: configuration rather than
credentials. The workflow masks the two that would name the source, since
this repository is public. `PUZZLE_FILE_PREFIX` is not masked, because it
names the artifact on the run page.

`TELEGRAM_BOT_TOKEN` is the one real credential here, so it goes in
**secrets**, not variables.

## Delivery

Two routes, and the second one is optional.

**WhatsApp** is manual and always available. The run summary carries a
`wa.me` link that opens WhatsApp with the message already typed; you pick the
chat, attach the `.puz` from the artifact, and send. There is no way to
pre-attach a file to a WhatsApp message without a verified business account,
so that last step stays manual.

**Telegram** is automatic. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
and the workflow uploads the `.puz` straight into a chat, captioned, with no
step left for you. Set neither and the workflow says so in the summary and
carries on; the artifact and the `wa.me` link still work.

To set it up: message [@BotFather](https://t.me/BotFather), send `/newbot`,
and keep the token. Make a private group and add the bot to it. Then send
`/start@yourbotname` in that group: a bot only ever sees messages addressed
to it, so a plain "hello" leaves the next step empty.

```sh
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
```

Read `"chat": {"id": ...}` out of the result; group ids are negative. If two
show up, Telegram migrated the group to a supergroup and the id changed, so
take the one starting `-100`. Add the token as a repository secret and the
chat id as a repository variable. A group needs the bot only as a member, a
channel needs it as an administrator.

Telegram keeps chat history indefinitely, which cuts against the point of a
1-day artifact, so set the chat's **Auto-Delete Timer** to 1 day.

## Workflow

The `.puz` is uploaded uncompressed rather than in a zip, so downloading it
gives you the file itself. Artifacts named this way take their name from the
file, which is why `PUZZLE_FILE_PREFIX` shows up on the run page.

`daily.yaml` runs on a schedule and also accepts a manual trigger
(`workflow_dispatch`) with an optional `date` input, for recovering a single
day that a scheduled run missed. Re-running a past workflow run does **not**
recover that day; it re-runs the code now, against today's date. Use the
manual trigger with an explicit date instead.

A failed run emails the repository owners via GitHub's default notifications;
no separate alerting is set up.

## License

Copyright (C) 2026 Abraham Menéndez

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version. The full text is in [`LICENSE`](./LICENSE).
