#!/usr/bin/env python3
"""wx2pdf: 把微信公众号文章（或普通网页）导出为排版干净的 A4 PDF。

用法:
  python3 wx2pdf.py <url> [--out 文件名.pdf] [--dir 工作目录] [--no-images]

依赖:
  apt-get install -y fonts-noto-cjk libpango-1.0-0 libpangoft2-1.0-0 \
      libcairo2 libgdk-pixbuf-2.0-0 libffi8
  pip install weasyprint beautifulsoup4 lxml
"""
import argparse
import datetime
import os
import re
import sys
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Mobile Safari/537.36")

DROP_STYLE = {
    "background", "background-color", "background-image",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "width", "max-width", "min-width", "min-height", "height",
    "text-align", "display", "position", "left", "top", "right", "bottom",
    "float", "box-shadow", "border-radius", "transform", "overflow",
}

CSS = """
@page { size: A4; margin: 17mm 15mm 18mm; }
@page { @bottom-center { content: counter(page) " / " counter(pages);
        font-size: 8.5pt; color: #999; } }
* { box-sizing: border-box; }
body { font-family: "Noto Sans CJK SC", "Noto Serif CJK SC", sans-serif;
       font-size: 10.5pt; line-height: 1.8; color: #222; margin: 0; }
h1 { font-size: 19pt; line-height: 1.35; margin: 0 0 3mm; font-weight: 700; }
h2 { font-size: 14pt; margin: 6mm 0 2.5mm; }
h3 { font-size: 12pt; margin: 5mm 0 2mm; }
.meta { font-size: 9pt; color: #777; border-bottom: 1px solid #e5e5e5;
        padding-bottom: 3mm; margin-bottom: 6mm; }
p { margin: 0 0 3mm; text-align: justify; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin: 0 0 1.2mm; }
img { max-width: 100%; height: auto; display: block; margin: 4mm auto; }
pre, code { font-family: "DejaVu Sans Mono", monospace; }
pre { background: #f6f8fa; padding: 3mm; border-radius: 2mm;
      white-space: pre-wrap; word-break: break-all; font-size: 8.5pt;
      line-height: 1.5; }
blockquote { border-left: 3px solid #ddd; margin: 3mm 0; padding: 1mm 0 1mm 4mm;
             color: #555; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; }
td, th { border: 1px solid #ddd; padding: 1.5mm; }
"""


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def fetch(url, referer=None):
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read(), r.headers.get("Content-Type", "")


def ext_for(ctype, url):
    ctype = (ctype or "").lower()
    if "png" in ctype:
        return ".png"
    if "gif" in ctype:
        return ".gif"
    if "webp" in ctype:
        return ".webp"
    if "svg" in ctype:
        return ".svg"
    path = urllib.parse.urlparse(url).path.lower()
    for e in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        if path.endswith(e):
            return ".jpg" if e == ".jpeg" else e
    return ".jpg"


def slug(text, limit=40):
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]", " ", text or "")
    text = re.sub(r"\s+", "-", text.strip())
    text = text.strip("-.#")
    return text[:limit] or "article"


def normalize(content):
    for el in content.find_all(True):
        st = el.get("style")
        if st:
            kept = []
            for part in st.split(";"):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                if k.strip().lower() not in DROP_STYLE:
                    kept.append(f"{k.strip()}:{v.strip()}")
            if kept:
                el["style"] = ";".join(kept)
            else:
                del el["style"]
        for attr in list(el.attrs):
            if attr.startswith("data-"):
                del el.attrs[attr]
    # 去掉纯空白且没有媒体内容的块，减少大片留白
    for el in list(content.find_all(["p", "section", "div", "span"])):
        if el.get_text(strip=True):
            continue
        if el.find(["img", "table", "pre", "code", "svg"]):
            continue
        el.decompose()


def download_images(content, img_dir, page_url, enabled=True):
    os.makedirs(img_dir, exist_ok=True)
    total = ok = 0
    for i, img in enumerate(content.find_all("img")):
        src = (img.get("data-src") or img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        total += 1
        src = urllib.parse.urljoin(page_url, src)
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("http://"):
            src = "https://" + src[7:]
        if not enabled:
            img.decompose()
            continue
        try:
            data, ctype = fetch(src, referer=page_url)
            if len(data) < 512:
                raise ValueError("too small")
            name = f"{i:02d}{ext_for(ctype, src)}"
            with open(os.path.join(img_dir, name), "wb") as f:
                f.write(data)
            img.attrs = {"src": f"img/{name}", "alt": ""}
            ok += 1
        except Exception as e:  # 单张失败不影响整体
            print(f"  img skip {src[:70]}: {e}", file=sys.stderr)
            img.decompose()
    return ok, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", help="输出 PDF 路径")
    ap.add_argument("--dir", help="工作目录（默认 .wx2pdf/<slug>-<时间>）")
    ap.add_argument("--no-images", action="store_true", help="不下载配图")
    ap.add_argument("--keep-html", action="store_true", help="保留清洗后的 clean.html")
    args = ap.parse_args()

    try:
        from bs4 import BeautifulSoup
        from weasyprint import HTML
    except ImportError as e:
        fail(f"缺少 Python 依赖: {e}. 先运行 pip install weasyprint beautifulsoup4 lxml")

    print("fetching", args.url)
    raw, _ = fetch(args.url)
    html_text = raw.decode("utf-8", "replace")

    soup = BeautifulSoup(html_text, "lxml")
    og = soup.find("meta", property="og:title")
    title = (og.get("content") if og else None) or (soup.title.string if soup.title else "")
    title = (title or "").strip()
    if not title or "环境异常" in html_text[:2000]:
        fail("没拿到正文（可能是反爬/验证页）。用浏览器打开确认可访问后再试。")

    content = (soup.select_one("#js_content") or soup.select_one("article")
               or soup.select_one("main") or soup.body)
    if content is None:
        fail("找不到正文容器")

    if content.name == "body":
        for tag in content.find_all(["header", "nav", "footer", "aside",
                                     "script", "style", "iframe", "noscript"]):
            tag.decompose()

    for tag in content.find_all(["script", "style", "iframe", "noscript", "video"]):
        tag.decompose()

    author = soup.find("meta", attrs={"name": "author"})
    author = author.get("content") if author else ""
    nick_el = soup.select_one("#js_name")
    nick = nick_el.get_text(strip=True) if nick_el else ""
    m = re.search(r'var\s+ct\s*=\s*"(\d{10})"', html_text)
    date = ""
    if m:
        date = datetime.datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    workdir = os.path.abspath(args.dir or os.path.join(
        ".wx2pdf", f"{slug(title, 30)}-{stamp}"))
    os.makedirs(workdir, exist_ok=True)

    ok, total = download_images(content, os.path.join(workdir, "img"),
                                args.url, enabled=not args.no_images)
    normalize(content)

    body = content.decode_contents()
    meta_line = " · ".join(x for x in [nick, author, date] if x)
    doc_html = (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                f"<style>{CSS}</style></head><body><h1>{title}</h1>"
                f'<div class="meta">{meta_line}</div>{body}</body></html>')

    if args.keep_html:
        with open(os.path.join(workdir, "clean.html"), "w", encoding="utf-8") as f:
            f.write(doc_html)

    out = args.out or os.path.join(workdir, slug(title) + ".pdf")
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    rendered = HTML(string=doc_html, base_url=workdir).render()
    rendered.write_pdf(out)
    print(f"ok  pages={len(rendered.pages)}  images={ok}/{total}  "
          f"size={os.path.getsize(out)}  out={out}")


if __name__ == "__main__":
    main()
