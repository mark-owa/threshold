// Records the existing application. No route interception, synthetic UI, or live providers.
import assert from 'node:assert/strict';
import { mkdir, writeFile, copyFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';

const baseURL = process.env.DEMO_URL || 'http://localhost:5173';
const output = new URL('./output/', import.meta.url).pathname;
const publish = `${output}publish/`;
await mkdir(publish, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir: `${output}raw`, size: { width: 1440, height: 1000 } },
});
const page = await context.newPage();
page.setDefaultTimeout(20000);
const started = Date.now();
const elapsed = () => (Date.now() - started) / 1000;
const subtitles = [];
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {
  if (response.url().includes('/api/') && response.status() >= 400) {
    errors.push(`HTTP ${response.status()}: ${new URL(response.url()).pathname}`);
  }
});
const status = page.getByRole('status');
const panel = name => page.locator('section.panel').filter({
  has: page.getByRole('heading', { name, exact: true }),
});
const step = name => page.locator('.step').filter({
  has: page.getByText(name, { exact: true }),
});
async function scene(text, seconds, action = async () => {}) {
  const start = elapsed();
  await action();
  await delay(Math.max(0, seconds - (elapsed() - start)) * 1000);
  subtitles.push({ start, end: elapsed(), text });
}
async function expectStatus(text) {
  await status.filter({ hasText: text }).waitFor();
}
async function run(label, scenario, expected) {
  const responsePromise = page.waitForResponse(r =>
    r.url().includes('/api/v1/demo/run?') && r.request().method() === 'POST');
  await page.getByRole('button', { name: label, exact: true }).click();
  const response = await responsePromise;
  assert.equal(response.status(), 200);
  const result = await response.json();
  assert.equal(result.scenario, scenario);
  assert.equal(result.status, expected);
  await expectStatus(`${scenario.replaceAll('_', ' ')} executed: ${expected}.`);
  return result;
}
function srtTime(seconds) {
  return new Date(Math.round(seconds * 1000)).toISOString().slice(11, 23).replace('.', ',');
}
let token, org, me, low, high, failure, approvalStart, approvalEnd;
const evidence = {
  recorded_at: new Date().toISOString(),
  source_commit: process.env.GITHUB_SHA || null,
  run_url: process.env.GITHUB_RUN_ID
    ? `https://github.com/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}` : null,
  environment: 'Docker Compose: PostgreSQL, Redis, FastAPI, nginx and production React build',
  provider: 'mock',
  recovery: 'manual; worker and Beat not running',
  checks: {},
};
const api = async path => {
  const response = await context.request.get(`${baseURL}/api/v1/${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  assert.equal(response.status(), 200, path);
  return response.json();
};
try {
  await scene('THRESHOLD | Controlled refund automation\nReal application; fictional retailer; mock AI and payment effects.', 18, async () => {
    await page.goto(baseURL);
    await page.getByLabel('Email', { exact: true }).fill('reviewer@acme-demo.example.com');
    await page.getByLabel('Password', { exact: true }).fill('demo1234');
    const login = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login'));
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    const response = await login;
    assert.equal(response.status(), 200);
    token = (await response.json()).access_token;
    await expectStatus('Dashboard refreshed.');
    me = await api('auth/me');
    assert.equal(me.memberships[0].role, 'reviewer');
    org = me.memberships[0].organization_id;
    assert.equal((await api(`ops/metrics?org_id=${org}`)).total_executions, 0,
      'Use a fresh disposable demo database.');
  });
  await scene('A customer asks for a $65 refund.\nDeterministic policy checks decide whether automatic handling is allowed.', 14, async () => {
    low = await run('Low-risk refund', 'low_risk_refund', 'completed');
    await step('rules').scrollIntoViewIfNeeded();
  });
  await scene('The configured automatic limit is $75.\nThis eligible order passes the rules and risk checks.', 14, async () => {
    await step('risk').scrollIntoViewIfNeeded();
  });
  await scene('The action and its verification are recorded.\nThis demo writes a local mock refund; it sends no real payment.', 14, async () => {
    await step('execute').scrollIntoViewIfNeeded();
    await step('execute').screenshot({ path: `${publish}execution-inspector.png` });
    const result = await api(`ops/executions/${low.execution_id}?org_id=${org}`);
    assert.equal(result.status, 'completed');
    assert(result.steps.some(s => s.step_key === 'verify' && s.output.verified === true));
    evidence.checks.automatic_refund = { execution_id: low.execution_id, status: result.status };
  });
  await scene('A second request asks for $89.99.\nIt exceeds the automatic limit, so the workflow pauses for human review.', 16, async () => {
    high = await run('High-risk refund', 'high_risk_refund', 'awaiting_approval');
    await panel('Approval queue').scrollIntoViewIfNeeded();
    await panel('Approval queue').screenshot({ path: `${publish}approval-required.png` });
    const pending = await api(`ops/approvals?org_id=${org}`);
    assert.equal(pending.length, 1);
    assert.equal(pending[0].execution_id, high.execution_id);
    evidence.checks.approval_pause = { execution_id: high.execution_id, status: high.status };
  });
  approvalStart = elapsed();
  await scene('The reviewer sees the amount and order before deciding.\nApproval resumes the workflow; the action still validates its parameters.', 12, async () => {
    await page.getByRole('button', { name: 'Approve', exact: true }).hover();
  });
  await scene('The reviewer approves. The pending request clears.\nThe execution completes and the reviewer identity is recorded.', 14, async () => {
    const decision = page.waitForResponse(r =>
      r.url().includes('/decision?') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Approve', exact: true }).click();
    const response = await decision;
    assert.equal(response.status(), 200);
    const result = await response.json();
    assert.equal(result.status, 'completed');
    assert.equal(result.reviewer_id, me.user_id);
    await expectStatus('Approval approved. Execution is completed.');
    assert.equal((await api(`ops/approvals?org_id=${org}`)).length, 0);
    await panel('Recent executions').scrollIntoViewIfNeeded();
    evidence.checks.approval_completed = result;
  });
  approvalEnd = elapsed();
  await scene('Now the demo injects one timeout on a separate order.\nThe failure remains visible in the execution timeline.', 16, async () => {
    failure = await run('Failure + retry', 'failed_refund', 'failed');
    await page.locator('.step.failed').scrollIntoViewIfNeeded();
    assert(await page.locator('.step.failed').count() > 0);
  });
  await scene('Recovery is triggered manually here; the scheduler is stopped.\nThe retry reuses the existing business action instead of creating another.', 16, async () => {
    await page.getByRole('button', { name: 'Retry failed action', exact: true }).click();
    await expectStatus('Retry finished: completed.');
    await step('execute.retry').scrollIntoViewIfNeeded();
    const result = await api(`ops/executions/${failure.execution_id}?org_id=${org}`);
    assert.equal(result.status, 'completed');
    assert(result.steps.some(s => s.status === 'failed'));
    assert(result.steps.some(s => s.step_key === 'verify.retry' && s.output.verified === true));
    const audit = await api(`ops/audit?org_id=${org}&limit=200`);
    const failed = audit.find(a => a.execution_id === failure.execution_id && a.event_type === 'action_failed');
    const recovered = audit.find(a => a.execution_id === failure.execution_id && a.event_type === 'action_retried_and_succeeded');
    assert(failed && recovered);
    assert(failed.payload.action_id);
    assert.equal(failed.payload.action_id, recovered.payload.action_id);
    evidence.checks.retry_same_action = {
      execution_id: failure.execution_id, action_id: recovered.payload.action_id,
      failed_event_id: failed.id, recovered_event_id: recovered.id, status: result.status,
    };
    await panel('Execution inspector').screenshot({ path: `${publish}retry-recovery.png` });
    await step('execute.retry').scrollIntoViewIfNeeded();
  });
  await scene('The original failed step remains alongside successful retry steps.\nAudit records tie the failed attempt and recovery to the same action ID.', 16, async () => {
    await step('verify.retry').scrollIntoViewIfNeeded();
    await delay(7000);
    await panel('Audit trail').scrollIntoViewIfNeeded();
  });
  await scene('Request identity and business-action identity are separate.\nThe application records decisions, outcomes and recovery for inspection.', 14, async () => {
    await page.getByRole('heading', { name: 'Run a controlled demo', exact: true }).scrollIntoViewIfNeeded();
    await page.getByRole('button', { name: 'Refresh dashboard', exact: true }).click();
    await expectStatus('Dashboard refreshed.');
    await page.locator('.hero').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${publish}dashboard-overview.png` });
  });
  await scene('Portfolio prototype: AI, payments and notifications are mocked.\nThis recording does not establish live-provider or production payment safety.', 16);
  assert.deepEqual(errors, [], 'Unexpected browser or HTTP errors');
  evidence.duration_seconds = elapsed();
  assert(evidence.duration_seconds >= 120 && evidence.duration_seconds <= 240);
} catch (error) {
  await page.screenshot({ path: `${output}failure.png`, fullPage: true }).catch(() => {});
  throw error;
} finally {
  await context.close();
  await browser.close();
}

