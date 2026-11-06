import { login, switchProject, runScenario } from './ms-client.mjs';

const baseUrl = (process.env.MS_BASE_URL || 'http://127.0.0.1:8081').replace(/\/$/, '');
const projectId = process.env.MS_PROJECT_ID;
const scenarioId = process.env.MS_SCENARIO_ID;

if (!scenarioId) {
  console.error('Missing MS_SCENARIO_ID; skip MeterSphere stage.');
  process.exit(0);
}

let sessionId = process.env.MS_TOKEN;
let csrfToken = process.env.MS_CSRF || '';
let userId = process.env.MS_USER_ID || 'admin';

if (!sessionId) {
  const session = await login({ baseUrl });
  sessionId = session.sessionId;
  csrfToken = session.csrfToken;
  userId = session.userId;
}

if (projectId) {
  await switchProject({ baseUrl, projectId, userId, sessionId, csrfToken });
}

const { reportId, body } = await runScenario({
  baseUrl, projectId, scenarioId, sessionId, csrfToken,
  reportId: process.env.MS_REPORT_ID,
});

console.log(`reportId=${reportId}`);
console.log(`taskId=${body.data?.taskInfo?.taskId}`);
console.log(JSON.stringify(body.data?.taskItem || {}, null, 2));
