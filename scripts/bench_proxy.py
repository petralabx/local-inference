#!/usr/bin/env python
"""Small OpenAI-compatible proxy benchmark. Requires proxy running."""
import concurrent.futures as cf
import json, os, statistics, time, urllib.request

base = os.getenv("LOCAL_PROXY_BASE_URL", "http://127.0.0.1:4000/v1")
key = os.getenv("LOCAL_LITELLM_MASTER_KEY", "sk-local-dev-change-me")
model = os.getenv("LOCAL_PROXY_MODEL", "local-primary")
concurrency = int(os.getenv("BENCH_CONCURRENCY", "4"))
requests = int(os.getenv("BENCH_REQUESTS", "8"))

payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Write exactly five bullet points about why deterministic backtests matter."}],
    "max_tokens": 128,
    "temperature": 0,
}

def one(i):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=data,
        headers={"Content-Type":"application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    t0=time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        raw=r.read()
    dt=time.perf_counter()-t0
    obj=json.loads(raw)
    usage=obj.get("usage", {})
    return {"i": i, "seconds": dt, "usage": usage, "chars": len(raw)}

with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
    results=list(ex.map(one, range(requests)))

secs=[r["seconds"] for r in results]
print(json.dumps({
    "base": base,
    "model": model,
    "requests": requests,
    "concurrency": concurrency,
    "latency_seconds": {"min": min(secs), "median": statistics.median(secs), "max": max(secs)},
    "results": results,
}, indent=2))
