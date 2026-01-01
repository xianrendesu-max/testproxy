from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
import requests
import gzip
import brotli
from urllib.parse import urlparse

app = FastAPI()

# ===============================
# 共通設定
# ===============================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Encoding": "identity",  # ★ 超重要（gzip無効）
    "Connection": "close",
}

TIMEOUT = 15


# ===============================
# Web Unblocker Client JS
# ===============================
UNBLOCKER_JS = r"""
<script>
window.__UNBLOCKER_CONFIG__ = {
  prefix: "/htmlproxy/",
  url: location.href
};
(function () {
  "use strict";

  const config = window.__UNBLOCKER_CONFIG__;
  if (!config) return;

  function fixUrl(urlStr) {
    try {
      if (!urlStr) return urlStr;
      if (urlStr.startsWith(config.prefix)) return urlStr;

      const base = new URL(config.url);
      const url = new URL(urlStr, base);

      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return urlStr;
      }
      return config.prefix + encodeURIComponent(url.href);
    } catch {
      return urlStr;
    }
  }

  if (window.fetch) {
    const _fetch = window.fetch;
    window.fetch = function (resource, init) {
      if (resource && resource.url) {
        resource = new Request(fixUrl(resource.url), resource);
      } else {
        resource = fixUrl(resource.toString());
      }
      return _fetch(resource, init);
    };
  }

  if (window.XMLHttpRequest) {
    const XHR = window.XMLHttpRequest;
    window.XMLHttpRequest = function () {
      const xhr = new XHR();
      const open = xhr.open;
      xhr.open = function (method, url) {
        return open.call(xhr, method, fixUrl(url));
      };
      return xhr;
    };
  }

  const _createElement = document.createElement.bind(document);
  document.createElement = function (tagName, options) {
    const el = _createElement(tagName, options);
    ["src", "href", "poster"].forEach(attr => {
      Object.defineProperty(el, attr, {
        set(value) {
          el.setAttribute(attr, fixUrl(value));
        }
      });
    });
    return el;
  };

})();
</script>
"""


# ===============================
# ヘルパー：レスポンス展開
# ===============================
def decode_response(resp: requests.Response) -> str:
    raw = resp.content
    encoding = resp.headers.get("Content-Encoding", "")

    try:
        if encoding == "gzip":
            raw = gzip.decompress(raw)
        elif encoding == "br":
            raw = brotli.decompress(raw)
    except Exception:
        pass

    return raw.decode("utf-8", errors="ignore")


# ===============================
# HTML プロキシ
# ===============================
@app.get("/htmlproxy/{target:path}")
def html_proxy(target: str):
    try:
        url = requests.utils.unquote(target)

        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Invalid URL")

        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        html = decode_response(r)

        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        # baseタグとJSを注入
        inject = f"""
<base href="{base}/">
{UNBLOCKER_JS}
"""

        if "<head>" in html:
            html = html.replace("<head>", "<head>" + inject, 1)
        else:
            html = inject + html

        return HTMLResponse(
            content=html,
            status_code=200,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-store"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# 通常プロキシ（HTML以外）
# ===============================
@app.get("/proxy/{target:path}")
def raw_proxy(target: str):
    try:
        url = requests.utils.unquote(target)

        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Invalid URL")

        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)

        return Response(
            content=r.content,
            status_code=r.status_code,
            headers={
                "Content-Type": r.headers.get("Content-Type", "application/octet-stream"),
                "Cache-Control": "no-store"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
