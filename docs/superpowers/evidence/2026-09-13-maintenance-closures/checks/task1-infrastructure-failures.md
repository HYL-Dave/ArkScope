# Task 1 Infrastructure Failures

These failures are not the assertion RED or a passing gate. No product CSS had
been edited. Each command ran from `/tmp/arkscope-research-output-boundary`.

## Test Loading

- `run_checks.py task1-red frontend test -- src/retiredPageHeader.test.tsx`
  exited 1: three failed nonempty stylesheet guards because CSS `?raw` imports
  were empty in this Vitest configuration. Direct jsdom parsing of the file
  produced 870 top-level CSS rules. Full receipt: `task1-red/`.
- `run_checks.py task1-assertion-red frontend test -- src/retiredPageHeader.test.tsx`
  exited 1 before collecting tests: `TypeError: The URL must be of scheme file`
  at `readFileSync(new URL("./styles.css", import.meta.url), "utf8")`.
  Corrected to the existing cwd/resolve source-reading pattern.
  Full receipt: `task1-assertion-red/`.
- Actual assertion RED is separately preserved in `task1-assertion-red-2/`:
  two selector-absence failures and one passing real-primitive positive control.

## Initial CSS Audit

Command: `/home/hyl/.nvm/versions/node/v22.14.0/bin/node --require ./.superpowers/sdd/2026-09-13-maintenance-closures/offline_node.cjs .superpowers/sdd/2026-09-13-maintenance-closures/task1_css_audit.cjs before`

Exit: 1. Assertion at `task1_css_audit.cjs:20:8`:

```text
AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
+ actual - expected
+ 'de506754b0b91d9e16281979c5dca9af2fdfc453'
- '5526bc40dc8d62efa6dd819cf1ffc99d8acff7ce'
Node.js v22.14.0
```

Controller confirmed a concurrent docs-only C11 clarification commit. Audit
now verifies base ancestry, preserves both base and HEAD identity, and still
requires every tracked frontend file other than the target CSS to equal base.

## Initial Fixture Server

Command: `env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp/arkscope-research-output-boundary/.superpowers/sdd/2026-09-13-maintenance-closures/task1-server-home CI=1 TZ=Asia/Taipei /home/hyl/.nvm/versions/node/v22.14.0/bin/node .superpowers/sdd/2026-09-13-maintenance-closures/task1_fixture_server.mjs`

Exit: 1, before any listen:

```text
The CJS build of Vite's Node API is deprecated.
task1_fixture_server.mjs:20
const server = await createServer({
                     ^
TypeError: createServer is not a function
Node.js v22.14.0
```

`require.resolve('vite')` selected its CJS entry; corrected to ESM `import('vite')`.
No dependency, product Vite configuration, or live App change was made.

## Loopback Bind Guard

The same isolated server command then exited 1 before listening:

```text
Error: Fixture server cannot initiate network connections
    at Object.reject (task1_fixture_server.mjs:11:30)
    at lookupAndListen (node:net:2193:7)
    at Server.listen (node:net:2095:7)
    at httpServer.listen (vite/dist/node/chunks/dep-BK3b2jBa.js:63419:14)
Node.js v22.14.0
```

Node calls `dns.lookup` while binding even a numeric IPv4 loopback address.
The fixture-only guard now permits the numeric `127.0.0.1` lookup; outbound
TCP connects, other DNS lookups/resolutions and UDP sends remain blocked.
