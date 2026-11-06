import { login } from './ms-client.mjs';

const session = await login();
console.log(`MS_TOKEN=${session.sessionId}`);
console.log(`MS_CSRF=${session.csrfToken}`);
console.log(`MS_USER_ID=${session.userId}`);
console.log(`MS_LAST_PROJECT_ID=${session.lastProjectId}`);
