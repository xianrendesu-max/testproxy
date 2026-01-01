from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import requests
import os
import re
import urllib.parse

app = FastAPI()

# ===============================
# Config
# ===============================
PREFIX = "/proxy/"
TIMEOUT = 20

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# ===============================
# Static (UI)
# ===============================
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")

# ===============================
# Injected Client Script
# ===============================
@app.get("/inject/unblocker.js")
def unblocker_js():
    return FileResponse(
        "inject/unblocker.js",
        media_type="application/javascript"
    )

# ===============================
# Utility
# ===============================
def rewrite_html_base(html: str, target_url: str) -> str:
    """
    <base> タグを強制挿入（相対URL完全対策）
    """
    base_tag = f'<base href="{target_url}">'
    if "<base" in html.lower():
        return html
    return re.sub(
        r"<head[^>]*>",
        lambda m: m.group(0) + "\n" + base_tag,
        html,
        flags=re.IGNORECASE
    )

def inject_unblocker(html: str, target_url: str) -> str:
    """
    NodeUnblocker クライアント注入
    """
    inject = f"""
<!-- NodeUnblocker injected -->
<script>
window.__UNBLOCKER_CONFIG__ = {{
  prefix: "{PREFIX}",
  url: "{target_url}"
}};
</script>
<script src="/inject/unblocker.js"></script>
<script>
if (window.unblockerInit) {{
  unblockerInit(window.__UNBLOCKER_CONFIG__);
}}
</script>
"""
    return re.sub(
        r"</head>",
        inject + "\n</head>",
        html,
        flags=re.IGNORECASE
    )

# ===============================
# Core Proxy (NodeUnblocker)
# ===============================
@app.api_route("/proxy/{url:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, url: str):
    try:
        # --- decode ---
        target_url = urllib.parse.unquote(url)

        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            raise HTTPException(status_code=400, detail="Invalid URL")

        # --- headers ---
        headers = dict(BASE_HEADERS)
        for k, v in request.headers.items():
            if k.lower() in ["host", "content-length"]:
                continue
            headers[k] = v

        # --- body ---
        body = await request.body()

        # --- request ---
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=body if body else None,
            stream=True,
            allow_redirects=True,
            timeout=TIMEOUT,
        )

        content_type = resp.headers.get("content-type", "")

        # ---------- HTML ----------
        if "text/html" in content_type:
            html = resp.text
            html = rewrite_html_base(html, target_url)
            html = inject_unblocker(html, target_url)
            return HTMLResponse(html, status_code=resp.status_code)

        # ---------- Stream (video/audio) ----------
        if any(x in content_type for x in ["video", "audio", "application/octet-stream"]):
            return StreamingResponse(
                resp.iter_content(chunk_size=8192),
                status_code=resp.status_code,
                media_type=content_type,
                headers={
                    "Accept-Ranges": "bytes"
                }
            )

        # ---------- Others ----------
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=content_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
