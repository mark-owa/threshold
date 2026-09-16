# Real application capture

The **Capture portfolio demo** Actions workflow builds the existing Docker images,
runs migrations, seeds a fresh disposable database, and records the dashboard.
It uses the existing mock provider and public demo reviewer. No external API keys
or customer data are required. Application code and dependencies are unchanged.

The recording checks automatic completion, a real approval pause, the reviewer
decision, and manual recovery with the same action ID in both audit events. It
records Chromium video, captures four screenshots, and uses FFmpeg to add explanatory
captions and extract an approval GIF. It never intercepts or fabricates API responses.

Worker and Beat are intentionally absent so automatic retries cannot race the
manual demonstration. This does not test broker delivery or scheduled recovery.
The video labels the mock effects and production limitations.

Open **Actions → Capture portfolio demo → Run workflow** to repeat it. A successful
run creates a `threshold-demo` artifact containing PNGs, GIF, captioned MP4, SRT,
and `capture-evidence.json` with the source commit and checked execution/action IDs.
The artifact expires after 14 days; publish reviewed media separately for lasting
portfolio links. Diagnostics are retained for seven days. Media must be reviewed
before being described as portfolio-ready.

To record locally, use a fresh disposable Docker demo as in the root README, keep
Beat stopped, install Node 22 and FFmpeg, then run from this directory:

```sh
npm install --no-package-lock
npx playwright install --with-deps chromium
npm run capture
```

Local capture expects `http://localhost:5173` (override with `DEMO_URL`) and a seeded
database with no executions. It does not erase or reset your local database.
Only the Actions job removes its own disposable volumes during cleanup.
