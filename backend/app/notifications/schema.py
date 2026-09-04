from __future__ import annotations


NOTIFICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_notification_alert_ledger (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id TEXT NOT NULL UNIQUE,
  client_key TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  FOREIGN KEY(alert_id)
    REFERENCES product_alert_events(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_product_notification_alert_ledger_client
ON product_notification_alert_ledger(client_key, sequence);

CREATE TABLE IF NOT EXISTS product_notification_devices (
  id TEXT PRIMARY KEY,
  client_key TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT 'expo',
  token_hash TEXT NOT NULL UNIQUE,
  push_token TEXT NOT NULL,
  platform TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  alert_watermark INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  disabled_at TEXT,
  CHECK (provider = 'expo'),
  CHECK (platform IN ('ios', 'android')),
  CHECK (enabled IN (0, 1)),
  CHECK (alert_watermark >= 0)
);

CREATE INDEX IF NOT EXISTS idx_product_notification_devices_client
ON product_notification_devices(client_key, enabled, created_at, id);

CREATE TABLE IF NOT EXISTS product_notification_deliveries (
  id TEXT PRIMARY KEY,
  client_key TEXT NOT NULL,
  device_id TEXT NOT NULL,
  alert_id TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT 'expo',
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  available_at_epoch INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT NOT NULL DEFAULT '',
  lease_expires_at_epoch INTEGER NOT NULL DEFAULT 0,
  provider_message_id TEXT NOT NULL DEFAULT '',
  error_type TEXT NOT NULL DEFAULT '',
  error_detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  accepted_at TEXT,
  CHECK (provider = 'expo'),
  CHECK (status IN ('pending', 'sending', 'accepted', 'failed', 'cancelled')),
  CHECK (attempts >= 0),
  CHECK (available_at_epoch >= 0),
  CHECK (lease_expires_at_epoch >= 0),
  UNIQUE (device_id, alert_id),
  FOREIGN KEY(device_id)
    REFERENCES product_notification_devices(id)
    ON DELETE CASCADE,
  FOREIGN KEY(alert_id)
    REFERENCES product_alert_events(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_product_notification_delivery_ready
ON product_notification_deliveries(status, available_at_epoch, created_at, id);

CREATE INDEX IF NOT EXISTS idx_product_notification_delivery_client
ON product_notification_deliveries(client_key, created_at, id);

CREATE TABLE IF NOT EXISTS product_web_push_subscriptions (
  id TEXT PRIMARY KEY,
  client_key TEXT NOT NULL,
  subscription_hash TEXT NOT NULL UNIQUE,
  endpoint TEXT NOT NULL,
  p256dh TEXT NOT NULL,
  auth_secret TEXT NOT NULL,
  expiration_time INTEGER,
  enabled INTEGER NOT NULL DEFAULT 1,
  alert_watermark INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  disabled_at TEXT,
  CHECK (enabled IN (0, 1)),
  CHECK (alert_watermark >= 0),
  CHECK (expiration_time IS NULL OR expiration_time >= 0)
);

CREATE INDEX IF NOT EXISTS idx_product_web_push_subscriptions_client
ON product_web_push_subscriptions(client_key, enabled, created_at, id);

CREATE TABLE IF NOT EXISTS product_web_push_deliveries (
  id TEXT PRIMARY KEY,
  client_key TEXT NOT NULL,
  subscription_id TEXT NOT NULL,
  alert_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  available_at_epoch INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT NOT NULL DEFAULT '',
  lease_expires_at_epoch INTEGER NOT NULL DEFAULT 0,
  provider_message_id TEXT NOT NULL DEFAULT '',
  error_type TEXT NOT NULL DEFAULT '',
  error_detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  accepted_at TEXT,
  CHECK (status IN ('pending', 'sending', 'accepted', 'failed', 'cancelled')),
  CHECK (attempts >= 0),
  CHECK (available_at_epoch >= 0),
  CHECK (lease_expires_at_epoch >= 0),
  UNIQUE (subscription_id, alert_id),
  FOREIGN KEY(subscription_id)
    REFERENCES product_web_push_subscriptions(id)
    ON DELETE CASCADE,
  FOREIGN KEY(alert_id)
    REFERENCES product_alert_events(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_product_web_push_delivery_ready
ON product_web_push_deliveries(status, available_at_epoch, created_at, id);

CREATE INDEX IF NOT EXISTS idx_product_web_push_delivery_client
ON product_web_push_deliveries(client_key, created_at, id);

CREATE TRIGGER IF NOT EXISTS product_notification_alert_ledger_append
AFTER INSERT ON product_alert_events BEGIN
  INSERT OR IGNORE INTO product_notification_alert_ledger(
    alert_id,
    client_key,
    detected_at
  ) VALUES (
    NEW.id,
    NEW.client_key,
    NEW.detected_at
  );
END;
"""


__all__ = ["NOTIFICATION_SCHEMA"]
