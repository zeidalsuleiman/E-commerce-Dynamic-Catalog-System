"""Add the Furniture vertical using data only.

FURNITURE holds shared attributes; CLOSET and BED add their own.
Same shape as VEHICLE -> CAR/TRUCK, proving the pattern generalises.

No schema change, no migration, no application code.

    python -m sql.add_furniture
"""
from app.db import get_conn


def cleanup(cur):
    cur.execute(
        "SELECT id FROM product_type WHERE code IN "
        "('FURNITURE', 'CLOSET', 'BED')"
    )
    type_ids = [r["id"] for r in cur.fetchall()]

    codes = (
        "material", "room", "width_cm", "depth_cm", "height_cm",
        "assembly_required", "care_notes",
        "door_count", "closet_style", "has_mirror",
        "bed_size", "storage_drawers",
    )
    placeholders = ", ".join(["%s"] * len(codes))
    cur.execute(f"SELECT id FROM attribute WHERE code IN ({placeholders})",
                codes)
    attr_ids = [r["id"] for r in cur.fetchall()]

    if type_ids:
        ph = ", ".join(["%s"] * len(type_ids))
        cur.execute(f"SELECT id FROM product WHERE product_type_id IN ({ph})",
                    type_ids)
        product_ids = [r["id"] for r in cur.fetchall()]
        if product_ids:
            pph = ", ".join(["%s"] * len(product_ids))
            cur.execute(f"DELETE FROM product WHERE id IN ({pph})", product_ids)

    if attr_ids:
        ph = ", ".join(["%s"] * len(attr_ids))
        cur.execute(
            f"DELETE FROM attribute_option_type_scope WHERE option_id IN "
            f"(SELECT id FROM attribute_option WHERE attribute_id IN ({ph}))",
            attr_ids)
        cur.execute(
            f"DELETE FROM product_type_attribute WHERE attribute_id IN ({ph})",
            attr_ids)
        cur.execute(f"DELETE FROM attribute_option WHERE attribute_id IN ({ph})",
                    attr_ids)
        cur.execute(f"DELETE FROM attribute WHERE id IN ({ph})", attr_ids)

    cur.execute(
        "DELETE FROM category_product_type WHERE category_id IN "
        "(SELECT id FROM category WHERE slug IN ('furniture','closets','beds'))"
    )
    cur.execute(
        "DELETE FROM category WHERE slug IN ('closets','beds')"
    )
    cur.execute("DELETE FROM category WHERE slug = 'furniture'")

    if type_ids:
        cur.execute("DELETE FROM product_type WHERE code IN ('CLOSET','BED')")
        cur.execute("DELETE FROM product_type WHERE code = 'FURNITURE'")


def run():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cleanup(cur)

            def add_type(code, name, parent_id):
                cur.execute(
                    "INSERT INTO product_type (parent_type_id, code, name) "
                    "VALUES (%s, %s, %s)", (parent_id, code, name))
                return cur.lastrowid

            def add_category(slug, name, parent_id, sort):
                cur.execute(
                    "INSERT INTO category (parent_id, slug, name, sort_order) "
                    "VALUES (%s, %s, %s, %s)", (parent_id, slug, name, sort))
                return cur.lastrowid

            def link(category_id, type_id):
                cur.execute(
                    "INSERT INTO category_product_type "
                    "(category_id, product_type_id) VALUES (%s, %s)",
                    (category_id, type_id))

            def add_attr(code, label, data_type, input_type,
                         unit=None, filterable=False):
                cur.execute(
                    "INSERT INTO attribute "
                    "(code, label, data_type, input_type, unit, is_filterable) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (code, label, data_type, input_type, unit, int(filterable)))
                return cur.lastrowid

            def add_option(attr_id, code, label, sort):
                cur.execute(
                    "INSERT INTO attribute_option "
                    "(attribute_id, code, label, sort_order) "
                    "VALUES (%s, %s, %s, %s)", (attr_id, code, label, sort))
                return cur.lastrowid

            def bind(type_id, attr_id, required, group, sort):
                cur.execute(
                    "INSERT INTO product_type_attribute "
                    "(product_type_id, attribute_id, is_required, "
                    "group_name, sort_order) VALUES (%s, %s, %s, %s, %s)",
                    (type_id, attr_id, int(required), group, sort))

            # ---- product types ----
            cur.execute("SELECT id FROM product_type WHERE code = 'PRODUCT'")
            t_root = cur.fetchone()["id"]

            t_furniture = add_type("FURNITURE", "Furniture", t_root)
            t_closet = add_type("CLOSET", "Closet", t_furniture)
            t_bed = add_type("BED", "Bed", t_furniture)

            # ---- categories: furniture is a branch, closets/beds are leaves ----
            c_furniture = add_category("furniture", "Furniture", None, 3)
            c_closets = add_category("closets", "Closets", c_furniture, 1)
            c_beds = add_category("beds", "Beds", c_furniture, 2)

            link(c_closets, t_closet)
            link(c_beds, t_bed)

            # ---- shared attributes on FURNITURE ----
            a_material = add_attr("material", "Material", "option", "select",
                                  filterable=True)
            for i, (code, label) in enumerate(
                [("wood", "Wood"), ("metal", "Metal"),
                 ("fabric", "Fabric"), ("leather", "Leather")], 1):
                add_option(a_material, code, label, i)
            bind(t_furniture, a_material, True, "Construction", 1)

            a_room = add_attr("room", "Room", "option", "select",
                              filterable=True)
            for i, (code, label) in enumerate(
                [("bedroom", "Bedroom"), ("living", "Living Room"),
                 ("guest", "Guest Room")], 1):
                add_option(a_room, code, label, i)
            bind(t_furniture, a_room, True, "General", 3)

            a_width = add_attr("width_cm", "Width", "decimal", "number",
                               unit="cm", filterable=True)
            bind(t_furniture, a_width, True, "Dimensions", 1)

            a_depth = add_attr("depth_cm", "Depth", "decimal", "number",
                               unit="cm")
            bind(t_furniture, a_depth, True, "Dimensions", 2)

            a_height = add_attr("height_cm", "Height", "decimal", "number",
                                unit="cm")
            bind(t_furniture, a_height, True, "Dimensions", 3)

            # ---- CLOSET only ----
            a_doors = add_attr("door_count", "Doors", "int", "number",
                               filterable=True)
            bind(t_closet, a_doors, True, "Construction", 2)

            a_style = add_attr("closet_style", "Style", "option", "select",
                               filterable=True)
            for i, (code, label) in enumerate(
                [("sliding", "Sliding"), ("hinged", "Hinged"),
                 ("walk_in", "Walk-in")], 1):
                add_option(a_style, code, label, i)
            bind(t_closet, a_style, True, "Construction", 3)

            # ---- BED only ----
            a_size = add_attr("bed_size", "Size", "option", "select",
                              filterable=True)
            for i, (code, label) in enumerate(
                [("single", "Single"), ("double", "Double"),
                 ("queen", "Queen"), ("king", "King")], 1):
                add_option(a_size, code, label, i)
            bind(t_bed, a_size, True, "Construction", 2)

            a_drawers = add_attr("storage_drawers", "Storage Drawers",
                                 "int", "number", filterable=True)
            bind(t_bed, a_drawers, False, "Construction", 3)

            print(f"Furniture added. FURNITURE={t_furniture}, "
                  f"CLOSET={t_closet}, BED={t_bed}")
            print("No schema change. No code change. No deploy.")


if __name__ == "__main__":
    run()