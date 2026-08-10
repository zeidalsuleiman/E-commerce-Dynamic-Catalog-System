from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.db import query_one
from app.resolver import resolve
from app.values import create_product, load_values, ValidationError
from app.resolver import resolve
from fastapi import HTTPException

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


@app.get("/api/resolve/{code}")
def api_resolve(code: str):
    """Debug: resolved attribute set for a product type code."""
    row = query_one("SELECT id FROM product_type WHERE code = %s", (code,))
    if not row:
        return {"error": f"No product type: {code}"}
    return resolve(row["id"])


@app.post("/api/test/product")
def api_test_product(payload: dict):
    """Debug: create a product. Body: {type_code, category_slug, title, price, attributes}"""
    t = query_one("SELECT id FROM product_type WHERE code = %s",
                  (payload["type_code"],))
    c = query_one("SELECT id FROM category WHERE slug = %s",
                  (payload["category_slug"],))
    if not t or not c:
        raise HTTPException(404, "Unknown type or category")

    r = resolve(t["id"])
    try:
        pid = create_product(
            t["id"], c["id"], payload["title"], payload.get("price"),
            r["attributes"], r["dependencies"], payload["attributes"],
        )
    except ValidationError as e:
        raise HTTPException(400, str(e))
    return {"product_id": pid}


@app.get("/api/test/product/{product_id}")
def api_get_product(product_id: int):
    p = query_one("SELECT * FROM product WHERE id = %s", (product_id,))
    if not p:
        raise HTTPException(404, "Not found")
    return {"product": p, "values": load_values(product_id)}