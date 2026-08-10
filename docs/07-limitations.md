# 07 — Limitations and Known Gaps

Deliberate scope decisions and known weaknesses, stated plainly. Everything
here was identified during development rather than discovered afterwards.

---

## Architectural

### Facet counts do not scale

One `GROUP BY` per filter in the sidebar. Eight facets means eight queries per
category page. This is EAV's defining cost and the reason Magento has a
reputation for slow category pages.

Mitigations in order of escalation: cache the facet block; denormalise each
product type into a wide flat table rebuilt by a background job (Magento's
approach); move faceting to Elasticsearch or OpenSearch entirely.

None implemented. At sample scale the queries are fast; the design assumes a
search index arrives later, which is why `is_filterable` exists as a flag
rather than being inferred.

### Filtering cost grows with filter count

N active filters means N `EXISTS` subqueries. Fine at ten thousand products,
needs attention at hundreds of thousands. The category filter running first
keeps the candidate set small, and the `(attribute_id, value, product_id)`
index order is what makes each subquery an index-only seek.

### Reading a product requires a pivot

One product with 15 attributes is a `UNION ALL` across up to seven tables,
pivoted in Python. A JSON-column approach would be one row. This is the trade
made for referential integrity and typed comparisons.

### Conditional rules are limited

Rules fire on option values only — no numeric triggers ("if year < 2000"), and
one trigger attribute per rule (no "if new AND imported"). See
`06-constraint-rules.md`.

### `rules` is an optional parameter

`create_product(..., rules=None)` means a call site that forgets to pass rules
silently skips enforcement. This bug occurred during development and was caught
only by an explicit bypass test. Making the parameter required would convert
the failure into an immediate `TypeError`.

---

## Not implemented

### Internationalisation

`attribute.label` and `attribute_option.label` are single columns. The design
anticipates `attribute_i18n` and `attribute_option_i18n` tables keyed on
`(id, locale)`, which is why values are stored as option **ids** rather than
strings — an Arabic version would be different label rows against the same
ids.

The database uses `utf8mb4` / `utf8mb4_unicode_ci` throughout, so the storage
layer is ready. RTL layout and locale-aware sorting are untouched.

### Units table

`attribute.unit` is a plain string. A `unit` table with base units and
conversion factors would allow cm/inch and kg/lb display switching. Out of
scope.

### Product variants

No variant axes. A t-shirt in three colours and four sizes would currently be
twelve separate products. The design notes exist (`variant`, `variant_axis`,
`variant_axis_value`) but nothing was built. Retrofitting variants touches
every table, so this is the most expensive omission.

### Offers and multi-seller inventory

Single-seller model. A marketplace needs an `offer` entity separate from
`product`, plus product matching and deduplication.

### Bulk import

No CSV or spreadsheet path. `create_product` accepts a plain dict and enforces
everything, so an import would be a loop with per-row error collection rather
than new architecture.

### Dictionary CRUD screens

Creating attributes, options, dependencies, scopes, and rules is done via SQL
or the seed scripts. The dynamic product form was prioritised because it is the
surface that demonstrates the architecture; dictionary CRUD is conventional
work over fixed tables.

### Media

No images. Every real catalog needs them.

### Authentication

No users, no permissions. "Admin" routes are open.

### Pagination

`LIMIT 24` with no page navigation.

### Tests

Manual verification only, documented per phase. No automated test suite.

---

## Operational

### Connection per query

`app/db.py` opens and closes a connection per `query()` call. Clear and
adequate at this scale; production needs a pool.

### No caching

The resolved attribute set changes only when an administrator edits
definitions, making it an obvious cache target keyed by `product_type_id`.
Left out deliberately so the mechanism stays visible.

### Schema rebuild rather than migrations

`sql/schema.sql` drops all tables and recreates them. This is a development
tool and **destroys all data**. A production system needs versioned
migrations (Alembic).

The distinction became concrete during development: changing two attribute
bindings required either three hand-written `UPDATE` statements or a full
re-seed that discarded all entered products. That is precisely the problem
migrations solve.

### Hard delete rather than archive

Products are deleted outright. Once orders exist, products must be archived
(`status = 'archived'`) instead — an invoice has to resolve its line items.

The seam is already correct in shape: order lines would reference a product id
and snapshot the display data at purchase time, so a renamed or delisted
product does not alter historical invoices.

---

## Data

### Automotive taxonomy

Four makes and nine models, entered by hand. A usable car catalog is thousands
of make/model/trim rows that change yearly. Sourcing that data is a separate
problem — a licensed feed, a public dataset, or a seller submission queue with
approval.

### Global dependency lookup

`get_dependencies()` returns every dependency in the database rather than
filtering to attributes in the resolved set. Harmless with one; needs scoping
at volume.

---

## Explicitly out of scope

The project scope was the **catalog data model** — the layer that makes
per-category filters and dynamic seller forms possible. Users, orders, carts,
payments, shipping, and reviews are conventional relational problems and were
excluded on purpose, not overlooked.

The general principle: metadata-driven modelling where types are open-ended,
plain relational tables where types are known. Applying EAV to orders would
cost referential integrity and transactional clarity on the hottest write path
while gaining nothing.

---

## What would come next

In rough priority order:

1. **Search index** for faceting — the first thing to break at scale
2. **Internationalisation tables** — cheap now, expensive later
3. **Dictionary CRUD admin** — removes the last reason to touch SQL
4. **Bulk import** — the practical blocker for real catalog volume
5. **Variants** — the most expensive retrofit, so worth deciding early
6. **Migrations** — required the moment real data exists
