# After this build, tokens go through the Sparks

Steady-state Organizer classify, digest, and any later token work on this corpus call Dell LiteLLM at `http://100.103.33.54:4000/v1`. The models are the DGX Spark aliases already on that proxy: `local-driver` (Spark B, structured classify) and `local-coder` (Spark A, fallback). Clients never hit a Spark port directly. Paid cloud hosts stay forbidden. Dell `local-fast` / `local-primary` are the proxy’s Qwen fallbacks, not the planned classify path after cutover.

Source: `C:\Users\vince\local-inference\litellm\config.yaml` and `docs\runbooks\dell-qwen-worker-lane.md`.
