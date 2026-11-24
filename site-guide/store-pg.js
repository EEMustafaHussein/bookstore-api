'use strict';
const {Pool} = require('pg');

const pool = new Pool({connectionString: process.env.DATABASE_URL, ssl: {rejectUnauthorized: false}, max: 5});
const q = async (sql, params = []) => (await pool.query(sql, params)).rows;
const bump = () => q("UPDATE meta SET v = v + 1 WHERE k = 'version'");

const DDL = [
  'CREATE TABLE IF NOT EXISTS meta (k text PRIMARY KEY, v bigint NOT NULL)',
  'CREATE TABLE IF NOT EXISTS config (k text PRIMARY KEY, v jsonb NOT NULL)',
  'CREATE TABLE IF NOT EXISTS zones (id int PRIMARY KEY, name text NOT NULL, short text NOT NULL, kind text NOT NULL, hz text, temp boolean NOT NULL DEFAULT true, is_new boolean NOT NULL DEFAULT false, poly jsonb NOT NULL, entry jsonb, updated_at timestamptz NOT NULL DEFAULT now())',
  'CREATE TABLE IF NOT EXISTS roads (id serial PRIMARY KEY, name text NOT NULL, pts jsonb NOT NULL)',
  'CREATE TABLE IF NOT EXISTS features (id serial PRIMARY KEY, kind text NOT NULL, lat double precision NOT NULL, lon double precision NOT NULL, r_m double precision NOT NULL)',
  "CREATE TABLE IF NOT EXISTS works (id text PRIMARY KEY, zone_id int NOT NULL, title text NOT NULL, crew jsonb NOT NULL DEFAULT '[]', permit text, ptw text, shift text, status text NOT NULL, sup text, day date, updated_at timestamptz NOT NULL DEFAULT now())",
  'CREATE TABLE IF NOT EXISTS blobs (k text PRIMARY KEY, mime text NOT NULL, data bytea NOT NULL)',
  'CREATE TABLE IF NOT EXISTS pois (id serial PRIMARY KEY, label text NOT NULL, zone_id int, lat double precision NOT NULL, lon double precision NOT NULL)',
  "INSERT INTO meta (k, v) VALUES ('version', 1) ON CONFLICT (k) DO NOTHING"
];
const ZONE_COLS = 'id, name, short, kind, hz, temp, is_new, poly, entry';
const WORK_COLS = "id, zone_id, title, crew, permit, ptw, shift, status, sup, to_char(day, 'YYYY-MM-DD') AS day";

module.exports = {
  async init() { for (const s of DDL) await q(s); },
  async version() { return Number((await q("SELECT v FROM meta WHERE k = 'version'"))[0].v); },
  async site() {
    const [cfg, zones, roads, features, pois] = await Promise.all([
      q("SELECT v FROM config WHERE k = 'map'"),
      q(`SELECT ${ZONE_COLS} FROM zones ORDER BY id`),
      q('SELECT name, pts FROM roads ORDER BY id'),
      q('SELECT kind, lat, lon, r_m FROM features ORDER BY id'),
      q('SELECT id, label, zone_id, lat, lon FROM pois ORDER BY id')
    ]);
    return {config: cfg[0] ? cfg[0].v : null, zones, roads, features, pois, version: await this.version()};
  },
  async works() { return q(`SELECT ${WORK_COLS} FROM works ORDER BY updated_at DESC`); },
  async blob(k) { return (await q('SELECT mime, data FROM blobs WHERE k = $1', [k]))[0] || null; },
  async addZone(z) {
    const r = await q(`INSERT INTO zones (id, name, short, kind, hz, temp, is_new, poly, entry)
      VALUES ((SELECT COALESCE(MAX(id), 0) + 1 FROM zones), $1, $2, $3, $4, false, false, $5::jsonb, $6::jsonb) RETURNING ${ZONE_COLS}`,
      [z.name, z.short, z.kind, z.hz, JSON.stringify(z.poly), z.entry ? JSON.stringify(z.entry) : null]);
    await bump(); return r[0];
  },
  async updateZone(id, z) {
    const sets = [], vals = [];
    for (const [k, v] of Object.entries(z)) {
      vals.push(k === 'poly' || k === 'entry' ? (v == null ? null : JSON.stringify(v)) : v);
      sets.push(`${k} = $${vals.length}${k === 'poly' || k === 'entry' ? '::jsonb' : ''}`);
    }
    if (!sets.length) return null;
    vals.push(id);
    const r = await q(`UPDATE zones SET ${sets.join(', ')}, updated_at = now() WHERE id = $${vals.length} RETURNING ${ZONE_COLS}`, vals);
    await bump(); return r[0] || null;
  },
  async deleteZone(id) {
    await q("DELETE FROM works WHERE zone_id = $1 AND status = 'done'", [id]);
    const open = await q('SELECT count(*)::int AS n FROM works WHERE zone_id = $1', [id]);
    if (open[0].n) { const e = new Error('zone_has_open_works'); e.status = 409; throw e; }
    await q('DELETE FROM zones WHERE id = $1', [id]); await bump();
  },
  async addWork(w) {
    const r = await q(`INSERT INTO works (id, zone_id, title, crew, permit, ptw, shift, status, sup, day)
      VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10) RETURNING ${WORK_COLS}`,
      [w.id, w.zone_id, w.title, JSON.stringify(w.crew), w.permit, w.ptw, w.shift, w.status, w.sup, w.day]);
    await bump(); return r[0];
  },
  async updateWork(id, w) {
    const r = await q(`UPDATE works SET zone_id = $2, title = $3, crew = $4::jsonb, permit = $5, ptw = $6, shift = $7, status = $8, sup = $9, day = $10, updated_at = now()
      WHERE id = $1 RETURNING ${WORK_COLS}`,
      [id, w.zone_id, w.title, JSON.stringify(w.crew), w.permit, w.ptw, w.shift, w.status, w.sup, w.day]);
    await bump(); return r[0] || null;
  },
  async deleteWork(id) { await q('DELETE FROM works WHERE id = $1', [id]); await bump(); }
};
