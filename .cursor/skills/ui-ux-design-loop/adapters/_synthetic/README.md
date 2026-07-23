# Synthetic non-VMC adapter fixture

This adapter exists only to prove the manifest contract is portable and not tied to `apps/vmc-web`.

- `ui-loop.config.json` uses `appDir: "web"` and only synthetic paths.
- `web/e2e/helpers/ui-loop/demo.routes.ts` is a minimal route module fixture.
- `web/e2e/helpers/ui-loop/demo.mocks.ts` demonstrates deterministic mock wiring.
- `scripts/token-check-stub.mjs` is a stub token-check command for manifest portability tests.
