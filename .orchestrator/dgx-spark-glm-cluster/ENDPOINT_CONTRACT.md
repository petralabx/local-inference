# Local Inference Endpoint Contract

MC-Checkout: dsp_mr24bm9au2e44s

## Current Primary Smoke Contract

Use the existing LiteLLM control plane for repo-loop smoke testing:

```bash
export OPENAI_BASE_URL="http://100.103.33.54:4000/v1"
export OPENAI_API_KEY="$LOCAL_LITELLM_MASTER_KEY"
export LOCAL_INFERENCE_MODEL="local-dgx-smoke"
```

On the Dell/control-plane host:

```bash
export OPENAI_BASE_URL="http://127.0.0.1:4000/v1"
export OPENAI_API_KEY="$LOCAL_LITELLM_MASTER_KEY"
export LOCAL_INFERENCE_MODEL="local-dgx-smoke"
```

This keeps repo loops pointed at the stable proxy while the backend can move from smoke to GLM.

## Direct DGX Smoke Endpoint

Use this endpoint only for backend diagnostics while the large GLM model downloads and validates:

```bash
export OPENAI_BASE_URL="http://100.111.220.1:18081/v1"
export OPENAI_API_KEY="local-inference"
export LOCAL_INFERENCE_MODEL="smoke-qwen2.5-0.5b-rpc"
```

Equivalent Tailnet host:

```bash
export OPENAI_BASE_URL="http://phase-f-dgx-spark:18081/v1"
```

## Intended GLM Endpoint

After the large GGUF load gate passes, the direct backend should become:

```bash
export OPENAI_BASE_URL="http://100.111.220.1:18082/v1"
export OPENAI_API_KEY="local-inference"
export LOCAL_INFERENCE_MODEL="local-glm52-ud-iq1m"
```

Then promote the LiteLLM alias in `c:\Users\vince\local-inference` so repo loops still call the proxy, not the direct backend.

## API Compatibility

Verified endpoints:

- `GET /v1/models`
- `POST /v1/chat/completions`

Smoke request:

```bash
curl -sS "$OPENAI_BASE_URL/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "'"$LOCAL_INFERENCE_MODEL"'",
    "messages": [
      {"role": "user", "content": "Reply with exactly: local inference online"}
    ],
    "max_tokens": 16,
    "temperature": 0
  }'
```

## Routing Rules

- Downstream repos should not hardcode Spark hostnames in source code.
- Prefer environment variables loaded by each repo's existing `.env`, task runner, CI secret, or agent config.
- Keep the endpoint private to Tailnet/LAN.
- Keep model aliases explicit so smoke, GLM, and fallback models can be swapped without code changes.
- Do not expose the abliterated GLM endpoint to public users.
