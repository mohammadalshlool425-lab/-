-- عزوتك production schema, migration 0001.
-- Run with a migration role over TLS. The application role must not own this schema.
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS app_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_subject text NOT NULL UNIQUE,
    phone_e164 text UNIQUE,
    display_name text,
    locale text NOT NULL DEFAULT 'ar-JO' CHECK (locale IN ('ar-JO', 'en')),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS service_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    name_ar text NOT NULL,
    name_en text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS services (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id uuid NOT NULL REFERENCES service_categories(id),
    slug text NOT NULL UNIQUE,
    name_ar text NOT NULL,
    name_en text,
    minimum_amount_minor bigint NOT NULL CHECK (minimum_amount_minor >= 0),
    currency char(3) NOT NULL DEFAULT 'JOD' CHECK (currency = 'JOD'),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS providers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id uuid NOT NULL UNIQUE REFERENCES app_users(id),
    business_name text NOT NULL,
    city text NOT NULL CHECK (city IN ('amman', 'irbid', 'zarqa', 'aqaba', 'other')),
    verification_status text NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected', 'suspended')),
    rating numeric(2, 1) CHECK (rating >= 0 AND rating <= 5),
    active boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provider_services (
    provider_id uuid NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    service_id uuid NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    PRIMARY KEY (provider_id, service_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_code text NOT NULL UNIQUE,
    customer_id uuid NOT NULL REFERENCES app_users(id),
    service_id uuid NOT NULL REFERENCES services(id),
    provider_id uuid REFERENCES providers(id),
    status text NOT NULL DEFAULT 'requested' CHECK (status IN ('requested', 'assigned', 'on_the_way', 'in_progress', 'completed', 'cancelled')),
    city text NOT NULL CHECK (city IN ('amman', 'irbid', 'zarqa', 'aqaba', 'other')),
    address_ciphertext bytea,
    address_nonce bytea,
    address_key_version smallint,
    estimated_amount_minor bigint NOT NULL CHECK (estimated_amount_minor >= 0),
    final_amount_minor bigint CHECK (final_amount_minor IS NULL OR final_amount_minor >= 0),
    currency char(3) NOT NULL DEFAULT 'JOD' CHECK (currency = 'JOD'),
    scheduled_from timestamptz NOT NULL,
    scheduled_to timestamptz NOT NULL,
    idempotency_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (scheduled_to > scheduled_from),
    CHECK ((address_ciphertext IS NULL AND address_nonce IS NULL AND address_key_version IS NULL) OR (address_ciphertext IS NOT NULL AND address_nonce IS NOT NULL AND address_key_version IS NOT NULL)),
    UNIQUE (customer_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS order_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    actor_subject text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL UNIQUE REFERENCES orders(id),
    provider text NOT NULL CHECK (provider IN ('cliq', 'card_gateway', 'cash_on_completion')),
    provider_reference text UNIQUE,
    amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
    currency char(3) NOT NULL DEFAULT 'JOD' CHECK (currency = 'JOD'),
    status text NOT NULL CHECK (status IN ('pending', 'authorized', 'captured', 'failed', 'refunded')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL UNIQUE REFERENCES orders(id),
    customer_id uuid NOT NULL REFERENCES app_users(id),
    provider_id uuid NOT NULL REFERENCES providers(id),
    rating smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    actor_subject text,
    action text NOT NULL,
    resource_type text,
    resource_id text,
    outcome text NOT NULL CHECK (outcome IN ('success', 'denied', 'failure')),
    client_fingerprint text,
    request_id text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_created ON orders (customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_provider_status ON orders (provider_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status_city ON orders (status, city, scheduled_from);
CREATE INDEX IF NOT EXISTS idx_order_events_order_created ON order_events (order_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON audit_events (actor_subject, created_at DESC);

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS app_users_set_updated_at ON app_users;
CREATE TRIGGER app_users_set_updated_at BEFORE UPDATE ON app_users FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS services_set_updated_at ON services;
CREATE TRIGGER services_set_updated_at BEFORE UPDATE ON services FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS providers_set_updated_at ON providers;
CREATE TRIGGER providers_set_updated_at BEFORE UPDATE ON providers FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS orders_set_updated_at ON orders;
CREATE TRIGGER orders_set_updated_at BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS payments_set_updated_at ON payments;
CREATE TRIGGER payments_set_updated_at BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE audit_events IS 'Append-only compliance log. Application role must not UPDATE or DELETE rows.';
COMMENT ON COLUMN orders.address_ciphertext IS 'Application-encrypted address; never store plaintext location here.';
COMMENT ON COLUMN orders.idempotency_key IS 'Client-generated key required for safe retries.';

REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC;

COMMIT;
