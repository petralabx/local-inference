#!/usr/bin/env bash
# Runs inside the disposable fleet-proxy test host that run.sh starts.
#
#   in-host.sh install   README steps 1 to 5 with dummy secrets, first start
#   in-host.sh checks    run, fail-closed, restart, backup and stop checks
#
# Every check prints one PASS, FAIL or INFO line. The script exits 1 when a
# check fails. All keys here are dummy values. The only model endpoint the
# proxy can reach is fake_upstream.py on 127.0.0.1.
set -uo pipefail

readonly IT=/srv/fleet-it
readonly SRC=/src
readonly HERE="$SRC/deploy/fleet-proxy/integration"
readonly HOST_IP=100.100.7.7
readonly PORT=4001
readonly BASE="http://$HOST_IP:$PORT"
readonly MASTER=sk-fleet-it-master-0000
readonly DB_PASS=it-db-pass-0000
readonly ENV_DIR=/etc/litellm-fleet
readonly S3_DIR="$IT/s3/example-bucket/fleet-proxy/pg"
failures=0

pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; failures=$((failures + 1)); }
info() { echo "INFO $*"; }
# check <label> <command...>: PASS when the command exits 0.
check() {
  local label="$1"
  shift
  if "$@"; then pass "$label"; else fail "$label"; fi
}
http_code() { curl -s -o /dev/null -w '%{http_code}' -m 20 "$@"; }
hits() { wc -l < "$IT/upstream-hits.log"; }
listening() { ss -ltnH "( sport = :$PORT )" | grep -q .; }
unit_prop() { systemctl show -p "$1" --value litellm-fleet; }
psql_fleet() { runuser -u postgres -- psql -X -A -t -d litellm_fleet -c "$1"; }
# chat <key> <alias>: print the HTTP code; the body goes to $IT/last-chat.json.
chat() {
  curl -s -o "$IT/last-chat.json" -w '%{http_code}' -m 60 \
    -H "Authorization: Bearer $1" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$2\",\"max_tokens\":8,\"messages\":[{\"role\":\"user\",\"content\":\"fleet-it-marker: say OK\"}]}" \
    "$BASE/v1/chat/completions"
}
# wait_ready <seconds>: print the seconds until /health/readiness returns 200.
wait_ready() {
  local limit="$1" start=$SECONDS
  while [ $((SECONDS - start)) -lt "$limit" ]; do
    if [ "$(http_code "$BASE/health/readiness")" = 200 ]; then
      echo $((SECONDS - start))
      return 0
    fi
    sleep 1
  done
  return 1
}
journal_since() { journalctl -u litellm-fleet --since "@$1" --no-pager -o cat; }

