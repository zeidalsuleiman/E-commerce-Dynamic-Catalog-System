# 04 — Value Storage and Insertion Methods

`app/values.py` handles reading and writing attribute values across seven
tables. This document also covers **every method available for getting data
into the system**, which is the practical question when operating it.

---

## Part 1 — The type router

```python
TABLE_BY_TYPE = {
    "int":          ("product_value_int",          "value"),
    "decimal":      ("product_value_decimal",      "value"),
    "varchar":      ("product_value_varchar",      "value"),
    "text":         ("product_value_text",         "value"),
    "datetime":     ("product_value_datetime",     "value"),
    "option":       ("product_value_option",       "option_id"),
    "multi_option": ("product_value_multi_option", "option_id"),
}
```

**This is the single source of truth for where a value lives.** Nothing else
in the codebase decides. If this logic spreads across multiple modules, EAV
becomes painful to maintain — keeping it in one dict is what makes an eighth
data type a contained change rather than a hunt.

Note that `option` maps to `option_id`, not `value` — enums store a foreign
key, which is why the router returns a column name as well as a table name.

### SQL injection

Table and column names are interpolated into the SQL string because SQL cannot
parameterise identifiers. This is safe **only** because they come from this
hardcoded dict, keyed by a value the database constrains to an `ENUM`. Every
actual value remains a bound parameter.

---

## Part 2 — Writing

### Coercion

Form data arrives as strings; the database wants typed values.

```python
def coerce(data_type, raw, code):
    if data_type == "int":      return int(raw)
    if data_type == "decimal":  return Decimal(str(raw))
    if data_type in ("varchar", "text"): return str(raw).strip()
    if data_type == "datetime": return datetime.fromisoformat(str(raw))
    if data_type in ("option", "multi_option"): return int(raw)   # option_id
```

### Validation

`validate()` iterates over the **definitions**, not the submitted data. That
ordering matters: iterating over submitted data would silently skip a missing
required field.

It also rejects unknown fields — posting `ram_gb` to a car fails loudly rather
than being ignored.

### Dependency validation

```python
cur.execute(
    "SELECT 1 FROM attribute_option_dependency "
    "WHERE child_option_id = %s AND parent_option_id = %s", (child, parent))
if not cur.fetchone():
    raise ValidationError(...)
```

This is what stops "BMW C-Class" reaching the database. The cascade dropdown
makes invalid combinations hard to select in a browser, but a crafted POST
bypasses the frontend entirely — so the check runs server-side.

### The write itself

```python
def save_values(cur, product_id, definitions, cleaned):
    _delete_existing(cur, product_id, [d["attribute_id"] for d in definitions])
    for code, value in cleaned.items():
        table, column = TABLE_BY_TYPE[by_code[code]["data_type"]]
        ...
```

**Delete-then-insert** rather than upsert. Simpler, and it correctly handles a
multi-select shrinking from three values to one. At this scale the cost is
irrelevant.

### Transaction boundary

```python
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO product ...")
        product_id = cur.lastrowid
        save_values(cur, product_id, definitions, cleaned)
# commits here, or rolls back everything
```

One product insert plus N value inserts land together or not at all. A product
row without its values is worse than a rejected save.

This is why `create_product` uses `get_conn()` directly rather than the
`query()` / `execute()` helpers — those each open their own connection and
therefore their own transaction.

---

## Part 3 — Reading

```python
load_values(product_id) -> {
    "display":    {"make": "Mercedes-Benz", "year": "2021"},
    "option_ids": {"make": 6},
}
```

A `UNION ALL` across all seven value tables, pivoted into dicts in Python.
`CAST(... AS CHAR)` is required because `UNION ALL` needs matching column
types across branches.

**Two return shapes on purpose.** The spec table needs "Mercedes-Benz"; an
edit form needs `6` to pre-select the dropdown. Same rows, two consumers.

---

# Part 4 — Insertion methods

Four ways to get data into the system, each suited to different work.

## Method 1 — The dynamic web form

**`/admin/products/new/{category_slug}`**

The normal path for adding products. The form renders itself from the
resolver, validates client-side, and posts to the same URL.

| | |
|---|---|
| Best for | Day-to-day product entry by non-technical users |
| Validation | Full — types, required, dependencies, constraint rules |
| Cascades | Yes, live |
| Effort | Fill in fields |

This is the only method that requires no technical knowledge, and the only one
where the cascade and rule UX actually assists the person entering data.

## Method 2 — The JSON API

**`POST /api/test/product`**

```json
{
  "type_code": "CAR",
  "category_slug": "cars",
  "title": "2021 Mercedes C-Class",
  "price": 28500,
  "attributes": {
    "condition": 2, "city": 3, "make": 6, "model": 10,
    "year": 2021, "mileage_km": 45000,
    "transmission": 19, "body_type": 21, "seats": 5
  }
}
```

Option attributes take **option ids**; scalar attributes take raw values.

