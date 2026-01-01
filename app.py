from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
import requests
import urllib.parse
import re

app = FastAPI()

# ===============================
# Static
# ===============================
app.mount("/static", StaticFiles(directory="static"), name="static")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

TIMEOUT = 25


# ===============================
# UI
# ===============================
@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


# ===============================
# NodeUnblocker style proxy
# ===============================
@app.api_route("/proxy/{url:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def raw_proxy(url: str, request: Request):
    target = urllib.parse.unquote(url)

    try:
        resp = requests.request(
            method=request.method,
            url=target,
            headers=HEADERS,
            data=request.body(),
            stream=True,
            allow_redirects=True,
            timeout=TIMEOUT,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    excluded = [
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    ]

    headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded
    }

    return StreamingResponse(
        resp.iter_content(chunk_size=8192),
        status_code=resp.status_code,
        headers=headers,
        media_type=resp.headers.get("content-type"),
    )


# ===============================
# HTML Proxy
# ===============================
@app.get("/htmlproxy/{url:path}", response_class=HTMLResponse)
def html_proxy(url: str):
    target_url = urllib.parse.unquote(url)

    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=TIMEOUT)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type:
        return Response(resp.content, media_type=content_type)

    html = resp.text
    prefix = "/htmlproxy/"

    inject = f"""
<script src="/static/unblocker.js"></script>
<script>
unblockerInit({{
  prefix: "{prefix}",
  url: "{target_url}"
}});
</script>
"""

    if "</head>" in html:
        html = html.replace("</head>", inject + "\n</head>", 1)
    else:
        html = inject + html

    if "<base" not in html:
        html = re.sub(
            r"<head[^>]*>",
            lambda m: m.group(0) + f'<base href="{prefix}{target_url}">',
            html,
            count=1,
        )

    return HTMLResponse(html)


# ===============================
# HTML Proxy Assets
# ===============================
@app.api_route("/htmlproxy/{url:path}", methods=["POST", "PUT", "DELETE", "PATCH"])
def html_proxy_assets(url: str, request: Request):
    target = urllib.parse.unquote(url)

    try:
        resp = requests.request(
            method=request.method,
            url=target,
            headers=HEADERS,
            data=request.body(),
            stream=True,
            timeout=TIMEOUT,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    excluded = [
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    ]

    headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded
    }

    return StreamingResponse(
        resp.iter_content(chunk_size=8192),
        status_code=resp.status_code,
        headers=headers,
        media_type=resp.headers.get("content-type"),
)
