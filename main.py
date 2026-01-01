from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
import requests
import gzip
import brotli
from urllib.parse import unquote, urlparse

app = FastAPI()

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
# NodeUnblocker Client JS
# ===============================
UNBLOCKER_JS = r"""
<script>
(function (global) {
  "use strict";

  const config = {
    prefix: "/proxy/",
    url: location.href
  };

  function fixUrl(urlStr) {
    try {
      if (!urlStr || urlStr.startsWith(config.prefix)) return urlStr;
      if (/^(data:|blob:|about:)/.test(urlStr)) return urlStr;

      const base = new URL(config.url);
      const url = new URL(urlStr, base);

      if (!/^https?:$/.test(url.protocol)) return urlStr;
      return config.prefix + url.href;
    } catch {
      return urlStr;
    }
  }

  const _fetch = global.fetch;
  if (_fetch) {
    global.fetch = function (input, init) {
      if (typeof input === "string") input = fixUrl(input);
      else if (input instanceof Request) input = new Request(fixUrl(input.url), input);
      return _fetch.call(this, input, init);
    };
  }

  const _open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u) {
    return _open.call(this, m, fixUrl(u));
  };

  const _create = document.createElement.bind(document);
  document.createElement = function (tag) {
    const el = _create(tag);
    ["src", "href", "poster"].forEach(attr => {
      if (attr in el) {
        Object.defineProperty(el, attr, {
          set(v) { el.setAttribute(attr, fixUrl(v)); },
          get() { return el.getAttribute(attr); }
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
        if (v !== f) m.target.setAttribute(m.attributeName, f);
      }
    });
  }).observe(document.documentElement, {
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "href", "poster"]
  });

  console.log("[Web Unblocker] ready");
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

    inject = f"<base href='{base}'>{UNBLOCKER_JS}"

    if "<head>" in html:
        html = html.replace("<head>", "<head>" + inject, 1)
    else:
        html = inject + html

    return HTMLResponse(html, headers={"Cache-Control": "no-store"})

# ===============================
# raw proxy
# ===============================
@app.get("/proxy/{target:path}")
def raw_proxy(target: str):
    if not target.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")

    r = requests.get(target, headers=HEADERS, timeout=TIMEOUT, stream=True)

    return Response(
        content=r.content,
        status_code=r.status_code,
        headers={
            "Content-Type": r.headers.get("Content-Type", "application/octet-stream"),
            "Cache-Control": "no-store",
        },
    )
