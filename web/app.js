// Mock Web UI for the ElasticGPT RAG platform. Single-file SPA with hash routing.
// nginx proxies /api and /health to the backend, so everything is same-origin.

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) {}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.status === 204 ? null : res.json();
}
const post = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const badge = (v, cls) => `<span class="badge ${cls || (v === "up" ? "up" : "down")}">${esc(v)}</span>`;
const srcBadge = (t) => `<span class="badge ${t === "generated" ? "gen" : "orig"}">${t === "generated" ? "generated" : "original"}</span>`;

let VAULTS = [];

// ---------------- Dashboard (US-08-01) ----------------
async function renderDashboard(el) {
  el.innerHTML = `<p class="loading">불러오는 중…</p>`;
  const [health, vaults, metrics, status, pending, dlq, qlogs] = await Promise.all([
    api("/api/health/detailed").catch(() => ({ components: {} })),
    api("/api/vaults").catch(() => ({ vaults: [] })),
    api("/api/metrics").catch(() => ({})),
    api("/api/indexing/status?limit=8").catch(() => ({ events: [] })),
    api("/api/note-updates?status=PENDING").catch(() => ({ candidates: [] })),
    api("/api/dlq").catch(() => ({ events: [] })),
    api("/api/query-logs?limit=5").catch(() => ({ logs: [] })),
  ]);
  const c = health.components || {};
  el.innerHTML = `
    <div class="grid">
      <div class="card"><h3>시스템 상태</h3>
        <div class="kv"><span class="k">Backend API</span>${badge(c.api)}</div>
        <div class="kv"><span class="k">Elasticsearch</span>${badge(c.elasticsearch)}</div>
        <div class="kv"><span class="k">Database</span>${badge(c.database)}</div>
        <div class="kv"><span class="k">AI Provider</span>${badge(health.aiProvider, "up")}</div>
      </div>
      <div class="card"><h3>지표</h3>
        <div class="kv"><span class="k">등록 Vault</span><span>${vaults.vaults.length}</span></div>
        <div class="kv"><span class="k">질의 수</span><span>${metrics.queries?.count ?? 0}</span></div>
        <div class="kv"><span class="k">평균 latency</span><span>${metrics.queries?.avgLatencyMs ?? 0} ms</span></div>
        <div class="kv"><span class="k">토큰 사용</span><span>${metrics.queries?.totalTokens ?? 0}</span></div>
      </div>
      <div class="card"><h3>파이프라인</h3>
        ${Object.entries(metrics.pipeline || {}).map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span>${v}</span></div>`).join("") || '<p class="muted">데이터 없음</p>'}
      </div>
      <div class="card"><h3>대기/실패</h3>
        <div class="kv"><span class="k">Pending 후보</span><span class="badge ${pending.candidates.length ? "warn" : "up"}">${pending.candidates.length}</span></div>
        <div class="kv"><span class="k">DLQ (신규)</span><span class="badge ${metrics.dlqNew ? "down" : "up"}">${metrics.dlqNew ?? dlq.events.length}</span></div>
      </div>
    </div>
    <div class="card" style="margin-top:14px"><h3>등록된 Vault</h3>
      <table><thead><tr><th>vaultId</th><th>name</th><th>path</th><th>status</th></tr></thead><tbody>
      ${vaults.vaults.map((v) => `<tr><td class="mono">${esc(v.vaultId)}</td><td>${esc(v.name)}</td><td class="mono">${esc(v.path)}</td><td>${badge(v.status, "up")}</td></tr>`).join("")}
      </tbody></table>
    </div>
    <div class="card" style="margin-top:14px"><h3>최근 인덱싱 이벤트</h3>
      <table><thead><tr><th>stage</th><th>path</th><th>ts</th></tr></thead><tbody>
      ${(status.events || []).slice(0, 8).map((e) => `<tr><td>${badge(e.stage, e.ok === false ? "down" : "up")}</td><td class="mono">${esc(e.path)}</td><td class="muted">${esc((e.ts || "").slice(11, 19))}</td></tr>`).join("") || '<tr><td colspan="3" class="muted">없음</td></tr>'}
      </tbody></table>
    </div>
    <div class="card" style="margin-top:14px"><h3>최근 질의응답</h3>
      <table><thead><tr><th>질문</th><th>latency</th><th>tokens</th></tr></thead><tbody>
      ${(qlogs.logs || []).map((q) => `<tr><td>${esc((q.question || "").slice(0, 60))}</td><td>${q.latency_ms} ms</td><td>${(q.prompt_tokens || 0) + (q.completion_tokens || 0)}</td></tr>`).join("") || '<tr><td colspan="3" class="muted">없음</td></tr>'}
      </tbody></table>
    </div>`;
}

// ---------------- Chat + Citation Viewer (US-08-02/03) ----------------
async function renderChat(el) {
  if (!VAULTS.length) VAULTS = (await api("/api/vaults").catch(() => ({ vaults: [] }))).vaults;
  el.innerHTML = `
    <div class="card">
      <h3>RAG Chat</h3>
      <div class="row">
        <select id="vault">${VAULTS.map((v) => `<option value="${esc(v.vaultId)}">${esc(v.name)}</option>`).join("")}</select>
        <label class="inline">topK <input id="topk" type="number" value="6" min="1" max="20" style="width:70px"></label>
        <label class="inline"><input id="graph" type="checkbox"> Graph expansion</label>
      </div>
      <textarea id="q" rows="3" placeholder="Obsidian 노트 기반 질문을 입력하세요"></textarea>
      <div class="row"><button id="ask">질문하기</button></div>
    </div>
    <div id="answer"></div>`;
  el.querySelector("#ask").onclick = async () => {
    const out = el.querySelector("#answer");
    const message = el.querySelector("#q").value.trim();
    if (!message) return;
    out.innerHTML = `<div class="card loading">답변 생성 중…</div>`;
    try {
      const r = await post("/api/rag/chat", {
        message,
        vaultId: el.querySelector("#vault").value,
        searchOptions: { topK: Number(el.querySelector("#topk").value), graphExpansion: el.querySelector("#graph").checked },
      });
      out.innerHTML = `
        <div class="card"><h3>답변 ${r.insufficientContext ? '<span class="badge warn">근거 부족</span>' : ""}</h3>
          <p>${esc(r.answer).replace(/\n/g, "<br>")}</p>
          <p class="muted mono">mode=${esc(r.retrieval.mode)} · topK=${r.retrieval.topK} · candidates=${r.retrieval.candidateCount} · ${r.usage.model} · ${r.latencyMs}ms · tokens ${r.usage.promptTokens}+${r.usage.completionTokens}</p>
        </div>
        <div class="card"><h3>Citations (${r.citations.length})</h3>
          ${r.citations.map((c, i) => `
            <div class="cite" data-chunk="${esc(c.chunkId)}">
              <div class="cite-head"><b>[${i + 1}] ${esc(c.noteTitle)}</b> ${srcBadge(c.sourceType)} <span class="muted">score ${c.score}</span></div>
              <div class="muted mono">${esc(c.path)} › ${esc(c.headingPath)}</div>
              <div class="cite-body muted" style="display:none"></div>
            </div>`).join("")}
        </div>`;
      out.querySelectorAll(".cite").forEach((node) => {
        node.querySelector(".cite-head").onclick = async () => {
          const body = node.querySelector(".cite-body");
          if (body.style.display === "none") {
            if (!body.dataset.loaded) {
              try {
                const chunk = await api(`/api/retrieval/chunk?chunkId=${encodeURIComponent(node.dataset.chunk)}`);
                body.innerHTML = `<pre>${esc(chunk.content)}</pre>`;
              } catch (e) { body.innerHTML = `<span class="muted">미리보기를 불러올 수 없습니다</span>`; }
              body.dataset.loaded = "1";
            }
            body.style.display = "block";
          } else body.style.display = "none";
        };
      });
    } catch (e) {
      out.innerHTML = `<div class="card"><h3>오류</h3><p class="muted">${esc(e.message)}</p></div>`;
    }
  };
}

// ---------------- Retrieval Debug (US-08-04) ----------------
async function renderRetrieval(el) {
  el.innerHTML = `
    <div class="card"><h3>Retrieval Debug</h3>
      <div class="row"><input id="q" placeholder="검색어" style="flex:1">
        <label class="inline"><input id="graph" type="checkbox"> Graph</label>
        <button id="run">검색</button></div>
    </div><div id="out"></div>`;
  el.querySelector("#run").onclick = async () => {
    const out = el.querySelector("#out");
    out.innerHTML = `<div class="card loading">검색 중…</div>`;
    try {
      const r = await post("/api/retrieval/debug", { query: el.querySelector("#q").value, topK: 8, graphExpansion: el.querySelector("#graph").checked });
      out.innerHTML = `
        <div class="card"><h3>결과 (mode=${esc(r.mode)}, 후보 ${r.candidateCount})</h3>
        <p class="muted">filter: vault_id, deleted=false · context에 포함된 chunk는 초록색</p>
        <table><thead><tr><th>note</th><th>heading</th><th>BM25</th><th>vector</th><th>score</th><th>graph</th><th>context</th></tr></thead><tbody>
        ${r.results.map((x) => `<tr class="${x.inContext ? "in-ctx" : ""}">
          <td>${esc(x.note_title)} ${srcBadge(x.source_type)}</td>
          <td class="muted">${esc(x.heading_path)}</td>
          <td>${x.bm25_score == null ? "-" : x.bm25_score.toFixed(2)}</td>
          <td>${x.vector_score == null ? "-" : x.vector_score.toFixed(3)}</td>
          <td>${x.score}</td>
          <td>${x.fromGraph ? badge(x.graphRelation || "graph", "warn") : "-"}</td>
          <td>${x.inContext ? "✓" : ""}</td></tr>`).join("")}
        </tbody></table></div>`;
    } catch (e) { out.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`; }
  };
}

