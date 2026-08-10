# 02 — The Schema

17 tables, grouped into four roles. The schema does not change when a vertical
is added.

| Group | Tables | Count |
|---|---|---|
| Taxonomy | `category`, `product_type`, `category_product_type` | 3 |
| Dictionary | `attribute`, `attribute_option`, `product_type_attribute`, `attribute_option_dependency`, `attribute_option_type_scope`, `attribute_rule` | 6 |
| Product | `product` | 1 |
| Values | `product_value_int`, `_decimal`, `_varchar`, `_text`, `_datetime`, `_option`, `_multi_option` | 7 |

Defined in `sql/schema.sql`. All tables are InnoDB with `utf8mb4` /
`utf8mb4_unicode_ci`.

---

## Taxonomy

### `category`

```sql
id, parent_id (self-FK, nullable), slug (unique), name, sort_order
```

The browse tree shoppers navigate. `parent_id` referencing the same table
gives unlimited depth from one table — the alternative would be
`category_level_1`, `category_level_2`, and a new table for every level added.

`NULL` parent means a root category.

**Categories do not inherit anything.** The parent link drives breadcrumbs,
URLs, and subtree queries only. Nothing binds attributes to categories.

### `product_type`

```sql
id, parent_type_id (self-FK, nullable), code (unique), name
```

Structurally identical to `category` — the same nullable self-referencing
foreign key. The difference is entirely in what the application does with it:
`product_type_attribute` binds attributes to types, so walking up this chain
collects something.

The seeded hierarchy:

```
PRODUCT
├── VEHICLE
│   ├── CAR
│   └── TRUCK
├── ELECTRONICS
│   └── MOBILE_PHONE
└── FURNITURE          (added post-launch, data only)
    ├── CLOSET
    ├── BED
    └── DESK
```

### `category_product_type`

Many-to-many join. This is the row the runtime lookup follows:

```
URL slug → category → product type → resolver → attributes
```

Without it a category exists but has no schema, and no form can render.

**Why two trees rather than one:** they answer different questions. Categories
answer "where does a shopper find this?" Product types answer "what fields
does this have?" They look identical in a simple catalog and diverge the
moment a marketing category like "Under 10,000 JOD" spans multiple types.

---

## Dictionary

### `attribute`

```sql
id, code (unique), label, data_type ENUM, input_type ENUM,
unit, is_filterable
```

A field definition, global and reusable. `ram_gb` is defined once and can be
bound to phones, laptops, and tablets — one definition, consistent filtering
across the site.

| Column | Purpose |
|---|---|
| `code` | Stable machine name, appears in URLs. Renaming breaks links; rename `label` instead. |
| `data_type` | Which value table stores it. Drives the Python type router. |
| `input_type` | Which form widget renders it. |
| `unit` | Display suffix — "km", "GB", "cm". Stored once, not per value. |
| `is_filterable` | Whether it appears in the filter sidebar. |

`data_type` and `input_type` are separate because they answer different
questions. `year` and `ram_gb` are both `int`, but one might render as a range
slider and the other as a plain number field. Merging them would force a
schema change later.

Both are `ENUM` rather than `VARCHAR` so the database rejects typos like
`'integar'` at insert time.

### `attribute_option`

```sql
id, attribute_id (FK), code, label, sort_order
UNIQUE (attribute_id, code)
```

The valid choices for `option` and `multi_option` attributes. Numeric
attributes have no rows here — there is no fixed list of valid RAM values to
enumerate.

**Options are foreign-keyed, not stored as strings.** This prevents "Samsung",
"samsung", and "SAMSUNG" accumulating as three separate facet entries, and
means renaming a brand updates one row rather than thousands of product
records.

### `product_type_attribute`

```sql
product_type_id (FK), attribute_id (FK),
is_required, group_name, sort_order
PRIMARY KEY (product_type_id, attribute_id)
```

The binding. An attribute exists globally; this row makes it part of a type.

`is_required`, `group_name`, and `sort_order` live on the **binding**, not the
attribute, so two types can use the same attribute with different rules. The
seed demonstrates this: `city` is optional on `PRODUCT` and required on `CAR`.

### `attribute_option_dependency`

```sql
child_option_id (FK), parent_option_id (FK)
PRIMARY KEY (child_option_id, parent_option_id)
KEY (parent_option_id, child_option_id)
```

Links one option to another — C-Class belongs to Mercedes. This is the
mechanism behind cascading dropdowns.

Both foreign keys point at `attribute_option`, making this the second
self-reference in the schema, expressed as a join table rather than a nullable
column.

The composite primary key allows **many parents per child**, which a tree
structure could not express. Rebadged models sold under two makes are handled
by adding a second row.

