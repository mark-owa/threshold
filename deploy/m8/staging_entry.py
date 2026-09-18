from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.main import app


# Staging-only additive CORS entry for the temporary validation console.
# The application's configured CORS_ORIGINS remains untouched; this outer
# middleware only adds the exact preview origin needed for staging validation.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://threshold-staging-console-odrgx1fhm-markjoshuagalit2-3620.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