// ---------------- Note Update Candidates (US-08-05) ----------------
async function renderNoteUpdates(el) {
  el.innerHTML = `<p class="loading">불러오는 중…</p>`;
  const { candidates } = await api("/api/note-updates?status=PENDING").catch(() => ({ candidates: [] }));
  el.innerHTML = `<h3 class="page-h">Note Update Candidates (PENDING: ${candidates.length})</h3>` +
    (candidates.length ? candidates.map((c) => `
      <div class="card cand" data-id="${esc(c.candidateId)}">
        <div class="row"><span class="badge ${c.candidateType === "NEW" ? "up" : "warn"}">${c.candidateType}</span>
          <span class="badge ${c.origin === "correction" ? "down" : "orig"}">${c.origin}</span>
          <span class="mono">${esc(c.targetNotePath)}</span></div>
        <p class="muted">${esc(c.summary)}</p>
        <pre>${esc(c.markdownPatch)}</pre>
        <div class="muted">citations: ${(c.citations || []).map((x) => esc(x.noteTitle)).join(", ") || "-"}</div>
        <div class="row"><button class="approve">승인</button><button class="secondary reject">거절</button><span class="result muted"></span></div>
      </div>`).join("") : '<div class="card muted">대기 중인 후보가 없습니다. Chat에서 질문하면 생성됩니다.</div>');
  el.querySelectorAll(".cand").forEach((node) => {
    const id = node.dataset.id;
    const done = (msg) => { node.querySelector(".result").textContent = msg; node.querySelectorAll("button").forEach((b) => (b.disabled = true)); };
    node.querySelector(".approve").onclick = async () => { try { await post(`/api/note-updates/${id}/approve`); done("승인됨 → 파일 반영/재색인"); } catch (e) { done(e.message); } };
    node.querySelector(".reject").onclick = async () => { try { await post(`/api/note-updates/${id}/reject`); done("거절됨"); } catch (e) { done(e.message); } };
  });
}

