# Setup Script

Prepare the challenge playground, run binary analysis, then run exploit development.

## Required env vars

- `LLM_MODEL` (preferred) or `MODEL`
- `IDA_MCP_URL`
- `PWNDBG_MCP_URL`
- One API key variable:
  - `LLM_API_KEY` (preferred), or
  - `API_KEY`, or
  - `NIM_API_KEY`, or
  - `OPENAI_API_KEY`, or
  - `OPENAI_KEY`

## Optional env vars (for OpenAI-compatible providers such as NVIDIA NIM)

- `LLM_BASE_URL` (preferred), or `API_BASE_URL`, or `NIM_BASE_URL`, or `OPENAI_BASE_URL`, or `OPENAI_API_BASE`
- `LLM_RATE_LIMIT_RPM` (preferred) or `API_RATE_LIMIT_RPM` (default: `40` requests/minute)

## Run

```bash
python3 scripts/setup_challenge.py
```

## Optional flags

```bash
python3 scripts/setup_challenge.py \
  --manifest manifest.json \
  --binary-name binary_name
```

## Output artifact

`/workspace/playground/artifacts/binary_analysis.json`

`/workspace/playground/artifacts/exploit.py`

`/workspace/playground/artifacts/exploit_report.json`
