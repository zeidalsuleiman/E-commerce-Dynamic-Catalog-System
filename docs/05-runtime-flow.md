# 05 — Runtime Flow

Two workflows. One runs once per vertical, by an administrator. The other runs
on every page load.

---

## Workflow A — Setup (once per vertical)

1. **Create the category tree** — rows in `category`
2. **Create the product types** — rows in `product_type` with `parent_type_id`
3. **Create or reuse attributes** — rows in `attribute`
4. **Create options, dependencies, scopes** — `attribute_option`,
   `attribute_option_dependency`, `attribute_option_type_scope`
5. **Bind attributes to types** — `product_type_attribute`; shared attributes
   go on the parent type
6. **Link category to type** — `category_product_type`

Step 6 is the moment the vertical goes live. Before it, the runtime lookup
finds nothing. After it, the admin form, the filters, and the spec table all
exist.

**Every step is an `INSERT`.** No step is a migration.

Step 5 is the one requiring judgment: push an attribute **as high as it is
still true**. `year` is true for every vehicle, so it binds to `VEHICLE` and
both cars and trucks inherit it. `seats` binds to `CAR` alone. Getting this
wrong in the safe direction (too low) means duplicating bindings later; too
high forces irrelevant fields onto unrelated types. Bias toward too low —
moving an attribute up later is a small data migration, moving it down after
products have used it means deleting values.

---

## Workflow B — Runtime (every request)

### Stage 1 — The user opens a category

`/c/cars`

```
slug "cars" → category_id 302
category_id → category_product_type → product_type_id (CAR)
resolve(CAR) → walks CAR → VEHICLE → PRODUCT
```

The resolver returns attributes, dependencies, and rules. This result changes
only when an administrator edits definitions, making it the obvious cache
target.

### Stage 2 — Render the filter sidebar

Take the resolved list, keep `is_filterable = 1`, render one widget per
`input_type`. Option attributes fetch their options scoped to the current
product type:

```sql
SELECT o.id, o.label FROM attribute_option o
LEFT JOIN attribute_option_type_scope s ON s.option_id = o.id
WHERE o.attribute_id = %s
  AND (s.product_type_id = %s OR s.option_id IS NULL)
```

The `OR s.option_id IS NULL` clause means unscoped options are available
everywhere, keeping the common case simple.

### Stage 3 — The user applies filters

URL becomes `/c/cars?make=6&transmission=19&year_min=2020`.

Parsed by `parse_filters()` in `app/filters.py`, which recognises two shapes:

| Param shape | Meaning |
|---|---|
| `?make=6` (repeatable) | Option equality; multiple values OR together |
| `?year_min=2018&year_max=2022` | Range bounds on a numeric attribute |

### Stage 4 — The result query

```sql
SELECT p.id, p.title, p.price
FROM product p
WHERE p.primary_category_id = %s
  AND p.status = 'active'
  AND EXISTS (SELECT 1 FROM product_value_option v
              WHERE v.product_id = p.id AND v.attribute_id = 3
                AND v.option_id IN (6))
  AND EXISTS (SELECT 1 FROM product_value_int v
              WHERE v.product_id = p.id AND v.attribute_id = 5
                AND v.value >= 2020)
ORDER BY p.created_at DESC
LIMIT 24
```

Two rules the builder always follows:

**Category filter first.** It cuts the candidate set before any attribute
subquery runs.

**One `EXISTS` per active filter.** Multiple values within one attribute
become `IN (...)` — OR within a filter, AND between filters. That is how
faceted search is expected to behave: "Mercedes or BMW, and automatic."

### Stage 5 — Facet counts

For each filterable attribute, count within the current result set:

```python
others = [f for f in filters if f["attr"]["code"] != attribute["code"]]
```

**The attribute's own filter is excluded from its own count.** Without this,
selecting Mercedes would make BMW show `(0)` — because you would be counting
within results already restricted to Mercedes. Every faceted search does this
exclusion, and it is the thing most implementations get wrong first.

One query per facet. This is the expensive part of the design and the reason a
search index becomes non-optional at scale.

### Stage 6 — The user clicks a product

`/products/101`

1. Load the product row → gives `product_type_id`
2. `resolve(product_type_id)` → attribute definitions
3. `load_values(101)` → `UNION ALL` across value tables, pivoted
4. Join values against definitions, keeping only attributes that have a value
5. Group by `group_name`, order by `sort_order`, append `unit`

The spec table **iterates over the definitions, not the values.** That gives
correct grouping and ordering for free, and skips optional attributes left
blank rather than rendering empty rows.

Note what the database actually stores: `option_id = 6`. "Mercedes-Benz" only
exists after joining through `attribute_option`. That indirection is what
would make an Arabic version free — same ids, different label rows.

---

## The mechanism in one line

> **Category → product type → resolved attribute set → everything else.**

Every screen is a different consumer of the same resolver call. The admin form
uses the full set plus `is_required`; the filter sidebar uses the
`is_filterable` subset; the spec table uses grouping and labels. One resolver,
four readers.

The admin path is the mirror image: category → same resolver → same list →
renders a **form** instead of a spec table → saves into the same value tables.

---

## Query budget

| Stage | Queries |
|---|---|
| Resolve attributes | 1 (cacheable to ~0) |
| Option lists for facets | 1 per option attribute (cacheable) |
| Result ids | 1 |
| Facet counts | 1 per facet — **the expensive part** |
| Product page | 1 + 1 union |

A category page with eight facets is roughly 10–12 queries. Acceptable at
sample scale. The facet block is what would be cached first and what moves to
a search index when caching stops being enough.

---

## Zero results

If a shopper searches for a vertical that does not exist, they get nothing —
the same as any normal website. "Dynamic" does not mean the system invents
categories on demand; it means an administrator can add one without a
developer.

The correct handling is to show no results, suggest what does exist, and
**log the query**. A search log full of terms with no matching vertical is the
business telling you what to stock next.
