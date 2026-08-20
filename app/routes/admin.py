"""Admin routes: the dynamic product form.

The form template contains no field names. It renders whatever the resolver
returns for the product type bound to the requested category.
"""
from itertools import groupby

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import query, query_one
from app.resolver import resolve, attach_options
from app.values import create_product, ValidationError

router = APIRouter()
templates = None          # injected from main.py


def _context(category_slug):
    """Resolve everything the form needs for a category, or None if unknown."""
    category = query_one(
        "SELECT * FROM category WHERE slug = %s", (category_slug,)
    )
    if not category:
        return None

    ptype = query_one(
        "SELECT pt.* FROM product_type pt "
        "JOIN category_product_type cpt ON cpt.product_type_id = pt.id "
        "WHERE cpt.category_id = %s",
        (category["id"],),
    )
    if not ptype:
        return None

    r = resolve(ptype["id"])
    attributes = attach_options(r["attributes"], ptype["id"])

    grouped = [
        (g, list(items))
        for g, items in groupby(attributes, key=lambda a: a["group_name"])
    ]

    return {
        "category": category,
        "product_type": ptype,
        "attributes": attributes,
        "dependencies": r["dependencies"],
        "rules": r["rules"],
        "grouped": grouped,
    }


@router.get("/admin/products/new", response_class=HTMLResponse)
def choose_category(request: Request):
    """Pick which category to add a product to. Built from the DB, so a new
    vertical appears here with no code change."""
    cats = query(
        "SELECT c.* FROM category c "
        "JOIN category_product_type cpt ON cpt.category_id = c.id "
        "ORDER BY c.sort_order"
    )
    return templates.TemplateResponse(
        request, "choose_category.html", {"categories": cats}
    )


@router.get("/admin/products/new/{category_slug}", response_class=HTMLResponse)
def new_product(request: Request, category_slug: str):
    ctx = _context(category_slug)
    if not ctx:
        return HTMLResponse("Unknown category", status_code=404)

    return templates.TemplateResponse(
        request,
        "product_form.html",
        {**ctx, "values": {}, "form": {}, "error": None},
    )


@router.post("/admin/products/new/{category_slug}", response_class=HTMLResponse)
async def create(request: Request, category_slug: str):
    ctx = _context(category_slug)
    if not ctx:
        return HTMLResponse("Unknown category", status_code=404)

    form = await request.form()

    # multi_option fields submit several values under one name, so they
    # need getlist(); everything else takes a single value.
    data = {}
    for a in ctx["attributes"]:
        if a["data_type"] == "multi_option":
            values = form.getlist(a["code"])
            if values:
                data[a["code"]] = values
        else:
            v = form.get(a["code"])
            if v not in (None, ""):
                data[a["code"]] = v

    try:
        product_id = create_product(
            ctx["product_type"]["id"],
            ctx["category"]["id"],
            form.get("title"),
            form.get("price") or None,
            ctx["attributes"],
            ctx["dependencies"],
            data,
            ctx["rules"],
        )
    except ValidationError as e:
        return templates.TemplateResponse(
            request,
            "product_form.html",
            {**ctx, "values": data, "form": dict(form), "error": str(e)},
            status_code=400,
        )

    return RedirectResponse(f"/products/{product_id}", status_code=303)