# Skill: Jike QR Login + Following Feed Fetch

## Purpose
Let an agent log in to Jike via QR code (web flow), periodically fetch the "following" feed, and store updates in its memory for later Q&A.

## Flow Overview
1) **Create session**: `POST https://api.ruguoapp.com/sessions.create`
   - Response JSON: `{ "uuid": "<uuid>" }`
2) **Generate QR payload** (to display):
   - Build URL: `https://www.okjike.com/account/scan?uuid=<uuid>`
   - QR content format: `jike://page.jk/web?url=<urlencoded URL>&displayHeader=false&displayFooter=false`
   - The fianl QR content example: `jike://page.jk/web?url=https%3A%2F%2Fwww.okjike.com%2Faccount%2Fscan%3Fuuid%3Dc075565c-3538-40c7-a714-a00bc3a7f6b5&amp;displayHeader=false&amp;displayFooter=false`
3) **User scans & confirms** in Jike mobile app.
4) **Poll for confirmation**: `GET https://api.ruguoapp.com/sessions.wait_for_confirmation?uuid=<uuid>` (poll every ~1s, timeout ~3 min).
   - On `200`, tokens in body JSON: `x-jike-refresh-token`, `x-jike-access-token`.
   - On `400 SESSION_IN_WRONG_STATUS`, keep polling.
5) **Normalize tokens** (optional): `POST https://api.ruguoapp.com/app_auth_tokens.refresh` with header `x-jike-refresh-token: <refresh>`, body `{}` → headers return fresh access/refresh.
6) **Fetch following feed**: `POST https://api.ruguoapp.com/1.0/personalUpdate/followingUpdates` with header `x-jike-access-token`, body `{ "limit": 20, "loadMoreKey": "<optional>" }`.

## Additional Jike APIs (from HAR)
- **Search**: `POST https://api.ruguoapp.com/1.0/search/integrate`
  - Headers: `x-jike-access-token`, `Content-Type: application/json`
  - Body not captured; typical fields: `keyword`, pagination (`loadMoreKey`/`cursor`) and `limit`.
- **User profile**: `GET https://api.ruguoapp.com/1.0/users/profile?username=<id_or_username>`
- **Post create**: `POST https://api.ruguoapp.com/1.0/originalPosts/create`
  - Headers: `x-jike-access-token`, `Content-Type: application/json`
  - Body not captured; typically includes `content`, optional `pictureKeys`, `topicIds`, `linkInfo`, etc.
- **Post detail**: `GET https://api.ruguoapp.com/1.0/originalPosts/get?id=<postId>`
- **Post delete**: `POST https://api.ruguoapp.com/1.0/originalPosts/remove`
  - Headers: `x-jike-access-token`, `Content-Type: application/json`
  - Body not captured; typically includes `id` (postId).
- **Comment add**: `POST https://api.ruguoapp.com/1.0/comments/add`
  - Headers: `x-jike-access-token`, `Content-Type: application/json`
  - Body example:
    ```json
    {
      "targetType": "ORIGINAL_POST",
      "targetId": "<postId>",
      "content": "comment",
      "syncToPersonalUpdates": false,
      "pictureKeys": [],
      "force": false
    }
    ```
- **Comment remove**: `POST https://api.ruguoapp.com/1.0/comments/remove`
  - Headers: `x-jike-access-token`, `Content-Type: application/json`
  - Body example:
    ```json
    { "id": "<commentId>", "targetType": "ORIGINAL_POST" }
    ```
- **Followers list**: `POST https://api.ruguoapp.com/1.0/userRelation/getFollowerList` (body not captured; expect `userId` + pagination).
- **Following list**: `POST https://api.ruguoapp.com/1.0/userRelation/getFollowingList` (body not captured; expect `userId` + pagination).
- **Single post detail (alt)**: `POST https://api.ruguoapp.com/1.0/personalUpdate/single` (body not captured; typically includes `id`).
- **Notifications**:
  - `GET https://api.ruguoapp.com/1.0/notifications/unread`
  - `POST https://api.ruguoapp.com/1.0/notifications/list` (body not captured; likely pagination).