// ---------------- Indexing Status (US-08-06) ----------------
async function renderIndexing(el) {
  el.innerHTML = `<p class="loading">불러오는 중…</p>`;
  const [status, vaults] = await Promise.all([
    api("/api/indexing/status?limit=40").catch(() => ({ events: [], reindexJobs: [] })),
    api("/api/vaults").catch(() => ({ vaults: [] })),
  ]);
  const vid = vaults.vaults[0]?.vaultId || "";
  el.innerHTML = `
    <div class="card"><h3>Reindex</h3>
      <div class="row"><span class="mono">${esc(vid)}</span><button id="reindex">전체 재색인</button><span id="rres" class="muted"></span></div></div>
    <div class="card"><h3>Reindex Jobs</h3>
      <table><thead><tr><th>job</th><th>status</th><th>notes</th><th>생성</th></tr></thead><tbody>
      ${(status.reindexJobs || []).map((j) => `<tr><td class="mono">${esc(j.jobId.slice(0, 14))}</td><td>${badge(j.status, j.status === "COMPLETED" ? "up" : j.status === "FAILED" ? "down" : "warn")}</td><td>${j.noteCount}</td><td class="muted">${esc((j.createdAt || "").slice(11, 19))}</td></tr>`).join("") || '<tr><td colspan="4" class="muted">없음</td></tr>'}
      </tbody></table></div>
    <div class="card"><h3>파이프라인 이벤트 (최근)</h3>
      <table><thead><tr><th>stage</th><th>path</th><th>info</th><th>ts</th></tr></thead><tbody>
      ${(status.events || []).map((e) => `<tr><td>${badge(e.stage, e.ok === false ? "down" : "up")}</td><td class="mono">${esc(e.path)}</td><td class="muted">${esc(e.chunkCount != null ? "chunks=" + e.chunkCount : e.error || "")}</td><td class="muted">${esc((e.ts || "").slice(11, 19))}</td></tr>`).join("") || '<tr><td colspan="4" class="muted">없음</td></tr>'}
      </tbody></table></div>`;
  el.querySelector("#reindex").onclick = async () => {
    const r = el.querySelector("#rres");
    r.textContent = "요청 중…";
    try { const res = await post("/api/reindex", { vaultId: vid, reason: "UI trigger" }); r.textContent = `job ${res.job.jobId.slice(0, 14)} 시작됨`; setTimeout(() => route(), 2000); }
    catch (e) { r.textContent = e.message; }
  };
}

