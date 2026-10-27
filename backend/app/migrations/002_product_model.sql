-- 002: product model (homes, device registry columns, syncs, flags, dosing, bottles, provisioning, settings).
-- DDL follows the product data model verbatim, except that the two
-- device_dosing table CHECKs are placed after the last column (SQLite rejects column definitions after a
-- table constraint; the constraints are unchanged), and four foreign-key lookup indexes are added.

CREATE TABLE settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL, actor TEXT NOT NULL);
-- keys: instance_id, server_address, admin_user, admin_password_hash, address_check (last result)

CREATE TABLE api_tokens (id INTEGER PRIMARY KEY, token_sha256 TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  actor TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('personal','oidc','bootstrap')),
  created_at TEXT NOT NULL, expires_at TEXT, last_used_at TEXT, revoked_at TEXT);

CREATE TABLE homes (id INTEGER PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL,
  created_at TEXT NOT NULL, actor TEXT NOT NULL);
CREATE UNIQUE INDEX homes_name ON homes(lower(name));

ALTER TABLE devices ADD COLUMN home_id INTEGER REFERENCES homes(id);
ALTER TABLE devices ADD COLUMN name TEXT;
ALTER TABLE devices ADD COLUMN location TEXT;
ALTER TABLE devices ADD COLUMN installed_at TEXT;
ALTER TABLE devices ADD COLUMN mac TEXT;             -- display only (lab profile)
ALTER TABLE devices ADD COLUMN last_ip TEXT;         -- display + identity flags only
ALTER TABLE devices ADD COLUMN hardware_type TEXT CHECK (hardware_type IN ('valve','motor'));
ALTER TABLE devices ADD COLUMN pcb_version TEXT;
ALTER TABLE devices ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
  CHECK (status IN ('provisioning','active','unclaimed','retired'));
ALTER TABLE devices ADD COLUMN retire_requested_at TEXT;
CREATE INDEX devices_home ON devices(home_id, status);
CREATE INDEX devices_status ON devices(status);

CREATE TABLE device_syncs (id INTEGER PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(device_id),
  started_at TEXT NOT NULL, ended_at TEXT NOT NULL, request_count INTEGER NOT NULL, source_ip TEXT NOT NULL,
  UNIQUE (device_id, started_at));
CREATE INDEX device_syncs_recent ON device_syncs(device_id, started_at DESC);

CREATE TABLE device_identity_flags (id INTEGER PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(device_id),
  kind TEXT NOT NULL CHECK (kind IN ('ip_conflict','telemetry_implausible')), detail_json TEXT NOT NULL,
  raised_at TEXT NOT NULL, acked_at TEXT, acked_by TEXT);
CREATE INDEX identity_flags_open ON device_identity_flags(device_id, acked_at);

CREATE TABLE liquid_profiles (id INTEGER PRIMARY KEY, home_id INTEGER REFERENCES homes(id),  -- NULL = system
  slug TEXT NOT NULL, name TEXT NOT NULL, flow_full_ml_s REAL NOT NULL CHECK (flow_full_ml_s > 0),
  curve_json TEXT NOT NULL, capacity_ml REAL NOT NULL CHECK (capacity_ml > 0),
  default_dose_ml REAL NOT NULL CHECK (default_dose_ml > 0), calibrated INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, actor TEXT NOT NULL);
CREATE UNIQUE INDEX liquid_profiles_slug ON liquid_profiles(coalesce(home_id, 0), slug);

CREATE TABLE device_dosing (device_id TEXT PRIMARY KEY REFERENCES devices(device_id),
  profile_id INTEGER NOT NULL REFERENCES liquid_profiles(id), dose_ml REAL, fixed_tenths INTEGER,
  compensation_enabled INTEGER NOT NULL DEFAULT 1,
  flow_scale REAL NOT NULL DEFAULT 1.0 CHECK (flow_scale BETWEEN 0.2 AND 5.0),
  updated_at TEXT NOT NULL, actor TEXT NOT NULL,
  CHECK ((dose_ml IS NULL) <> (fixed_tenths IS NULL)),
  CHECK (fixed_tenths IS NULL OR fixed_tenths BETWEEN 10 AND 300));
CREATE TABLE dose_servings (id INTEGER PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(device_id),
  served_at TEXT NOT NULL, tenths INTEGER NOT NULL, flow_ml_s REAL NOT NULL);
CREATE INDEX dose_servings_recent ON dose_servings(device_id, served_at DESC);

CREATE TABLE bottles (id INTEGER PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(device_id),
  profile_id INTEGER NOT NULL REFERENCES liquid_profiles(id), capacity_ml REAL NOT NULL,
  initial_fill_ml REAL, started_at TEXT NOT NULL, ended_at TEXT, end_reason TEXT);
CREATE UNIQUE INDEX bottles_one_open ON bottles(device_id) WHERE ended_at IS NULL;
CREATE TABLE fill_adjustments (id INTEGER PRIMARY KEY, bottle_id INTEGER NOT NULL REFERENCES bottles(id),
  delta_ml REAL NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL, actor TEXT NOT NULL);

ALTER TABLE dispenses ADD COLUMN bottle_id INTEGER REFERENCES bottles(id);
ALTER TABLE dispenses ADD COLUMN est_volume_ml REAL;
ALTER TABLE dispenses ADD COLUMN dose_count INTEGER NOT NULL DEFAULT 1;

ALTER TABLE device_controls ADD COLUMN wake_preset TEXT
  CHECK (wake_preset IN ('battery_saver','balanced','responsive','testing'));
ALTER TABLE device_controls ADD COLUMN schedules_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE device_controls ADD COLUMN actor TEXT;

