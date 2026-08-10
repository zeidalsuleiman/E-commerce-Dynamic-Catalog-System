"""Seed the catalog with two verticals: vehicles (cars, trucks) and mobiles.

Run:  python -m sql.seed
Idempotent: wipes all data first, then rebuilds. Schema is untouched.
"""
from app.db import get_conn


# ---------------------------------------------------------------- helpers

def wipe(cur):
    """Delete all data, keep the schema."""
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in [
        "attribute_rule",
        "product_value_multi_option", "product_value_option",
        "product_value_datetime", "product_value_text",
        "product_value_varchar", "product_value_decimal",
        "product_value_int", "product",
        "attribute_option_type_scope", "attribute_option_dependency",
        "product_type_attribute", "attribute_option", "attribute",
        "category_product_type", "category", "product_type",
    ]:
        cur.execute(f"TRUNCATE TABLE {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")


def add_category(cur, slug, name, parent_id=None, sort=0):
    cur.execute(
        "INSERT INTO category (parent_id, slug, name, sort_order) "
        "VALUES (%s, %s, %s, %s)",
        (parent_id, slug, name, sort),
    )
    return cur.lastrowid


def add_type(cur, code, name, parent_id=None):
    cur.execute(
        "INSERT INTO product_type (parent_type_id, code, name) "
        "VALUES (%s, %s, %s)",
        (parent_id, code, name),
    )
    return cur.lastrowid


def link_category_type(cur, category_id, type_id):
    cur.execute(
        "INSERT INTO category_product_type (category_id, product_type_id) "
        "VALUES (%s, %s)",
        (category_id, type_id),
    )


def add_attribute(cur, code, label, data_type, input_type,
                  unit=None, filterable=False):
    cur.execute(
        "INSERT INTO attribute "
        "(code, label, data_type, input_type, unit, is_filterable) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (code, label, data_type, input_type, unit, int(filterable)),
    )
    return cur.lastrowid


def add_option(cur, attribute_id, code, label, sort=0):
    cur.execute(
        "INSERT INTO attribute_option (attribute_id, code, label, sort_order) "
        "VALUES (%s, %s, %s, %s)",
        (attribute_id, code, label, sort),
    )
    return cur.lastrowid


def bind(cur, type_id, attribute_id, required=False, group=None, sort=0):
    cur.execute(
        "INSERT INTO product_type_attribute "
        "(product_type_id, attribute_id, is_required, group_name, sort_order) "
        "VALUES (%s, %s, %s, %s, %s)",
        (type_id, attribute_id, int(required), group, sort),
    )


def link_options(cur, child_option_id, parent_option_id):
    cur.execute(
        "INSERT INTO attribute_option_dependency "
        "(child_option_id, parent_option_id) VALUES (%s, %s)",
        (child_option_id, parent_option_id),
    )


def scope_option(cur, option_id, type_id):
    cur.execute(
        "INSERT INTO attribute_option_type_scope (option_id, product_type_id) "
        "VALUES (%s, %s)",
        (option_id, type_id),
    )


def add_rule(cur, type_id, trigger_attr_id, trigger_option_id,
             target_attr_id, rule_type, rule_value=None, message=None):
    cur.execute(
        "INSERT INTO attribute_rule "
        "(product_type_id, trigger_attribute_id, trigger_option_id, "
        " target_attribute_id, rule_type, rule_value, message) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (type_id, trigger_attr_id, trigger_option_id, target_attr_id,
         rule_type, rule_value, message),
    )
    return cur.lastrowid


# ---------------------------------------------------------------- seed