phase_install() {
  set -e
  echo "== Test fixtures: stubs for aws and tailscale, a tailnet address on lo, dummy secret"
  mkdir -p "$IT"
  : > "$IT/upstream-hits.log"
  : > "$IT/aws-calls.log"
  echo "$HOST_IP" > "$IT/tailnet-ip"
  install -m 0755 "$HERE/aws-stub" /usr/local/bin/aws
  install -m 0755 "$HERE/tailscale-stub" /usr/local/bin/tailscale
  ip addr add "$HOST_IP/32" dev lo
  cat > "$IT/secret.json" <<JSON
{
  "FLEET_LITELLM_MASTER_KEY": "$MASTER",
  "DATABASE_URL": "postgresql://litellm_fleet:$DB_PASS@127.0.0.1:5432/litellm_fleet",
  "ANTHROPIC_API_KEY": "dummy-anthropic-0000",
  "OPENAI_API_KEY": "dummy-openai-0000",
  "GEMINI_API_KEY": "dummy-gemini-0000",
  "XAI_API_KEY": "dummy-xai-0000",
  "MISTRAL_API_KEY": "dummy-mistral-0000",
  "DEEPSEEK_API_KEY": "dummy-deepseek-0000",
  "OPENROUTER_API_KEY": "dummy-openrouter-0000",
  "FLEET_BACKUP_S3_URI": "s3://example-bucket/fleet-proxy/pg"
}
JSON
  chmod 0600 "$IT/secret.json"

  echo "== README step 1: packages, service user and state directory"
  apt-get update -q >/dev/null
  apt-get install -y -q python3-venv postgresql git libatomic1 >/dev/null
  # Test fixture (needs python3): the fake upstream, and a drop-in that sends
  # the openai/ aliases to it.
  systemd-run --quiet --unit fleet-it-upstream --property=Restart=always \
    python3 "$HERE/fake_upstream.py"
  mkdir -p /etc/systemd/system/litellm-fleet.service.d
  printf '[Service]\nEnvironment=OPENAI_API_BASE=http://127.0.0.1:18999/v1\n' \
    > /etc/systemd/system/litellm-fleet.service.d/90-integration-test.conf
  useradd --system --home-dir /var/lib/litellm-fleet --shell /usr/sbin/nologin litellm-fleet
  install -d -m 0700 -o litellm-fleet -g litellm-fleet /var/lib/litellm-fleet

  echo "== README step 2: PostgreSQL on localhost, one database litellm_fleet"
  systemctl start postgresql
  local listen
  listen="$(runuser -u postgres -- psql -X -A -t -c 'SHOW listen_addresses')"
  check "PostgreSQL listen_addresses is localhost (got: $listen)" test "$listen" = localhost
  # README uses createuser --pwprompt; this is the same role without a prompt.
  runuser -u postgres -- psql -X -q -c "CREATE ROLE litellm_fleet LOGIN PASSWORD '$DB_PASS'"
  runuser -u postgres -- createdb --owner litellm_fleet litellm_fleet

  echo "== README step 3: pinned install in /opt/litellm-fleet"
  install -d -m 0755 /opt/litellm-fleet
  # Stands in for the git clone and checkout: the tree under test.
  mkdir /opt/litellm-fleet/src
  tar -C "$SRC" --exclude=./.venv --exclude=./.git -cf - . | tar -C /opt/litellm-fleet/src -xf -
  cd /opt/litellm-fleet/src
  python3 -m venv /opt/litellm-fleet/venv
  /opt/litellm-fleet/venv/bin/pip install -q -r deploy/fleet-proxy/requirements.txt
  install -m 0644 litellm/fleet.yaml /opt/litellm-fleet/fleet.yaml
  install -m 0644 deploy/fleet-proxy/check_fleet_config.py /opt/litellm-fleet/
  install -m 0755 deploy/fleet-proxy/render-env.sh deploy/fleet-proxy/backup-db.sh /opt/litellm-fleet/
  install -m 0644 deploy/fleet-proxy/litellm-fleet.service \
    deploy/fleet-proxy/litellm-fleet-backup.service \
    deploy/fleet-proxy/litellm-fleet-backup.timer /etc/systemd/system/
  info "installed: $(/opt/litellm-fleet/venv/bin/pip list 2>/dev/null | grep -E '^(litellm|litellm-proxy-extras|prisma) ' | tr -s ' ' | tr '\n' ';')"

  echo "== README step 4: litellm-fleet owns the prisma package only"
  local PY=/opt/litellm-fleet/venv/bin/python
  ln -sfn "$($PY -c 'import litellm.proxy, os; print(os.path.join(os.path.dirname(litellm.proxy.__file__), "schema.prisma"))')" \
    /opt/litellm-fleet/schema.prisma
  chown -R litellm-fleet:litellm-fleet "$($PY -c 'import prisma, os; print(os.path.dirname(prisma.__file__))')"

  echo "== README step 5: render the env files and start"
  /opt/litellm-fleet/render-env.sh > "$IT/render-good.out" 2>&1
  cat "$IT/render-good.out"
  systemctl daemon-reload
  set +e
  systemctl enable --now litellm-fleet litellm-fleet-backup.timer \
    || info "systemctl enable --now returned non-zero; waiting for the restart loop"
  local took
  if took="$(wait_ready 900)"; then
    pass "first start: /health/readiness 200 after ${took} s (downloads Prisma engines, runs migrations)"
  else
    fail "first start: not ready after 900 s"
    journalctl -u litellm-fleet --no-pager -o cat | tail -n 40
  fi
}

