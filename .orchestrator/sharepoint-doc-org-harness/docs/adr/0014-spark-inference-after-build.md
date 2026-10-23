# After this build, tokens go through the Sparks

Steady-state Organizer classify, digest, and any later token work on this corpus call LiteLLM on spark-b4ec at `http://100.92.253.61:4000/v1`. The models are the DGX Spark aliases already on that proxy: `local-driver` (Spark B, structured classify) and `local-coder` (Spark A, fallback). Clients call that proxy, not a Spark model port (`:8000`). Paid cloud hosts stay forbidden. Dell `local-fast` / `local-primary` are the proxy’s Qwen fallbacks, not the planned classify path after cutover.

Source: `C:\Users\vince\local-inference\litellm\config.yaml` and `docs\runbooks\dell-qwen-worker-lane.md`.
