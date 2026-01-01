from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, Response, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import requests
import gzip
import brotli
from urllib.parse import unquote, urlparse, quote

app = FastAPI()

# ===============================
# Static
# ===============================
app.mount("/static", StaticFiles(directory="static"), name="static")

# ===============================
# 共通設定
# ===============================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Connection": "close",
}

TIMEOUT = 15

# ===============================
# トップページ
# ===============================
@app.get("/")
def root():
    return FileResponse("static/index.html")

# ===============================
# 実行処理（完全サーバー処理）
# ===============================
@app.post("/go")
def go(url: str = Form(...), mode: str = Form(...)):
    url = url.strip()

    # https:// 補正
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")

    if mode == "nodeunblocker":
        return RedirectResponse(
            url="/htmlproxy/" + quote(url, safe=""),
            status_code=302
        )

    raise HTTPException(400, "Invalid mode")

# ===============================
# NodeUnblocker Client JS
# ===============================
UNBLOCKER_JS = r"""
<script>
(function () {
  "use strict";
  const PREFIX = "/proxy/";

  function realUrl() {
    const u = location.href;
    if (u.includes("/htmlproxy/")) {
      return decodeURIComponent(u.split("/htmlproxy/")[1]);
    }
    return u;
  }

  const baseUrl = realUrl();

  function fix(u) {
    try {
      if (!u) return u;
      if (/^(data:|blob:|about:|javascript:)/i.test(u)) return u;
      if (u.startsWith(PREFIX)) return u;

      const abs = new URL(u, baseUrl);
      if (!/^https?:$/.test(abs.protocol)) return u;

      return PREFIX + encodeURIComponent(abs.href);
    } catch {
      return u;
    }
  }

  const _fetch = window.fetch;
  if (_fetch) {
    window.fetch = function (i, o) {
      if (typeof i === "string") i = fix(i);
      else if (i instanceof Request) i = new Request(fix(i.url), i);
      return _fetch.call(this, i, o);
    };
  }

  const _open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u, ...r) {
    return _open.call(this, m, fix(u), ...r);
  };

  new MutationObserver(ms => {
    ms.forEach(m => {
      const v = m.target.getAttribute?.(m.attributeName);
      const f = fix(v);
      if (v && v !== f) m.target.setAttribute(m.attributeName, f);
    });
  }).observe(document.documentElement, {
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "href", "poster"]
  });

  console.log("[Web Unblocker] client ready");
})();
</script>
"""

# ===============================
# decode helper
# ===============================
def decode_response(resp: requests.Response) -> str:
    raw = resp.content
    enc = resp.headers.get("Content-Encoding", "")
    try:
        if enc == "gzip":
            raw = gzip.decompress(raw)
        elif enc == "br":
            raw = brotli.decompress(raw)
    except:
        pass
    return raw.decode("utf-8", errors="ignore")

# ===============================
# HTML proxy
# ===============================
@app.get("/htmlproxy/{target:path}")
def html_proxy(target: str):
    url = unquote(target)

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")

    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    html = decode_response(r)

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    inject = f"<base href='{base}'>\n{UNBLOCKER_JS}"

    if "<head>" in html.lower():
        html = html.replace("<head>", "<head>" + inject, 1)
    else:
        html = inject + html

    return HTMLResponse(html, headers={"Cache-Control": "no-store"})

# ===============================
# raw proxy
# ===============================
@app.get("/proxy/{target:path}")
def raw_proxy(target: str):
    url = unquote(target)

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")

    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

    return Response(
        content=r.content,
        status_code=r.status_code,
        headers={
            "Content-Type": r.headers.get("Content-Type", "application/octet-stream"),
            "Cache-Control": "no-store",
        },
        )
