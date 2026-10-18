-- ==============================================================================
-- CAMRAIL RailMind Lite - Initialisation sécurisée PostgreSQL & pgvector
-- ==============================================================================
-- Ce script est exécuté automatiquement à l'initialisation du conteneur DB
-- par le super-utilisateur postgres (/docker-entrypoint-initdb.d/init.sql).
--
-- Principes de sécurité :
-- 1. L'extension 'vector' est créée par le super-utilisateur (privilège requis).
-- 2. Le rôle applicatif 'railmind_app' est créé SANS droits de super-utilisateur
--    (NOSUPERUSER, NOCREATEDB, NOCREATEROLE).
-- 3. La base de données 'railmind' et le schéma 'public' sont transférés à
--    'railmind_app', permettant à Alembic de migrer les tables et index sans
--    jamais compromettre l'instance PostgreSQL globale.
-- ==============================================================================

-- 1. Activation de l'extension pgvector dans la base de données courante (railmind)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Création du rôle applicatif restreint (sans privilège super-utilisateur)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'railmind_app'
   ) THEN
      CREATE ROLE railmind_app WITH LOGIN PASSWORD 'railmind_app_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE;
   END IF;
END
$do$;

-- 3. Attribution de la propriété de la base et du schéma public au rôle applicatif
ALTER DATABASE railmind OWNER TO railmind_app;
ALTER SCHEMA public OWNER TO railmind_app;

-- 4. Attribution des droits d'accès et d'exécution
GRANT ALL PRIVILEGES ON DATABASE railmind TO railmind_app;
GRANT ALL ON SCHEMA public TO railmind_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO railmind_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO railmind_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO railmind_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO railmind_app;

-- 5. Protection en profondeur du journal d'audit (Chaîne de hachage et immuabilité)
-- Limite architecturale documentée :
-- Le propriétaire de la table ou le super-utilisateur peut modifier ou contourner les triggers.
-- C'est la chaîne cryptographique HMAC-SHA256 vérifiée par l'application (verify_chain) qui
-- détecte de façon infaillible toute altération, suppression ou insertion frauduleuse.
CREATE OR REPLACE FUNCTION prevent_audit_logs_tampering()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs are immutable: UPDATE, DELETE, and TRUNCATE are strictly prohibited.';
END;
$$ LANGUAGE plpgsql;

