-- One database, all clients, keyed by client_slug.
-- Deploy: wrangler d1 create makeitring-leads && wrangler d1 execute makeitring-leads --file=schema.sql

CREATE TABLE IF NOT EXISTS leads (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  client      TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  name        TEXT,
  phone       TEXT,
  email       TEXT,
  service     TEXT,
  moving_from TEXT,
  moving_to   TEXT,
  move_date   TEXT,
  -- the attribution chain, captured by the landing page's hidden fields
  gclid       TEXT,
  campaign    TEXT,
  content     TEXT,
  keyword     TEXT,
  landing_page TEXT,
  -- filled in later by a human or the CRM: is this a booked job, and for how much
  status      TEXT DEFAULT 'new',       -- new | contacted | quoted | booked | lost
  job_value   REAL
);

CREATE TABLE IF NOT EXISTS calls (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  client         TEXT NOT NULL,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  caller_number  TEXT,
  caller_name    TEXT,
  duration_sec   INTEGER,
  recording_url  TEXT,
  tracking_number TEXT,
  first_call     INTEGER DEFAULT 0,
  -- call tracking vendors pass through what they know about the click
  gclid          TEXT,
  campaign       TEXT,
  keyword        TEXT,
  answered       INTEGER DEFAULT 1,
  status         TEXT DEFAULT 'new',
  job_value      REAL
);

-- every paid click the landing page sees, for the fraud layer
CREATE TABLE IF NOT EXISTS clicks (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  client     TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  ip         TEXT,
  gclid      TEXT,
  campaign   TEXT,
  keyword    TEXT,
  user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_leads_client ON leads(client, created_at);
CREATE INDEX IF NOT EXISTS idx_calls_client ON calls(client, created_at);
CREATE INDEX IF NOT EXISTS idx_clicks_ip    ON clicks(client, ip, created_at);