| | |
|---|---|
| Best for | Testing, scripted imports, integration |
| Validation | Full — identical code path to the form |
| Cascades | N/A (no UI), but dependencies are still enforced |
| Effort | Construct JSON, know the option ids |

**Important:** this endpoint passes `rules` to `create_product`. During
development it did not, which meant constraint rules were silently skipped —
a new car with 50,000 km saved successfully. That bug is documented in
`06-constraint-rules.md` because it illustrates a real risk of optional
parameters.

Query the ids you need:

```sql
SELECT o.id, a.code AS attr, o.code, o.label
FROM attribute_option o JOIN attribute a ON a.id = o.attribute_id
ORDER BY a.code, o.sort_order;
```

## Method 3 — Raw SQL

**`sql/add_product_type.sql`**

For dictionary changes — new categories, product types, attributes, options,
bindings. Runs in DBeaver against a live database; the application picks up
changes on the next request with no restart.

```sql
-- A complete new vertical in three statements
INSERT INTO product_type (parent_type_id, code, name)
SELECT id, 'DESK', 'Desk' FROM product_type WHERE code = 'FURNITURE';

INSERT INTO category (parent_id, slug, name, sort_order)
SELECT id, 'desks', 'Desks', 3 FROM category WHERE slug = 'furniture';

INSERT INTO category_product_type (category_id, product_type_id)
SELECT c.id, pt.id FROM category c, product_type pt
WHERE c.slug = 'desks' AND pt.code = 'DESK';
```

| | |
|---|---|
| Best for | Small dictionary changes; documentation |
| Validation | None — foreign keys only |
| Effort | Low for a few rows, high for many |

**Ids are looked up by code**, never hardcoded. `INSERT ... SELECT ... WHERE
code = '...'` makes the script portable to any database with the same seed —
which is what makes it usable as documentation.

**Caution:** `INSERT ... SELECT` inserts zero rows *silently* if the `WHERE`
matches nothing. Verify the parent exists first.

### Adding a product in raw SQL

Possible but instructive in its difficulty:

```sql
INSERT INTO product (product_type_id, primary_category_id, title, price, status)
SELECT pt.id, c.id, '2019 BMW 3 Series', 22000, 'active'
FROM product_type pt, category c
WHERE pt.code = 'CAR' AND c.slug = 'cars';

SET @pid = LAST_INSERT_ID();

INSERT INTO product_value_option (product_id, attribute_id, option_id)
SELECT @pid, a.id, o.id
FROM attribute a JOIN attribute_option o ON o.attribute_id = a.id
WHERE a.code = 'make' AND o.code = 'bmw';
-- ... repeated for every option attribute

INSERT INTO product_value_int (product_id, attribute_id, value)
SELECT @pid, id, 2019 FROM attribute WHERE code = 'year';
-- ... repeated for every scalar attribute
```

Nine statements for one car, and **nothing verifies** that required fields
were filled, that the model is valid for the make, or that constraint rules
were respected.

**That asymmetry is the design.** Dictionary changes are rare, structural, and
administrative — SQL is appropriate. Product entry is frequent and validated —
that is what the application layer exists for.

## Method 4 — Python scripts

**`sql/seed.py`, `sql/add_furniture.py`**

For building whole verticals. Three advantages over SQL:

**Captured ids.** `cur.lastrowid` lets later inserts reference earlier ones
directly. In SQL every reference repeats a lookup subquery — with nine model
links, that subquery is written nine times.

**Loops.** Nine models with dependency links and type scopes is 27 inserts;
in Python it is a list and a three-line loop. Adding a tenth model is one list
entry.

**Transactions and re-runnability.** `get_conn()` wraps everything — if
statement 40 fails, the first 39 roll back, so you never get a half-built
vertical. A `cleanup()` or `wipe()` function at the top makes the script
idempotent, so it can be tweaked and re-run freely.

| | |
|---|---|
| Best for | Whole verticals, seed data, bulk dictionary work |
| Validation | None beyond foreign keys (bypasses `values.py`) |
| Effort | Higher upfront, much lower at scale |

### The rule of thumb

> If you would copy-paste a statement more than three times with only the
> values changing, use Python.

---

## Choosing a method

| Task | Method |
|---|---|
| Add one product | Web form |
| Add many products from a data source | JSON API, scripted |
| Add one attribute to an existing type | Raw SQL |
| Add a whole new vertical | Python script |
| Show someone how the model works | Raw SQL — nothing between reader and database |

Both `add_product_type.sql` and `add_furniture.py` demonstrate the same
capability. The choice is about authoring ergonomics, not capability — and
**neither is a schema change.**

---

## Bulk import: not implemented

A production catalog would need CSV or spreadsheet import for sellers. The
foundation is there — `create_product` accepts a plain dict and enforces
everything — so an import path would be a loop with per-row error collection
rather than new architecture.

Deliberately out of scope. Noted in `07-limitations.md`.
