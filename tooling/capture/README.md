# Current dashboard capture

The workflow starts a disposable Docker Compose demo, migrates and seeds it, then
uses Chromium to sign in, reload the session, complete a mock refund, approve a
request, and manually recover a simulated failure. API assertions check final
state and that recovery uses the same action ID.

Four screenshots, an approval GIF, and dated JSON evidence are published only
after those assertions pass. Worker and Beat are absent to keep manual retry
observable. This does not verify broker delivery, real providers, or n8n/HubSpot.

From a fresh local demo database, with Node 22 and FFmpeg installed:

```bash
cd tooling/capture
npm ci
npx playwright install chromium
npm run capture
```

Local output is under `output/`. The workflow removes only its disposable Compose
volumes. It commits successful captures to the checked-out same-repository branch;
failed runs retain diagnostics and publish no portfolio media.
