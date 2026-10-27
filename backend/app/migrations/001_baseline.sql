-- Baseline: the schema as of the pre-runner release (incl. dose_tenths, shift_time_seconds).
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    registered INTEGER NOT NULL DEFAULT 0,
    firmware_version TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    ott_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    remote_addr TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qc_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_state (
    device_id TEXT PRIMARY KEY,
    schedule_synced INTEGER NOT NULL DEFAULT 0,
    settings_synced INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    dose_count INTEGER NOT NULL,
    cmd INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS protocol_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    device_id TEXT,
    status INTEGER NOT NULL,
    request_json TEXT,
    response_json TEXT,
    headers_json TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS device_controls (
    device_id TEXT PRIMARY KEY,
    dispensing_enabled INTEGER NOT NULL DEFAULT 0,
    sync_interval_seconds INTEGER,
    dose_tenths INTEGER,
    shift_time_seconds INTEGER,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dispenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    code INTEGER NOT NULL,
    device_timestamp INTEGER,
    received_at TEXT NOT NULL,
    UNIQUE (device_id, code, device_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_dispenses_device
    ON dispenses(device_id, id DESC);
CREATE TABLE IF NOT EXISTS dispense_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    nonce INTEGER NOT NULL,
    requested_at TEXT NOT NULL,
    delivered_at TEXT,
    cancelled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_dispense_requests_pending
    ON dispense_requests(device_id, delivered_at, cancelled_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_device_ts
    ON telemetry(device_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_device_ts
    ON events(device_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON protocol_logs(ts DESC);
CREATE INDEX IF NOT EXISTS idx_schedules_device
    ON schedules(device_id, active, timestamp);
