# Dynamic Product Catalog

A working reference for the problem every marketplace hits: a car has mileage
and transmission, a phone has RAM and storage, a bed has a size and a drawer
count. No fixed set of columns fits them all.

The naive answer is a table per product type — and a developer, a migration,
and a deploy every time the business enters a new vertical. This project
implements the alternative used by Amazon, Magento, and most large PIM
systems: **the category defines a schema, and that schema is data.**

> **The test this project is built to pass:** adding an entirely new vertical
> requires only `INSERT` statements. No new tables, no migration, no deploy.

---

## Stack

MySQL 8.0 · Python 3.12 · FastAPI · Jinja2 · raw SQL, no ORM

No ORM by choice: the resolver needs recursive CTEs, the value layer selects
its table at runtime, and filtering builds N dynamic `EXISTS` clauses. All
three fight an ORM. Every query in the repository is hand-written and
inspectable.

---

## The design in one line

```
Category → product type → resolved attribute set → everything else
```

The admin form, the save validator, the filter sidebar, and the product spec
table are four consumers of one resolver call.

---

## What was built

| # | Phase | Outcome |
|---|---|---|
| 1 | Schema | 17 tables — taxonomy, dictionary, product, 7 value tables |
| 2 | Connection layer | PyMySQL helpers, transaction-scoped context manager |
| 3 | Seed | Vehicles and mobiles, with make→model cascade and type scoping |
| 4 | Resolver | Recursive CTE walks the type chain, child overrides parent |
| 5 | Value layer | Type router, coercion, validation, dependency checks |
| 6 | Dynamic form | Renders itself from the resolver; one template, every vertical |
| 7 | Cascades | Dependent dropdowns filtered by parent choice *and* product type |
| 8 | Product page | Grouped spec table from stored values plus definitions |
| 9 | Category page | Filter sidebar generated from `is_filterable`; faceted search |
| 10 | Furniture | A new vertical added with data only — the proof |
| 11 | Constraint rules | Conditional cross-attribute rules with type-chain inheritance |

### Verified capabilities

- **Inheritance** — `CAR` and `TRUCK` share seven attributes from a single set
  of `VEHICLE` bindings, with no duplication
- **Override** — `city` is optional on `PRODUCT` and required on `CAR`; the
  resolver returns required, proving root-first merge order
- **Option scoping** — Mercedes is one row scoped to both `CAR` and `TRUCK`; a
  category tree would need two nodes that can drift apart
- **Cascades** — Mercedes on a car form returns C-Class and E-Class; the same
  make on a truck form returns Actros and Atego
- **Constraint rules** — a rule bound to `VEHICLE` fires for trucks with no
  truck-specific row
- **Server-side enforcement** — verified by bypassing the form entirely with a
  crafted API request
- **Data-only extension** — Furniture, Closets, Beds, and Desks added while
  the server was running; `git status` shows no application file changed

---

## Quick start

```bash
# 1. Database
mysql -u root -p < sql/setup.sql          # creates catalog + catalog_user

# 2. Environment
python -m venv venv
venv\Scripts\Activate.ps1                 # Windows
pip install -r requirements.txt
cp .env.example .env                      # then fill in DB_PASSWORD

# 3. Schema and data
#    run sql/schema.sql in a MySQL client
python -m sql.seed
python -m sql.add_furniture

# 4. Run
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000

| Route | Purpose |
|---|---|
| `/` | Categories and recent products |
| `/c/{slug}` | Category page with generated filters |
| `/products/{id}` | Product detail with grouped spec table |
| `/admin/products/new/{slug}` | The dynamic form |
| `/api/resolve/{TYPE_CODE}` | Debug: the resolved attribute set |
| `/docs` | FastAPI interactive API docs |

---

## Seeing the architecture in ninety seconds

Read **`sql/add_product_type.sql`**. It adds a complete new vertical, and
every statement is an `INSERT`. Run the first three, refresh the browser, and
a working form for a product type that did not exist appears.

---

## Documentation

| File | Contents |
|---|---|
| [`docs/01-problem-and-approach.md`](docs/01-problem-and-approach.md) | Why table-per-type fails; what this pattern is called; precedent |
| [`docs/02-schema.md`](docs/02-schema.md) | All 17 tables, why value tables split by type, the filter index |
| [`docs/03-resolver.md`](docs/03-resolver.md) | The recursive CTE, root-first merge, why raw SQL |
| [`docs/04-values-and-insertion.md`](docs/04-values-and-insertion.md) | The type router, and all four insertion methods |
| [`docs/05-runtime-flow.md`](docs/05-runtime-flow.md) | Setup workflow and per-request flow |
| [`docs/06-constraint-rules.md`](docs/06-constraint-rules.md) | The rules engine, and two silent-failure bugs |
| [`docs/07-limitations.md`](docs/07-limitations.md) | Honest gaps and what would come next |

---

## Repository layout

```
app/
  db.py               connection helpers, transaction context manager
  resolver.py         the type-chain walk and merge
  values.py           type router, validation, read/write
  filters.py          EXISTS-per-filter query builder, facet counts
  main.py             app setup, health, debug routes
  routes/
    admin.py          dynamic product form
    catalog.py        category and product pages
    api.py            cascade options endpoint
  templates/          Jinja2, including partials/field.html
  static/cascade.js   cascades and constraint rules

sql/
  schema.sql              17 tables (dev rebuild — destroys data)
  seed.py                 vehicles and mobiles
  add_furniture.py        a vertical added post-launch, in Python
  add_product_type.sql    the same, in raw SQL, as a template

docs/                 phase documentation
```

---

## Scope

This implements the **catalog data model** — the layer that makes
per-category filters and dynamic seller forms possible. Offers, search
infrastructure, media, internationalisation, orders, and payments are out of
scope by design, not oversight. See `docs/07-limitations.md`.
