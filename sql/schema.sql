-- Block 1 — reset

USE catalog;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS attribute_rule;
DROP TABLE IF EXISTS product_value_multi_option;
DROP TABLE IF EXISTS product_value_option;
DROP TABLE IF EXISTS product_value_datetime;
DROP TABLE IF EXISTS product_value_text;
DROP TABLE IF EXISTS product_value_varchar;
DROP TABLE IF EXISTS product_value_decimal;
DROP TABLE IF EXISTS product_value_int;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS attribute_option_type_scope;
DROP TABLE IF EXISTS attribute_option_dependency;
DROP TABLE IF EXISTS product_type_attribute;
DROP TABLE IF EXISTS attribute_option;
DROP TABLE IF EXISTS attribute;
DROP TABLE IF EXISTS category_product_type;
DROP TABLE IF EXISTS product_type;
DROP TABLE IF EXISTS category;
SET FOREIGN_KEY_CHECKS = 1;

-- Block 2 — taxonomy

CREATE TABLE category (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  parent_id  INT UNSIGNED NULL,
  slug       VARCHAR(120) NOT NULL,
  name       VARCHAR(120) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_category_slug (slug),
  KEY idx_category_parent (parent_id),
  CONSTRAINT fk_category_parent
    FOREIGN KEY (parent_id) REFERENCES category(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_type (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  parent_type_id INT UNSIGNED NULL,
  code           VARCHAR(64) NOT NULL,
  name           VARCHAR(120) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_product_type_code (code),
  KEY idx_product_type_parent (parent_type_id),
  CONSTRAINT fk_product_type_parent
    FOREIGN KEY (parent_type_id) REFERENCES product_type(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE category_product_type (
  category_id     INT UNSIGNED NOT NULL,
  product_type_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (category_id, product_type_id),
  KEY idx_cpt_type (product_type_id),
  CONSTRAINT fk_cpt_category
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE,
  CONSTRAINT fk_cpt_type
    FOREIGN KEY (product_type_id) REFERENCES product_type(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Block 3 — dictionary

CREATE TABLE attribute (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  code          VARCHAR(64) NOT NULL,
  label         VARCHAR(120) NOT NULL,
  data_type     ENUM('int','decimal','varchar','text','datetime','option','multi_option') NOT NULL,
  input_type    ENUM('text','number','select','multiselect','range','toggle','date','checklist') NOT NULL,
  unit          VARCHAR(16) NULL,
  is_filterable TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_attribute_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE attribute_option (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  attribute_id INT UNSIGNED NOT NULL,
  code         VARCHAR(64) NOT NULL,
  label        VARCHAR(120) NOT NULL,
  sort_order   INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_option (attribute_id, code),
  CONSTRAINT fk_option_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_type_attribute (
  product_type_id INT UNSIGNED NOT NULL,
  attribute_id    INT UNSIGNED NOT NULL,
  is_required     TINYINT(1) NOT NULL DEFAULT 0,
  group_name      VARCHAR(64) NULL,
  sort_order      INT NOT NULL DEFAULT 0,
  PRIMARY KEY (product_type_id, attribute_id),
  KEY idx_pta_attribute (attribute_id),
  CONSTRAINT fk_pta_type
    FOREIGN KEY (product_type_id) REFERENCES product_type(id) ON DELETE CASCADE,
  CONSTRAINT fk_pta_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE attribute_option_dependency (
  child_option_id  INT UNSIGNED NOT NULL,
  parent_option_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (child_option_id, parent_option_id),
  KEY idx_dep_parent (parent_option_id, child_option_id),
  CONSTRAINT fk_dep_child
    FOREIGN KEY (child_option_id) REFERENCES attribute_option(id) ON DELETE CASCADE,
  CONSTRAINT fk_dep_parent
    FOREIGN KEY (parent_option_id) REFERENCES attribute_option(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE attribute_option_type_scope (
  option_id       INT UNSIGNED NOT NULL,
  product_type_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (option_id, product_type_id),
  KEY idx_scope_type (product_type_id),
  CONSTRAINT fk_scope_option
    FOREIGN KEY (option_id) REFERENCES attribute_option(id) ON DELETE CASCADE,
  CONSTRAINT fk_scope_type
    FOREIGN KEY (product_type_id) REFERENCES product_type(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE attribute_rule (
  id                   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_type_id      INT UNSIGNED NOT NULL,
  trigger_attribute_id INT UNSIGNED NOT NULL,
  trigger_option_id    INT UNSIGNED NOT NULL,
  target_attribute_id  INT UNSIGNED NOT NULL,
  rule_type            ENUM('force_value','hide','require','max','min') NOT NULL,
  rule_value           VARCHAR(64) NULL,
  message              VARCHAR(255) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_rule (product_type_id, trigger_attribute_id,
                      trigger_option_id, target_attribute_id, rule_type),
  KEY idx_rule_type (product_type_id),
  CONSTRAINT fk_rule_ptype
    FOREIGN KEY (product_type_id) REFERENCES product_type(id) ON DELETE CASCADE,
  CONSTRAINT fk_rule_trigger_attr
    FOREIGN KEY (trigger_attribute_id) REFERENCES attribute(id),
  CONSTRAINT fk_rule_trigger_opt
    FOREIGN KEY (trigger_option_id) REFERENCES attribute_option(id) ON DELETE CASCADE,
  CONSTRAINT fk_rule_target_attr
    FOREIGN KEY (target_attribute_id) REFERENCES attribute(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Block 4 — product and values

CREATE TABLE product (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_type_id     INT UNSIGNED NOT NULL,
  primary_category_id INT UNSIGNED NOT NULL,
  title               VARCHAR(255) NOT NULL,
  price               DECIMAL(12,2) NULL,
  status              VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_product_browse (primary_category_id, status, created_at),
  KEY idx_product_type (product_type_id),
  CONSTRAINT fk_product_type
    FOREIGN KEY (product_type_id) REFERENCES product_type(id),
  CONSTRAINT fk_product_category
    FOREIGN KEY (primary_category_id) REFERENCES category(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_value_int (
  product_id   BIGINT UNSIGNED NOT NULL,
  attribute_id INT UNSIGNED NOT NULL,
  value        INT NOT NULL,
  PRIMARY KEY (product_id, attribute_id),
  KEY idx_pvi_filter (attribute_id, value, product_id),
  CONSTRAINT fk_pvi_product
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
  CONSTRAINT fk_pvi_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_value_decimal (
  product_id   BIGINT UNSIGNED NOT NULL,
  attribute_id INT UNSIGNED NOT NULL,
  value        DECIMAL(18,4) NOT NULL,
  PRIMARY KEY (product_id, attribute_id),
  KEY idx_pvd_filter (attribute_id, value, product_id),
  CONSTRAINT fk_pvd_product
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
  CONSTRAINT fk_pvd_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_value_varchar (
  product_id   BIGINT UNSIGNED NOT NULL,
  attribute_id INT UNSIGNED NOT NULL,
  value        VARCHAR(255) NOT NULL,
  PRIMARY KEY (product_id, attribute_id),
  KEY idx_pvv_filter (attribute_id, value, product_id),
  CONSTRAINT fk_pvv_product
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
  CONSTRAINT fk_pvv_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_value_text (
  product_id   BIGINT UNSIGNED NOT NULL,
  attribute_id INT UNSIGNED NOT NULL,
  value        TEXT NOT NULL,
  PRIMARY KEY (product_id, attribute_id),
  CONSTRAINT fk_pvt_product
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
  CONSTRAINT fk_pvt_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_value_datetime (
  product_id   BIGINT UNSIGNED NOT NULL,
  attribute_id INT UNSIGNED NOT NULL,
  value        DATETIME NOT NULL,
  PRIMARY KEY (product_id, attribute_id),
  KEY idx_pvdt_filter (attribute_id, value, product_id),
  CONSTRAINT fk_pvdt_product
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
  CONSTRAINT fk_pvdt_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_value_option (
  product_id   BIGINT UNSIGNED NOT NULL,
  attribute_id INT UNSIGNED NOT NULL,
  option_id    INT UNSIGNED NOT NULL,
  PRIMARY KEY (product_id, attribute_id),
  KEY idx_pvo_filter (attribute_id, option_id, product_id),
  CONSTRAINT fk_pvo_product
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
  CONSTRAINT fk_pvo_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id),
  CONSTRAINT fk_pvo_option
    FOREIGN KEY (option_id) REFERENCES attribute_option(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_value_multi_option (
  product_id   BIGINT UNSIGNED NOT NULL,
  attribute_id INT UNSIGNED NOT NULL,
  option_id    INT UNSIGNED NOT NULL,
  PRIMARY KEY (product_id, attribute_id, option_id),
  KEY idx_pvmo_filter (attribute_id, option_id, product_id),
  CONSTRAINT fk_pvmo_product
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
  CONSTRAINT fk_pvmo_attribute
    FOREIGN KEY (attribute_id) REFERENCES attribute(id),
  CONSTRAINT fk_pvmo_option
    FOREIGN KEY (option_id) REFERENCES attribute_option(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
