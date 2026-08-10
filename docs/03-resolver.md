# 03 — The Resolver

`app/resolver.py`. One function answering one question: **what does this
product type consist of?**

```python
resolve(product_type_id) -> {
    "attributes":   [ {code, label, data_type, input_type, unit,
                       is_filterable, is_required, group_name, sort_order}, ... ],
    "dependencies": { child_code: parent_code },
    "rules":        { trigger_code: { trigger_option_id: [rule, ...] } },
}
```

This is the centrepiece. Four separate parts of the application consume that
one return value:

| Consumer | Reads |
|---|---|
| Admin form | `input_type`, `options`, `is_required`, `group_name`, `sort_order`, `dependencies`, `rules` |
| Save validator | `data_type`, `is_required`, `dependencies`, `rules` |
| Filter sidebar | entries where `is_filterable` |
| Product spec table | `group_name`, `label`, `unit` |

Write it once, correctly, and adding a vertical updates all four with no code.

---

## What it must do

1. Walk the type chain upward — `CAR → VEHICLE → PRODUCT`
2. Apply bindings **root-first** so children override parents
3. Return dependencies and rules alongside the attribute list

Point 3 was designed in from the start rather than added later. If the
resolver returned a bare list, adding cascades or rules would change its
return shape and force every consumer to be revised.

---

## Step 1 — walking the chain

```sql
WITH RECURSIVE chain AS (
    SELECT id, parent_type_id, 0 AS depth
    FROM product_type
    WHERE id = %s
    UNION ALL
    SELECT pt.id, pt.parent_type_id, c.depth + 1
    FROM product_type pt
    JOIN chain c ON pt.id = c.parent_type_id
)
SELECT id, depth FROM chain ORDER BY depth DESC
```

The CTE walks *up*, so `CAR` is depth 0 and `PRODUCT` is depth 2.
`ORDER BY depth DESC` reverses that to `PRODUCT, VEHICLE, CAR` — root first.

**That ordering is the entire override mechanism.**

One query for the whole chain, not one per level — a per-level loop would be
an N+1 query pattern.

### Cycle guard

```python
ids = [r["id"] for r in rows]
if len(ids) != len(set(ids)):
    raise ValueError(f"Cycle in product_type hierarchy from {product_type_id}")
```

Someone will eventually set a parent that points back down the tree. Without
this, MySQL's recursive CTE spins until `cte_max_recursion_depth` kills it
with an unhelpful error. The check is a duplicate-id test on the returned
chain.

---

## Step 2 — fetching bindings

```sql
SELECT a.id AS attribute_id, a.code, a.label, a.data_type, a.input_type,
       a.unit, a.is_filterable,
       pta.product_type_id, pta.is_required, pta.group_name, pta.sort_order
FROM product_type_attribute pta
JOIN attribute a ON a.id = pta.attribute_id
WHERE pta.product_type_id IN (...)
```

One query covering every type in the chain.

---

## Step 3 — the merge

```python
merged = {}
for type_id in chain:                    # root -> leaf
    for r in by_type.get(type_id, []):
        merged[r["code"]] = dict(r)      # later write wins
```

Six lines, and this is the whole inheritance mechanism.

Keyed by attribute `code`, written in chain order. Later writes overwrite
earlier ones. Because the leaf type is processed last, **the child always
wins.**

### The override, verified

The seed binds `city` as optional on `PRODUCT` and required on `CAR`:

| Chain step | Type | `city` state after this step |
|---|---|---|
| 1 | `PRODUCT` | required: **no**, group: General |
| 2 | `VEHICLE` | unchanged |
| 3 | `CAR` | required: **yes**, group: General |

`resolve(CAR)` returns `city` with `is_required = 1`. If the chain were
processed leaf-first, the parent would win and the value would be 0 — which
makes this a live test of merge order in the seed data.

Note that the attribute itself is defined **once**. Only the binding differs.

---

## Step 4 — sorting

```python
attributes = sorted(
    merged.values(),
    key=lambda a: (a["group_name"] or "", a["sort_order"]),
)
```

Grouped, then ordered within each group. This ordering is what the admin form
and the spec table render directly — neither does any sorting of its own.

---

## Step 5 — dependencies

```python
{"model": "make"}
```

Derived from `attribute_option_dependency` rather than stored in a dedicated
table:

```sql
SELECT DISTINCT ca.code AS child_code, pa.code AS parent_code
FROM attribute_option_dependency d
JOIN attribute_option co ON co.id = d.child_option_id
JOIN attribute_option po ON po.id = d.parent_option_id
JOIN attribute ca ON ca.id = co.attribute_id
JOIN attribute pa ON pa.id = po.attribute_id
```

Since every `model` option links to a `make` option, the attribute-level
relationship falls out of the option-level data. One fewer table.

**Trade-off:** a dependency cannot be declared before any options exist. An
explicit `attribute_dependency` table would be clearer at scale.

**Known limitation:** `get_dependencies` currently returns all dependencies
globally rather than filtering to attributes in the resolved set. Harmless
with one dependency; would need scoping at larger volumes.

---

## Step 6 — rules

```python
{"condition": {1: [ {...force_value...} ], 2: [ {...min...} ]}}
```

Nested by trigger option, because `new` and `used` fire different rules.
Scoped to the type chain exactly like attributes, so a rule bound to `VEHICLE`
resolves for both `CAR` and `TRUCK`.

Detailed in `06-constraint-rules.md`.

---

## Why raw SQL rather than an ORM

Three concrete blockers, not preferences:

**1. Recursive CTEs.** Django's ORM and SQLAlchemy's declarative layer have no
syntax for `WITH RECURSIVE`. This alone forces raw SQL for the chain walk.

**2. Runtime table selection.** The value layer chooses among seven tables
based on `attribute.data_type`. ORMs bind model classes at import time;
expressing this would require a dict of model classes and `getattr`
indirection that reads worse than the SQL.

**3. Dynamic N-way `EXISTS`.** Filtering on five attributes means five
subqueries built from user input. Expressible with ORM constructs, but the
result is harder to debug and often generates worse SQL.

The project therefore uses PyMySQL directly with a small helper module
(`app/db.py`). Every query in the repository is visible and explainable.

---

## Verification

```
GET /api/resolve/CAR           → 9 attributes,  dependencies {model: make}, rules present
GET /api/resolve/TRUCK         → 9 attributes,  payload/axles instead of body_type/seats
GET /api/resolve/MOBILE_PHONE  → 7 attributes,  Display/General/Performance groups
```

`CAR` and `TRUCK` share the same seven inherited attributes and differ only in
their two leaf-specific ones — from a single set of `VEHICLE` bindings, with
no duplication.

---

## Caching

Not implemented. The resolved set changes only when an administrator edits
definitions, which is rare, so it is an obvious cache target keyed by
`product_type_id` and invalidated on writes to `product_type`,
`product_type_attribute`, `attribute`, or `attribute_rule`.

Left out deliberately: at sample scale the query is trivially fast, and a
cache would obscure the mechanism the project is meant to demonstrate.
