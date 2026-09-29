#!/usr/bin/env bash
# Render the fleet proxy env files from the secret prod/fleet-proxy.
#
#   sudo /opt/litellm-fleet/render-env.sh
#
# Writes, as root with mode 0600:
#   /etc/litellm-fleet/fleet.env   read by litellm-fleet.service
#   /etc/litellm-fleet/backup.env  read by litellm-fleet-backup.service
#
# The secret is a JSON object. fleet.env gets the master key, the database
# URL and one key per D11 provider, plus FLEET_PROXY_HOST (this host's
# tailnet IPv4 address from `tailscale ip -4`). backup.env gets only
# FLEET_BACKUP_S3_URI. Other fields in the secret are ignored.
#
# The script reads only prod/fleet-proxy, never prod/ec2-secrets (D11).
# It never prints a secret value. It writes each file to a temporary file
# in the same directory and renames it, so a failed run keeps the old file.
# After a render, run: sudo systemctl restart litellm-fleet
set -euo pipefail

readonly SECRET_ID="prod/fleet-proxy"
readonly ENV_DIR="/etc/litellm-fleet"

if [ "$(id -u)" -ne 0 ]; then
  echo "render-env.sh: run as root (sudo)" >&2
  exit 1
fi
for tool in aws python3 tailscale; do
  command -v "$tool" >/dev/null 2>&1 || { echo "render-env.sh: $tool not found" >&2; exit 1; }
done

umask 077
install -d -m 0700 -o root -g root "$ENV_DIR"

fleet_host="$(tailscale ip -4 | head -n 1)"
if [ -z "$fleet_host" ]; then
  echo "render-env.sh: tailscale has no IPv4 address; run tailscale up first" >&2
  exit 1
fi

region_args=()
if [ -n "${AWS_REGION:-}" ]; then
  region_args=(--region "$AWS_REGION")
fi

# The secret goes from the AWS CLI to Python over a pipe: never in argv,
# never on disk outside ENV_DIR.
aws secretsmanager get-secret-value "${region_args[@]}" \
    --secret-id "$SECRET_ID" --query SecretString --output text \
  | FLEET_PROXY_HOST="$fleet_host" python3 -c '
import datetime
import ipaddress
import json
import os
import re
import sys
import tempfile
import urllib.parse

ENV_DIR = sys.argv[1]
FLEET_KEYS = (
    "FLEET_LITELLM_MASTER_KEY",
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
)
BACKUP_KEYS = ("FLEET_BACKUP_S3_URI",)
# Printable ASCII without space, quotes or backslash: safe inside single
# quotes in a systemd EnvironmentFile.
SAFE_VALUE = re.compile(r"[!#-&(-\[\]-~]+")


def fail(message):
    print("render-env.sh: " + message, file=sys.stderr)
    sys.exit(1)


try:
    secret = json.loads(sys.stdin.read())
except ValueError:
    fail("the secret is not JSON")
if not isinstance(secret, dict):
    fail("the secret is not a JSON object")

values = {}
for key in FLEET_KEYS + BACKUP_KEYS:
    value = secret.get(key)
    if not isinstance(value, str) or not value:
        fail("the secret has no value for " + key)
    if not SAFE_VALUE.fullmatch(value):
        fail(key + " holds a space, quote, backslash or control character")
    values[key] = value

if not values["FLEET_LITELLM_MASTER_KEY"].startswith("sk-"):
    fail("FLEET_LITELLM_MASTER_KEY must start with sk- (the LiteLLM key format)")

db = urllib.parse.urlsplit(values["DATABASE_URL"])
if db.scheme not in ("postgresql", "postgres") or db.hostname not in ("localhost", "127.0.0.1", "::1"):
    fail("DATABASE_URL must be a postgresql:// URL on localhost")

backup = urllib.parse.urlsplit(values["FLEET_BACKUP_S3_URI"])
if backup.scheme != "s3" or not backup.netloc or backup.path.strip("/") == "":
    fail("FLEET_BACKUP_S3_URI must be s3://<bucket>/<prefix>")

host = os.environ["FLEET_PROXY_HOST"]
try:
    address = ipaddress.ip_address(host)
except ValueError:
    fail("tailscale ip -4 did not return an IP address")
if address.version != 4 or address not in ipaddress.ip_network("100.64.0.0/10"):
    fail("the tailscale address is not in 100.64.0.0/10")

stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
header = "# Rendered by render-env.sh from prod/fleet-proxy at " + stamp + ". Do not edit.\n"


def write(name, lines):
    path = os.path.join(ENV_DIR, name)
    fd, tmp = tempfile.mkstemp(dir=ENV_DIR, prefix="." + name + ".")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(header)
            handle.writelines(line + "\n" for line in lines)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.chown(tmp, 0, 0)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print("render-env.sh: wrote " + path + " (" + str(len(lines)) + " variables, mode 0600)")


write("fleet.env", ["FLEET_PROXY_HOST=" + host] + [k + "=\x27" + values[k] + "\x27" for k in FLEET_KEYS])
write("backup.env", [k + "=\x27" + values[k] + "\x27" for k in BACKUP_KEYS])
' "$ENV_DIR"
