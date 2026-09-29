#!/usr/bin/env python3
"""Fake OpenAI endpoint on 127.0.0.1 (fleet proxy integration test only).

The test points the cloud-gpt-mini alias here with OPENAI_API_BASE, so a chat
request never leaves the container. Each request adds one line to
/srv/fleet-it/upstream-hits.log. The log never holds a key.
"""

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

HITS = "/srv/fleet-it/upstream-hits.log"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 (http.server API)
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            model = json.loads(body or b"{}").get("model", "")
        except ValueError:
            model = "<not json>"
        with open(HITS, "a", encoding="utf-8") as log:
            log.write(f"{time.time():.0f} {self.path} model={model}\n")
        reply = {
            # LiteLLM keys its spend log row on this id, so each reply needs its own.
            "id": f"chatcmpl-fleet-it-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 18999), Handler).serve_forever()
