from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.db import query_one

app = FastAPI(title="Dynamic Catalog")


@app.get("/health")
def health():
    """Confirm the API is up and the database answers."""
    row = query_one("SELECT VERSION() AS version")
    tables = query_one(
        "SELECT COUNT(*) AS n FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE()"
    )
    return {
        "status": "ok",
        "mysql_version": row["version"],
        "table_count": tables["n"],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return "<h1>Dynamic Catalog</h1><p><a href='/health'>/health</a></p>"