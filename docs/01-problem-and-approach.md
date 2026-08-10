# 01 — The Problem and the Approach

## The problem

A car has mileage, transmission, and a make/model pair. A phone has RAM,
storage, and a screen size. A bed has a size and a drawer count. There is no
fixed set of columns that fits all of them.

Every marketplace hits this. Amazon, Noon, and OpenSouq all sell across
categories whose products share almost no attributes, and all three had to
answer the same question: **where does "what a product is" get defined?**

## The naive answer, and why it fails

The obvious approach is one table per product type:

```sql
CREATE TABLE car    (id, make, model, year, mileage_km, ...);
CREATE TABLE mobile (id, brand, ram_gb, storage_gb, ...);
CREATE TABLE bed    (id, material, size, drawers, ...);
```

This works, and it is what most systems start with. The cost appears when the
business enters a new vertical:

1. A developer writes a migration
2. A developer builds a form by hand
3. A developer builds filters by hand
4. Code review, testing, deploy

Roughly one to two weeks of engineering time, every time, for a decision the
business could otherwise make in an afternoon. Ten verticals means ten tables,
ten forms, and ten sets of filter code, all maintained separately.

The system grows linearly with the company's ambitions, and every growth step
requires engineering.

## The approach taken here

Instead of "laptops need a table with a RAM column," the system says:

> There exists a product type called `LAPTOP`. It has an attribute called
> `ram_gb`, which is an integer, measured in GB, filterable, required.

That entire sentence is **data**. It is four or five rows in tables that
already exist.

The database no longer knows what a laptop is. It knows only that there are
product types, that product types have attributes, and that attributes have
data types and rules. Laptop-ness lives in rows, not in the schema.

### The two layers

**The dictionary** defines what fields exist and which product types use them.
Nobody buys anything from these tables — they are the rulebook.

**The data** holds actual products and their values.

An administrator edits the dictionary. The dictionary then tells the
application how to build forms, validate input, render filters, and display
spec tables. Add a page to the dictionary and the application immediately
knows how to handle a new kind of product.

### The single success criterion

> Adding an entirely new vertical requires only `INSERT` statements.
> No new table. No migration. No code deploy.

Everything in the design serves that criterion, and Phase 10 of this project
tested it directly.

## What this is called

The pattern has several names depending on which community is describing it:

| Term | Origin |
|---|---|
| **EAV** (Entity–Attribute–Value) | The classic name for storing attributes as rows. Magento is the textbook implementation. |
| **Metadata-driven design** | Data-platform terminology: behaviour lives in metadata rows, not code. |
| **Schema-on-read** | Contrasted with schema-on-write, where DDL enforces structure at insert time. |
| **Open / flexible schema** | Describes the property that new entity types need no DDL. |
| **PIM** (Product Information Management) | The product category. Akeneo, Pimcore, and inRiver implement exactly this. |
| **Generic / universal data model** | Silverston's data-modelling literature. |

The most accurate description of this project is:

> A **metadata-driven catalog with EAV value storage and product-type
> inheritance.**

## Precedent

This is not an invented approach. Amazon documents it publicly through the
Selling Partner API:

- **Product Type Definitions** describe attribute and data requirements as
  JSON Schemas
- Product types are explicitly hierarchical
- Property groups exist for display grouping
- Display labels are locale-specific
- Validation is application-side — Amazon's own documentation states it is up
  to the integrator to implement it

Every one of those maps directly onto a table in this project. Magento runs
the same model on MySQL at large scale, which is the main reason EAV was
chosen here over a JSON-column approach.

## Where the boundary sits

This project implements the **catalog data model** — the layer that makes
per-category filters and dynamic seller forms possible.

Deliberately out of scope: offers and multi-seller inventory, search
infrastructure, media handling, internationalisation, orders, and payments.
Those are the things built *around* a catalog, not the catalog itself.

## Applying it only to products

The metadata-driven model exists to solve one specific problem: **the types
are open-ended.** Product types are unpredictable — cars, mobiles, furniture,
whatever launches next year.

Users, orders, carts, and payments do not have that problem. A user has an
email, a phone, a status. An order has a total, a currency, line items. Those
fields are known, stable, and finite.

Applying EAV to a stable entity gives you all the costs and none of the
benefit: lost foreign keys, lost database constraints, lost transactional
clarity on the hottest write path.

**The rule:** use metadata-driven modelling where types are open-ended; use
normal relational tables where types are known. In a full platform, the
catalog module would be the only metadata-driven part, and order lines would
reference products by id while snapshotting display data at purchase time.
