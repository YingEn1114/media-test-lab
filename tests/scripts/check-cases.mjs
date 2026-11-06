import { login, switchProject } from './ms-client.mjs';
const base = (process.env.MS_BASE_URL || 'http://127.0.0.1:8081').replace(/\/$/, '');
const projectId = process.env.MS_PROJECT_ID || '1721461186165219328';
const s = await login({ baseUrl: base });
await switchProject({ baseUrl: base, projectId, userId: s.userId, sessionId: s.sessionId, csrfToken: s.csrfToken });
const h = { 'Content-Type': 'application/json', 'X-AUTH-TOKEN': s.sessionId, 'CSRF-TOKEN': s.csrfToken, PROJECT: projectId };
for (const [name, url, body] of [
  ['cases', '/api/case/page', { projectId, protocols: ['HTTP'], moduleIds: ['root'], current: 1, pageSize: 10 }],
  ['scenarios', '/api/scenario/page', { projectId, protocols: ['HTTP'], moduleIds: ['root'], current: 1, pageSize: 10 }],
  ['definitions', '/api/definition/page', { projectId, current: 1, pageSize: 5 }],
]) {
  const r = await fetch(base + url, { method: 'POST', headers: h, body: JSON.stringify(body) });
  const j = await r.json();
  const d = j.data || {};
  console.log(name, 'HTTP', r.status, 'total', d.total, 'names', (d.list || []).map(x => x.name).slice(0, 5));
}
