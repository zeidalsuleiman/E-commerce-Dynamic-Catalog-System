"""Public catalog routes: product detail pages."""
from itertools import groupby

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.db import query_one
from app.resolver import resolve
from app.values import load_values

router = APIRouter()
templates = None          # injected from main.py

PRODUCT_SQL = """
SELECT p.*, pt.code AS type_code, pt.name AS type_name,
       c.name AS category_name, c.slug AS category_slug
FROM product p
JOIN product_type pt ON pt.id = p.product_type_id
JOIN category c ON c.id = p.primary_category_id
WHERE p.id = %s AND p.status = 'active'
"""


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int):
    product = query_one(PRODUCT_SQL, (product_id,))
    if not product:
        return HTMLResponse("Product not found", status_code=404)

    r = resolve(product["product_type_id"])
    values = load_values(product_id)["display"]

    # Keep only attributes this product actually has a value for.
    specs = [
        {**a, "value": values[a["code"]]}
        for a in r["attributes"]
        if a["code"] in values
    ]

    grouped = [
        (g, list(items))
        for g, items in groupby(specs, key=lambda a: a["group_name"])
    ]

    return templates.TemplateResponse(
        request,
        "product_detail.html",
        {"product": product, "grouped": grouped, "spec_count": len(specs)},
    )