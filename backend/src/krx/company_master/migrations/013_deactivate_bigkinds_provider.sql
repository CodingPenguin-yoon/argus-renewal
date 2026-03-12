UPDATE provider_registry
SET
    is_active = 0,
    updated_at = CURRENT_TIMESTAMP
WHERE provider_key = 'BIGKINDS';