// ---------------- DLQ Viewer (US-08-07) ----------------
async function renderDlq(el) {
  el.innerHTML = `<p class="loading">불러오는 중…</p>`;
  const { events } = await api("/api/dlq").catch(() => ({ events: [] }));
  el.innerHTML = `<h3 class="page-h">DLQ Viewer (${events.length})</h3>` +
    (events.length ? events.map((e) => `
      <div class="card dlq" data-id="${esc(e.dlqId)}">
        <div class="row"><span class="badge down">${esc(e.errorType)}</span><span class="mono">${esc(e.sourceTopic)}</span>
          <span class="muted">consumer=${esc(e.consumerGroup)} · retries=${e.retryCount} · ${badge(e.status, e.status === "REPROCESSED" ? "up" : "warn")}</span></div>
        <p class="muted">${esc(e.errorMessage)}</p>
        <pre>${esc(JSON.stringify(e.payload, null, 2).slice(0, 600))}</pre>
        <div class="row"><button class="reproc" ${e.status === "REPROCESSED" ? "disabled" : ""}>재처리</button><span class="result muted"></span></div>
      </div>`).join("") : '<div class="card muted">DLQ 이벤트가 없습니다.</div>');
  el.querySelectorAll(".dlq").forEach((node) => {
    node.querySelector(".reproc").onclick = async () => {
      try { await post(`/api/dlq/${node.dataset.id}/reprocess`); node.querySelector(".result").textContent = "원본 topic으로 재발행됨"; node.querySelector(".reproc").disabled = true; }
      catch (e) { node.querySelector(".result").textContent = e.message; }
    };
  });
}

// ---------------- Router ----------------
const ROUTES = [
  { id: "dashboard", label: "Dashboard", render: renderDashboard },
  { id: "chat", label: "RAG Chat", render: renderChat },
  { id: "retrieval", label: "Retrieval Debug", render: renderRetrieval },
  { id: "note-updates", label: "Note Updates", render: renderNoteUpdates },
  { id: "indexing", label: "Indexing", render: renderIndexing },
  { id: "dlq", label: "DLQ", render: renderDlq },
];

function renderNav() {
  const cur = location.hash.replace("#", "") || ROUTES[0].id;
  document.getElementById("nav").innerHTML = ROUTES.map(
    (r) => `<a href="#${r.id}" class="${r.id === cur ? "active" : ""}">${r.label}</a>`
  ).join("");
}
function route() {
  renderNav();
  const id = location.hash.replace("#", "") || ROUTES[0].id;
  const r = ROUTES.find((x) => x.id === id) || ROUTES[0];
  const el = document.getElementById("app");
  el.innerHTML = "";
  Promise.resolve(r.render(el)).catch((e) => (el.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`));
}
window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);
