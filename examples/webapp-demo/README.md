# webapp-demo

Zero-dependency HTTP server used to demo the Phase 3 layers:

```powershell
# unit layer
node --test tests/

# system layer (boots server.js, polls /health, smoke-checks endpoints)
uv run testing-agent run --path examples/webapp-demo --type system

# performance layer (set a target_url in .testing-agent.json first)
uv run testing-agent run --path examples/webapp-demo --type performance
```

Routes: `/`, `/health`, `/api/health`, `/api/slow` (100 ms), anything else 404.
Port: `8901` (override with `PORT`).

## Compatibility layer (optional)

`playwright.config.js` + `tests/e2e/` demo the browser-matrix layer. To run it
for real (not required for the system/performance demos):

```powershell
npm i -D @playwright/test
npx playwright install chromium
uv run testing-agent run --path examples/webapp-demo --type compatibility
```

Without the install, the compatibility runner reports an honest failure note
instead of a false pass.
