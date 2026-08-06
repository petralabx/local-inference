# Buzz on EC2 — Compose + Tailscale (`lattice-prod`)

Pilot host locked in SPEC: **`i-03b18532cda3c6be6`** (`lattice-prod`,
`t3a.large`, Ubuntu 24.04, `us-east-1`).

Upstream deploy path: [`block/buzz` `deploy/compose/`](https://github.com/block/buzz/tree/main/deploy/compose)
(not the repo-root `docker-compose.yml`).

## 0. Co-tenancy preflight (mandatory — abort if fail)

SSH to the instance (SSM or your usual key), then:

```bash
# Identity
ec2-metadata --instance-id 2>/dev/null || curl -s http://169.254.169.254/latest/meta-data/instance-id
hostnamectl

# Headroom (prefer ≥4 GiB free RAM, ≥20 GiB free disk)
free -h
df -h /

# Docker / Compose (Compose must be ≥ 2.24.4 for TLS overlay)
docker --version
docker compose version

# Port / process collisions with Lattice (adjust if Lattice uses these)
ss -ltnp | egrep ':3000|:5432|:6379|:9000|:9001|:80|:443' || true
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
```

**Pass criteria:** instance id matches `i-03b18532cda3c6be6`; Compose ≥ 2.24.4;
enough free RAM/disk; no irreconcilable port clash (or document remaps).

**Fail → abort:** do **not** install Buzz on this host. Open a dedicated EC2
instead and update SPEC `pilot_host`.

Record results under
`.orchestrator/buzz-collab-workspace/P1/preflight-YYYYMMDD.md`.

## 1. Install Docker (if missing)

Follow Docker’s official Ubuntu install. Confirm:

```bash
docker compose version   # ≥ v2.24.4
```

## 2. Join Tailscale

```bash
# Install Tailscale if needed, then:
sudo tailscale up --ssh=false
tailscale status
tailscale ip -4
```

Prefer cohort access via Tailscale MagicDNS / HTTPS certs rather than the
instance public IPv4 alone.

## 3. Fetch Buzz compose bundle

```bash
sudo mkdir -p /opt/buzz && sudo chown "$USER":"$USER" /opt/buzz
cd /opt/buzz
git clone --depth 1 https://github.com/block/buzz.git
cd buzz/deploy/compose
cp .env.example .env
```

Pin the image (do not leave floating `main` for longer than smoke day):

```bash
# After first successful pull, record digest and set e.g.:
# BUZZ_IMAGE=ghcr.io/block/buzz:sha-<7>
grep -E '^BUZZ_IMAGE=' .env || true
```

## 4. Fill `.env` secrets

`./run.sh` refuses to start while any `CHANGE_ME` placeholder remains.

Required identities (generate offline; **never commit**):

- `BUZZ_RELAY_PRIVATE_KEY`
- `RELAY_OWNER_PUBKEY` (64-char hex; closed-relay owner)

Fill Postgres/Redis/MinIO/HMAC placeholders with random secrets. Keep a sealed
backup (Vince owns backup location — see KEYS-AND-L5-FENCE.md).

Set relay URL for clients, e.g. Tailscale HTTPS:

```bash
# Example — replace with your tailnet DNS name after `tailscale cert` / serve:
# RELAY_URL=wss://lattice-prod.<tailnet>.ts.net
```

## 5. Start stack

Fresh DB:

```bash
# In .env: BUZZ_AUTO_MIGRATE=true for first boot (then revisit)
./run.sh start
./run.sh status
curl -fsS "http://127.0.0.1:${BUZZ_HTTP_PORT:-3000}/_liveness"
```

Optional public TLS (only if using a real DNS name + open 80/443 — usually
**not** required when using Tailscale `wss`):

```bash
BUZZ_COMPOSE_TLS=true ./run.sh start
```

## 6. Expose `wss` to the cohort (recommended: Tailscale)

Option A — Tailscale Serve (host terminates TLS):

```bash
# After HTTPS enabled on the tailnet:
sudo tailscale serve --bg --https=443 http://127.0.0.1:3000
```

Option B — clients use `ws://100.x.y.z:3000` only on-tailnet (no TLS). Acceptable
for early smoke; move to `wss` before daily use.

Verify from Ricardo/Stephen machines on the same tailnet before calling P1 done.

## 7. Backup hint

```bash
./run.sh backup-hint
```

Minimum backup set: relay private key, owner key, Postgres volume, MinIO/git
volumes. Schedule owner: Vince.

## 8. Rollback

```bash
cd /opt/buzz/buzz/deploy/compose
./run.sh stop
# Optional: docker compose down  (keep volumes unless wiping pilot)
```

Does not touch portal RDS/Vercel. Lattice processes should be left running.

## References

- https://github.com/block/buzz/tree/main/deploy/compose
- https://engineering.block.xyz/blog/run-your-own-buzz-relay
- SPEC: `.orchestrator/buzz-collab-workspace/SPEC.md` (`pilot_host.instance_id`)