def seed():
    with get_conn() as conn:
        with conn.cursor() as cur:
            wipe(cur)

            # ---- product types: the inheritance chain ----
            t_product = add_type(cur, "PRODUCT", "Product")
            t_vehicle = add_type(cur, "VEHICLE", "Vehicle", t_product)
            t_car = add_type(cur, "CAR", "Car", t_vehicle)
            t_truck = add_type(cur, "TRUCK", "Truck", t_vehicle)
            t_elec = add_type(cur, "ELECTRONICS", "Electronics", t_product)
            t_mobile = add_type(cur, "MOBILE_PHONE", "Mobile Phone", t_elec)

            # ---- categories: what shoppers browse ----
            c_vehicles = add_category(cur, "vehicles", "Vehicles", None, 1)
            c_cars = add_category(cur, "cars", "Cars", c_vehicles, 1)
            c_trucks = add_category(cur, "trucks", "Trucks", c_vehicles, 2)
            c_elec = add_category(cur, "electronics", "Electronics", None, 2)
            c_mobiles = add_category(cur, "mobiles", "Mobiles", c_elec, 1)

            link_category_type(cur, c_cars, t_car)
            link_category_type(cur, c_trucks, t_truck)
            link_category_type(cur, c_mobiles, t_mobile)

            # ---- attributes on PRODUCT: everything inherits these ----
            a_condition = add_attribute(cur, "condition", "Condition",
                                        "option", "select", filterable=True)
            o_new = add_option(cur, a_condition, "new", "New", 1)
            o_used = add_option(cur, a_condition, "used", "Used", 2)
            bind(cur, t_product, a_condition, True, "General", 1)

            a_city = add_attribute(cur, "city", "City",
                                   "option", "select", filterable=True)
            for i, (code, label) in enumerate(
                [("amman", "Amman"), ("zarqa", "Zarqa"), ("irbid", "Irbid")], 1
            ):
                add_option(cur, a_city, code, label, i)
            bind(cur, t_product, a_city, False, "General", 2)

            # ---- attributes on VEHICLE: cars AND trucks inherit these ----
            a_make = add_attribute(cur, "make", "Make",
                                   "option", "select", filterable=True)
            a_model = add_attribute(cur, "model", "Model",
                                    "option", "select", filterable=True)
            a_year = add_attribute(cur, "year", "Year",
                                   "int", "range", filterable=True)
            a_mileage = add_attribute(cur, "mileage_km", "Mileage",
                                      "int", "range", unit="km",
                                      filterable=True)
            a_trans = add_attribute(cur, "transmission", "Transmission",
                                    "option", "select", filterable=True)

            for attr, sort in [
                (a_make, 1), (a_model, 2), (a_year, 3), (a_trans, 5),
            ]:
                bind(cur, t_vehicle, attr, True, "Vehicle", sort)

            # mileage is optional at the type level; the constraint rules
            # decide: forced to 0 when new, must be >= 1 when used
            bind(cur, t_vehicle, a_mileage, False, "Vehicle", 4)

            # ---- makes, scoped to car and/or truck ----
            o_mercedes = add_option(cur, a_make, "mercedes", "Mercedes-Benz", 1)
            o_bmw = add_option(cur, a_make, "bmw", "BMW", 2)
            o_toyota = add_option(cur, a_make, "toyota", "Toyota", 3)
            o_volvo = add_option(cur, a_make, "volvo", "Volvo", 4)

            scope_option(cur, o_mercedes, t_car)
            scope_option(cur, o_mercedes, t_truck)
            scope_option(cur, o_bmw, t_car)
            scope_option(cur, o_toyota, t_car)
            scope_option(cur, o_volvo, t_truck)

            # ---- models: each linked to its make, scoped to its type ----
            models = [
                ("c_class", "C-Class", o_mercedes, t_car),
                ("e_class", "E-Class", o_mercedes, t_car),
                ("actros", "Actros", o_mercedes, t_truck),
                ("atego", "Atego", o_mercedes, t_truck),
                ("3_series", "3 Series", o_bmw, t_car),
                ("5_series", "5 Series", o_bmw, t_car),
                ("corolla", "Corolla", o_toyota, t_car),
                ("camry", "Camry", o_toyota, t_car),
                ("fh16", "FH16", o_volvo, t_truck),
            ]
            for i, (code, label, parent, scope_type) in enumerate(models, 1):
                oid = add_option(cur, a_model, code, label, i)
                link_options(cur, oid, parent)
                scope_option(cur, oid, scope_type)

            # ---- transmission options ----
            for i, (code, label) in enumerate(
                [("automatic", "Automatic"), ("manual", "Manual")], 1
            ):
                add_option(cur, a_trans, code, label, i)

            # ---- CAR only ----
            a_body = add_attribute(cur, "body_type", "Body Type",
                                   "option", "select", filterable=True)
            for i, (code, label) in enumerate(
                [("sedan", "Sedan"), ("suv", "SUV"),
                 ("hatchback", "Hatchback")], 1
            ):
                add_option(cur, a_body, code, label, i)
            bind(cur, t_car, a_body, True, "Vehicle", 6)

            a_seats = add_attribute(cur, "seats", "Seats", "int", "number")
            bind(cur, t_car, a_seats, False, "Vehicle", 7)

            # ---- override: city optional on PRODUCT, required on CAR.
            #      Child wins in the resolver. ----
            bind(cur, t_car, a_city, True, "General", 2)

            # ---- TRUCK only ----
            a_payload = add_attribute(cur, "payload_capacity_kg", "Payload",
                                      "int", "range", unit="kg",
                                      filterable=True)
            bind(cur, t_truck, a_payload, True, "Vehicle", 6)

            a_axles = add_attribute(cur, "axles", "Axles", "int", "number")
            bind(cur, t_truck, a_axles, False, "Vehicle", 7)

            # ---- ELECTRONICS: mobiles inherit these ----
            a_brand = add_attribute(cur, "brand", "Brand",
                                    "option", "select", filterable=True)
            for i, (code, label) in enumerate(
                [("samsung", "Samsung"), ("apple", "Apple"),
                 ("xiaomi", "Xiaomi")], 1
            ):
                add_option(cur, a_brand, code, label, i)
            bind(cur, t_elec, a_brand, True, "General", 1)

            a_warranty = add_attribute(cur, "warranty_months", "Warranty",
                                       "int", "number", unit="months")
            bind(cur, t_elec, a_warranty, False, "General", 2)

            # ---- MOBILE_PHONE only ----
            a_ram = add_attribute(cur, "ram_gb", "RAM",
                                  "int", "range", unit="GB", filterable=True)
            bind(cur, t_mobile, a_ram, True, "Performance", 1)

            a_storage = add_attribute(cur, "storage_gb", "Storage",
                                      "int", "range", unit="GB",
                                      filterable=True)
            bind(cur, t_mobile, a_storage, True, "Performance", 2)

            a_screen = add_attribute(cur, "screen_inches", "Screen",
                                     "decimal", "number", unit="in")
            bind(cur, t_mobile, a_screen, False, "Display", 1)

            # warranty is optional for phones; the rules below decide
            # whether it is required (new) or hidden (used)
            bind(cur, t_mobile, a_warranty, False, "General", 3)

            # ================= constraint rules =================
            # Rules bind to a product type and fire on a specific option
            # value. They resolve along the type chain like attributes, so
            # a rule on VEHICLE applies to both CAR and TRUCK.

            add_rule(cur, t_vehicle, a_condition, o_new, a_mileage,
                     "force_value", "0",
                     "A new vehicle has no mileage.")

            add_rule(cur, t_vehicle, a_condition, o_used, a_mileage,
                     "min", "1",
                     "A used vehicle must have recorded mileage.")

            add_rule(cur, t_mobile, a_condition, o_new, a_warranty,
                     "require", None,
                     "Warranty is required for new phones.")

            add_rule(cur, t_mobile, a_condition, o_used, a_warranty,
                     "hide", None,
                     "Used phones are sold without manufacturer warranty.")

            print("Seed complete.")


if __name__ == "__main__":
    seed()