phase_checks() {
  set +e
  local t0 code h0 h1 n pid pid0 took

  echo "== 1. The test host has no network"
  check "no IPv4 route (container network disconnected)" test -z "$(ip -4 route)"

  echo "== 2. Unit, service user and bind address"
  check "litellm-fleet is active" test "$(unit_prop ActiveState)" = active
  pid="$(unit_prop MainPID)"
  local user
  user="$(ps -o user= -p "$pid")"
  check "the main process runs as litellm-fleet (got: $user)" test "$user" = litellm-fleet
  local socks
  socks="$(ss -ltnH "( sport = :$PORT )" | awk '{print $4}' | sort -u | tr '\n' ' ')"
  check "port 4001 listens on $HOST_IP only (got: $socks)" test "$socks" = "$HOST_IP:$PORT "
  check "nothing answers on 127.0.0.1:4001" test "$(http_code http://127.0.0.1:$PORT/health/readiness)" = 000

  echo "== 3. Env files from render-env.sh"
  check "$ENV_DIR is 700 root:root" test "$(stat -c '%a %U:%G' "$ENV_DIR")" = "700 root:root"
  local f
  for f in fleet.env backup.env; do
    check "$f is 600 root:root" test "$(stat -c '%a %U:%G' "$ENV_DIR/$f")" = "600 root:root"
  done
  check "litellm-fleet cannot read fleet.env" bash -c "! runuser -u litellm-fleet -- cat $ENV_DIR/fleet.env >/dev/null 2>&1"
  info "fleet.env names: $(grep -v '^#' "$ENV_DIR/fleet.env" | cut -d= -f1 | tr '\n' ' ')"
  info "backup.env names: $(grep -v '^#' "$ENV_DIR/backup.env" | cut -d= -f1 | tr '\n' ' ')"
  local leaked=0 value
  for value in $(python3 -c 'import json; print("\n".join(json.load(open("/srv/fleet-it/secret.json")).values()))'); do
    grep -qF -- "$value" "$IT/render-good.out" && leaked=$((leaked + 1))
  done
  check "render-env.sh printed no secret value" test "$leaked" -eq 0

  echo "== 4. Aliases"
  local served want
  served="$(curl -s -m 20 -H "Authorization: Bearer $MASTER" "$BASE/v1/models" \
    | python3 -c 'import json,sys; print(" ".join(sorted(m["id"] for m in json.load(sys.stdin)["data"])))')"
  want="$(/opt/litellm-fleet/venv/bin/python -c 'import yaml; print(" ".join(sorted(m["model_name"] for m in yaml.safe_load(open("/opt/litellm-fleet/fleet.yaml"))["model_list"])))')"
  info "served: $served"
  check "/v1/models lists exactly the fleet.yaml aliases ($(echo "$served" | wc -w))" test "$served" = "$want"
  check "/v1/models lists no local- alias" bash -c "! grep -q 'local-' <<< '$served'"
  code="$(http_code "$BASE/v1/models")"
  check "/v1/models without a key is refused (HTTP $code)" test "$code" = 401
  code="$(http_code -H 'Authorization: Bearer sk-wrong-0000' "$BASE/v1/models")"
  check "/v1/models with a wrong key is refused (HTTP $code)" bash -c "[ $code = 400 ] || [ $code = 401 ]"

  echo "== 5. Database"
  local db
  db="$(curl -s -m 20 "$BASE/health/readiness" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("db"))')"
  check "/health/readiness reports db=$db" test "$db" = connected
  n="$(psql_fleet "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")"
  check "litellm_fleet holds the LiteLLM tables ($n)" test "$n" -gt 10
  n="$(psql_fleet 'SELECT count(*) FROM "_prisma_migrations" WHERE finished_at IS NOT NULL')"
  check "Prisma migrations applied ($n)" test "$n" -gt 0
  check "the Prisma cache is in /var/lib/litellm-fleet, owned by litellm-fleet" \
    bash -c 'test -d /var/lib/litellm-fleet/.cache && test -z "$(find /var/lib/litellm-fleet ! -user litellm-fleet | head -n 1)"'
  check "no Prisma cache under /root" bash -c '! ls -d /root/.cache/prisma* >/dev/null 2>&1'

  echo "== 6. Requests, virtual key and spend logs"
  local vkey
  vkey="$(curl -s -m 30 -H "Authorization: Bearer $MASTER" -H 'Content-Type: application/json' \
    -d '{"models":["cloud-gpt-mini"],"key_alias":"fleet-it-agent"}' "$BASE/key/generate" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("key",""))')"
  check "POST /key/generate mints a virtual key in the database" test "${vkey#sk-}" != "$vkey"
  h0="$(hits)"
  code="$(chat "$vkey" cloud-gpt-mini)"
  check "chat with the virtual key on cloud-gpt-mini: HTTP $code" test "$code" = 200
  code="$(chat "$MASTER" cloud-gpt-mini)"
  check "chat with the master key on cloud-gpt-mini: HTTP $code" test "$code" = 200
  code="$(chat "$vkey" cloud-gpt)"
  check "the virtual key is refused on an alias it does not hold: HTTP $code" \
    bash -c "[ $code = 401 ] || [ $code = 403 ]"
  check "the fake upstream got exactly 2 requests ($(( $(hits) - h0 )))" test "$(( $(hits) - h0 ))" -eq 2
  n=0
  for _ in $(seq 1 60); do
    n="$(psql_fleet "SELECT count(*) FROM \"LiteLLM_SpendLogs\" WHERE model_group = 'cloud-gpt-mini'")"
    [ "$n" -ge 2 ] && break
    sleep 2
  done
  check "LiteLLM_SpendLogs holds both calls ($n rows for cloud-gpt-mini)" test "$n" -ge 2
  n="$(curl -s -m 30 -H "Authorization: Bearer $MASTER" "$BASE/spend/logs" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); d=d.get("data", d) if isinstance(d, dict) else d; print(sum(1 for r in d if r.get("model_group") == "cloud-gpt-mini"))')"
  check "GET /spend/logs lists both calls ($n)" test "$n" -ge 2
  n="$(psql_fleet "SELECT count(*) FROM \"LiteLLM_SpendLogs\" t WHERE t::text LIKE '%fleet-it-marker%'")"
  check "no spend log row holds the prompt text ($n)" test "$n" -eq 0

  echo "== 7. Backup with the database up"
  systemctl start litellm-fleet-backup.service
  check "litellm-fleet-backup.service succeeds" test "$(systemctl show -p Result --value litellm-fleet-backup.service)" = success
  info "$(journalctl -u litellm-fleet-backup --no-pager -o cat | grep 'backup-db.sh:' | tail -n 1)"
  local dumps dump
  dumps="$(ls "$S3_DIR"/*.dump 2>/dev/null | wc -l)"
  check "one dump reached the (stub) S3 prefix ($dumps)" test "$dumps" -eq 1
  dump="$(ls "$S3_DIR"/*.dump 2>/dev/null | head -n 1)"
  check "the upload asks for SSE (AES256)" grep -q -- '--sse AES256' "$IT/aws-calls.log"
  check "no restore-check database is left" test -z "$(runuser -u postgres -- psql -X -A -t -c "SELECT datname FROM pg_database WHERE datname LIKE '%restore_check'")"
  runuser -u postgres -- createdb it_restore
  runuser -u postgres -- pg_restore --exit-on-error --no-owner --no-privileges -d it_restore < "$dump"
  check "the uploaded dump restores into a new database" test $? -eq 0
  local live restored
  live="$(psql_fleet 'SELECT count(*) FROM "LiteLLM_SpendLogs"')"
  restored="$(runuser -u postgres -- psql -X -A -t -d it_restore -c 'SELECT count(*) FROM "LiteLLM_SpendLogs"')"
  check "the restored spend logs match the live ones ($restored of $live)" test "$restored" = "$live"
  live="$(psql_fleet 'SELECT count(*) FROM "LiteLLM_VerificationToken"')"
  restored="$(runuser -u postgres -- psql -X -A -t -d it_restore -c 'SELECT count(*) FROM "LiteLLM_VerificationToken"')"
  check "the restored virtual keys match the live ones ($restored of $live)" test "$restored" = "$live"
  runuser -u postgres -- dropdb it_restore
  check "litellm-fleet-backup.timer is enabled" test "$(systemctl is-enabled litellm-fleet-backup.timer)" = enabled
  info "$(systemctl list-timers --all --no-pager litellm-fleet-backup.timer | sed -n 2p | tr -s ' ')"

  echo "== 8. Database outage while the proxy runs"
  systemctl stop postgresql
  code=000
  for _ in $(seq 1 30); do
    code="$(http_code "$BASE/health/readiness")"
    [ "$code" = 503 ] && break
    sleep 1
  done
  check "/health/readiness returns 503 without the database (HTTP $code)" test "$code" = 503
  code="$(chat "$vkey" cloud-gpt-mini)"
  info "virtual key right after the outage starts: HTTP $code (LiteLLM may serve a key from its 60 s cache)"
  h1="$(hits)"
  info "waiting 65 s for the key cache to expire"
  sleep 65
  code="$(chat "$vkey" cloud-gpt-mini)"
  check "virtual key after the cache expires is refused: HTTP $code" test "$code" != 200
  info "refusal body: $(head -c 240 "$IT/last-chat.json")"
  code="$(http_code -H "Authorization: Bearer $MASTER" -H 'Content-Type: application/json' \
    -d '{"models":["cloud-gpt-mini"]}' "$BASE/key/generate")"
  check "POST /key/generate is refused without the database: HTTP $code" test "$code" != 200
  check "the fake upstream got no request from the refused calls" test "$(hits)" -eq "$h1"
  systemctl start litellm-fleet-backup.service
  check "backup fails without the database" test "$(systemctl show -p Result --value litellm-fleet-backup.service)" != success
  check "the failed backup uploaded nothing" test "$(ls "$S3_DIR"/*.dump | wc -l)" -eq 1
  h1="$(hits)"
  code="$(chat "$MASTER" cloud-gpt-mini)"
  info "master key during the outage: HTTP $code, upstream requests +$(( $(hits) - h1 )) (LiteLLM does not look up the master key in the database)"

  echo "== 9. Start without the database"
  pid0="$(unit_prop MainPID)"
  n="$(unit_prop NRestarts)"
  t0="$(date +%s)"
  h1="$(hits)"
  systemctl restart litellm-fleet
  local ready_seen=0 listen_seen=0 refused=0 served=0
  for _ in $(seq 1 45); do
    listening && listen_seen=$((listen_seen + 1))
    [ "$(http_code "$BASE/health/readiness")" = 200 ] && ready_seen=$((ready_seen + 1))
    if listening; then
      code="$(chat "$vkey" cloud-gpt-mini)"
      if [ "$code" = 200 ]; then served=$((served + 1)); else refused=$((refused + 1)); fi
    fi
    sleep 2
  done
  check "never ready in 90 s without the database" test "$ready_seen" -eq 0
  check "no virtual-key request served in 90 s ($refused refused while listening)" test "$served" -eq 0
  check "the fake upstream got no request" test "$(hits)" -eq "$h1"
  info "port 4001 listening in $listen_seen of 45 samples; NRestarts $n -> $(unit_prop NRestarts); ActiveState $(unit_prop ActiveState)/$(unit_prop SubState)"
  info "journal: $(journal_since "$t0" | grep -iE 'prisma|database|db |connect|P1001|migration' | tail -n 3 | cut -c1-220 | tr '\n' '|')"
  systemctl start postgresql
  if took="$(wait_ready 600)"; then
    pass "after PostgreSQL starts, the proxy serves again without an operator restart (${took} s)"
  else
    fail "the proxy did not recover within 600 s after PostgreSQL started"
    journal_since "$t0" | tail -n 30
  fi

  echo "== 10. systemctl kill: restart within 30 s"
  pid0="$(unit_prop MainPID)"
  t0=$SECONDS
  local t_restart="" t_ready=""
  systemctl kill litellm-fleet
  while [ $((SECONDS - t0)) -lt 180 ]; do
    pid="$(unit_prop MainPID)"
    if [ -z "$t_restart" ] && [ "$pid" != 0 ] && [ "$pid" != "$pid0" ]; then t_restart=$((SECONDS - t0)); fi
    if [ -n "$t_restart" ] && [ "$(http_code "$BASE/health/readiness")" = 200 ]; then t_ready=$((SECONDS - t0)); break; fi
    sleep 1
  done
  check "systemd started a new process ${t_restart:-never} s after the kill" test -n "$t_restart" -a "${t_restart:-99}" -le 30
  check "the proxy served again ${t_ready:-never} s after the kill" test -n "$t_ready" -a "${t_ready:-999}" -le 30

  echo "== 11. A bad bind address or config stops the start (fail closed)"
  cp -p "$ENV_DIR/fleet.env" "$IT/fleet.env.save"
  sed -i 's/^FLEET_PROXY_HOST=.*/FLEET_PROXY_HOST=0.0.0.0/' "$ENV_DIR/fleet.env"
  t0="$(date +%s)"
  systemctl restart litellm-fleet
  sleep 20
  check "FLEET_PROXY_HOST=0.0.0.0: port 4001 never opens" bash -c "! ss -ltnH '( sport = :$PORT )' | grep -q ."
  check "FLEET_PROXY_HOST=0.0.0.0: the config check refuses it" bash -c "journalctl -u litellm-fleet --since @$t0 --no-pager -o cat | grep -q 'not a tailnet address'"
  cp -p "$IT/fleet.env.save" "$ENV_DIR/fleet.env"
  cp -p /opt/litellm-fleet/fleet.yaml "$IT/fleet.yaml.save"
  awk '{print} /^model_list:/{print "  - model_name: local-driver"; print "    litellm_params:"; print "      model: openai/x"; print "      api_key: os.environ/OPENAI_API_KEY"}' \
    "$IT/fleet.yaml.save" > /opt/litellm-fleet/fleet.yaml
  t0="$(date +%s)"
  systemctl restart litellm-fleet
  sleep 20
  check "local-driver alias added: port 4001 never opens" bash -c "! ss -ltnH '( sport = :$PORT )' | grep -q ."
  check "local-driver alias added: the config check refuses it" bash -c "journalctl -u litellm-fleet --since @$t0 --no-pager -o cat | grep -q 'local-driver is forbidden'"
  cp -p "$IT/fleet.yaml.save" /opt/litellm-fleet/fleet.yaml
  systemctl restart litellm-fleet
  if took="$(wait_ready 300)"; then pass "restored config: ready again after ${took} s"; else fail "restored config: not ready after 300 s"; fi

  echo "== 12. render-env.sh refuses a bad secret and keeps the old files"
  local sums case_name rc out ok
  sums="$(sha256sum "$ENV_DIR/fleet.env" "$ENV_DIR/backup.env")"
  cp -p "$IT/secret.json" "$IT/secret.good"
  for case_name in not-json missing-openrouter master-without-sk remote-database value-with-space backup-without-prefix; do
    python3 - "$case_name" <<'PY'