The extra index on `(parent_option_id, child_option_id)` exists because
queries run *downward* ("children of Mercedes") while the primary key is
ordered child-first.

### `attribute_option_type_scope`

```sql
option_id (FK), product_type_id (FK)
```

Restricts an option to specific product types. Mercedes is scoped to both
`CAR` and `TRUCK`; BMW to `CAR` only; Volvo to `TRUCK` only.

**This is the table that solves the duplication problem.** In a naive category
tree, Mercedes would appear as a node under both cars and trucks — two rows
that can silently drift apart. Here Mercedes is one row appearing in two
contexts.

An option with no scope rows is available to every type, keeping the common
case simple.

### `attribute_rule`

```sql
id, product_type_id (FK), trigger_attribute_id (FK),
trigger_option_id (FK), target_attribute_id (FK),
rule_type ENUM('force_value','hide','require','max','min'),
rule_value, message
```

Conditional constraints. Documented in full in `06-constraint-rules.md`.

---

## Product

### `product`

```sql
id BIGINT, product_type_id (FK), primary_category_id (FK),
title, price, status, created_at
KEY idx_product_browse (primary_category_id, status, created_at)
```

`title`, `price`, and `status` are **columns rather than attributes**. This is
deliberate denormalisation, justified by three things: they are universal to
every product in every vertical, they appear on every result card (as
attributes, a 24-result page would mean 24 extra value-table lookups), and
`price` requires efficient `ORDER BY`.

**The test for adding another column:** does *every* product, in *every*
vertical, forever, have this field? "Almost every" means it belongs in the
attribute registry, bound high in the type hierarchy — a global field can be
achieved either way, and the registry version participates automatically in
form rendering, validation, and filtering.

---

## Value tables

Seven tables, all the same shape:

```sql
product_id BIGINT (FK CASCADE), attribute_id INT (FK), value <type>
PRIMARY KEY (product_id, attribute_id)
KEY idx_*_filter (attribute_id, value, product_id)
```

| Table | Column type |
|---|---|
| `product_value_int` | `INT` |
| `product_value_decimal` | `DECIMAL(18,4)` |
| `product_value_varchar` | `VARCHAR(255)` |
| `product_value_text` | `TEXT` |
| `product_value_datetime` | `DATETIME` |
| `product_value_option` | `option_id` FK |
| `product_value_multi_option` | `option_id` FK, in the primary key |

### Why split by data type

The naive version is one table with `value VARCHAR`. That breaks immediately:
`"999" > "2018"` is **true** when compared as text. Range filters would
silently return wrong results, and no index would help.

Typed columns give correct comparisons and usable indexes.

### The filter index order

```sql
KEY idx_pvi_filter (attribute_id, value, product_id)
```

This ordering is load-bearing. It lets MySQL seek directly to "attribute 21,
value ≥ 2018" and read matching product ids straight from the index without
touching the table. Any other column order degrades filtering badly.

### Why five tables sit empty after seeding

`product_value_varchar`, `_text`, `_datetime`, and `_multi_option` hold no
rows in the seeded state. This is expected and is the point of the design:
they are **storage shapes waiting for a use**, not per-vertical tables.

Adding an attribute with `data_type = 'text'` starts populating
`product_value_text` immediately, with no schema change.

### Delete behaviour

`ON DELETE CASCADE` on `product_id` — deleting a product removes its values.
`RESTRICT` (default) on `attribute_id` — an attribute still in use cannot be
deleted.

In a system with orders, products would be archived (`status = 'archived'`)
rather than deleted, since an invoice must still resolve its line items.

---

## Verifying the schema

```sql
SHOW TABLES;                                    -- 17

SHOW INDEX FROM product_value_int
  WHERE Key_name = 'idx_pvi_filter';            -- attribute_id, value, product_id

SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'catalog' AND CONSTRAINT_TYPE = 'FOREIGN KEY';

WITH RECURSIVE t AS (
  SELECT 1 AS n UNION ALL SELECT n+1 FROM t WHERE n < 3
) SELECT * FROM t;                              -- 1, 2, 3
```

The recursive CTE check matters: the resolver depends on it, and it requires
MySQL 8.0+.

---

## A note on `schema.sql`

The file begins with a DROP block guarded by `SET FOREIGN_KEY_CHECKS = 0`.
This makes it re-runnable during development — edit, re-run, rebuild — but it
**destroys all data** and must never run against a database holding real
records.

This is a development rebuild script, not a migration. A production system
would apply versioned `ALTER TABLE` statements through a migration tool
(Alembic for FastAPI). Noted as a limitation in `07-limitations.md`.
