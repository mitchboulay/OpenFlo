-- Migration 003 (B3.1): schedule rules expand server-side into <= 33 device entries (AD-6).
-- Replaces the unused 001 `schedules` table and the `enable_schedule` setting.

CREATE TABLE schedule_rules (id INTEGER PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(device_id),
  kind TEXT NOT NULL CHECK (kind IN ('daily','weekly','interval','once')),
  local_time TEXT, days_mask INTEGER, interval_hours INTEGER, at_epoch INTEGER,
  dose_count INTEGER NOT NULL DEFAULT 1 CHECK (dose_count IN (1,2)), enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, actor TEXT NOT NULL);
CREATE INDEX schedule_rules_device ON schedule_rules(device_id, id);

CREATE TABLE schedule_entries (id INTEGER PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(device_id),
  timestamp INTEGER NOT NULL, dose_count INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','served','fired','missed','cleared')),
  reason TEXT, served_at TEXT, fired_at TEXT, UNIQUE (device_id, timestamp));
CREATE INDEX schedule_entries_due ON schedule_entries(device_id, status, timestamp);

CREATE TABLE schedule_entry_rules (entry_id INTEGER NOT NULL REFERENCES schedule_entries(id),
  rule_id INTEGER NOT NULL REFERENCES schedule_rules(id), PRIMARY KEY (entry_id, rule_id));
CREATE INDEX schedule_entry_rules_rule ON schedule_entry_rules(rule_id);

-- Hash of the (timestamp, doseCount) set last served; NULL = must be (re)served (AD-6).
ALTER TABLE sync_state ADD COLUMN schedule_hash TEXT;

DROP TABLE schedules;
