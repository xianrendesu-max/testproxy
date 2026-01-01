from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
import requests
import gzip
import brotli
from urllib.parse import unquote, urlparse
import os

app = FastAPI()

# ===============================
# Static files（重要）
# ===============================
if os.path.isdir("static"):
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
# トップページ（static/index.html）
# ===============================
@app.get("/")
def root():
    return FileResponse("static/index.html")

# ===============================
# NodeUnblocker Client JS（完全修整）
# ===============================
UNBLOCKER_JS = r"""
<script>
(function (global) {
  "use strict";

  const PREFIX = "/proxy/";

  function getRealUrl() {
    try {
      const u = location.href;
      if (u.includes("/htmlproxy/")) {
        return decodeURIComponent(u.split("/htmlproxy/")[1]);
      }
      return u;
    } catch {
      return location.href;
    }
  }

  const config = {
    prefix: PREFIX,
    url: getRealUrl()
  };

  function fixUrl(urlStr) {
    try {
      if (!urlStr || typeof urlStr !== "string") return urlStr;
      if (urlStr.startsWith(PREFIX)) return urlStr;
      if (/^(data:|blob:|about:|javascript:)/i.test(urlStr)) return urlStr;

      const base = new URL(config.url);
      const url = new URL(urlStr, base);

      if (!/^https?:$/.test(url.protocol)) return urlStr;

      return PREFIX + encodeURIComponent(url.href);
    } catch {
      return urlStr;
    }
  }

  if (global.fetch) {
    const _fetch = global.fetch;
    global.fetch = function (input, init) {
      if (typeof input === "string") {
        input = fixUrl(input);
      } else if (input instanceof Request) {
        input = new Request(fixUrl(input.url), input);
      }
      return _fetch.call(this, input, init);
    };
  }

  const _open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u, a, user, pass) {
    return _open.call(this, m, fixUrl(u), a !== false, user, pass);
  };

  const _create = document.createElement.bind(document);
  document.createElement = function (tag) {
    const el = _create(tag);
    ["src", "href", "poster"].forEach(attr => {
      if (attr in el) {
        Object.defineProperty(el, attr, {
          set(v) { el.setAttribute(attr, fixUrl(v)); },
          get() { return el.getAttribute(attr); },
          configurable: true
        });
      }
    });
    return el;
  };

  new MutationObserver(muts => {
    muts.forEach(m => {
      if (m.type === "attributes") {
        const v = m.target.getAttribute(m.attributeName);
        const f = fixUrl(v);
        if (v && v !== f) m.target.setAttribute(m.attributeName, f);
      }
    });
  }).observe(document.documentElement, {
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "href", "poster"]
  });

  console.log("[Web Unblocker] client ready");
})(window);
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

    if "<head" in html.lower():
        idx = html.lower().find("<head")
        end = html.find(">", idx) + 1
        html = html[:end] + inject + html[end:]
    else:
        html = inject + html

    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Type": "text/html; charset=utf-8"
        }
    )

# ===============================
# raw proxy
# ===============================
@app.get("/proxy/{target:path}")
def raw_proxy(target: str):
    url = unquote(target)

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        stream=True,
        allow_redirects=True
    )

    return Response(
        content=r.content,
        status_code=r.status_code,
        headers={
            "Content-Type": r.headers.get(
                "Content-Type", "application/octet-stream"
            ),
            "Cache-Control": "no-store",
        },
    )
