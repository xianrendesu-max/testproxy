from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
import requests
import os
import re

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

PREFIX = "/proxy/"

# ===============================
# Static (UI)
# ===============================
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")

# ===============================
# Inject JS
# ===============================
@app.get("/inject/unblocker.js")
def unblocker_js():
    return FileResponse(
        "inject/unblocker.js",
        media_type="application/javascript"
    )

# ===============================
# Core Proxy
# ===============================
@app.get("/proxy/{url:path}")
def proxy(url: str):
    try:
        target_url = url

        r = requests.get(
            target_url,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True
        )

        content_type = r.headers.get("content-type", "")

        # ---------- HTML ----------
        if "text/html" in content_type:
            html = r.text

            inject = f"""
<script>
window.__UNBLOCKER_CONFIG__ = {{
  prefix: "{PREFIX}",
  url: "{target_url}"
}};
</script>
<script src="/inject/unblocker.js"></script>
"""

            html = re.sub(
                r"</head>",
                inject + "\n</head>",
                html,
                flags=re.IGNORECASE
            )

            return HTMLResponse(html)

        # ---------- Others ----------
        return Response(
            content=r.content,
            status_code=r.status_code,
            media_type=content_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
