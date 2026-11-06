const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `HTTP ${res.status}`);
  return data;
}
function toast(msg) {
  let el = $('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2600);
}
function fmtTime(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString('zh-CN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
}
function badge(status) { return `<span class="badge ${esc(status)}">${esc(status)}</span>`; }
function totalOf(r) { return (r.passed||0)+(r.failed||0)+(r.skipped||0)+(r.xfailed||0); }
// 有效用例 = passed + failed；xfail 是已知站点现状，单独展示，不计入通过率分母
function effectiveOf(r) { return (r.passed||0)+(r.failed||0); }
function rateOf(r) {
  if (r && typeof r.rate === 'number') return r.rate;
  const t = effectiveOf(r);
  return t ? Math.round((r.passed||0)/t*100) : (r.status === 'passed' ? 100 : 0);
}
function chips(c) {
  const tags = (c.tags||[]).map(t => `<span class="chip tag">${esc(t)}</span>`).join('');
  return `<span class="chip ${esc((c.priority||'P2').toLowerCase())}">${esc(c.priority||'P2')}</span>${tags}`;
}

async function getCases(refresh = false) {
  const data = await api('/api/cases' + (refresh ? '?refresh=true' : ''));
  return data.cases || [];
}
async function getHistory() { return await api('/api/history'); }
async function getDefects() { return await api('/api/defects'); }
async function getMeta() { return await api('/api/meta'); }
async function getStatus() { return await api('/api/status'); }
async function runCases(ids, opts = {}) {
  const body = {ids, headed: !!opts.headed, slowmo: Number(opts.slowmo || (opts.headed ? 300 : 0))};
  if (opts.tags && opts.tags.length) body.tags = opts.tags;
  return await api('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
}
async function cancelRun() { return await api('/api/cancel', {method:'POST'}); }

async function pollStatus(cb, interval = 1000) {
  let stopped = false;
  const tick = async () => {
    try {
      const s = await getStatus();
      cb(s);
      if (s.status !== 'running' && !stopped) { stopped = true; clearInterval(timer); return; }
    } catch (e) { /* ignore */ }
  };
  const timer = setInterval(tick, interval);
  await tick();
  return () => { stopped = true; clearInterval(timer); };
}

function renderCoverage(cases, el) {
  if (!el) return;
  const map = {};
  cases.forEach(c => { const a = c.area || '其他'; map[a] = (map[a]||0)+1; });
  const entries = Object.entries(map).sort((a,b) => b[1]-a[1]);
  const max = Math.max(1, ...entries.map(e => e[1]));
  el.innerHTML = entries.map(([a,n]) => `<div class="coverage-row"><span>${esc(a)}</span><div class="coverage-bar"><i style="width:${n/max*100}%"></i></div><b>${n}</b></div>`).join('') || '<div class="empty">暂无</div>';
}

function renderRuns(rows, tbody) {
  if (!tbody) return;
  tbody.innerHTML = rows.map(r => `<tr>
    <td class="mono">${fmtTime(r.started)}</td>
    <td>${badge(r.status)}</td>
    <td>${r.count}${r.xfailed ? `<span class="hint">（${r.xfailed} xfail）</span>` : ''}</td>
    <td>${r.duration ?? '-'}s</td>
    <td>${r.report ? `<a href="${r.report}" target="_blank">HTML</a>` : '-'}</td>
    <td>${r.allure ? `<a href="${r.allure}" target="_blank">Allure</a>` : '-'}</td>
  </tr>`).join('') || '<tr><td colspan="6" class="empty">暂无运行记录</td></tr>';
}

function selectedIds() {
  return [...document.querySelectorAll('.case input:checked')].map(i => i.value);
}
