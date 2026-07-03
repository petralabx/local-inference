# DGX Spark Cutover Checklist

Use this tomorrow after the two DGX Spark machines are wired and reachable.

## 1. Prove DGX backend directly

On the DGX head, start a known-fit vLLM/SGLang backend first. Do not start with GLM-5.2.

Example known-fit smoke target:

```bash
vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 \
  --host 0.0.0.0 \
  --port 8000 \
  --distributed-executor-backend ray \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.85 \
  --max-model-len 65536
```

Then from Dell:

```bash
curl http://DGX_HEAD_IP:8000/v1/models
```

## 2. Repoint LiteLLM only

Edit `C:\Users\vince\local-inference\litellm\config.yaml` and change `api_base` for `local-primary` to:

```yaml
api_base: http://DGX_HEAD_IP:8000/v1
```

Keep client alias `local-primary` unchanged.

## 3. Restart and verify

```bash
cd "$HOME/local-inference"
./scripts/start_proxy.sh
./scripts/smoke_proxy.sh
```

## 4. GLM-5.2 lane

Only test GLM-5.2 after the cluster is proven with a known-fit model. Start with low context and treat as experimental until it passes:

- load test
- `/v1/models`
- chat smoke
- JSON/tool-call smoke
- concurrency smoke
- overnight stability

If GLM-5.2 artifact is GGUF Q4, route it through a llama.cpp/KTransformers lane, not vLLM/Ray mainline.
