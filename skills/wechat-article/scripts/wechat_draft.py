#!/usr/bin/env python3
"""WeChat draft helper: token, permission test, cover upload, draft add/update.

Only draft endpoints are used. This script never publishes or mass-sends.

Credentials (never commit):
  ~/.config/opencode/wechat.env
    WECHAT_APPID=wx...
    WECHAT_APPSECRET=...
  chmod 600 ~/.config/opencode/wechat.env

Examples:
  python3 wechat_draft.py test
  python3 wechat_draft.py create --html html/a.html --cover cover.jpg --digest "摘要" \
      --source https://example.com/a.html
  python3 wechat_draft.py update --media-id <DRAFT_MEDIA_ID> --html html/a.html
  python3 wechat_draft.py list

Quirks handled:
  - draft/add:    articles = [ {...} ]
  - draft/update: articles = {...}      (object, not array; otherwise 47001)
  - thumb_media_id must be a permanent media id; cover is uploaded as image material.
  - Session uses trust_env=False, so the direct egress IP must be whitelisted.
"""
import argparse
import html as html_mod
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path

import requests

API = "https://api.weixin.qq.com"
DEFAULT_ENV = Path.home() / ".config/opencode/wechat.env"
DEFAULT_CACHE = Path.home() / ".cache/wechat-token.json"


def client():
    s = requests.Session()
    s.trust_env = False
    return s


def load_creds(env_file):
    vals = {}
    for key in ("WECHAT_APPID", "WECHAT_APPSECRET"):
        if os.environ.get(key):
            vals[key] = os.environ[key]
    path = Path(env_file).expanduser()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    appid = vals.get("WECHAT_APPID") or vals.get("APPID")
    secret = vals.get("WECHAT_APPSECRET") or vals.get("APPSECRET")
    if not appid or not secret:
        raise SystemExit(
            f"missing WECHAT_APPID/WECHAT_APPSECRET in env or {path}"
        )
    return appid, secret


def token_error(d):
    print(json.dumps(d, ensure_ascii=False))
    code = d.get("errcode")
    if code == 40164:
        print("hint: egress IP is not in the WeChat IP whitelist")
    elif code == 40013:
        print("hint: invalid AppID")
    elif code == 40125:
        print("hint: invalid AppSecret")
    raise SystemExit(1)


def get_token(args):
    cache = Path(args.cache).expanduser()
    if cache.exists():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            d = {}
        if d.get("expires_at", 0) > time.time() and d.get("access_token"):
            return d["access_token"]
    appid, secret = load_creds(args.env_file)
    d = client().get(
        f"{API}/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": appid, "secret": secret},
        timeout=20,
    ).json()
    if "access_token" not in d:
        token_error(d)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {
                "access_token": d["access_token"],
                "expires_at": time.time() + int(d.get("expires_in", 7200)) - 120,
            }
        ),
        encoding="utf-8",
    )
    os.chmod(cache, 0o600)
    return d["access_token"]


def get_json(tok, path, params=None):
    p = {"access_token": tok}
    if params:
        p.update(params)
    d = client().get(f"{API}{path}", params=p, timeout=30).json()
    if d.get("errcode") not in (None, 0):
        raise RuntimeError(json.dumps(d, ensure_ascii=False))
    return d


def post_json(tok, path, payload):
    d = client().post(
        f"{API}{path}",
        params={"access_token": tok},
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=60,
    )
    return json.loads(d.content.decode("utf-8"))


def fail_api(name, d):
    print(name, json.dumps({k: v for k, v in d.items() if k in ("errcode", "errmsg", "media_id")}, ensure_ascii=False))
    code = d.get("errcode")
    if code == 47001:
        print("hint: draft/update uses articles as an OBJECT; draft/add uses an array")
    elif code == 48001:
        print("hint: API unauthorized for this account (draft/material permission)")
    elif code == 40164:
        print("hint: egress IP is not in the WeChat IP whitelist")
    raise SystemExit(1)


def extract(path):
    raw = Path(path).read_text(encoding="utf-8")
    m = re.search(r"<section[^>]*>(.*)</section>", raw, re.S)
    if m:
        body = m.group(1)
    else:
        m = re.search(r"<body[^>]*>(.*)</body>", raw, re.S)
        body = m.group(1) if m else raw
    hm = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = html_mod.unescape(re.sub(r"<[^>]+>", "", hm.group(1))).strip() if hm else ""
    content = re.sub(r"<h1[^>]*>.*?</h1>", "", body, count=1, flags=re.S)
    return title, content


