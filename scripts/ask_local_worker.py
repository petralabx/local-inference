#!/usr/bin/env python3
"""One-shot chat client for local worker aliases via LiteLLM proxy."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

DEFAULT_BASE_URL = "http://100.103.33.54:4000/v1"
MASTER_KEY_ENV = "LOCAL_LITELLM_MASTER_KEY"
MODEL_ALIASES = ("local-glm52", "local-primary", "local-coder", "local-fast")
NO_THINK_MODELS = {"local-primary", "local-coder", "local-fast"}
PROXY_SCHEMES = {"http", "https"}

_THINKING_BLOCK_PATTERNS = (
    re.compile(r"(?is)<redacted_thinking>.*?</redacted_thinking>\s*"),
    re.compile(r"(?is)<think>.*?</think>\s*"),
)


class WorkerClientError(RuntimeError):
    """Raised when the worker request or response cannot be handled safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a one-shot chat prompt to a local worker alias."
    )
    parser.add_argument(
        "--model",
        choices=MODEL_ALIASES,
        default="local-glm52",
        help="LiteLLM model alias to target.",
    )
    parser.add_argument(
        "--system",
        default="",
        help="Optional system instruction prepended as the first message.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OpenAI-compatible /v1 base URL for the proxy.",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Fallback env file used only when LOCAL_LITELLM_MASTER_KEY is unset.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Maximum completion tokens for the request.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="Sampling temperature for the request.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--proxy",
        default="",
        help="Optional HTTP/HTTPS proxy URL (example: http://127.0.0.1:1054).",
    )
    parser.add_argument(
        "--prompt",
        dest="prompt_flag",
        default="",
        help="Prompt text (flag form).",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="",
        help="Prompt text (positional form).",
    )
    args = parser.parse_args(argv)

    prompt = args.prompt_flag.strip() or args.prompt.strip()
    if not prompt:
        parser.error("A prompt is required (use --prompt or positional prompt).")
    args.prompt = prompt

    if args.max_tokens <= 0:
        parser.error("--max-tokens must be > 0.")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0.")

    return args


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_optional_quotes(value.strip())
    return values


def _is_usable_master_key(value: str) -> bool:
    key = value.strip()
    if not key:
        return False
    return "CHANGE-ME" not in key.upper()


def resolve_master_key(
    environ: Mapping[str, str], env_file_arg: str, default_env_file: Path
) -> str:
    env_key = environ.get(MASTER_KEY_ENV, "").strip()
    if env_key:
        if not _is_usable_master_key(env_key):
            raise WorkerClientError(f"{MASTER_KEY_ENV} is set but appears invalid.")
        return env_key

    candidate_paths: list[Path] = []
    if env_file_arg:
        candidate_paths.append(Path(env_file_arg).expanduser())
    elif default_env_file.exists():
        candidate_paths.append(default_env_file)

    if not candidate_paths:
        raise WorkerClientError(
            f"{MASTER_KEY_ENV} is not set. Export it or provide --env-file."
        )

    env_path = candidate_paths[0]
    if not env_path.exists():
        raise WorkerClientError(f"Missing env file: {env_path}")

    values = parse_env_file(env_path)
    file_key = values.get(MASTER_KEY_ENV, "").strip()
    if not file_key:
        raise WorkerClientError(f"{MASTER_KEY_ENV} not found in {env_path}")
    if not _is_usable_master_key(file_key):
        raise WorkerClientError(f"{MASTER_KEY_ENV} is unset in {env_path}")
    return file_key


def normalize_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        raise WorkerClientError("Base URL cannot be empty.")
    return value


def apply_no_think(prompt: str, model: str) -> str:
    if model in NO_THINK_MODELS and "/no_think" not in prompt:
        return f"{prompt.rstrip()} /no_think"
    return prompt


def strip_thinking_blocks(text: str) -> str:
    result = text
    for pattern in _THINKING_BLOCK_PATTERNS:
        result = pattern.sub("", result)
    return result.strip()


def build_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return messages


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "model": args.model,
        "messages": build_messages(args.system, apply_no_think(args.prompt, args.model)),
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }


def build_opener(proxy: str) -> urllib.request.OpenerDirector:
    proxy_value = proxy.strip()
    if not proxy_value:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    parsed = urllib.parse.urlparse(proxy_value)
    if not parsed.scheme or not parsed.netloc:
        raise WorkerClientError("Proxy must be a full URL (scheme://host:port).")
    if parsed.scheme.lower() not in PROXY_SCHEMES:
        raise WorkerClientError(
            f"Unsupported proxy scheme '{parsed.scheme}'. Use HTTP/HTTPS URL."
        )

    proxy_map = {"http": proxy_value, "https": proxy_value}
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxy_map))


def _http_error_message(status_code: int, raw_body: bytes) -> str:
    body_text = raw_body.decode("utf-8", errors="replace").strip()
    if body_text:
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                msg = err.get("message")
                if isinstance(msg, str) and msg.strip():
                    return f"HTTP {status_code}: {msg.strip()}"
        return f"HTTP {status_code}: {body_text[:400]}"
    return f"HTTP {status_code}: empty error body"


def _redact_secret(message: str, secret: str) -> str:
    return message.replace(secret, "[REDACTED]") if secret else message


def post_chat_completion(
    base_url: str,
    master_key: str,
    payload: dict[str, Any],
    timeout: int,
    proxy: str,
) -> dict[str, Any]:
    url = f"{normalize_base_url(base_url)}/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    opener = build_opener(proxy)

    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw_error = exc.read() if exc.fp is not None else b""
        message = _http_error_message(exc.code, raw_error)
        raise WorkerClientError(_redact_secret(message, master_key)) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise WorkerClientError(f"Request failed: {reason}") from exc

    if not raw:
        raise WorkerClientError("Empty response body from worker.")

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerClientError("Worker returned invalid JSON response.") from exc

    if not isinstance(decoded, dict):
        raise WorkerClientError("Worker response JSON must be an object.")
    return decoded


def _extract_content_from_message(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if item.get("type") == "text" and isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return ""


def extract_clean_content(response: dict[str, Any], model: str) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise WorkerClientError("Missing choices in worker response.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise WorkerClientError("Malformed first choice in worker response.")

    message = first_choice.get("message")
    content = _extract_content_from_message(message)
    if not content.strip():
        raise WorkerClientError(f"Empty response from {model}")

    cleaned = strip_thinking_blocks(content)
    if not cleaned:
        raise WorkerClientError(
            f"Empty content after stripping thinking blocks from {model}"
        )
    return cleaned


def main(
    argv: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
    stdout: Any = None,
    stderr: Any = None,
) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr

    try:
        args = parse_args(argv)
        env = dict(os.environ) if environ is None else dict(environ)
        default_env_file = Path(__file__).resolve().parents[1] / ".env.local"
        key = resolve_master_key(env, args.env_file, default_env_file)
        payload = build_payload(args)
        response = post_chat_completion(
            base_url=args.base_url,
            master_key=key,
            payload=payload,
            timeout=args.timeout,
            proxy=args.proxy,
        )
        content = extract_clean_content(response, args.model)
        print(content, file=out)
        return 0
    except WorkerClientError as exc:
        print(f"ERROR: {exc}", file=err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