const rawVideo = await page.video().path();
const subtitlesPath = `${output}captions.srt`;
await writeFile(subtitlesPath, subtitles.map((s, i) =>
  `${i + 1}\n${srtTime(s.start)} --> ${srtTime(s.end)}\n${s.text}\n`).join('\n'));
await copyFile(subtitlesPath, `${publish}threshold-demo.srt`);
const assPath = `${output}captions.ass`;
const assTime = seconds => srtTime(seconds).slice(1, -1).replace(',', '.');
await writeFile(assPath, `[Script Info]\nScriptType: v4.00+\nPlayResX: 1440\nPlayResY: 1120\n\n` +
  `[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n` +
  `Style: Default,DejaVu Sans,28,&H00FFFFFF,&H00FFFFFF,&H000F172A,&H000F172A,0,0,0,0,100,100,0,0,1,0,0,2,24,24,22,1\n\n` +
  `[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n` +
  subtitles.map(s => `Dialogue: 0,${assTime(s.start)},${assTime(s.end)},Default,,0,0,0,,${s.text.replaceAll('\n', '\\N')}`).join('\n') + '\n');
const videoPath = `${publish}threshold-demo.mp4`;
execFileSync('ffmpeg', ['-y', '-i', rawVideo, '-vf',
  `pad=1440:1120:0:0:color=0x0f172a,ass=${assPath}`,
  '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '24', '-pix_fmt', 'yuv420p',
  '-movflags', '+faststart', videoPath], { stdio: 'inherit' });
execFileSync('ffmpeg', ['-y', '-ss', String(approvalStart), '-t', String(approvalEnd - approvalStart),
  '-i', videoPath, '-filter_complex',
  '[0:v]fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer',
  '-loop', '0', `${publish}approval-demo.gif`], { stdio: 'inherit' });
await writeFile(`${publish}capture-evidence.json`, JSON.stringify(evidence, null, 2) + '\n');
console.log(JSON.stringify(evidence, null, 2));
