# Restart here

Everything in the code has been fixed. What is left needs your logins, so it
has to be you. Total time: about 20 minutes.

Work top to bottom. Commands are for Windows PowerShell in the repo folder.

---

## 1. Rotate the eBay verification token — do this first

The old token was hardcoded in `worker/scanner.js` in a **public** GitHub repo,
so treat it as burned.

1. Go to <https://developer.ebay.com> → Application Keys → **Notifications** /
   Marketplace Account Deletion for the **TrendRadar** production keyset.
2. Generate a new verification token (32–80 characters, letters/numbers/`_`/`-`).
3. Keep the endpoint as
   `https://dropshipping.battersea-dynamics.workers.dev/ebay/notifications`.
4. Store it on the Worker:

   ```powershell
   wrangler secret put EBAY_VERIFICATION_TOKEN
   ```

5. Do **not** click "Send Test Notification" in eBay yet — deploy first (step 4).

Severity note so you can judge this yourself: a leaked verification token lets
someone answer eBay's challenge as if they were your endpoint. It does not
expose customer data and it is not your API keyset. Rotate it, don't panic.

## 2. Create the push secret

This is what closes the open `/api/push` endpoint.

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output, then:

- Paste it into `.env` as `PUSH_SECRET=<value>`
- Give the Worker the same value:

  ```powershell
  wrangler secret put PUSH_SECRET
  ```

Both sides must match exactly or the scanner gets a 401.

## 3. Update Wrangler

The dashboard is now shipped as a static asset, which needs a recent Wrangler.

```powershell
npm install -g wrangler@latest
wrangler --version
```

## 4. Deploy and verify

```powershell
wrangler deploy
curl https://dropshipping.battersea-dynamics.workers.dev/api/health
```

You want to see:

```json
{"status":"ok","version":"v3","push_secret_configured":true,
 "ebay_token_configured":true,"kv_bound":true,"assets_bound":true}
```

Then confirm the endpoint is actually closed — this must return **401**:

```powershell
curl -X Method POST https://dropshipping.battersea-dynamics.workers.dev/api/push `
     -Body '{"signals":[]}' -ContentType 'application/json'
```

(If `curl` behaves oddly in PowerShell, use `Invoke-WebRequest` or just open
`/api/health` in a browser and trust the 401 test to the scanner run in step 6.)

Now go back to eBay and send the test notification — it should pass.

## 5. Review and commit

The git side is already staged for you: the Wrangler account cache and the
scan-result dumps have been untracked (they stay on your disk), `index.html`
has been moved to `public/index.html`, and `server.py` — a local dev server
that duplicated the Worker's routes — has been moved to `_to_delete/`.

Look it over, then commit:

```powershell
git status
git add -A
git commit -m "Secure /api/push, fix false-signal matching, rebuild eBay scanner as price signal"
git push
```

Delete the `_to_delete\` folder yourself whenever you're happy.

Your Cloudflare **account ID** was in that cached file. An account ID is an
identifier, not a credential — nobody can do anything with it without an API
token. Removing it is hygiene, not an emergency.

## 6. Run a scan

```powershell
pip install -r requirements.txt
playwright install chromium

python tests\test_matching.py      # 12 checks, all should pass
node tests\worker.test.mjs         # 15 checks, all should pass

python trend_radar.py
```

Watch for `[Save] Pushed to Cloudflare KV`. If you see a 401 or 503 instead,
the two `PUSH_SECRET` values don't match — redo step 2.

Then open the dashboard. Scores now come with reasons attached, so if something
says STRONG you can see exactly why.

---

## Still open — decide later, not now

**Automation.** `python trend_radar.py auto` only runs while your PC is on.
The old plan of enabling a Cloudflare cron cannot work: the scan scrapes
Amazon, and Amazon blocks datacenter IPs, which is what Cloudflare (and GitHub
Actions, and any VPS) egresses from. Realistic options, in order of effort:

1. Windows Task Scheduler on your PC — free, works today, PC must be awake.
2. A cheap always-on box (an old laptop, a Pi) running the same script.
3. A residential-proxy or paid product-data API — costs money, only worth it
   if the radar is actually driving buying decisions.

Option 1 until the radar earns its keep.

**Telegram.** `TELEGRAM_CHAT_ID` used to be in `wrangler.toml` in the public
repo. A chat ID alone is harmless without the bot token, and the bot token was
only ever in `.env`. No action needed, but if you want to be thorough you can
rotate the bot token via @BotFather.

**The dashboard's Reddit and Google Trends panels** are still wired to data
sources that are disabled. They show blanks. Cosmetic, fix during polishing.
