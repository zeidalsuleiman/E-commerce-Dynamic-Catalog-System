"""JSON endpoints for the dynamic form."""
from fastapi import APIRouter

from app.db import query

router = APIRouter()

CHILD_OPTIONS_SQL = """
SELECT o.id, o.code, o.label
FROM attribute_option o
JOIN attribute a ON a.id = o.attribute_id
JOIN attribute_option_dependency d ON d.child_option_id = o.id
LEFT JOIN attribute_option_type_scope s ON s.option_id = o.id
WHERE a.code = %s
  AND d.parent_option_id = %s
  AND (s.product_type_id = %s OR s.option_id IS NULL)
GROUP BY o.id, o.code, o.label, o.sort_order
ORDER BY o.sort_order, o.label
"""


@router.get("/api/options/{attribute_code}")
def child_options(attribute_code: str, parent_option_id: int,
                  product_type_id: int):
    """Options for a dependent attribute, filtered by parent choice and type."""
    rows = query(CHILD_OPTIONS_SQL,
                 (attribute_code, parent_option_id, product_type_id))
    return {"options": rows}