'use strict';
// Site guide: map, GPS position, voice navigation and work orders for one industrial site.
// No site data lives in this repository: map, zones, roads and work orders come from the database.
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = Number(process.env.PORT) || 3000;
const SECRET = process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex');
const WORKER_CODE = process.env.WORKER_CODE || '';
const SUPERVISOR_PASSWORD = process.env.SUPERVISOR_PASSWORD || '';
const SECURE_COOKIE = process.env.NODE_ENV === 'production';
const store = process.env.DATABASE_URL ? require('./store-pg') : require('./store-memory');

if (!WORKER_CODE || !SUPERVISOR_PASSWORD) console.warn('WORKER_CODE and SUPERVISOR_PASSWORD must be set; logins are disabled until they are.');

/* ---------- sessions: signed, stateless cookie ---------- */
const sign = s => crypto.createHmac('sha256', SECRET).update(s).digest('base64url');
function makeToken(role) {
  const body = Buffer.from(JSON.stringify({role, exp: Date.now() + 30 * 864e5})).toString('base64url');
  return body + '.' + sign(body);
}
function readToken(req) {
  const m = /(?:^|;\s*)sg=([^;]+)/.exec(req.headers.cookie || '');
  if (!m) return null;
  const [body, mac] = m[1].split('.');
  if (!body || !mac) return null;
  const a = Buffer.from(mac), b = Buffer.from(sign(body));
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try { const t = JSON.parse(Buffer.from(body, 'base64url').toString()); return t.exp > Date.now() ? t : null; } catch { return null; }
}
const same = (a, b) => { const x = crypto.createHash('sha256').update(String(a)).digest(), y = crypto.createHash('sha256').update(String(b)).digest(); return crypto.timingSafeEqual(x, y); };

/* ---------- site plan overlay: stored encrypted (AES-256-GCM: iv | tag | data), key only in the environment ---------- */
let planCache;
function planImage() {
  if (planCache !== undefined) return planCache;
  planCache = null;
  try {
    const key = Buffer.from(process.env.OVERLAY_KEY || '', 'hex');
    if (key.length !== 32) return null;
    const buf = fs.readFileSync(path.join(__dirname, 'assets', 'plan.bin'));
    const d = crypto.createDecipheriv('aes-256-gcm', key, buf.subarray(0, 12));
    d.setAuthTag(buf.subarray(12, 28));
    planCache = Buffer.concat([d.update(buf.subarray(28)), d.final()]);
  } catch (e) { console.error('plan overlay unavailable:', e.message); }
  return planCache;
}

/* ---------- login rate limit ---------- */
const attempts = new Map();
function limited(ip) {
  const now = Date.now(), list = (attempts.get(ip) || []).filter(t => now - t < 10 * 60e3);
  attempts.set(ip, list);
  return list.length >= 10;
}

/* ---------- helpers ---------- */
function send(res, code, obj, headers = {}) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers});
  res.end(body);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => { size += c.length; if (size > 256 * 1024) { reject(new Error('too_large')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : {}); } catch { reject(new Error('bad_json')); } });
    req.on('error', reject);
  });
}
const str = (v, max) => (typeof v === 'string' ? v.trim().slice(0, max) : '');
const KINDS = ['وحدة تشغيل', 'خزانات', 'مرافق', 'خدمات', 'مباني', 'ساحة'];
const HZ = ['z1', 'z2', 'hv', 'restricted'];
const PERMITS = ['hot', 'cold', 'loto', 'cse', 'height'];
const SHIFTS = ['am', 'pm', 'night'];
const STATUSES = ['planned', 'active', 'done'];
function cleanPoly(p) {
  if (!Array.isArray(p) || p.length < 3 || p.length > 200) return null;
  const out = p.map(q => Array.isArray(q) && q.length === 2 && q.every(Number.isFinite) ? [Math.round(q[0] * 1e7) / 1e7, Math.round(q[1] * 1e7) / 1e7] : null);
  return out.every(Boolean) && out.every(([la, lo]) => Math.abs(la) <= 90 && Math.abs(lo) <= 180) ? out : null;
}
const cleanPoint = p => (Array.isArray(p) && p.length === 2 && p.every(Number.isFinite) ? p : null);
function cleanZone(b, partial) {
  const z = {};
  if (b.name !== undefined || !partial) { z.name = str(b.name, 80); if (!z.name) return null; }
  if (b.short !== undefined || !partial) z.short = str(b.short, 30) || z.name;
  if (b.kind !== undefined || !partial) z.kind = KINDS.includes(b.kind) ? b.kind : 'وحدة تشغيل';
  if (b.hz !== undefined || !partial) z.hz = HZ.includes(b.hz) ? b.hz : null;
  if (b.poly !== undefined || !partial) { z.poly = cleanPoly(b.poly); if (!z.poly) return null; }
  if (b.entry !== undefined) z.entry = cleanPoint(b.entry);
  if (b.name !== undefined) z.temp = false;
  return z;
}
function cleanWork(b) {
  const title = str(b.title, 160), zone_id = Number(b.zone_id);
  if (!title || !Number.isInteger(zone_id)) return null;
  const crew = Array.isArray(b.crew) ? b.crew.map(c => str(c, 60)).filter(Boolean).slice(0, 40) : [];
  const day = /^\d{4}-\d{2}-\d{2}$/.test(b.day || '') ? b.day : new Date().toISOString().slice(0, 10);
  return {zone_id, title, crew, permit: PERMITS.includes(b.permit) ? b.permit : 'cold', ptw: str(b.ptw, 30),
    shift: SHIFTS.includes(b.shift) ? b.shift : 'am', status: STATUSES.includes(b.status) ? b.status : 'planned', sup: str(b.sup, 60), day};
}