import json, sys
case = sys.argv[1]
secret = json.load(open("/srv/fleet-it/secret.good"))
if case == "not-json":
    open("/srv/fleet-it/secret.json", "w").write("{not json")
    sys.exit(0)
if case == "missing-openrouter":
    del secret["OPENROUTER_API_KEY"]
if case == "master-without-sk":
    secret["FLEET_LITELLM_MASTER_KEY"] = "fleet-master-0000"
if case == "remote-database":
    secret["DATABASE_URL"] = secret["DATABASE_URL"].replace("127.0.0.1", "10.0.0.5")
if case == "value-with-space":
    secret["XAI_API_KEY"] = "dummy xai"
if case == "backup-without-prefix":
    secret["FLEET_BACKUP_S3_URI"] = "s3://example-bucket"
json.dump(secret, open("/srv/fleet-it/secret.json", "w"))
PY
    out="$(/opt/litellm-fleet/render-env.sh 2>&1)"
    rc=$?
    ok=0
    [ "$rc" -eq 1 ] \
      && [ "$(sha256sum "$ENV_DIR/fleet.env" "$ENV_DIR/backup.env")" = "$sums" ] \
      && [ -z "$(ls -A "$ENV_DIR" | grep '^\.')" ] \
      && ok=1
    check "render-env.sh $case_name: exit $rc, old files kept, no temp file | $out" test "$ok" -eq 1
  done
  cp -p "$IT/secret.good" "$IT/secret.json"
  out="$(runuser -u litellm-fleet -- /opt/litellm-fleet/render-env.sh 2>&1)"
  rc=$?
  check "render-env.sh as litellm-fleet: exit $rc | $out" test "$rc" -eq 1
  check "render-env.sh read only prod/fleet-proxy" bash -c "! grep secretsmanager $IT/aws-calls.log | grep -v -- '--secret-id prod/fleet-proxy '"

  echo "== 13. systemd-analyze verify"
  out="$(systemd-analyze verify /etc/systemd/system/litellm-fleet.service \
    /etc/systemd/system/litellm-fleet-backup.service /etc/systemd/system/litellm-fleet-backup.timer 2>&1)"
  rc=$?
  check "systemd-analyze verify: exit $rc${out:+ | $out}" test "$rc" -eq 0

  echo "== 14. Stop rule: systemctl stop stops the proxy for good"
  systemctl stop litellm-fleet
  sleep 10
  check "after systemctl stop: inactive, port closed ($(unit_prop ActiveState))" \
    bash -c "[ \"\$(systemctl show -p ActiveState --value litellm-fleet)\" = inactive ] && ! ss -ltnH '( sport = :$PORT )' | grep -q ."

  echo "== checks done: $failures failed"
  [ "$failures" -eq 0 ]
}

case "${1:-}" in
  install) phase_install ;;
  checks) phase_checks ;;
  *) echo "usage: in-host.sh install|checks" >&2; exit 2 ;;
esac
status=$?
[ "$failures" -eq 0 ] && exit "$status"
exit 1
