"""Public catalog routes: product detail pages."""
from itertools import groupby

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.db import query_one
from app.resolver import resolve, attach_options
from app.values import load_values

from app.filters import parse_filters, search_products, facet_counts

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


@router.get("/c/{category_slug}", response_class=HTMLResponse)
def category_page(request: Request, category_slug: str):
    category = query_one("SELECT * FROM category WHERE slug = %s",
                         (category_slug,))
    if not category:
        return HTMLResponse("Unknown category", status_code=404)

    ptype = query_one(
        "SELECT pt.* FROM product_type pt "
        "JOIN category_product_type cpt ON cpt.product_type_id = pt.id "
        "WHERE cpt.category_id = %s",
        (category["id"],),
    )
    if not ptype:
        return HTMLResponse("No product type for this category",
                            status_code=404)

    r = resolve(ptype["id"])
    attributes = attach_options(r["attributes"], ptype["id"])
    filterable = [a for a in attributes if a["is_filterable"]]

    params = request.query_params
    filters = parse_filters(params, attributes)
    products = search_products(category["id"], filters)

    # Attach counts and current selections to each facet.
    active = {f["attr"]["code"]: f for f in filters}
    facets = []
    for a in filterable:
        entry = {**a, "selected": []}
        if a["data_type"] in ("option", "multi_option"):
            entry["counts"] = facet_counts(category["id"], filters, a)
            if a["code"] in active:
                entry["selected"] = active[a["code"]]["values"]
        else:
            entry["min_value"] = params.get(f"{a['code']}_min", "")
            entry["max_value"] = params.get(f"{a['code']}_max", "")
        facets.append(entry)

    return templates.TemplateResponse(
        request,
        "category.html",
        {
            "category": category,
            "product_type": ptype,
            "facets": facets,
            "products": products,
            "filter_count": len(filters),
        },
    )