import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';

const base = process.env.DEMO_URL || 'http://localhost:5173';
const output = new URL('./output/', import.meta.url).pathname;
const publish = `${output}publish/`;
await mkdir(publish, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir: `${output}video`, size: { width: 1440, height: 1000 } },
});
const page = await context.newPage();
page.setDefaultTimeout(25000);
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {
  if (response.url().includes('/api/') && response.status() >= 400) {
    errors.push(`${response.status()} ${new URL(response.url()).pathname}`);
  }
});
const started = Date.now();
const elapsed = () => (Date.now() - started) / 1000;
let token, org, me, approvalStart, approvalEnd;
const evidence = {
  recorded_at: new Date().toISOString(),
  source_commit: process.env.CAPTURE_SOURCE_COMMIT || null,
  run_url: `https://github.com/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}`,
  environment: 'Docker Compose: PostgreSQL 16, Redis 7, FastAPI, nginx, production React build; Chromium',
  provider: 'mock',
  recovery: 'manual; worker and Beat not running',
  checks: {},
};
const api = async path => {
  const r = await context.request.get(`${base}/api/v1/${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  assert.equal(r.status(), 200, path);
  return r.json();
};
async function screen(name) {
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `${publish}${name}.png`, fullPage: true });
}
async function run(title, scenario, status) {
  await page.goto(`${base}/demo`);
  const panel = page.locator('section.panel').filter({
    has: page.getByRole('heading', { name: title, exact: true }),
  });
  const request = page.waitForResponse(r => r.url().includes('/api/v1/demo/run?') && r.request().method() === 'POST');
  await panel.getByRole('button', { name: 'Run scenario', exact: true }).click();
  const r = await request;
  assert.equal(r.status(), 200);
  const result = await r.json();
  assert.equal(result.scenario, scenario);
  assert.equal(result.status, status);
  await page.waitForURL(`**/executions/${result.execution_id}`);
  await page.getByRole('heading', { name: 'Control path', exact: true }).waitFor();
  return result;
}
try {
  await page.goto(base);
  await page.getByLabel('Email', { exact: true }).fill('reviewer@acme-demo.example.com');
  await page.getByLabel('Password', { exact: true }).fill('demo1234');
  const login = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login'));
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const response = await login;
  assert.equal(response.status(), 200);
  token = (await response.json()).access_token;
  await page.getByRole('heading', { name: 'Overview', exact: true }).waitFor();
  me = await api('auth/me');
  const membership = me.memberships.find(m => m.role === 'reviewer');
  assert(membership);
  org = membership.organization_id;
  assert.equal((await api(`ops/metrics?org_id=${org}`)).total_executions, 0);
  await page.reload();
  await page.getByRole('heading', { name: 'Overview', exact: true }).waitFor();
  evidence.checks.session_reload = true;

  const low = await run('Low-risk refund', 'low_risk_refund', 'completed');
  const lowDetail = await api(`ops/executions/${low.execution_id}?org_id=${org}`);
  assert(lowDetail.steps.some(s => s.step_key === 'verify' && s.output?.verified === true));
  await screen('execution-inspector');
  evidence.checks.automatic_refund = { execution_id: low.execution_id, status: lowDetail.status };

  const high = await run('High-risk refund', 'high_risk_refund', 'awaiting_approval');
  const pending = await api(`ops/approvals?org_id=${org}`);
  assert.equal(pending.length, 1);
  assert.equal(pending[0].execution_id, high.execution_id);
  await page.goto(`${base}/approvals?focus=${pending[0].id}`);
  await page.getByRole('heading', { name: 'Why this needs review', exact: true }).waitFor();
  await screen('approval-required');
  evidence.checks.approval_pause = { execution_id: high.execution_id, approval_id: pending[0].id };
  approvalStart = elapsed();
  await delay(2000);
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('heading', { name: 'Approve this action?', exact: true }).waitFor();
  await delay(2000);
  const decision = page.waitForResponse(r => r.url().includes('/decision?') && r.request().method() === 'POST');
  await dialog.getByRole('button', { name: 'Approve', exact: true }).click();
  const decisionResponse = await decision;
  assert.equal(decisionResponse.status(), 200);
  assert.equal((await decisionResponse.json()).status, 'completed');
  await page.getByText('No pending approvals', { exact: true }).waitFor();
  const approved = await api(`ops/executions/${high.execution_id}?org_id=${org}`);
  assert.equal(approved.status, 'completed');
  assert.equal((await api(`ops/approvals?org_id=${org}`)).length, 0);
  evidence.checks.approval_completed = { execution_id: high.execution_id, status: approved.status };
  await delay(2000);
  approvalEnd = elapsed();

  const failure = await run('Provider failure', 'failed_refund', 'failed');
  await page.getByText('simulated_external_timeout', { exact: true }).first().waitFor();
  await page.getByRole('button', { name: 'Retry execution', exact: true }).click();
  const retryDialog = page.getByRole('dialog');
  await retryDialog.getByRole('heading', { name: 'Retry this execution?', exact: true }).waitFor();
  const retry = page.waitForResponse(r => r.url().includes(`/executions/${failure.execution_id}/retry?`) && r.request().method() === 'POST');
  await retryDialog.getByRole('button', { name: 'Retry execution', exact: true }).click();
  const retryResponse = await retry;
  assert.equal(retryResponse.status(), 200);
  assert.equal((await retryResponse.json()).status, 'completed');
  await page.getByText('action_retried_and_verified', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Retry execution', exact: true }).waitFor({ state: 'hidden' });
  const recovered = await api(`ops/executions/${failure.execution_id}?org_id=${org}`);
  assert.equal(recovered.status, 'completed');
  assert(recovered.steps.some(s => s.status === 'failed'));
  assert.equal(recovered.context.verified, true);
  const audit = await api(`ops/audit?org_id=${org}&limit=200`);
  const failed = audit.find(a => a.execution_id === failure.execution_id && a.event_type === 'action_failed');
  const done = audit.find(a => a.execution_id === failure.execution_id && a.event_type === 'action_retried_and_verified');
  assert(failed && done);
  assert(failed.payload.action_id);
  assert.equal(failed.payload.action_id, done.payload.action_id);
  const action = await api(`ops/actions/${done.payload.action_id}?org_id=${org}`);
  assert.equal(action.execution_id, failure.execution_id);
  assert.equal(action.status, 'succeeded');
  assert(action.verified_at);
  assert.equal(action.attempts.length, 2);
  assert(action.attempts.some(a => a.operation === 'retry' && a.outcome === 'succeeded'));
  await page.getByText('#2', { exact: true }).waitFor();
  evidence.checks.retry_same_action = {
    execution_id: failure.execution_id, action_id: done.payload.action_id,
    failed_event_id: failed.id, recovered_event_id: done.id, status: recovered.status,
    action_status: action.status, verified_at: action.verified_at,
    attempt_count: action.attempts.length,
  };
  await screen('retry-recovery');
  await page.goto(`${base}/overview`);
  await page.getByRole('heading', { name: 'Recent executions', exact: true }).waitFor();
  await screen('dashboard-overview');
  assert.deepEqual(errors, [], 'Unexpected browser/API errors');
  evidence.checks.browser_errors = errors;
} catch (error) {
  await page.screenshot({ path: `${output}failure.png`, fullPage: true }).catch(() => {});
  throw error;
} finally {
  await context.close();
  await browser.close();
}
const rawVideo = await page.video().path();
execFileSync('ffmpeg', ['-y', '-ss', String(approvalStart), '-t', String(approvalEnd - approvalStart),
  '-i', rawVideo, '-filter_complex',
  '[0:v]fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer',
  '-loop', '0', `${publish}approval-demo.gif`], { stdio: 'inherit' });
await writeFile(`${publish}capture-evidence.json`, JSON.stringify(evidence, null, 2) + '\n');
console.log(JSON.stringify(evidence, null, 2));