## Required Headers (all requests)
- `Origin: https://web.okjike.com`
- `User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1`
- `Accept: application/json, text/plain, */*`
- `DNT: 1`
- `Content-Type: application/json` for POST bodies
- Auth where needed: `x-jike-access-token: <access>`

## Error Handling
- `sessions.wait_for_confirmation` 400 → keep polling until timeout.
- **Any API 401** → immediately use the latest `x-jike-refresh-token` to call `app_auth_tokens.refresh`, update access/refresh tokens, then retry the original request once.
- QR polling timeout → redo `sessions.create`.

## Persistence & Privacy
- Keep tokens in volatile memory only; do not log or write to disk.
- Cache latest refresh/access tokens for reuse until expiry.

## Hourly Fetch Task (agent loop)
1) Ensure valid tokens; refresh if needed, redo QR if refresh is absent/expired.
2) Pull `followingUpdates` (`limit` e.g. 20; use `loadMoreKey` for pagination) and store new items; dedupe by ID/timestamp.
3) Repeat hourly.

## Minimal cURL Examples
- Create session: `curl -s -X POST "https://api.ruguoapp.com/sessions.create" -H "Origin: https://web.okjike.com"`
- Wait for confirm: `curl -s "https://api.ruguoapp.com/sessions.wait_for_confirmation?uuid=<uuid>" -H "Origin: https://web.okjike.com"`
- Refresh: `curl -i -X POST "https://api.ruguoapp.com/app_auth_tokens.refresh" -H "Origin: https://web.okjike.com" -H "x-jike-refresh-token: <refresh>" -d '{}'`
- Feed: `curl -s -X POST "https://api.ruguoapp.com/1.0/personalUpdate/followingUpdates" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>" -H "Content-Type: application/json" -d '{"limit":20}'`
- Search: `curl -s -X POST "https://api.ruguoapp.com/1.0/search/integrate" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>" -H "Content-Type: application/json" -d '{"keyword":"test","limit":20}'`
- Profile: `curl -s "https://api.ruguoapp.com/1.0/users/profile?username=<uid>" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>"`
- Post create: `curl -s -X POST "https://api.ruguoapp.com/1.0/originalPosts/create" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>" -H "Content-Type: application/json" -d '{"content":"hi","pictureKeys":[]}'`
- Post detail: `curl -s "https://api.ruguoapp.com/1.0/originalPosts/get?id=<postId>" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>"`
- Post delete: `curl -s -X POST "https://api.ruguoapp.com/1.0/originalPosts/remove" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>" -H "Content-Type: application/json" -d '{"id":"<postId>"}'`
- Comment add: `curl -s -X POST "https://api.ruguoapp.com/1.0/comments/add" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>" -H "Content-Type: application/json" -d '{"targetType":"ORIGINAL_POST","targetId":"<postId>","content":"comment","syncToPersonalUpdates":false,"pictureKeys":[],"force":false}'`
- Comment remove: `curl -s -X POST "https://api.ruguoapp.com/1.0/comments/remove" -H "Origin: https://web.okjike.com" -H "x-jike-access-token: <access>" -H "Content-Type: application/json" -d '{"id":"<commentId>","targetType":"ORIGINAL_POST"}'`

## Notes
- Tokens from `sessions.wait_for_confirmation` come in the **body**, not headers.
- QR content must use the `jike://page.jk/web?url=...account/scan?uuid=...` format; render via `api.qrserver.com`.
- Some endpoints above lack captured bodies; fill `keyword`, `userId`, `loadMoreKey`, `content`, `pictureKeys`, `id` as appropriate when integrating.
- Keep polling interval gentle (e.g., 1s) to avoid unnecessary load.
