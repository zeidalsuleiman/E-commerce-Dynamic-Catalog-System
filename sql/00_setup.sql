-- Creates the catalog database and the app user.
-- In Docker, this runs automatically via the MySQL image's
-- /docker-entrypoint-initdb.d/ mechanism, in alphabetical order,
-- BEFORE schema.sql and any seed step.

CREATE DATABASE IF NOT EXISTS catalog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- MYSQL_USER/MYSQL_PASSWORD env vars on the official mysql image already
-- create this user, but we grant explicitly here for clarity/portability
-- (e.g. if you ever run schema.sql by hand against a fresh server).
CREATE USER IF NOT EXISTS 'catalog_user'@'%' IDENTIFIED BY 'change_me';
GRANT ALL PRIVILEGES ON catalog.* TO 'catalog_user'@'%';
FLUSH PRIVILEGES;
