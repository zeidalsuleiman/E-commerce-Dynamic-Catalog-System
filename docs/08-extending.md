# 08 — Extending the System

The project's central claim is that adding a new product vertical requires
only `INSERT` statements. That claim is true, but it is not unlimited, and a
design document that does not say where it stops is not much use.

Phases 12 and 13 were built back to back as a deliberate test of the boundary.
One required no schema change. The other required a new table. This document
explains why they fall on opposite sides.

---

## The three categories of change

| Change | Requires | Who does it |
|---|---|---|
| A new value for an existing field | `INSERT` | Admin |
| A new field, or a whole new vertical | `INSERT` | Admin |
| A new **widget** for an existing data type | ENUM value + template branch | Developer |
| A new **data type** | New value table + router entry | Developer |
| A new **related entity** | New table + application code | Developer |

The design eliminates the second row — the one that used to require an
engineer for every business decision. It does not eliminate the last three,
and was never intended to.

---

## Case 1 — Feature checklists (Phase 12)

**What was wanted:** OpenSooq-style tick lists of vehicle features, split into
Interior and Exterior groups, each showing a count.

**What it cost:** no schema change.

Every part of the storage path already existed and had never been used:

| Layer | Status before Phase 12 |
|---|---|
| `multi_option` in the `data_type` ENUM | present |
| `TABLE_BY_TYPE` routing to `product_value_multi_option` | present |
| `validate()` handling list values | present |
| `save_values()` writing one row per selection | present |
| `load_values()` returning a list | present |
| `product_value_multi_option` with `option_id` in its primary key | present |

Adding the feature meant inserting two attributes with their options and
bindings. The only code was presentation: a `checklist` value added to the
`input_type` ENUM, a checkbox-grid branch in `field.html`, `form.getlist()`
for reading multi-valued fields, and a tick-list branch on the product page.
Filtering worked with no change to `filters.py` at all.

**The instructive part** is that `product_value_multi_option` had sat empty
since Phase 1. It was not dead weight — it was a storage shape waiting for a
use, and it received its first rows without any table being altered.

### The widget distinction

Adding `checklist` to the `input_type` ENUM *is* a schema change, and it would
be dishonest to claim otherwise. But it is a change to **presentation**, not
storage. The data continued to flow through the same table, the same router
entry, and the same validation branch.

A new `input_type` is a new way to *collect* a value. A new `data_type` would
be a new way to *store* one, and that is a much larger change.

---

## Case 2 — Product images (Phase 13)

**What was wanted:** upload several photos per product, show a gallery on the
detail page and a thumbnail on listing cards.

**What it cost:** a new table, a new module, and a new dependency.

### Why images do not fit the attribute registry

You could store an image URL as a `varchar` attribute. It would even work for
one image. But images have four properties no attribute value has:

**Multiplicity with meaningful order.** A product has several images and the
first one is the thumbnail. `multi_option` gives multiple values, but they are
selections from a fixed list, not arbitrary uploads.

**A file outside the database.** The row is a pointer; the actual bytes live
on disk. Nothing else in the system has a physical artifact attached.

**Metadata of its own.** Width, height, file size, alt text, sort order,
primary flag. An attribute value is a single scalar; an image is a record.

**A lifecycle.** Files must be written on upload and removed on delete. No
attribute value needs cleanup outside the database.

### What it actually required

- `product_image` table — 18th table in the schema
- `app/uploads.py` — validation, storage, deletion
- Pillow as a dependency
- Upload handling in the create route
- `save_images`, `load_images`, `load_primary_images` in `values.py`
- Gallery and thumbnail rendering in three templates
- `enctype="multipart/form-data"` on the form

Roughly two hours against Phase 12's one, and it introduced security concerns
nothing else in the project had.

---

## The rule that separates them

> **Is this something a product *has as a value*, or a *thing related to* the
> product?**

Values go in the registry. Related entities get their own table.

| Feature | Verdict |
|---|---|
| Interior features | Value — a selection from a fixed list |
| Colour, size, material | Value |
| A number, a date, free text | Value |
| Images | Related entity — file, order, lifecycle |
| Reviews | Related entity — author, date, moderation state |
| Price history | Related entity — time series |
| Stock movements | Related entity — event log |

The registry's scope is **"what a product is."** It was never intended to
cover everything a catalog does.

---

## What a new data type would require

The seven value tables cover every attribute type in the project's planned
verticals. A genuinely new storage shape — spatial coordinates for
distance-based search, say — would need:

1. A new table, e.g. `product_value_geo` with a `POINT` column and a spatial
   index
2. `geo` added to the `attribute.data_type` ENUM
3. One entry in `TABLE_BY_TYPE`
4. A coercion branch in `coerce()`
5. A `UNION ALL` branch in `LOAD_SQL`
6. A new form widget — a map picker

Six changes, contained because the routing lives in one dictionary. This is
rare: seven types cover essentially every product field in e-commerce.

---

## The claim, stated precisely

The imprecise version — *"no schema changes"* — is easy to disprove and
therefore not worth defending.

The accurate version:

> Adding a new product **category**, with its own attributes, options,
> dependencies, and constraint rules, requires only `INSERT` statements
> against tables that already exist. Verified by adding Furniture, Closets,
> Beds, and Desks to a running system with no application file modified.
>
> Adding a new **capability** — a new storage shape, a new input widget, or a
> new related entity — is an engineering change. The design moves the
> developer requirement from *every business decision* to *a rare technical
> one*.

That second version survives scrutiny, and it is the more useful claim: it
tells a reader exactly what they get and exactly what they still have to
build.
