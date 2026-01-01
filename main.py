from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, Response, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote, unquote

app = FastAPI()

# ===============================
# Static
# ===============================
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

# ===============================
# 共通設定
# ===============================
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

TIMEOUT = 15
PROXY_PREFIX = "/proxy/"

# ===============================
# NodeUnblocker 的 fixUrl（Python版）
# ===============================
def fix_url(raw_url: str, base_url: str) -> str:
    if not raw_url:
        return raw_url

    raw_url = raw_url.strip()

    # 既に proxy 済み
    if raw_url.startswith(PROXY_PREFIX):
        return raw_url

    # data: / about: / javascript:
    if raw_url.startswith(("data:", "about:", "javascript:", "blob:")):
        return raw_url

    try:
        abs_url = urljoin(base_url, raw_url)
        parsed = urlparse(abs_url)

        if parsed.scheme not in ("http", "https"):
            return raw_url

        return PROXY_PREFIX + quote(abs_url, safe="")
    except Exception:
        return raw_url

# ===============================
# HTML Proxy（サーバー主導）
# ===============================
@app.get("/htmlproxy/{target:path}")
def html_proxy(target: str):
    url = unquote(target)

    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    content_type = r.headers.get("Content-Type", "")

    if "text/html" not in content_type:
        # HTML 以外は raw proxy へ
        return RedirectResponse(PROXY_PREFIX + quote(url, safe=""))

    soup = BeautifulSoup(r.text, "html.parser")

    # base URL（NodeUnblocker の currentRemoteHref 相当）
    base_url = url

    # <base> を強制挿入
    if soup.head:
        base_tag = soup.new_tag("base", href=base_url)
        soup.head.insert(0, base_tag)

    # 書き換え対象タグ
    TARGET_ATTRS = {
        "a": ["href"],
        "img": ["src", "srcset"],
        "script": ["src"],
        "link": ["href"],
        "iframe": ["src"],
        "video": ["src", "poster"],
        "source": ["src"],
        "audio": ["src"],
        "form": ["action"],
    }

    for tag, attrs in TARGET_ATTRS.items():
        for el in soup.find_all(tag):
            for attr in attrs:
                if el.has_attr(attr):
                    if attr == "srcset":
                        # srcset はカンマ区切り
                        parts = []
                        for part in el[attr].split(","):
                            u = part.strip().split(" ")[0]
                            rest = part.strip()[len(u):]
                            fixed = fix_url(u, base_url)
                            parts.append(fixed + rest)
                        el[attr] = ", ".join(parts)
                    else:
                        el[attr] = fix_url(el[attr], base_url)

    # meta refresh 対策
    for meta in soup.find_all("meta"):
        if meta.get("http-equiv", "").lower() == "refresh":
            content = meta.get("content", "")
            if "url=" in content.lower():
                delay, u = content.split(";", 1)
                real_url = u.split("=", 1)[1]
                meta["content"] = f"{delay};url={fix_url(real_url, base_url)}"

    return HTMLResponse(
        str(soup),
        headers={
            "Cache-Control": "no-store",
            "Content-Type": "text/html; charset=utf-8",
        },
    )

# ===============================
# Raw Proxy（fetch / img / js / css / video）
# ===============================
@app.get("/proxy/{target:path}")
def raw_proxy(target: str):
    url = unquote(target)

    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        stream=True,
        allow_redirects=True,
    )

    headers = {}
    for h in ("Content-Type", "Cache-Control"):
        if h in r.headers:
            headers[h] = r.headers[h]

    headers["Cache-Control"] = "no-store"

    return Response(
        content=r.content,
        status_code=r.status_code,
        headers=headers,
                            )
