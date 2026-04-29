# Dendra for VS Code

Inline diagnostics for [Dendra](https://github.com/b-tree-labs/dendra) analyzer hazards, plus a one-click "auto-lift here" quick fix.

This extension shells out to your local `dendra` CLI (`dendra analyze --json <file>`) on every Python file open or save, parses the resulting `AnalyzerReport`, and surfaces each non-auto-liftable site as a VS Code Diagnostic.

## Install

1. Install the [`dendra`](https://pypi.org/project/dendra/) Python package (or build from source).
2. Install this extension from a `.vsix`:
   ```
   code --install-extension dendra-1.1.0.vsix
   ```
3. Open any Python file. Hazards from the analyzer appear as squigglies.

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `dendra.binaryPath` | `dendra` | Path to the `dendra` CLI. Useful when the binary isn't on `PATH`. |
| `dendra.enable` | `true` | Toggle the extension off without uninstalling. |

## Commands

| Command | What it does |
|---|---|
| `Dendra: Re-scan workspace` | Re-runs the analyzer on every open Python doc. |
| `Dendra: run auto-lift here` | (Quick Fix) Spawns `dendra init <file>:<func> --author @you:team --auto-lift` in a terminal, then re-scans. |

## How severity maps

| Hazard severity | VS Code severity |
|---|---|
| `error` (refused) | Error (red) |
| `warn` (needs annotation) | Warning (yellow) |
| (auto-liftable) | (no diagnostic) |

## Screenshots

_Placeholders, drop screenshots in `docs/`:_

- `docs/screenshot-squiggly.png` — hazard squigglies on a refused function.
- `docs/screenshot-quickfix.png` — quick-fix menu.
- `docs/screenshot-terminal.png` — terminal running `dendra init --auto-lift`.

## Manual validation steps

These are the manual checks Ben runs before each release. Headless tests cover the wiring; these confirm the user-visible UX.

1. Install the .vsix locally: `code --install-extension dendra-*.vsix`.
2. Open `examples/24_when_auto_lift_refuses.py`. Confirm squigglies appear on `test_cors`, `route`, `evaluate`, `maybe_charge`, and `route_request`.
3. Hover one of the squigglies. Confirm tooltip text matches the hazard's `reason` and `suggested_fix`.
4. Right-click one of the squigglies. Confirm "Dendra: run auto-lift here" appears in the Quick Fix menu.
5. Click it. Confirm a new terminal spawns running `dendra init ... --auto-lift`, AND the squigglies update after the run.
6. Open the command palette. Confirm "Dendra: Re-scan workspace" is listed.
7. Verify zero diagnostics on a clean file like `examples/01_hello_world.py`.

## Why no LSP?

Dendra's analyzer is fast and stateless per file; the v1.1 contract is "open a Python file, get squigglies." Direct `child_process` invocations cover that contract, keep the extension under 200 KB, and keep the test surface to a single Mocha runner. We'll revisit LSP if and when we want incremental analysis or workspace-wide indexing.

## License

Apache-2.0.
