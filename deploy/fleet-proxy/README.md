# Fleet proxy (`fleet-proxy`, port 4001)

The fleet proxy is the model gateway for the agent fleet (agent fleet spec,
phase P1, decision D5). It is a separate LiteLLM instance on its own EC2
host, `fleet-proxy`. It serves cloud aliases on `<fleet-proxy>:4001`, where
`<fleet-proxy>` is the host's tailnet address.

The trading gateway on the Dell (`:4000`, `litellm/config.yaml`,
`scripts/start_proxy.sh`, `scripts/ensure_proxy.sh`) does not change. Nothing
in this folder runs on the Dell, and the Dell never reads these files.

## Files

| File | Installed as | Purpose |
|---|---|---|
| `../../litellm/fleet.yaml` | `/opt/litellm-fleet/fleet.yaml` | Aliases and settings |
| `requirements.txt` | `/opt/litellm-fleet/venv` | Pinned LiteLLM and Prisma |
| `check_fleet_config.py` | `/opt/litellm-fleet/check_fleet_config.py` | Config and bind-address check before each start |
| `litellm-fleet.service` | `/etc/systemd/system/` | The proxy unit |
| `render-env.sh` | `/opt/litellm-fleet/render-env.sh` | Renders the env files from `prod/fleet-proxy` |
| `backup-db.sh` | `/opt/litellm-fleet/backup-db.sh` | `pg_dump` to the S3 backup prefix |
| `litellm-fleet-backup.service`, `litellm-fleet-backup.timer` | `/etc/systemd/system/` | Daily backup at 03:30 ET, as root |

## Rules

- Cloud aliases only: a strong and a fast alias for each D11 provider
  (Anthropic, OpenAI, Google Gemini, xAI, Mistral, DeepSeek, OpenRouter).
  Phase P1b adds `local-primary` and `local-fast`.
- Never a `local-driver` or `local-coder` alias (D23, SC-13).
- Keys live only in the secret `prod/fleet-proxy` and in
  `/etc/litellm-fleet/fleet.env` on `fleet-proxy` (D11, SC-6). The fleet
  never uses a key from `prod/ec2-secrets`. This repository is public: never
  commit a key, an account id, a bucket name or the host's address.
- No trace callback. The fleet sends no traces to trading's Langfuse or to
  Langfuse Cloud. Request and spend logs go to the local Postgres database
  `litellm_fleet`. Spend logs keep metadata and cost, not prompt text.
- `allow_requests_on_db_unavailable` stays false: without the database, the
  proxy refuses requests.
- The unit binds one tailnet address. `check_fleet_config.py` refuses an
  empty address, `0.0.0.0`, loopback and any address outside `100.64.0.0/10`.
- Stop rule: only `sudo systemctl stop litellm-fleet` stops the fleet proxy.
  Any other exit restarts it after 5 seconds.

## Aliases

| Provider | Strong | Fast |
|---|---|---|
| Anthropic | `cloud-claude-sonnet` | `cloud-claude-haiku` |
| OpenAI | `cloud-gpt` | `cloud-gpt-mini` |
| Google | `cloud-gemini-pro` | `cloud-gemini-flash` |
| xAI | `cloud-grok` | `cloud-grok-fast` |
| Mistral | `cloud-mistral-large` | `cloud-mistral-small` |
| DeepSeek | `cloud-deepseek-pro` | `cloud-deepseek-flash` |
| OpenRouter | `cloud-openrouter-kimi` | `cloud-openrouter-qwen-flash` |

`litellm/fleet.yaml` maps each alias to a vendor model id. The pinned LiteLLM
lists a retirement date of 2026-10-15 for `claude-haiku-4-5`, the model behind
`cloud-claude-haiku`. Replace that model id through a normal PR before then.

## The secret `prod/fleet-proxy`

A JSON object with these fields (names only; the values stay in Secrets
Manager):

- `FLEET_LITELLM_MASTER_KEY`: starts with `sk-`.
- `DATABASE_URL`: `postgresql://litellm_fleet:<password>@127.0.0.1:5432/litellm_fleet`.
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`,
  `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`: keys from the
  fleet's own provider accounts (separate organisations or teams, D11).
- `FLEET_BACKUP_S3_URI`: `s3://<bucket>/<prefix>`, the backup prefix that the
  instance role may write.

`render-env.sh` refuses a missing or empty field, a value with a space, quote
or backslash, a database that is not on localhost, and a backup URI without a
prefix.

## Install (operator, on `fleet-proxy`)

The host, its security group, its instance role, the `nftables` rule for the
metadata service and the tailnet policy come first. The spec's P1 "Infra"
bullet lists them. Then:

1. Packages and users.

   ```bash
   sudo apt-get install -y python3-venv postgresql git
   # Install AWS CLI v2 from the official installer.
   sudo useradd --system --home-dir /var/lib/litellm-fleet --shell /usr/sbin/nologin litellm-fleet
   sudo install -d -m 0700 -o litellm-fleet -g litellm-fleet /var/lib/litellm-fleet
   ```

