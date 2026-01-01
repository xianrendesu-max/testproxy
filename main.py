import requests
import urllib.parse
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# ===============================
# Static files
# ===============================
app.mount("/static", StaticFiles(directory="static"), name="static")

# ===============================
# Global headers
# ===============================
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# ===============================
# Utils
# ===============================
def validate_url(url: str) -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    return url


def rewrite_html_links(html: str, base_url: str) -> str:
    """
    HTML 内の href / src を /htmlproxy/ 経由に書き換える
    """
    prefix = "/htmlproxy/"

    def convert(url: str) -> str:
        try:
            abs_url = urllib.parse.urljoin(base_url, url)
            return prefix + urllib.parse.quote(abs_url, safe="")
        except Exception:
            return url

    result = ""
    i = 0
    while i < len(html):
        if html.startswith("href=\"", i) or html.startswith("src=\"", i):
            attr = "href=\"" if html.startswith("href=\"", i) else "src=\""
            result += attr
            i += len(attr)
            start = i
            while i < len(html) and html[i] != "\"":
                i += 1
            raw_url = html[start:i]
            result += convert(raw_url) + "\""
            i += 1
        elif html.startswith("href='", i) or html.startswith("src='", i):
            attr = "href='" if html.startswith("href='", i) else "src='"
            result += attr
            i += len(attr)
            start = i
            while i < len(html) and html[i] != "'":
                i += 1
            raw_url = html[start:i]
            result += convert(raw_url) + "'"
            i += 1
        else:
            result += html[i]
            i += 1

    return result


# ===============================
# Routes
# ===============================
@app.get("/", response_class=HTMLResponse)
def root():
    return FileResponse("static/index.html")


# ===============================
# HTML Proxy
# ===============================
@app.get("/htmlproxy/{encoded_url:path}")
def html_proxy(encoded_url: str):
    try:
        target_url = urllib.parse.unquote(encoded_url)
        target_url = validate_url(target_url)

        response = requests.get(
            target_url,
            headers=DEFAULT_HEADERS,
            timeout=15,
        )

        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type:
            html = response.text
            rewritten = rewrite_html_links(html, target_url)
            return HTMLResponse(
                content=rewritten,
                status_code=response.status_code,
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=content_type,
        )

    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="Upstream Error")


# ===============================
# NodeUnblocker style proxy
# ===============================
@app.api_route(
    "/proxy/{target_url:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def node_unblocker_proxy(request: Request, target_url: str):
    target_url = validate_url(target_url)

    method = request.method
    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()

    try:
        upstream = requests.request(
            method=method,
            url=target_url,
            headers=headers,
            data=body if body else None,
            cookies=request.cookies,
            allow_redirects=False,
            timeout=20,
        )

        excluded_headers = {
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        }

        response_headers = {}
        for k, v in upstream.headers.items():
            if k.lower() not in excluded_headers:
                response_headers[k] = v

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=response_headers,
        )

    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="Upstream Error")


# ===============================
# Health check (Render)
# ===============================
@app.get("/health")
def health():
    return {"status": "ok"}    