CREATE TABLE provisioning_sessions (id INTEGER PRIMARY KEY, home_id INTEGER NOT NULL REFERENCES homes(id),
  kind TEXT NOT NULL CHECK (kind IN ('new','reset')), target_device_id TEXT REFERENCES devices(device_id),
  device_name TEXT NOT NULL, location TEXT, ott_sha256 TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('awaiting_reset','awaiting_softap','awaiting_join',
    'completed','expired','failed','cancelled')),
  bound_device_id TEXT, bound_ip TEXT, reset_requested_at TEXT, reset_result TEXT,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, completed_at TEXT, actor TEXT NOT NULL);
CREATE INDEX provisioning_open ON provisioning_sessions(status, expires_at);
CREATE TABLE provisioning_events (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES provisioning_sessions(id),
  at TEXT NOT NULL, step TEXT NOT NULL, detail_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE pairing_sightings (device_id TEXT NOT NULL, source_ip TEXT NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, PRIMARY KEY (device_id, source_ip));

-- Lookup indexes beyond the doc DDL, for foreign keys read on hot paths (bottle remaining volume, provisioning
-- progress, register's sighting-by-IP binding).
CREATE INDEX fill_adjustments_bottle ON fill_adjustments(bottle_id);
CREATE INDEX dispenses_bottle ON dispenses(bottle_id);
CREATE INDEX provisioning_events_session ON provisioning_events(session_id);
CREATE INDEX pairing_sightings_ip ON pairing_sightings(source_ip, last_seen);

-- ---------------------------------------------------------------------------------------------------------
-- Data steps. Timestamps use the app's ISO-8601 UTC form.

-- settings.instance_id: this server instance's stable identity (served as X-OpenFLO-Instance and in
-- /api/v1/server-info). A random RFC 4122 version-4 UUID, stored as a JSON string.
INSERT INTO settings (key, value_json, updated_at, actor)
SELECT 'instance_id',
       '"' || substr(h, 1, 8) || '-' || substr(h, 9, 4) || '-4' || substr(h, 14, 3) || '-'
           || substr('89ab', 1 + (abs(random()) % 4), 1) || substr(h, 18, 3) || '-' || substr(h, 21, 12) || '"',
       strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'), 'system'
FROM (SELECT lower(hex(randomblob(16))) AS h);

-- System liquid profiles (home_id NULL). Curve: (remaining fraction, flow multiplier) pairs, descending r (AD-5).
INSERT INTO liquid_profiles
  (home_id, slug, name, flow_full_ml_s, curve_json, capacity_ml, default_dose_ml, calibrated, created_at, actor)
VALUES
  (NULL, 'standard', 'Standard', 27.2,
   '[[1.0,1.00],[0.83,0.93],[0.67,0.89],[0.50,0.81],[0.33,0.66],[0.17,0.25],[0.0,0.25]]',
   1065, 177, 1, strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'), 'system'),
  (NULL, 'vinegar', 'Vinegar', 27.2,
   '[[1.0,1.00],[0.83,0.93],[0.67,0.89],[0.50,0.81],[0.33,0.66],[0.17,0.25],[0.0,0.25]]',
   1000, 120, 0, strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'), 'system');

-- Every existing device gets a dosing row on the standard profile: device_controls.dose_tenths moves into
-- fixed_tenths (column left unused, dropped in 004), otherwise 177 mL by volume. Fresh installs have no devices.
INSERT INTO device_dosing (device_id, profile_id, dose_ml, fixed_tenths, updated_at, actor)
SELECT d.device_id,
       (SELECT id FROM liquid_profiles WHERE home_id IS NULL AND slug = 'standard'),
       CASE WHEN c.dose_tenths IS NULL THEN 177 END,
       c.dose_tenths,
       strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'), 'system'
FROM devices d LEFT JOIN device_controls c ON c.device_id = d.device_id;

-- Upgrade for a pre-002 install: every existing device moves into one home named "Home". Each step is a
-- no-op without devices, so a fresh install gets no home. Per-unit facts (MAC, hardware type, PCB) stay NULL
-- until the device reports them; last_ip comes from its latest registration. device_controls rows are
-- untouched (wake_preset stays NULL = Custom).
INSERT INTO homes (name, timezone, created_at, actor)
SELECT 'Home', 'UTC', strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'), 'system'
WHERE EXISTS (SELECT 1 FROM devices);

UPDATE devices
SET home_id = (SELECT id FROM homes WHERE lower(name) = 'home'),
    name = coalesce(
      CASE WHEN json_valid(metadata_json) THEN nullif(trim(json_extract(metadata_json, '$.name')), '') END, 'iFLO'),
    last_ip = (SELECT r.remote_addr FROM registrations r
               WHERE r.device_id = devices.device_id AND r.remote_addr IS NOT NULL
               ORDER BY r.created_at DESC, r.id DESC LIMIT 1),
    installed_at = coalesce(
      (SELECT min(created_at) FROM registrations r WHERE r.device_id = devices.device_id), first_seen),
    status = CASE WHEN registered = 1 THEN 'active' ELSE status END;

INSERT INTO bottles (device_id, profile_id, capacity_ml, initial_fill_ml, started_at)
SELECT d.device_id, p.id, p.capacity_ml, NULL, strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')
FROM devices d JOIN liquid_profiles p ON p.home_id IS NULL AND p.slug = 'standard';

-- Seed each pre-existing device's last check-in as one sync, so sync honesty (FR-14) knows the device has
-- checked in and the next expected wake is computable from the first deploy, not only after its next wake.
INSERT INTO device_syncs (device_id, started_at, ended_at, request_count, source_ip)
SELECT device_id, last_seen, last_seen, 1, coalesce(last_ip, '')
FROM devices;
