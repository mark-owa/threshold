from fastapi.responses import FileResponse
from app.main import app

@app.get("/", include_in_schema=False)
def staging_frontend():
    return FileResponse("/app/frontend_index.html", media_type="text/html")