/* ---------- static files ---------- */
const PUB = path.join(__dirname, 'public');
const TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json'};
function serveStatic(req, res, p) {
  const file = path.normalize(path.join(PUB, p === '/' ? 'index.html' : p));
  if (!file.startsWith(PUB)) return false;
  let data; try { data = fs.readFileSync(file); } catch { return false; }
  const ext = path.extname(file);
  res.writeHead(200, {'Content-Type': TYPES[ext] || 'application/octet-stream', 'Cache-Control': ext === '.png' || ext === '.svg' ? 'public, max-age=86400' : 'no-cache', 'X-Content-Type-Options': 'nosniff'});
  res.end(data);
  return true;
}

/* ---------- API ---------- */
async function api(req, res, url) {
  const p = url.pathname, m = req.method;
  if (p === '/api/login' && m === 'POST') {
    const ip = (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
    if (limited(ip)) return send(res, 429, {error: 'too_many_attempts'});
    const b = await readBody(req), code = str(b.code, 100);
    let role = null;
    if (SUPERVISOR_PASSWORD && code && same(code, SUPERVISOR_PASSWORD)) role = 'sup';
    else if (WORKER_CODE && code && same(code, WORKER_CODE)) role = 'worker';
    if (!role) { attempts.get(ip).push(Date.now()); return send(res, 401, {error: 'wrong_code'}); }
    return send(res, 200, {role}, {'Set-Cookie': `sg=${makeToken(role)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${30 * 86400}${SECURE_COOKIE ? '; Secure' : ''}`});
  }
  if (p === '/api/logout' && m === 'POST') return send(res, 200, {ok: true}, {'Set-Cookie': 'sg=; Path=/; Max-Age=0'});
  if (p === '/api/health') return send(res, 200, {ok: true});

  const t = readToken(req);
  if (!t) return send(res, 401, {error: 'login_required'});
  const sup = t.role === 'sup';
  if (p === '/api/me') return send(res, 200, {role: t.role});
  if (p === '/api/version' && m === 'GET') return send(res, 200, {v: await store.version()});
  if (p === '/api/site' && m === 'GET') return send(res, 200, await store.site());
  if (p === '/api/works' && m === 'GET') return send(res, 200, await store.works());
  if (p === '/api/layer/plan' && m === 'GET') {
    const img = planImage();
    if (!img) return send(res, 404, {error: 'not_found'});
    res.writeHead(200, {'Content-Type': 'image/png', 'Cache-Control': 'private, max-age=86400'});
    return res.end(img);
  }
  if (p === '/api/layer/2026' && m === 'GET') {
    const blob = await store.blob('layer2026');
    if (!blob) return send(res, 404, {error: 'not_found'});
    res.writeHead(200, {'Content-Type': blob.mime, 'Cache-Control': 'private, max-age=86400'});
    return res.end(blob.data);
  }
  if (!sup) return send(res, 403, {error: 'supervisor_only'});

  let mm;
  if (p === '/api/zones' && m === 'POST') {
    const z = cleanZone(await readBody(req), false); if (!z) return send(res, 400, {error: 'invalid_zone'});
    return send(res, 200, await store.addZone(z));
  }
  if ((mm = /^\/api\/zones\/(\d+)$/.exec(p))) {
    const id = Number(mm[1]);
    if (m === 'PUT') { const z = cleanZone(await readBody(req), true); if (!z) return send(res, 400, {error: 'invalid_zone'}); return send(res, 200, await store.updateZone(id, z)); }
    if (m === 'DELETE') { await store.deleteZone(id); return send(res, 200, {ok: true}); }
  }
  if (p === '/api/works' && m === 'POST') {
    const w = cleanWork(await readBody(req)); if (!w) return send(res, 400, {error: 'invalid_work'});
    w.id = crypto.randomUUID(); if (!w.ptw) w.ptw = '';
    return send(res, 200, await store.addWork(w));
  }
  if ((mm = /^\/api\/works\/([0-9a-f-]{36})$/.exec(p))) {
    if (m === 'PUT') { const w = cleanWork(await readBody(req)); if (!w) return send(res, 400, {error: 'invalid_work'}); return send(res, 200, await store.updateWork(mm[1], w)); }
    if (m === 'DELETE') { await store.deleteWork(mm[1]); return send(res, 200, {ok: true}); }
  }
  return send(res, 404, {error: 'not_found'});
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  res.setHeader('Referrer-Policy', 'same-origin');
  res.setHeader('X-Frame-Options', 'DENY');
  try {
    if (url.pathname.startsWith('/api/')) return await api(req, res, url);
    if ((req.method === 'GET' || req.method === 'HEAD') && serveStatic(req, res, url.pathname)) return;
    serveStatic(req, res, '/') || send(res, 404, {error: 'not_found'});
  } catch (e) {
    console.error(e);
    const known = e.status || (e.message === 'too_large' || e.message === 'bad_json' ? 400 : 0);
    if (!res.headersSent) send(res, known || 500, {error: known ? e.message : 'server_error'});
  }
});

store.init().then(() => server.listen(PORT, () => console.log(`site guide listening on ${PORT}`)))
  .catch(e => { console.error('startup failed', e); process.exit(1); });
