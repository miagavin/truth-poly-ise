# Truth-Poly Pipeline

An automated trading pipeline that monitors Trump's Truth Social posts for Federal Reserve Chair nomination announcements and executes trades on Polymarket prediction markets.

## Architecture

```
Post detected → Keyword filter → Claude analysis → Trade router → Polymarket execution
```

The pipeline polls Truth Social at configurable intervals, filters posts for Fed-related keywords, sends matches to Claude for nomination detection, and routes trade decisions to Polymarket's CLOB API.

## Project Structure

```
truth-poly/
├── src/
│   ├── main.py                  # Entry point, truthbrush monkey-patches
│   ├── pipeline.py              # Post processing glue (~30 lines)
│   ├── truth/
│   │   ├── auth.py              # Truth Social authentication
│   │   ├── poller.py            # Polling loop
│   │   └── filter.py            # Keyword detection
│   ├── analysis/
│   │   ├── claude_client.py     # Anthropic API wrapper
│   │   └── prompt.py            # System prompt + response parsing
│   ├── trading/
│   │   ├── candidates.py        # Candidate → token ID registry
│   │   ├── client.py            # Polymarket client
│   │   ├── executor.py          # Order execution (FOK market orders)
│   │   └── router.py            # Claude response → trade decisions
│   └── notifications/
│       └── telegram.py          # Telegram alerts + heartbeat
├── tests/
│   ├── test_filter.py           # Keyword filter tests
│   ├── test_router.py           # Trade routing tests
│   ├── test_poller.py           # Polling logic tests (mocked)
│   ├── test_pipeline.py         # End-to-end pipeline tests (mocked)
│   └── eval_prompt.py           # Claude prompt evaluation (needs API key)
├── .env.example
├── .gitignore
├── pyproject.toml
└── requirements.txt
```

## Setup

### Prerequisites

- Python 3.13
- conda (recommended) or venv

### Installation

```bash
# Create a clean environment
conda create -n truth_poly python=3.13 -y
conda activate truth_poly

# Install dependencies
pip install -r requirements.txt
pip install -e .
pip install pytest
```

### Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Required variables for running the bot:

- `TRUTH_USER_1` / `TRUTH_PASS_1` — Truth Social account credentials
- `POLYMARKET_PRIVATE_KEY` / `POLYMARKET_FUNDER_ADDRESS` — Polymarket wallet
- `ANTHROPIC_API_KEY` — Claude API key

Optional:

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — Telegram notifications
- `POLL_INTERVAL_MS` — Polling interval in milliseconds (default: 1000)
- `PROXY_URL` — Proxy for Truth Social requests

## Running Tests

### Core tests (no API keys required)

All core tests use mocks — no network, no credentials, no cost.

```bash
pytest tests/ -v
```

This runs 92 tests covering:

- **test_filter.py** — Keyword detection (candidate names, misspellings, Fed keywords, non-matching posts, HTML handling)
- **test_router.py** — Trade routing (known candidates, unknown valid names, junk responses, edge cases)
- **test_poller.py** — Polling logic (baseline detection, new post tracking, ID management, error handling)
- **test_pipeline.py** — End-to-end flow (filter → Claude → router → executor, all mocked)

### Prompt evaluation (requires ANTHROPIC_API_KEY)

Tests the Claude prompt against 30 curated Trump-style posts. Requires a valid `ANTHROPIC_API_KEY` in `.env`. Skips automatically if the key is missing.

```bash
pytest tests/eval_prompt.py -v
```

### Useful pytest commands

```bash
# Run a single test file
pytest tests/test_filter.py -v

# Run a single test class
pytest tests/test_router.py::TestKnownCandidates -v

# Run a single test
pytest tests/test_router.py::TestKnownCandidates::test_kevin_warsh_specifically -v

# Stop on first failure
pytest tests/ -x

# Short failure summary
pytest tests/ --tb=short
```

## Running the Bot

```bash
python -m src.main
```

This authenticates with Truth Social and Polymarket, starts a Telegram heartbeat, and begins polling `@realDonaldTrump` for new posts.

## Cleanup

To remove the environment:

```bash
conda deactivate
conda remove -n truth_poly --all -y
```