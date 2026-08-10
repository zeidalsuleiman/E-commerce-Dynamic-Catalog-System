-- =====================================================================
-- Adding a product type using data only.
--
-- Demonstrates the core claim of this project: a new vertical requires
-- no schema change, no migration, and no application code. Every
-- statement below is an INSERT.
--
-- Example: DESK, inheriting from FURNITURE.
--
-- Run against a live database while the server is running, then refresh
-- the browser. The category picker, product form, validation, detail
-- page, and filter sidebar all pick it up with no restart.
--
-- IDs are looked up by code rather than hardcoded, so this script is
-- portable to any database with the same seed.
-- =====================================================================

USE catalog;

-- ---------------------------------------------------------------------
-- 1. Product type
--    parent_type_id decides which attributes are inherited. DESK sits
--    under FURNITURE, so it receives material, room, and the three
--    dimensions, plus condition and city from the root PRODUCT type.
-- ---------------------------------------------------------------------
INSERT INTO product_type (parent_type_id, code, name)
SELECT id, 'DESK', 'Desk'
FROM product_type
WHERE code = 'FURNITURE';

-- ---------------------------------------------------------------------
-- 2. Category
--    What shoppers browse. Separate from product_type: the tree is for
--    navigation, the type hierarchy is for attribute inheritance.
-- ---------------------------------------------------------------------
INSERT INTO category (parent_id, slug, name, sort_order)
SELECT id, 'desks', 'Desks', 3
FROM category
WHERE slug = 'furniture';

-- ---------------------------------------------------------------------
-- 3. Link category to type
--    This is the row the runtime lookup follows: URL slug -> category
--    -> product type -> resolver. Without it the category exists but
--    has no schema, and no form can be rendered.
-- ---------------------------------------------------------------------
INSERT INTO category_product_type (category_id, product_type_id)
SELECT c.id, pt.id
FROM category c, product_type pt
WHERE c.slug = 'desks' AND pt.code = 'DESK';

-- At this point the vertical is live. Refresh the homepage.

-- ---------------------------------------------------------------------
-- 4. A type-specific attribute (optional)
--    data_type decides which value table stores it.
--    input_type decides which form widget renders it.
--    is_filterable decides whether it appears in the filter sidebar.
-- ---------------------------------------------------------------------
INSERT INTO attribute (code, label, data_type, input_type, unit, is_filterable)
VALUES ('has_drawers', 'Has Drawers', 'int', 'toggle', NULL, 1);

-- ---------------------------------------------------------------------
-- 5. Bind the attribute to the type
--    The attribute exists globally; this row makes it part of DESK.
--    is_required, group_name and sort_order belong to the binding, not
--    the attribute, so another type can bind the same attribute with
--    different rules.
-- ---------------------------------------------------------------------
INSERT INTO product_type_attribute
  (product_type_id, attribute_id, is_required, group_name, sort_order)
SELECT pt.id, a.id, 0, 'Construction', 2
FROM product_type pt, attribute a
WHERE pt.code = 'DESK' AND a.code = 'has_drawers';


-- =====================================================================
-- Verify
-- =====================================================================

-- Effective attribute set for DESK. Should return the inherited
-- attributes plus has_drawers. This is the query the resolver runs.
WITH RECURSIVE chain AS (
    SELECT id, parent_type_id FROM product_type WHERE code = 'DESK'
    UNION ALL
    SELECT pt.id, pt.parent_type_id
    FROM product_type pt JOIN chain c ON pt.id = c.parent_type_id
)
SELECT a.code, a.data_type, a.input_type,
       pta.is_required, pta.group_name, pta.sort_order
FROM product_type_attribute pta
JOIN attribute a ON a.id = pta.attribute_id
WHERE pta.product_type_id IN (SELECT id FROM chain)
ORDER BY pta.group_name, pta.sort_order;


-- =====================================================================
-- Rollback
-- Order matters: remove referencing rows before referenced ones.
-- =====================================================================

-- DELETE FROM product_type_attribute
--   WHERE attribute_id = (SELECT id FROM attribute WHERE code = 'has_drawers');
-- DELETE FROM attribute WHERE code = 'has_drawers';
-- DELETE FROM category_product_type
--   WHERE category_id = (SELECT id FROM category WHERE slug = 'desks');
-- DELETE FROM category WHERE slug = 'desks';
-- DELETE FROM product_type WHERE code = 'DESK';