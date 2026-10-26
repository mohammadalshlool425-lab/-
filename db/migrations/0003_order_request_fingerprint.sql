-- عزوتك order idempotency fingerprint, migration 0003.
-- The keyed fingerprint detects a changed retry payload without storing plaintext address data.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS request_fingerprint bytea;

COMMENT ON COLUMN orders.request_fingerprint IS 'HMAC of the canonical order request, keyed by the deployment address-encryption key; used to reject changed idempotency replays.';
