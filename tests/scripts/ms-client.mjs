import crypto from 'node:crypto';

const DEFAULT_BASE = 'http://127.0.0.1:8081';

function encrypt(publicKeyBase64, value) {
  const key = crypto.createPublicKey({
    key: Buffer.from(publicKeyBase64, 'base64'),
    format: 'der',
    type: 'spki',
  });
  return crypto.publicEncrypt(
    { key, padding: crypto.constants.RSA_PKCS1_PADDING },
    Buffer.from(value),
  ).toString('base64');
}

export async function login(options = {}) {
  const baseUrl = (options.baseUrl || process.env.MS_BASE_URL || DEFAULT_BASE).replace(/\/$/, '');
  const username = options.username || process.env.MS_USERNAME;
  const password = options.password || process.env.MS_PASSWORD;
  if (!username || !password) throw new Error('MS_USERNAME / MS_PASSWORD is required');

  const keyRes = await fetch(`${baseUrl}/get-key`);
  const keyBody = await keyRes.json();
  if (!keyRes.ok || keyBody.code !== 100200) throw new Error(`get-key failed: ${keyRes.status}`);

  const res = await fetch(`${baseUrl}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: encrypt(keyBody.data, username),
      password: encrypt(keyBody.data, password),
      authenticate: 'LOCAL',
    }),
  });
  const body = await res.json();
  if (!res.ok || body.code !== 100200) {
    throw new Error(`login failed: HTTP ${res.status} ${body.message || ''}`);
  }
  return {
    baseUrl,
    userId: body.data.id,
    sessionId: body.data.sessionId,
    csrfToken: body.data.csrfToken,
    lastProjectId: body.data.lastProjectId,
    lastOrganizationId: body.data.lastOrganizationId,
  };
}

export async function switchProject({ baseUrl, projectId, userId, sessionId, csrfToken }) {
  if (!projectId) return;
  const res = await fetch(`${baseUrl}/project/switch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-AUTH-TOKEN': sessionId,
      'CSRF-TOKEN': csrfToken,
    },
    body: JSON.stringify({ projectId, userId }),
  });
  const body = await res.json();
  if (!res.ok || body.code !== 100200) {
    throw new Error(`switch project failed: HTTP ${res.status} ${body.message || ''}`);
  }
}

export async function runScenario({ baseUrl, projectId, scenarioId, sessionId, csrfToken, reportId }) {
  const rid = reportId || crypto.randomUUID().replace(/-/g, '');
  const res = await fetch(`${baseUrl}/api/scenario/run/${scenarioId}?reportId=${rid}`, {
    headers: {
      'X-AUTH-TOKEN': sessionId,
      'CSRF-TOKEN': csrfToken,
      PROJECT: projectId,
    },
  });
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = null; }
  if (!res.ok || !body || body.code !== 100200) {
    throw new Error(`run scenario failed: HTTP ${res.status} ${body?.message || text.slice(0, 200)}`);
  }
  return { reportId: rid, body };
}
