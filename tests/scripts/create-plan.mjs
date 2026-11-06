import { login, switchProject } from './ms-client.mjs';

const baseUrl = (process.env.MS_BASE_URL || 'http://127.0.0.1:8081').replace(/\/$/, '');
const projectId = process.env.MS_PROJECT_ID;
if (!projectId) throw new Error('MS_PROJECT_ID is required');

const session = await login({ baseUrl });
await switchProject({
  baseUrl, projectId,
  userId: session.userId,
  sessionId: session.sessionId,
  csrfToken: session.csrfToken,
});

const payload = {
  projectId,
  groupId: 'NONE',
  name: process.env.MS_PLAN_NAME || 'MediaCMS 版本回归',
  moduleId: 'root',
  description: 'MediaCMS Web / 播放器 / H5 / API 版本回归计划',
  automaticStatusUpdate: true,
  repeatCase: false,
  passThreshold: 100,
  type: 'TEST_PLAN',
};

const res = await fetch(`${baseUrl}/test-plan/add`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-AUTH-TOKEN': session.sessionId,
    'CSRF-TOKEN': session.csrfToken,
    PROJECT: projectId,
  },
  body: JSON.stringify(payload),
});
const text = await res.text();
console.log(`HTTP ${res.status}`);
console.log(text.slice(0, 800));
if (!res.ok) process.exit(1);
