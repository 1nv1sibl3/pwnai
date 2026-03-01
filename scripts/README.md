# Setup Script

Prepare the challenge playground inside the running `ctf-dev` container, then start binary analysis (recon + IDA MCP agent).

## Required env vars

- `OPENAI_KEY`
- `MODEL`
- `IDA_MCP_URL`

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
