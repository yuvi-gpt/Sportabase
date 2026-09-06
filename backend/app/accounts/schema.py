ACCOUNT_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_accounts (
 id TEXT PRIMARY KEY, subject_hash TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'active', defaults_json TEXT NOT NULL DEFAULT '{}',
 revision INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL,
 last_seen_at INTEGER NOT NULL, first_analysis_at INTEGER,
 CHECK(status IN ('active','deleting','deleted'))
);
CREATE TABLE IF NOT EXISTS product_installations (
 account_id TEXT NOT NULL REFERENCES product_accounts(id) ON DELETE CASCADE,
 device_id TEXT NOT NULL, platform TEXT NOT NULL, name TEXT NOT NULL,
 follows_defaults INTEGER NOT NULL DEFAULT 1, overrides_json TEXT NOT NULL DEFAULT '{}',
 revision INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL, last_seen_at INTEGER NOT NULL,
 PRIMARY KEY(account_id,device_id), CHECK(platform IN ('web','mobile','extension'))
);
CREATE TABLE IF NOT EXISTS product_legacy_links (
 legacy_key TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES product_accounts(id) ON DELETE CASCADE,
 device_id TEXT NOT NULL, linked_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS product_notification_bindings (
 provider TEXT NOT NULL, registration_id TEXT NOT NULL,
 account_id TEXT NOT NULL REFERENCES product_accounts(id) ON DELETE CASCADE,
 device_id TEXT NOT NULL, PRIMARY KEY(provider,registration_id)
);
CREATE TABLE IF NOT EXISTS product_activity (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES product_accounts(id) ON DELETE CASCADE,
 device_id TEXT NOT NULL, platform TEXT NOT NULL, kind TEXT NOT NULL,
 title TEXT NOT NULL, url TEXT NOT NULL, media_item_id TEXT,
 created_at INTEGER NOT NULL, CHECK(kind IN ('article','video'))
);
CREATE INDEX IF NOT EXISTS idx_product_activity_owner ON product_activity(account_id,created_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS product_analytics (
 id TEXT PRIMARY KEY, account_id TEXT REFERENCES product_accounts(id) ON DELETE CASCADE,
 event TEXT NOT NULL, platform TEXT NOT NULL, day TEXT NOT NULL,
 UNIQUE(account_id,event,platform,day,id)
);
CREATE INDEX IF NOT EXISTS idx_product_analytics_day ON product_analytics(day,event);
"""