2. PostgreSQL on localhost only, one database `litellm_fleet`.

   ```bash
   # postgresql.conf: listen_addresses = 'localhost'
   sudo -u postgres createuser --pwprompt litellm_fleet
   sudo -u postgres createdb --owner litellm_fleet litellm_fleet
   ```

3. The pinned install in `/opt/litellm-fleet`, from a merged commit of this
   repository.

   ```bash
   sudo install -d -m 0755 /opt/litellm-fleet
   sudo git clone https://github.com/petralabx/local-inference /opt/litellm-fleet/src
   sudo git -C /opt/litellm-fleet/src checkout <merged-commit>
   cd /opt/litellm-fleet/src
   sudo python3 -m venv /opt/litellm-fleet/venv
   sudo /opt/litellm-fleet/venv/bin/pip install -r deploy/fleet-proxy/requirements.txt
   sudo install -m 0644 litellm/fleet.yaml /opt/litellm-fleet/fleet.yaml
   sudo install -m 0644 deploy/fleet-proxy/check_fleet_config.py /opt/litellm-fleet/
   sudo install -m 0755 deploy/fleet-proxy/render-env.sh deploy/fleet-proxy/backup-db.sh /opt/litellm-fleet/
   sudo install -m 0644 deploy/fleet-proxy/litellm-fleet.service \
     deploy/fleet-proxy/litellm-fleet-backup.service \
     deploy/fleet-proxy/litellm-fleet-backup.timer /etc/systemd/system/
   ```

4. Let `litellm-fleet` run `prisma generate`. The generator writes into the
   venv's `prisma` package, so `litellm-fleet` owns that one directory. The
   rest of `/opt/litellm-fleet` stays owned by root.

   ```bash
   PY=/opt/litellm-fleet/venv/bin/python
   sudo ln -sfn "$($PY -c 'import litellm.proxy, os; print(os.path.join(os.path.dirname(litellm.proxy.__file__), "schema.prisma"))')" \
     /opt/litellm-fleet/schema.prisma
   sudo chown -R litellm-fleet:litellm-fleet "$($PY -c 'import prisma, os; print(os.path.dirname(prisma.__file__))')"
   ```

5. Render the env files and start.

   ```bash
   sudo /opt/litellm-fleet/render-env.sh
   sudo systemctl daemon-reload
   sudo systemctl enable --now litellm-fleet litellm-fleet-backup.timer
   sudo journalctl -u litellm-fleet -f
   ```

   The first start downloads the Prisma engines and a Node runtime into
   `/var/lib/litellm-fleet/.cache` and runs the LiteLLM migrations. This can
   take several minutes.

To change aliases: merge a PR, then repeat the `fleet.yaml` install line from
step 3 and run `sudo systemctl restart litellm-fleet`. To rotate a key: update
`prod/fleet-proxy`, run `render-env.sh`, and restart the unit.

## Check (P1 acceptance)

From the repository, before the PR merges:

```bash
git diff --name-only origin/main...HEAD
git diff -U0 origin/main...HEAD -- litellm/ | grep '^+.*api_key:' | grep -v 'os.environ/'   # prints nothing
python deploy/fleet-proxy/check_fleet_config.py litellm/fleet.yaml
```

From the operator's tailnet identity, after the install:

```bash
curl -sS -H "Authorization: Bearer $FLEET_LITELLM_MASTER_KEY" http://<fleet-proxy>:4001/v1/models
# Lists the 14 cloud-* aliases and no local-* alias.
for alias in cloud-claude-sonnet cloud-claude-haiku cloud-gpt cloud-gpt-mini \
  cloud-gemini-pro cloud-gemini-flash cloud-grok cloud-grok-fast \
  cloud-mistral-large cloud-mistral-small cloud-deepseek-pro cloud-deepseek-flash \
  cloud-openrouter-kimi cloud-openrouter-qwen-flash; do
  curl -sS -o /dev/null -w "$alias %{http_code}\n" \
    -H "Authorization: Bearer $FLEET_LITELLM_MASTER_KEY" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$alias\",\"max_tokens\":16,\"messages\":[{\"role\":\"user\",\"content\":\"Say OK.\"}]}" \
    http://<fleet-proxy>:4001/v1/chat/completions
done
# Each prints 200. Expected cost: under $0.25 in total.
curl -sS -H "Authorization: Bearer $FLEET_LITELLM_MASTER_KEY" http://<fleet-proxy>:4001/spend/logs
# Each alias appears.
```

On `fleet-proxy`:

```bash
aws secretsmanager get-secret-value --secret-id prod/ec2-secrets        # AccessDenied
sudo -u litellm-fleet curl -sS -m 5 -X PUT http://169.254.169.254/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 60'                           # times out
sudo systemctl kill litellm-fleet; sleep 30; systemctl status litellm-fleet   # active again
sudo systemctl start litellm-fleet-backup.service; journalctl -u litellm-fleet-backup -n 5
```

The probes to the Dell's `:4000` and `:8000`, the Sparks and TRADINGBOX must
fail. The tailnet policy `tests` must pass. No command runs on the Dell.

## Rollback

```bash
sudo systemctl disable --now litellm-fleet litellm-fleet-backup.timer
```

Then restore the saved tailnet policy, terminate the instance, and revert the
PR. The trading gateway on `:4000` never changed.
