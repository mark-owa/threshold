from fastapi import Request
from fastapi.responses import FileResponse

from app.main import app


@app.middleware("http")
async def staging_frontend_csp(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' blob: https://esm.sh; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https://esm.sh; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
    return response


@app.get("/", include_in_schema=False)
def staging_frontend():
    return FileResponse("/app/frontend_index.html", media_type="text/html")
