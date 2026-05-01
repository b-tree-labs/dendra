// Paste-your-code Pyodide analyzer.
//
// Loads Pyodide on first interaction (lazy — keeps landing fast for
// the 90% who don't use this), fetches the bundled
// landing/wasm/dendra_analyzer.py, then runs `analyze(temp_path)` on
// whatever the visitor pasted into the textarea. Pasted code stays
// in the browser — Pyodide runs in WASM, the only thing that hits
// the wire is the result table on explicit "email me / send to
// teammate" actions (handled separately by leads-capture.js).
//
// Contract:
//   [data-paste-textarea] — the source code input
//   [data-paste-run]      — the analyze button
//   [data-paste-status]   — loader / error region
//   [data-paste-results]  — render target (table + summary)
//   [data-paste-share]    — share CTA region (revealed after analysis)

(function () {
  "use strict";

  const PYODIDE_VERSION = "0.26.4";
  const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
  const ANALYZER_BUNDLE_URL = "/wasm/dendra_analyzer.py";

  let pyodideReady = null; // Promise<pyodide>; cached after first load.
  let pyodide = null;

  const root = document.querySelector("[data-paste-root]");
  if (!root) return;

  const textarea = root.querySelector("[data-paste-textarea]");
  const runBtn = root.querySelector("[data-paste-run]");
  const statusEl = root.querySelector("[data-paste-status]");
  const resultsEl = root.querySelector("[data-paste-results]");
  const shareEl = root.querySelector("[data-paste-share]");

  if (!textarea || !runBtn || !resultsEl) return;

  function setStatus(msg, kind) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.dataset.kind = kind || "";
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c]);
  }

  // ----- Lazy Pyodide bootstrap --------------------------------------------
  // First click starts the load (~5–10 s on cold cache, instant on warm).
  // Returning the same promise on subsequent clicks de-dupes concurrent
  // initializations.
  async function ensurePyodide() {
    if (pyodide) return pyodide;
    if (pyodideReady) return pyodideReady;
    pyodideReady = (async () => {
      setStatus("Loading Pyodide (~5 s, runs locally in your browser)…", "loading");
      // Inject the loader script if not already present.
      if (!window.loadPyodide) {
        await new Promise((resolve, reject) => {
          const s = document.createElement("script");
          s.src = `${PYODIDE_CDN}pyodide.js`;
          s.onload = resolve;
          s.onerror = () => reject(new Error("Pyodide CDN unreachable"));
          document.head.appendChild(s);
        });
      }
      pyodide = await window.loadPyodide({ indexURL: PYODIDE_CDN });
      setStatus("Loading analyzer bundle…", "loading");
      const resp = await fetch(ANALYZER_BUNDLE_URL);
      if (!resp.ok) {
        throw new Error(`analyzer bundle fetch failed: ${resp.status}`);
      }
      const src = await resp.text();
      // Define the module in Pyodide's globals; analyze() becomes a
      // top-level callable. Using runPython (sync) is fine here — the
      // bundle is ~57 KB and parses in well under a frame.
      pyodide.runPython(src);
      setStatus("Ready. Paste Python and click Analyze.", "ready");
      return pyodide;
    })().catch((err) => {
      pyodideReady = null;
      throw err;
    });
    return pyodideReady;
  }

  // ----- Run analyze on the pasted source ----------------------------------
  async function runAnalyze() {
    const source = (textarea.value || "").trim();
    if (!source) {
      setStatus("Paste some Python first.", "error");
      return;
    }
    if (source.length > 200_000) {
      setStatus(
        "Snippet over 200 KB — paste a smaller chunk or run `dendra analyze .` locally on the full repo.",
        "error",
      );
      return;
    }

    runBtn.disabled = true;
    try {
      const py = await ensurePyodide();
      setStatus("Analyzing…", "loading");

      // Write the pasted source to MEMFS, then call analyze() on it.
      // We escape backticks and dollar signs since we're embedding the
      // source in a Python string literal via JSON.
      py.globals.set("_paste_source", source);
      py.runPython(`
import os, tempfile, json
_paste_path = tempfile.NamedTemporaryFile(
    suffix=".py", delete=False, mode="w", encoding="utf-8",
).name
with open(_paste_path, "w", encoding="utf-8") as _f:
    _f.write(_paste_source)
_paste_report = analyze(_paste_path)
_paste_json = render_json(_paste_report)
os.unlink(_paste_path)
      `);
      const reportJson = py.globals.get("_paste_json");
      const data = JSON.parse(reportJson);
      renderResults(data, source);
      setStatus(
        data.total_sites > 0
          ? `Found ${data.total_sites} classification site${data.total_sites === 1 ? "" : "s"}.`
          : "No classification sites detected. Try pasting a function with if/elif string returns.",
        data.total_sites > 0 ? "success" : "ready",
      );
      if (shareEl && data.total_sites > 0) {
        shareEl.hidden = false;
        shareEl.dataset.siteCount = String(data.total_sites);
        const top = (data.sites || [])[0];
        if (top) shareEl.dataset.topPriority = String(top.priority_score);
      }
    } catch (err) {
      console.error("[paste-analyzer]", err);
      setStatus(`Error: ${err.message || err}`, "error");
    } finally {
      runBtn.disabled = false;
    }
  }

  // ----- Result rendering --------------------------------------------------
  function renderResults(data, sourceText) {
    if (!data || !data.sites) {
      resultsEl.innerHTML = "";
      return;
    }
    if (data.sites.length === 0) {
      resultsEl.innerHTML = `
        <p class="paste-empty caption">
          No classification sites detected in the snippet. The analyzer
          looks for if/elif chains, match/case dispatchers, dict-routed
          handlers, keyword scanners, regex dispatchers, and LLM-prompted
          classifiers. Try pasting a function whose body returns one of
          a fixed set of string labels.
        </p>`;
      return;
    }

    const sites = data.sites;
    const sourceLines = sourceText.split("\n");

    const rows = sites
      .map((s) => {
        const lineRange = `L${s.line_start}–${s.line_end}`;
        const snippet = sourceLines
          .slice(Math.max(0, s.line_start - 1), s.line_end)
          .join("\n");
        return `
          <tr class="paste-row">
            <td class="mono">${escapeHtml(s.function_name)}<br /><small class="dim">${lineRange}</small></td>
            <td>${escapeHtml(s.pattern)}</td>
            <td>${s.label_cardinality}</td>
            <td>${escapeHtml(s.regime)}</td>
            <td>${escapeHtml(s.volume_estimate)}</td>
            <td class="num">${(s.priority_score || 0).toFixed(2)}</td>
            <td>${escapeHtml(s.lift_status.replace(/_/g, " "))}</td>
          </tr>
          <tr class="paste-snippet-row">
            <td colspan="7"><pre class="paste-snippet">${escapeHtml(snippet)}</pre></td>
          </tr>`;
      })
      .join("");

    resultsEl.innerHTML = `
      <table class="paste-results-table">
        <thead>
          <tr>
            <th>Function</th>
            <th>Pattern</th>
            <th>Labels</th>
            <th>Regime</th>
            <th>Volume</th>
            <th>Priority</th>
            <th>Lift</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  // ----- Wire UI -----------------------------------------------------------
  runBtn.addEventListener("click", runAnalyze);
  // Allow Cmd/Ctrl+Enter from inside the textarea to run.
  textarea.addEventListener("keydown", (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
      ev.preventDefault();
      runAnalyze();
    }
  });
})();