def upload_cover(tok, path):
    if not path:
        return ""
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"cover not found: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    last = {}
    for kind in ("image", "thumb"):
        with path.open("rb") as f:
            d = post_json_file(
                f"/cgi-bin/material/add_material",
                tok,
                {"type": kind},
                {"media": (path.name, f, mime)},
            )
        if d.get("media_id"):
            return d["media_id"]
        last = d
    fail_api("cover upload", last)


def post_json_file(path, tok, params, files):
    p = {"access_token": tok}
    p.update(params)
    d = client().post(f"{API}{path}", params=p, files=files, timeout=60)
    return json.loads(d.content.decode("utf-8"))


def get_draft(tok, media_id):
    d = post_json(tok, "/cgi-bin/draft/get", {"media_id": media_id})
    if "news_item" not in d:
        fail_api("draft/get", d)
    return d["news_item"][0]


def check_stats(content):
    return (
        f"len={len(content)} table={content.count('<table')} "
        f"img={content.count('<img')} class={content.count('class=')} "
        f"script={content.count('<script')} style_tag={content.count('<style')}"
    )


def cmd_test(args):
    tok = get_token(args)
    print("token: OK")
    for name, path in (
        ("draft/count", "/cgi-bin/draft/count"),
        ("material/count", "/cgi-bin/material/get_materialcount"),
    ):
        try:
            d = get_json(tok, path)
            print(name, json.dumps(d, ensure_ascii=False))
        except RuntimeError as e:
            print(name, e)
    print("note: whitelist the direct egress IP; this script does not use a proxy")


def cmd_list(args):
    tok = get_token(args)
    d = post_json(
        tok,
        "/cgi-bin/draft/batchget",
        {"offset": 0, "count": args.count, "no_content": 1},
    )
    if d.get("errcode") not in (None, 0):
        fail_api("draft/batchget", d)
    for item in d.get("item", []):
        news = item.get("content", {}).get("news_item", [{}])[0]
        print(item.get("media_id"), "|", news.get("title"), "|", news.get("content_source_url"))


def cmd_create(args):
    tok = get_token(args)
    title, content = extract(args.html)
    title = args.title or title
    if not title:
        raise SystemExit("no title: add an H1 or pass --title")
    thumb = "<dry-run>" if args.dry_run else upload_cover(tok, args.cover)
    art = {
        "title": title,
        "author": args.author or "",
        "digest": args.digest or "",
        "content": content,
        "content_source_url": args.source or "",
        "thumb_media_id": thumb,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    print("create:", title, check_stats(content))
    if args.dry_run:
        print("dry-run: not calling draft/add")
        return
    d = post_json(tok, "/cgi-bin/draft/add", {"articles": [art]})
    if d.get("errcode") not in (None, 0):
        fail_api("draft/add", d)
    print("draft media_id:", d.get("media_id"))


def cmd_update(args):
    tok = get_token(args)
    item = get_draft(tok, args.media_id)
    title, content = extract(args.html)
    title = args.title or title or item.get("title", "")
    thumb = upload_cover(tok, args.cover) if args.cover else item.get("thumb_media_id", "")
    art = {
        "title": title,
        "author": args.author if args.author is not None else item.get("author", ""),
        "digest": args.digest if args.digest is not None else item.get("digest", ""),
        "content": content,
        "content_source_url": args.source if args.source is not None else item.get("content_source_url", ""),
        "thumb_media_id": thumb,
        "need_open_comment": int(item.get("need_open_comment", 0)),
        "only_fans_can_comment": int(item.get("only_fans_can_comment", 0)),
    }
    print("update:", title, check_stats(content))
    if args.dry_run:
        print("dry-run: not calling draft/update")
        return
    d = post_json(
        tok,
        "/cgi-bin/draft/update",
        {"media_id": args.media_id, "index": args.index, "articles": art},
    )
    if d.get("errcode") not in (None, 0):
        fail_api("draft/update", d)
    print("updated:", args.media_id)


def main():
    ap = argparse.ArgumentParser(description="WeChat draft helper (no publish)")
    ap.add_argument("--env-file", default=str(DEFAULT_ENV))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("test", help="token + draft/material permission")
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("list", help="list drafts")
    p.add_argument("--count", type=int, default=20)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("create", help="create a draft")
    p.add_argument("--html", required=True)
    p.add_argument("--cover", required=True)
    p.add_argument("--title")
    p.add_argument("--digest")
    p.add_argument("--source")
    p.add_argument("--author", default="")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("update", help="update an existing draft in place")
    p.add_argument("--media-id", required=True)
    p.add_argument("--html", required=True)
    p.add_argument("--cover", help="optional; keep old cover if omitted")
    p.add_argument("--title")
    p.add_argument("--digest")
    p.add_argument("--source")
    p.add_argument("--author", default=None)
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_update)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
