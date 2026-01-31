# Skill: Jike QR Login + Following Feed Fetch

## Purpose
Let an agent log in to Jike via QR code (web flow), periodically fetch the "following" feed, and store updates in its memory for later Q&A.

## Flow Overview
1) **Create session**: `POST https://api.ruguoapp.com/sessions.create`
   - Response JSON: `{ "uuid": "<uuid>" }`
2) **Generate QR payload** (to display):
   - QR content: `jike://page.jk/web?url=<urlencoded https://web.okjike.com/account/scan?uuid=<uuid>>&displayHeader=false&displayFooter=false`
   - Render QR via API (recommended): `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=<urlencoded QR content>`
3) **User scans & confirms** in Jike mobile app.
4) **Poll for confirmation**: `GET https://api.ruguoapp.com/sessions.wait_for_confirmation?uuid=<uuid>` (poll every ~1s, timeout e.g. 3 min).
   - On success (`200`), tokens are returned in **response body JSON**, keys:
     - `x-jike-refresh-token`
     - `x-jike-access-token`
   - `400 SESSION_IN_WRONG_STATUS` → keep polling.
5) **Normalize tokens (optional but recommended)**: `POST https://api.ruguoapp.com/app_auth_tokens.refresh`
   - Headers: `x-jike-refresh-token: <refresh>`
   - Body: `{}`
   - Response headers return fresh `x-jike-access-token` and `x-jike-refresh-token`.
6) **Fetch following feed**: `POST https://api.ruguoapp.com/1.0/personalUpdate/followingUpdates`
   - Headers: `x-jike-access-token: <access>`
   - Body: `{ "limit": 20, "loadMoreKey": "<optional>" }`
   - Response JSON contains feed items and (if present) `loadMoreKey` for pagination.

## Required Headers (all requests)
- `Origin: https://web.okjike.com`
- `User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1`
- `Accept: application/json, text/plain, */*`
- `DNT: 1`
- `Content-Type: application/json` for POST bodies

## Error Handling
- `sessions.wait_for_confirmation` returning 400 → keep polling until timeout.
- If feed call gets `401`, refresh with the latest refresh token, then retry once.
- If QR polling times out, restart from `sessions.create` to get a new uuid/QR.

## Persistence & Privacy
- Store tokens only in volatile memory; do not log or write to disk.
- Cache the latest `refresh_token` and `access_token` in agent memory for reuse until expiry.

## Hourly Fetch Task (agent loop)
1) Ensure valid tokens; if access token missing/expired, refresh using stored refresh token. If refresh token missing/expired, redo QR login.
2) Call `followingUpdates` with `limit` (e.g., 20) and optional `loadMoreKey` to pull new items.
3) Deduplicate by item ID/timestamp; append new items to agent memory.
4) Repeat hourly.

## Minimal cURL Examples
- Create session: `curl -s -X POST "https://api.ruguoapp.com/sessions.create" -H "Origin: https://web.okjike.com"`
- Wait for confirm: `curl -s "https://api.ruguoapp.com/sessions.wait_for_confirmation?uuid=<uuid>" -H "Origin: https://web.okjike.com"`
- Refresh: `curl -i -X POST "https://api.ruguoapp.com/app_auth_tokens.refresh" -H "Origin: https://web.okjike.com" -H "x-jike-refresh-token: <refresh>" -d '{}'`
- Feed: `curl -s -X POST "https://api.ruguoapp.com/1.0/personalUpdate/followingUpdates" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>" -H "Content-Type: application/json" -d '{"limit":20}'`

## Notes
- Tokens from `sessions.wait_for_confirmation` come in the **body**, not headers.
- QR content must use the `jike://page.jk/web?url=...account/scan?uuid=...` format; render it via `api.qrserver.com` for convenience.
- Keep polling interval gentle (e.g., 1s) to avoid unnecessary load.
