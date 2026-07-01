// Minimal SPA shell. EPIC-08 expands this with Chat, Citation, Retrieval Debug,
// Note Update, Indexing Status and DLQ views. For now: a live dashboard.

const API = ""; // same-origin; nginx proxies /api and /health to the backend

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

const ROUTES = [
  { id: "dashboard", label: "Dashboard", render: renderDashboard },
];

function renderNav() {
  const nav = document.getElementById("nav");
  const current = location.hash.replace("#", "") || ROUTES[0].id;
  nav.innerHTML = ROUTES.map(
    (r) => `<a href="#${r.id}" class="${r.id === current ? "active" : ""}">${r.label}</a>`
  ).join("");
}

async function renderDashboard(el) {
  el.innerHTML = `<p class="loading">불러오는 중…</p>`;
  try {
    const [health, vaults] = await Promise.all([
      api("/api/health/detailed"),
      api("/api/vaults"),
    ]);
    const c = health.components || {};
    const badge = (v) => `<span class="badge ${v === "up" ? "up" : "down"}">${v}</span>`;
    el.innerHTML = `
      <div class="grid">
        <div class="card">
          <h3>시스템 상태</h3>
          <div class="kv"><span class="k">Backend API</span>${badge(c.api)}</div>
          <div class="kv"><span class="k">Elasticsearch</span>${badge(c.elasticsearch)}</div>
          <div class="kv"><span class="k">Database</span>${badge(c.database)}</div>
          <div class="kv"><span class="k">AI Provider</span><span class="badge up">${health.aiProvider}</span></div>
        </div>
        <div class="card">
          <h3>등록된 Vault</h3>
          <div class="kv"><span class="k">개수</span><span>${vaults.vaults.length}</span></div>
          ${vaults.vaults
            .map((v) => `<div class="kv"><span class="k">${v.name}</span><span class="badge up">${v.status}</span></div>`)
            .join("")}
        </div>
      </div>
      <div class="card" style="margin-top:14px">
        <h3>Vault 상세</h3>
        <table>
          <thead><tr><th>vaultId</th><th>name</th><th>path</th><th>status</th></tr></thead>
          <tbody>
            ${vaults.vaults
              .map(
                (v) =>
                  `<tr><td class="mono">${v.vaultId}</td><td>${v.name}</td><td class="mono">${v.path}</td><td>${v.status}</td></tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="card"><h3>오류</h3><p class="muted">백엔드에 연결할 수 없습니다: ${e.message}</p></div>`;
  }
}

function route() {
  renderNav();
  const id = location.hash.replace("#", "") || ROUTES[0].id;
  const r = ROUTES.find((x) => x.id === id) || ROUTES[0];
  r.render(document.getElementById("app"));
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);
