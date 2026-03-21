---
name: wao
description: Install and use the local wao CLI repository to fetch trends, search news or X, pull RSS feeds, and generate topic dashboards.
metadata: {"openclaw":{"os":["darwin","linux"],"requires":{"bins":["python3"]}}}
---

# wao

Use this skill when the user wants to install, configure, troubleshoot, or operate the `wao` CLI from this repository checkout.

Install this skill as a workflow skill in OpenClaw. Do not install it as a reference-only skill, because this skill is intended to run commands, install dependencies, and operate the local `wao` CLI.

Assumptions:

- `{baseDir}` is the root of the `wao` repository and contains `pyproject.toml`.
- Prefer installing from local source at `{baseDir}` instead of fetching remote packages.
- Use `python3` consistently for `-m pip` and `-m playwright`.

## Install

OpenClaw installation requirement:

- Register or install this directory as a workflow skill.
- The skill needs command execution against the local repository, so a reference-only installation is not sufficient.

Preferred one-command install:

```bash
cd {baseDir}
bash scripts/install.sh simple
```

or:

```bash
cd {baseDir}
bash scripts/install.sh full
```

- `simple` installs only the required base dependencies.
- `full` installs `.[all]`, Playwright Chromium, and downloads the semantic model assets.

Manual install flow:

1. Verify the repository and interpreter:

```bash
test -f {baseDir}/pyproject.toml
python3 --version
```

2. Base install:

```bash
cd {baseDir}
python3 -m pip install .
```

3. Optional feature installs:

- Body fetch support for `--fetch-body`:

```bash
cd {baseDir}
python3 -m pip install '.[body]'
python3 -m playwright install chromium
```

- Embedding model filter support:

```bash
cd {baseDir}
python3 -m pip install '.[model]'
wao model download
```

- Full feature set:

```bash
cd {baseDir}
python3 -m pip install '.[all]'
python3 -m playwright install chromium
wao model download
```

4. Smoke-check the install:

```bash
wao topics
wao trend --limit 3
wao search "OpenAI" --limit 3
```

## Command selection

- Use `wao trend` for hot lists such as Google Trends, Baidu hot board, or GitHub trending.
- Use `wao search` for keyword search across Google News or X-based sources.
- Use `wao rss` to fetch, save, list, pull, or remove RSS and RSSHub subscriptions.
- Use `wao summary` for the default dashboard.
- Use `wao fetch <topic ...>` for one or more business topics such as `us-hot`, `china-hot`, `ai`, `finance`, `us-market`, or `github`.
- Use `wao topics` when the user wants to see the available topic registry.
- Use `wao x login`, `wao x status`, and `wao x logout` to manage the X Bearer Token.

## Common commands

```bash
wao trend
wao trend --source baidu --limit 20
wao trend --source all --format json

wao search "OpenAI"
wao search "OpenAI" --source x
wao search elonmusk --source x-user
wao search "AI" --source x-news
wao search "Federal Reserve" --fetch-body

wao rss fetch https://36kr.com/feed
wao rss add rsshub://twitter/user/elonmusk --name Elon
wao rss list
wao rss pull

wao summary
wao summary --fetch-body

wao fetch us-hot
wao fetch china-hot ai finance
wao fetch us-market --source all --limit 8
```

## Operational notes

- `wao search --source google` uses Google News search, not the full Google Web Search API.
- X-based sources require a valid X Bearer Token. If the user wants `--source x`, `x-user`, or `x-news`, make sure `wao x login` has been completed first.
- `--fetch-body` uses Playwright headless Chromium and is slower than plain fetches. Install `.[body]` and Chromium before using it.
- `--filter-mode model` requires the model extra and a prior `wao model download`.
- Prefer `--format json` when the result will be parsed, summarized, filtered, or piped into another step.
- `github` items do not fetch article body text.
- Keep `--limit` small unless the user explicitly asks for broader output.

## Execution workflow

1. Identify whether the user needs install/setup help, one-shot retrieval, saved RSS management, or a dashboard/topic workflow.
2. If a required dependency is missing, install only the minimum needed extra before retrying the command.
3. Run the narrowest `wao` command that satisfies the request.
4. If the user asks for structured output or downstream processing, rerun with `--format json`.
5. If a command fails because an X token, Playwright, or model asset is missing, explain the missing prerequisite and fix that specific dependency.
