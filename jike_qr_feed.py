#!/usr/bin/env python3
"""
Jike QR login + following feed fetcher (CLI).
Requires: Python 3, network access to api.ruguoapp.com.
Optional: qrcode[pil] for terminal QR rendering.
"""
import json
import sys
import time
import urllib.parse
import requests

BASE = "https://api.ruguoapp.com"
ORIGIN = "https://web.okjike.com"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"


def req(method: str, path: str, ok_codes=(200,), **kw) -> requests.Response:
    headers = kw.pop("headers", {})
    headers.setdefault("Origin", ORIGIN)
    headers.setdefault("User-Agent", UA)
    headers.setdefault("Accept", "application/json, text/plain, */*")
    headers.setdefault("DNT", "1")
    if method.lower() == "post":
        headers.setdefault("Content-Type", "application/json")
    r = requests.request(method, BASE + path, headers=headers, **kw)
    if r.status_code not in ok_codes:
        raise requests.HTTPError(f"{r.status_code} {r.reason}", response=r)
    return r


def make_qr_payload(uuid: str) -> str:
    url = f"https://www.okjike.com/account/scan?uuid={uuid}"
    return (
        "jike://page.jk/web?url="
        + urllib.parse.quote(url, safe="")
        + "&displayHeader=false&displayFooter=false"
    )


def print_qr(data: str) -> bool:
    try:
        import qrcode  # type: ignore

        qr = qrcode.QRCode(border=1)
        qr.add_data(data)
        qr.make(fit=True)
        qr.print_ascii(out=sys.stdout)
        return True
    except Exception:
        return False


def main():
    # 1) create session
    resp = req("post", "/sessions.create")
    uuid = resp.json()["uuid"]
    print(f"[+] session uuid: {uuid}")

    # 2) show QR with jike:// schema payload
    qr_payload = make_qr_payload(uuid)
    if print_qr(qr_payload):
        print("[+] 请用即刻 App 扫描上方二维码")
    else:
        print("[!] 未安装 qrcode 库，请将下述链接生成二维码或在即刻中打开：")
        print(qr_payload)

    # 3) poll confirmation
    access_token = refresh_token = None
    for _ in range(180):  # 3 minutes
        try:
            r = req(
                "get",
                f"/sessions.wait_for_confirmation?uuid={uuid}",
                ok_codes=(200, 400),
            )
        except requests.HTTPError as e:
            print(f"[!] 请求失败: {e}")
            time.sleep(1)
            continue

        if r.status_code == 200:
            # tokens can appear in body or headers
            body = {}
            try:
                body = r.json()
            except Exception:
                pass
            access_token = (
                r.headers.get("x-jike-access-token")
                or body.get("x-jike-access-token")
                or body.get("x-jike-access-token".lower())
                or body.get("access_token")
            )
            refresh_token = (
                r.headers.get("x-jike-refresh-token")
                or body.get("x-jike-refresh-token")
                or body.get("x-jike-refresh-token".lower())
                or body.get("refresh_token")
            )
            if refresh_token:
                print("[+] 扫码确认成功，获取到 refresh_token")
                break
            else:
                print("[!] 200 返回但未解析到 refresh_token，打印响应调试：")
                print("    Headers:")
                for k, v in r.headers.items():
                    print(f"      {k}: {v}")
                if body:
                    print("    Body (json):")
                    print(json.dumps(body, ensure_ascii=False, indent=2)[:2000])
                else:
                    txt = r.text
                    if txt:
                        print("    Body (text snippet):")
                        print(txt[:2000])
                break
        else:
            # 400 SESSION_IN_WRONG_STATUS -> keep polling
            time.sleep(1)

    if not refresh_token:
        print("[!] 等待超时或未拿到 token，退出")
        sys.exit(1)

    # 4) refresh once to normalize tokens
    r = req(
        "post",
        "/app_auth_tokens.refresh",
        headers={"x-jike-refresh-token": refresh_token},
        json={},
    )
    access_token = r.headers.get("x-jike-access-token", access_token)
    refresh_token = r.headers.get("x-jike-refresh-token", refresh_token)
    print("[+] 已刷新 token")

    # 5) fetch following feed
    body = {"limit": 20}
    r = req(
        "post",
        "/1.0/personalUpdate/followingUpdates",
        headers={"x-jike-access-token": access_token},
        json=body,
    )
    feed = r.json()
    print("[+] 关注流示例（截断 1 条预览）：")
    items = feed.get("data") or feed.get("items") or []
    if items:
        print(json.dumps(items[0], ensure_ascii=False, indent=2)[:800])
    else:
        print(json.dumps(feed, ensure_ascii=False, indent=2)[:800])


if __name__ == "__main__":
    main()
