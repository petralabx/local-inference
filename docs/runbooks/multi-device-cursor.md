# Multi-device Cursor workflow (laptop ↔ desktop)

Canonical guidance lives in `.cursor/rules/multi-device-cursor.mdc` and the
“Multi-device” section of `AGENTS.md`.

## Worker host vs compute fabric

- **Cursor worker host:** Dell-VTA. Remote agents edit this checkout here.
- **Compute fabric:** Dell LiteLLM proxy, the two DGX Sparks, and the AWS
  primitives already in the operator mesh (Mission Control, secrets, EC2,
  and related). See `docs/runbooks/dgx-spark-fleet.md` and
  `docs/runbooks/local-agent-governed-workflow.md`.

Sitting at Dell is zero-friction. Open Cursor and work. Do not start My
Machines for a session that is already on this machine.

## Quick operator checklist

1. On Dell, work locally when you are at the desk.
2. For laptop / web / phone: keep a long-lived My Machines worker on Dell.
3. From the other device, start a Cloud Agent or use Remote Control against
   that worker. Authorize the run. Tool calls execute on Dell, then use the
   fabric above.
4. For pure interactive coding on the other machine, Remote SSH into Dell
   when you want one checkout.
5. Always push branches. Keep durable context in-repo (`AGENTS.md`, rules,
   runbooks, `.orchestrator/` evidence).
6. Chat history will not appear on the other machine. Rehydrate from the
   files above. Use a Chat Transfer extension only when you must move one
   specific long conversation.

## My Machines quickstart (Dell worker)

Run this on Dell-VTA, from the repo checkout, when you want remote devices
to drive this machine:

```bash
# once per machine
agent --version || curl https://cursor.com/install -fsS | bash

agent login
agent worker start --name dell-vta
```

Keep that process running. Then on laptop, web, or phone:

1. Open [cursor.com/agents](https://cursor.com/agents).
2. Pick `dell-vta` under My Machines / Remote Control.
3. Send the task and authorize it.

Debug a missing machine with `agent worker start --debug` from the same
checkout. Both devices must use the same Cursor account. The worker
registers the git remote of the directory where you started it.

Official reference:
[My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines).

## Related

- `docs/runbooks/cursor-orchestrator-worker.md`
- `docs/runbooks/local-agent-governed-workflow.md`
- `docs/runbooks/dgx-spark-fleet.md`
- `.cursor/environment.json` + Cloud Agents dashboard environments
