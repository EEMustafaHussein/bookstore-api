(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const NS = 'http://www.w3.org/2000/svg';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  /* ---------- server ---------- */
  async function api(path, opts = {}) {
    const init = {method: opts.method || 'GET', credentials: 'same-origin', headers: {}};
    if (opts.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.body); }
    const r = await fetch(path, init);
    let data = null; try { data = await r.json(); } catch (e) {}
    if (!r.ok) { const e = new Error((data && data.error) || 'http_' + r.status); e.status = r.status; throw e; }
    return data;
  }

  /* ---------- labels and vocabulary ---------- */
  const HZ = {
    z1: {label:'منطقة خطرة · Zone 1', chip:'Zone 1', note:'قد تتواجد غازات قابلة للاشتعال أثناء التشغيل. الموبايل العادي ممنوع، ويلزم جهاز مقاوم للانفجار (Ex) وتصريح عمل.', voice:'هاي منطقة خطرة زون واحد، لازم تصريح عمل وجهاز مقاوم للانفجار'},
    z2: {label:'منطقة خطرة · Zone 2', chip:'Zone 2', note:'غازات قابلة للاشتعال محتملة عند حدوث تسرب. الالتزام بتصريح العمل ومعدات الوقاية.', voice:'هاي منطقة خطرة زون اثنين، لازم تصريح عمل'},
    hv: {label:'جهد عالي', chip:'جهد عالي', note:'الدخول للمخوّلين فقط. أي شغل يحتاج عزل كهربائي وقفل وبطاقات (LOTO).', voice:'هاي منطقة جهد عالي، لازم عزل كهربائي قبل أي شغل'},
    restricted: {label:'منطقة محظورة', chip:'محظورة', note:'الدخول بتصريح خاص فقط.', voice:'هاي منطقة محظورة، الدخول بتصريح خاص بس'}
  };
  const KINDS = ['وحدة تشغيل','خزانات','مرافق','خدمات','مباني','ساحة'];
  const PERMITS = {hot:'عمل ساخن', cold:'عمل بارد', loto:'عزل كهربائي LOTO', cse:'دخول مكان محصور', height:'عمل على ارتفاع'};
  const SHIFTS = {am:'الوجبة الصباحية', pm:'الوجبة المسائية', night:'الوجبة الليلية'};
  const STATUS = {active:'شغّال الآن', planned:'مخطط', done:'منجز'};
  const ORDER = {active:0, planned:1, done:2};
  const TURN = {right:'لف يمين', left:'لف يسار', uturn:'ارجع للخلف'};
  const SIDE = {right:'يمينك', left:'يسارك', uturn:'وراك'};
  const ICON = {
    right:'<svg viewBox="0 0 48 48"><path d="M15 42V27c0-6 4-10 10-10h13M30 9l8 8-8 8"/></svg>',
    left:'<svg viewBox="0 0 48 48"><path d="M33 42V27c0-6-4-10-10-10H10M18 9l-8 8 8 8"/></svg>',
    uturn:'<svg viewBox="0 0 48 48"><path d="M32 42V20a9 9 0 0 0-18 0v10M7 23l7 7 7-7"/></svg>',
    arrive:'<svg viewBox="0 0 48 48"><path d="M14 43V7M14 9h20l-4 7 4 7H14"/></svg>'
  };
  const SPK_ON = '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>';
  const SPK_OFF = '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="m17 9 5 6M22 9l-5 6"/></svg>';
  const NAV_ICO = '<svg viewBox="0 0 24 24"><path d="M3 11 21 3l-8 18-2-8-8-2z"/></svg>';
  const EDIT_ICO = '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/></svg>';
  const SHAPE_ICO = '<svg viewBox="0 0 24 24"><path d="M5 6l7-3 7 4-1 10-8 4-6-6z"/></svg>';
  const PLUS_ICO = '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>';

  /* ---------- formatting ---------- */
  const fmtDist = d => d >= 1000 ? `${(d/1000).toFixed(1)} كم` : `${d >= 100 ? Math.round(d/10)*10 : Math.max(0, Math.round(d/5)*5)} م`;
  const round10 = d => Math.max(10, Math.round(d / 10) * 10);
  const WALK = 1.3, CAR = 5.5;
  const walkMin = d => Math.max(1, Math.ceil(d / WALK / 60));
  const carMin = d => Math.max(1, Math.ceil(d / CAR / 60));
  function clock(sec) { const t = new Date(Date.now() + sec * 1000); let h = t.getHours(); const m = String(t.getMinutes()).padStart(2, '0'); const ap = h < 12 ? 'ص' : 'م'; h = h % 12 || 12; return `${h}:${m} ${ap}`; }
  const turnsWord = n => n === 0 ? 'بدون انعطافات' : n === 1 ? 'انعطافة وحدة' : n === 2 ? 'انعطافتين' : `${n} انعطافات`;
  const crewWord = n => n === 1 ? 'عامل واحد' : n === 2 ? 'عاملان' : `${n} عمال`;
  const iso = (off = 0) => { const d = new Date(); d.setDate(d.getDate() + off); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
  function dayLabel(s) {
    if (!s) return '';
    const diff = Math.round((new Date(s + 'T00:00:00') - new Date(iso() + 'T00:00:00')) / 86400000);
    if (diff === 0) return 'اليوم'; if (diff === 1) return 'غداً'; if (diff === -1) return 'أمس';
    const d = new Date(s + 'T00:00:00'); return `${d.getDate()}/${d.getMonth()+1}`;
  }

  /* ---------- geometry ---------- */
  const WORLD = 256 * 2 ** 17;
  let ORG = {x: 0, y: 0}, S = 1, MAP_W = 1000, MAP_H = 1000, SITE = [];
  function gpx(lat, lon) { const s = Math.sin(lat * Math.PI / 180); return {x: (lon + 180) / 360 * WORLD, y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * WORLD}; }
  const GEO = {
    toMap(lat, lon) { const g = gpx(lat, lon); return {x: (g.x - ORG.x) * S, y: (g.y - ORG.y) * S}; },
    toGeo(x, y) { const gx = x / S + ORG.x, gy = y / S + ORG.y, n = Math.PI * (1 - 2 * gy / WORLD); return {lat: Math.atan(Math.sinh(n)) * 180 / Math.PI, lon: gx / WORLD * 360 - 180}; }
  };
  const ll2m = p => { const m = GEO.toMap(p[0], p[1]); return [m.x, m.y]; };
  const m2ll = p => { const g = GEO.toGeo(p[0], p[1]); return [+g.lat.toFixed(7), +g.lon.toFixed(7)]; };
  function pip(p, poly) {
    let ins = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > p.y) !== (yj > p.y) && p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi) ins = !ins;
    }
    return ins;
  }
  function projSeg(p, a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1], L = dx*dx + dy*dy;
    const t = L ? clamp(((p.x - a[0]) * dx + (p.y - a[1]) * dy) / L, 0, 1) : 0;
    return {x: a[0] + t*dx, y: a[1] + t*dy};
  }
  const segDist = (p, a, b) => { const q = projSeg(p, a, b); return Math.hypot(p.x - q.x, p.y - q.y); };
  function polyDist(p, poly) { let m = Infinity; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) m = Math.min(m, segDist(p, poly[j], poly[i])); return m; }
  function rot(x, y, deg) { const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a); return {x: x*c - y*s, y: x*s + y*c}; }
  const bearing = (a, b) => (Math.atan2(b.x - a.x, -(b.y - a.y)) * 180 / Math.PI + 360) % 360;
  function insidePoint(poly) {
    let a = 0, cx = 0, cy = 0;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const f = poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1]; a += f; cx += (poly[j][0] + poly[i][0]) * f; cy += (poly[j][1] + poly[i][1]) * f; }
    let c = a ? {x: cx / (3 * a), y: cy / (3 * a)} : {x: poly[0][0], y: poly[0][1]};
    if (pip(c, poly)) return [c.x, c.y];
    for (let i = 1; i < poly.length - 1; i++) { const t = {x: (poly[0][0] + poly[i][0] + poly[i+1][0]) / 3, y: (poly[0][1] + poly[i][1] + poly[i+1][1]) / 3}; if (pip(t, poly)) return [t.x, t.y]; }
    return [poly[0][0], poly[0][1]];
  }

  /* ---------- site data ---------- */
  let ZONES = [], ZM = {}, ROADS = [], FEATS = [], POIS = [], BY_AREA = [], CONFIG = null;
  const zoneAt = p => BY_AREA.find(z => pip(p, z.poly)) || null;   // smallest zone wins where zones overlap
  const polyArea = poly => Math.abs(poly.reduce((a, p, i) => { const q = poly[(i + 1) % poly.length]; return a + p[0] * q[1] - q[0] * p[1]; }, 0)) / 2;
  const circlePoly = (cx, cy, r, n = 16) => Array.from({length: n}, (_, i) => [cx + r * Math.cos(i * 2 * Math.PI / n), cy + r * Math.sin(i * 2 * Math.PI / n)]);
  // search: ignore case, spaces, dashes and dots; read Arabic-Indic digits as Latin
  const norm = s => String(s || '').toLowerCase()
    .replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 0x660)).replace(/[۰-۹]/g, d => String(d.charCodeAt(0) - 0x6F0))
    .replace(/[\s\-_.·/]/g, '');
  function nearestPoi(p, max) { let best = null, d = max; POIS.forEach(o => { const dd = Math.hypot(o.x - p.x, o.y - p.y); if (dd < d) { d = dd; best = o; } }); return best; }
  function poiDest(o) {
    if (o.dest) return o.dest;
    const z = ZM[o.zone_id], dr = ROADS.length ? nearestOnRoads({x: o.x, y: o.y}) : null;
    o.dest = {id: 'p' + o.id, isPoi: true, poi: o, zone: z || null, name: o.label + (z ? ` · ${z.short}` : ''), short: o.label, kind: z ? z.kind : '', hz: z ? z.hz : null,
      in: [o.x, o.y], doorRef: dr, door: dr ? [dr.x, dr.y] : [o.x, o.y], poly: circlePoly(o.x, o.y, 30)};
    return o.dest;
  }
  function nearestZone(p) { let best = null, d = Infinity; ZONES.forEach(z => { const dd = polyDist(p, z.poly); if (dd < d) { d = dd; best = z; } }); return {zone: best, d}; }
  function nearestOnRoads(p) {
    let best = null;
    ROADS.forEach((r, ri) => { for (let i = 0; i < r.pts.length - 1; i++) {
      const a = r.pts[i], b = r.pts[i+1], q = projSeg(p, a, b), d = Math.hypot(p.x - q.x, p.y - q.y);
      if (!best || d < best.d) best = {x: q.x, y: q.y, d, ri, s: r.cum[i] + Math.hypot(q.x - a[0], q.y - a[1])};
    } });
    return best;
  }
  function setupGeo(cfg) {
    const nw = gpx(cfg.nw[0], cfg.nw[1]), se = gpx(cfg.se[0], cfg.se[1]);
    ORG = {x: nw.x, y: nw.y};
    S = 156543.03392804097 * Math.cos((cfg.nw[0] + cfg.se[0]) / 2 * Math.PI / 180) / 2 ** 17;
    MAP_W = (se.x - nw.x) * S; MAP_H = (se.y - nw.y) * S;
    SITE = [[0,0],[MAP_W,0],[MAP_W,MAP_H],[0,MAP_H]];
  }
  function applySite(site) {
    ROADS = (site.roads || []).map(r => {
      const pts = r.pts.map(ll2m), cum = [0];
      for (let i = 1; i < pts.length; i++) cum.push(cum[i-1] + Math.hypot(pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1]));
      return {name: r.name, pts, cum};
    });
    ZONES = (site.zones || []).map(d => {
      const poly = d.poly.map(ll2m), xs = poly.map(p => p[0]), ys = poly.map(p => p[1]);
      const bbox = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
      const inn = d.entry ? ll2m(d.entry) : insidePoint(poly);
      const z = {id: d.id, name: d.name, short: d.short || d.name, kind: d.kind, hz: HZ[d.hz] ? d.hz : null, temp: !!d.temp, isNew: !!d.is_new, raw: d.poly,
        poly, in: inn, bbox, lx: (bbox[0] + bbox[2]) / 2, ly: (bbox[1] + bbox[3]) / 2};
      if (!pip({x: z.lx, y: z.ly}, poly)) { z.lx = inn[0]; z.ly = inn[1]; }
      z.doorRef = ROADS.length ? nearestOnRoads({x: inn[0], y: inn[1]}) : null;
      z.door = z.doorRef ? [z.doorRef.x, z.doorRef.y] : inn;
      return z;
    });
    ZM = Object.fromEntries(ZONES.map(z => [z.id, z]));
    BY_AREA = [...ZONES].sort((a, b) => polyArea(a.poly) - polyArea(b.poly));
    FEATS = (site.features || []).map(f => { const m = GEO.toMap(f.lat, f.lon); return {x: m.x, y: m.y, r: f.r_m}; });
    POIS = (site.pois || []).map(o => { const m = GEO.toMap(o.lat, o.lon); return {id: o.id, label: o.label, zone_id: o.zone_id, x: m.x, y: m.y, key: norm(o.label)}; });
    state.version = site.version;
  }

  /* ---------- routing ---------- */
  function buildGraph(extra) {
    const nodes = new Map(), key = (x, y) => `${x.toFixed(2)},${y.toFixed(2)}`;
    const add = (x, y) => { const k = key(x, y); if (!nodes.has(k)) nodes.set(k, {k, x, y, adj: []}); return k; };
    const lists = ROADS.map(r => r.pts.map((p, i) => ({x: p[0], y: p[1], s: r.cum[i]})));
    // roads join where a vertex of one lies on another
    ROADS.forEach((r, ri) => r.pts.forEach(p => ROADS.forEach((o, oi) => {
      if (oi === ri) return;
      for (let i = 0; i < o.pts.length - 1; i++) {
        const q = projSeg({x: p[0], y: p[1]}, o.pts[i], o.pts[i+1]);
        if (Math.hypot(q.x - p[0], q.y - p[1]) < 0.6) { lists[oi].push({x: p[0], y: p[1], s: o.cum[i] + Math.hypot(q.x - o.pts[i][0], q.y - o.pts[i][1])}); break; }
      }
    })));
    [...ZONES.map(z => z.doorRef).filter(Boolean), ...extra].forEach(e => lists[e.ri].push({x: e.x, y: e.y, s: e.s}));
    lists.forEach((list, ri) => {
      list.sort((a, b) => a.s - b.s);
      for (let n = 0; n < list.length - 1; n++) {
        const a = list[n], b = list[n+1], ka = add(a.x, a.y), kb = add(b.x, b.y); if (ka === kb) continue;
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        nodes.get(ka).adj.push({k: kb, d, ri}); nodes.get(kb).adj.push({k: ka, d, ri});
      }
    });
    return {nodes, key};
  }
  function dijkstra(g, src, dst) {
    if (!g.nodes.has(src) || !g.nodes.has(dst)) return null;
    const dist = new Map([[src, 0]]), prev = new Map(), done = new Set();
    for (;;) {
      let u = null, best = Infinity;
      for (const [k, d] of dist) if (!done.has(k) && d < best) { best = d; u = k; }
      if (u === null) return null;
      if (u === dst) break;
      done.add(u);
      for (const e of g.nodes.get(u).adj) { const nd = best + e.d; if (nd < (dist.has(e.k) ? dist.get(e.k) : Infinity)) { dist.set(e.k, nd); prev.set(e.k, u); } }
    }
    const path = []; let k = dst;
    while (k !== undefined) { path.unshift(g.nodes.get(k)); if (k === src) break; k = prev.get(k); }
    return path;
  }
  function cleanPts(pts) {
    const out = [];
    pts.forEach(p => { const l = out[out.length - 1]; if (l && Math.hypot(p.x - l.x, p.y - l.y) < 0.5) { if (p.r != null) l.r = p.r; return; } out.push({...p}); });
    for (let i = 1; i < out.length - 1;) {
      const a = out[i-1], b = out[i], c = out[i+1];
      const ux = b.x - a.x, uy = b.y - a.y, vx = c.x - b.x, vy = c.y - b.y;
      const sin = Math.abs(ux * vy - uy * vx) / (Math.hypot(ux, uy) * Math.hypot(vx, vy) || 1);
      if (sin < 0.02 && ux * vx + uy * vy > 0) out.splice(i, 1); else i++;
    }
    return out;
  }
  const cardinal = (a, b) => { const h = bearing(a, b); return h < 45 || h >= 315 ? 'الشمال' : h < 135 ? 'الشرق' : h < 225 ? 'الجنوب' : 'الغرب'; };
  function makeRoute(pts, dz, startZone) {
    const cum = [0];
    for (let i = 1; i < pts.length; i++) cum.push(cum[i-1] + Math.hypot(pts[i].x - pts[i-1].x, pts[i].y - pts[i-1].y));
    const len = cum[cum.length - 1], man = [];
    for (let i = 1; i < pts.length - 1; i++) {
      const a = pts[i-1], b = pts[i], c = pts[i+1];
      const v1x = b.x - a.x, v1y = b.y - a.y, v2x = c.x - b.x, v2y = c.y - b.y;
      const ang = Math.atan2(v1x*v2y - v1y*v2x, v1x*v2x + v1y*v2y) * 180 / Math.PI;
      if (Math.abs(ang) < 30) continue;
      const last = i === pts.length - 2;
      man.push({i, at: cum[i], type: Math.abs(ang) > 150 ? 'uturn' : ang > 0 ? 'right' : 'left', last, road: last || b.r == null ? null : ROADS[b.r]});
    }
    man.push({i: pts.length - 1, at: len, type: 'arrive', last: false});
    const roads = [];
    pts.forEach(p => { if (p.r != null && !roads.includes(ROADS[p.r])) roads.push(ROADS[p.r]); });
    const r0 = pts[0].r != null ? ROADS[pts[0].r] : null;
    const startText = startZone ? `اطلع من ${startZone.short} للشارع` : `امشِ باتجاه ${cardinal(pts[0], pts[1])}${r0 ? ` على ${r0.name}` : ''}`;
    return {pts, cum, len, man, roads, startText, dest: dz};
  }
  function computeRoute(from, dz) {
    if (!from || !ROADS.length) return null;
    const here = zoneAt(from);
    if ((here && here.id === dz.id) || (dz.isPoi && pip(from, dz.poly))) return {error: 'here'};
    if (!pip(from, SITE)) return {error: 'outside'};
    const lead = []; let entry;
    if (here && here.doorRef) { entry = here.doorRef; lead.push({x: from.x, y: from.y, r: null}); }
    else { entry = nearestOnRoads(from); if (entry.d > 12) lead.push({x: from.x, y: from.y, r: null}); }
    const g = buildGraph(dz.isPoi && dz.doorRef ? [entry, dz.doorRef] : [entry]);
    const path = dijkstra(g, g.key(entry.x, entry.y), g.key(dz.door[0], dz.door[1]));
    if (!path) return null;
    const core = path.map((n, i) => { let r = null; if (i < path.length - 1) { const e = n.adj.find(e => e.k === path[i+1].k); r = e ? e.ri : null; } return {x: n.x, y: n.y, r}; });
    const pts = cleanPts([...lead, ...core, {x: dz.in[0], y: dz.in[1], r: null}]);
    if (pts.length < 2) return {error: 'here'};
    return makeRoute(pts, dz, here);
  }
  function pointOn(Rt, d) {
    d = clamp(d, 0, Rt.len);
    for (let i = 0; i < Rt.pts.length - 1; i++) {
      const L = Rt.cum[i+1] - Rt.cum[i];
      if (d <= Rt.cum[i+1] || i === Rt.pts.length - 2) { const t = L ? (d - Rt.cum[i]) / L : 0, a = Rt.pts[i], b = Rt.pts[i+1]; return {x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t}; }
    }
    return Rt.pts[Rt.pts.length - 1];
  }
  function headingAt(Rt, d) { for (let i = 0; i < Rt.pts.length - 1; i++) if (d < Rt.cum[i+1] || i === Rt.pts.length - 2) return bearing(Rt.pts[i], Rt.pts[i+1]); return 0; }
  function manText(m, dz) {
    if (m.type === 'arrive') return `وصلت إلى ${dz.name}`;
    if (m.last) return `${dz.name} على ${SIDE[m.type]}`;
    return `${TURN[m.type]}${m.road ? ` على ${m.road.name}` : ''}`;
  }

  /* ---------- state ---------- */
  const state = {role: null, version: 0, pos: null, hereId: null, selectedId: null, follow: true, sim: false, tab: 'site', filter: 'all', q: '',
    works: [], view: {x: 0, y: 0, w: 1000, h: 1000}, ppu: 1, rot: 0, heading: 0, headingUp: true, nav: null,
    formOpen: false, zoneForm: null, focusPoi: null, plan: true, delArm: null, zoneDelArm: false, draw: null, layer26: false, userMoved: false, busy: false};
  const isSup = () => state.role === 'sup';
  const countsFor = zid => { const ws = state.works.filter(w => w.zone_id === zid && w.status !== 'done'); const active = ws.filter(w => w.status === 'active').length; return {active, planned: ws.length - active, total: ws.length}; };
  const byStatus = (a, b) => (ORDER[a.status] - ORDER[b.status]) || String(a.day).localeCompare(String(b.day));

  /* ---------- voice ---------- */
  const hasSS = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  const speech = {on: true, voice: null, warned: false};
  function pickVoice() { try { const vs = speechSynthesis.getVoices(); speech.voice = vs.find(v => /^ar[-_]IQ/i.test(v.lang)) || vs.find(v => /^ar/i.test(v.lang)) || null; } catch (e) {} }
  if (hasSS) { pickVoice(); try { speechSynthesis.addEventListener('voiceschanged', pickVoice); } catch (e) {} }
  function say(text, urgent) {
    if (!speech.on || !hasSS) return;
    if (!speech.voice) pickVoice();
    if (!speech.voice) { if (!speech.warned) { speech.warned = true; toast('ما لكيت صوت عربي بموبايلك. نزّله من الإعدادات ← تحويل النص إلى كلام ← العربية، والتعليمات تبقى مكتوبة.'); } return; }
    try { if (urgent) speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.voice = speech.voice; u.lang = speech.voice.lang; u.rate = 1.02; speechSynthesis.speak(u); } catch (e) {}
  }
  const hush = () => { try { if (hasSS) speechSynthesis.cancel(); } catch (e) {} };

  /* ---------- map drawing ---------- */
  const svg = $('#map');
  const pstr = a => a.map(p => `${(p.x ?? p[0]).toFixed(1)},${(p.y ?? p[1]).toFixed(1)}`).join(' ');
  function buildStatic() {
    svg.innerHTML = `<defs><pattern id="hatch" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect class="hb1" width="9" height="9"/><rect class="hb2" width="3" height="9"/></pattern></defs>
      <g id="world"><rect class="ground" x="-20000" y="-20000" width="50000" height="50000"/>
      <g id="tilesBase"></g><g id="tiles"></g>
      <image id="layer26" href="/api/layer/2026" x="0" y="0" width="${MAP_W.toFixed(2)}" height="${MAP_H.toFixed(2)}" preserveAspectRatio="none" style="display:none"/>
      <image id="layerPlan" href="/api/layer/plan" x="0" y="0" width="${MAP_W.toFixed(2)}" height="${MAP_H.toFixed(2)}" preserveAspectRatio="none"/>
      <g id="dyn"></g>
      <g id="pois"></g>
      <g id="routeG"><polyline id="rCase" class="r-case" points=""/><polyline id="rLine" class="r-line" points=""/></g>
      <g id="draft"></g>
      <g id="labels"></g>
      <g id="focusMark" style="display:none"><circle class="fm-ring" r="22"/><text class="fm-txt" y="-34"></text></g>
      <g id="destPin" style="display:none"><path class="pin-b" d="M0 0C-4-7-13-14-13-23a13 13 0 0 1 26 0C13-14 4-7 0 0z"/><circle class="pin-c" cy="-23" r="5"/></g>
      <g id="you" style="display:none"><circle id="acc" class="acc" r="5"/><g id="youDot"><circle class="pulse" r="9"/><circle class="dot" r="7.5"/><path class="arrow" d="M0-15 11 11 0 5-11 11z"/></g></g></g>`;
    // a coarse imagery layer that always covers the site while sharper tiles load
    const b = [0, 0, MAP_W, MAP_H], t = tileRange(15, b), g = $('#tilesBase');
    for (let x = t.x0; x <= t.x1; x++) for (let y = t.y0; y <= t.y1; y++) g.appendChild(tileEl(15, x, y));
  }
  function renderDyn() {
    let s = ROADS.map(r => `<polyline class="road-l" points="${pstr(r.pts)}"/>`).join('');
    s += `<g id="zones">` + ZONES.map(z => `<g class="zone${z.isNew ? ' isnew' : ''}" data-id="${z.id}">${z.isNew ? `<polygon class="zh" points="${pstr(z.poly)}"/>` : ''}<polygon class="zp" points="${pstr(z.poly)}"/></g>`).join('') + `</g>`;
    s += FEATS.map(f => `<circle class="newf" cx="${f.x.toFixed(1)}" cy="${f.y.toFixed(1)}" r="${f.r.toFixed(1)}"/>`).join('');
    $('#dyn').innerHTML = s;
    $('#pois').innerHTML = POIS.map(o => `<g class="poi" data-pid="${o.id}"><circle class="pd" r="3.5"/><text class="pt" y="-11">${esc(o.label)}</text></g>`).join('');
    POIS.forEach(o => { o.el = svg.querySelector(`.poi[data-pid="${o.id}"]`); });
    $('#labels').innerHTML = ZONES.map(z => `<g class="lbl" data-id="${z.id}"><circle class="b" r="12"/><text class="bt">${z.id}</text><path class="hzm" d="M-28 8 L-20 -6 L-12 8 Z"/><g class="cnt"></g><text class="nm" y="28">${esc(z.short)}</text></g>`).join('');
    ZONES.forEach(z => { z.el = svg.querySelector(`.zone[data-id="${z.id}"]`); z.lblEl = svg.querySelector(`.lbl[data-id="${z.id}"]`); });
  }

  /* ---------- satellite tiles (Esri World Imagery, loaded live) ---------- */
  const TILE_URL = (z, x, y) => `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`;
  const tileEls = new Map(); let tileRaf = 0, tileGc = 0;
  function tileRange(z, b) {
    const sz = 256 * 2 ** (17 - z);
    return {x0: Math.floor((b[0] / S + ORG.x) / sz), x1: Math.floor((b[2] / S + ORG.x) / sz), y0: Math.floor((b[1] / S + ORG.y) / sz), y1: Math.floor((b[3] / S + ORG.y) / sz)};
  }
  function tileEl(z, x, y) {
    const sz = 256 * 2 ** (17 - z), el = document.createElementNS(NS, 'image');
    el.setAttribute('x', ((x * sz - ORG.x) * S).toFixed(2)); el.setAttribute('y', ((y * sz - ORG.y) * S).toFixed(2));
    el.setAttribute('width', (sz * S + 0.6).toFixed(2)); el.setAttribute('height', (sz * S + 0.6).toFixed(2));
    el.setAttribute('preserveAspectRatio', 'none'); el.setAttribute('href', TILE_URL(z, x, y));
    return el;
  }
  function scheduleTiles() { if (!tileRaf) tileRaf = requestAnimationFrame(() => { tileRaf = 0; updateTiles(); }); }
  function updateTiles() {
    const r = rect(); if (!r.width) return;
    const cs = [[r.left, r.top], [r.right, r.top], [r.left, r.bottom], [r.right, r.bottom]].map(c => clientToMap(c[0], c[1]));
    const b = [Math.min(...cs.map(c => c.x)), Math.min(...cs.map(c => c.y)), Math.max(...cs.map(c => c.x)), Math.max(...cs.map(c => c.y))];
    let z = clamp(Math.round(17 + Math.log2(state.ppu * S * Math.min(window.devicePixelRatio || 1, 2))), 12, 18), t;
    for (;;) { t = tileRange(z, b); if ((t.x1 - t.x0 + 1) * (t.y1 - t.y0 + 1) <= 64 || z <= 12) break; z--; }
    const want = new Set(), g = $('#tiles');
    for (let x = t.x0; x <= t.x1; x++) for (let y = t.y0; y <= t.y1; y++) {
      const k = `${z}/${x}/${y}`; want.add(k);
      if (!tileEls.has(k)) { const el = tileEl(z, x, y); g.appendChild(el); tileEls.set(k, el); }
    }
    for (const [k, el] of tileEls) if (!want.has(k) && +k.split('/')[0] === z) { el.remove(); tileEls.delete(k); }
    clearTimeout(tileGc);
    tileGc = setTimeout(() => { for (const [k, el] of tileEls) if (!want.has(k)) { el.remove(); tileEls.delete(k); } }, 900);
  }

  /* ---------- view: pan, zoom, rotate ---------- */
  const rect = () => svg.getBoundingClientRect();
  const NAMES_AT = 0.8;
  function clientToMap(cx, cy) {
    const r = rect(), v = state.view;
    const q = rot(((cx - r.left) / r.width - 0.5) * v.w, ((cy - r.top) / r.height - 0.5) * v.h, state.rot);
    return {x: v.x + v.w/2 + q.x, y: v.y + v.h/2 + q.y};
  }
  function applyView() {
    const v = state.view, r = rect();
    if (!r.width) return;
    v.h = v.w * r.height / r.width;
    if (!state.nav) {
      const M = 400, cl = (val, size, full) => { const a = -M, b = full - size + M; return clamp(val, Math.min(a, b), Math.max(a, b)); };
      v.x = cl(v.x, v.w, MAP_W); v.y = cl(v.y, v.h, MAP_H);
    }
    svg.setAttribute('viewBox', `${v.x.toFixed(2)} ${v.y.toFixed(2)} ${v.w.toFixed(2)} ${v.h.toFixed(2)}`);
    const cx = v.x + v.w/2, cy = v.y + v.h/2, world = $('#world');
    if (Math.abs(state.rot) > 0.01) world.setAttribute('transform', `rotate(${(-state.rot).toFixed(2)} ${cx.toFixed(2)} ${cy.toFixed(2)})`); else world.removeAttribute('transform');
    state.ppu = r.width / v.w;
    const k = (1 / state.ppu).toFixed(4), rr = state.rot.toFixed(2);
    ZONES.forEach(z => z.lblEl && z.lblEl.setAttribute('transform', `translate(${z.lx.toFixed(1)} ${z.ly.toFixed(1)}) rotate(${rr}) scale(${k})`));
    POIS.forEach(o => o.el && o.el.setAttribute('transform', `translate(${o.x.toFixed(1)} ${o.y.toFixed(1)}) rotate(${rr}) scale(${k})`));
    svg.classList.toggle('show-names', state.ppu >= NAMES_AT);
    svg.classList.toggle('show-pois', state.ppu >= 1.3);
    $('#northIco').style.transform = `rotate(${-state.rot}deg)`;
    updateYou(); updatePin(); updateFocus(); renderScale(); renderDraft(); scheduleTiles();
  }
  function zoomTo(w, mapPt, clientPt) {
    const r = rect(); w = clamp(w, 120, 6000);
    const h = w * r.height / r.width;
    const q = rot(((clientPt.x - r.left) / r.width - 0.5) * w, ((clientPt.y - r.top) / r.height - 0.5) * h, state.rot);
    state.view = {x: mapPt.x - q.x - w/2, y: mapPt.y - q.y - h/2, w, h}; applyView();
  }
  function zoomCenter(f) { const r = rect(), c = {x: r.left + r.width/2, y: r.top + r.height/2}; zoomTo(state.view.w * f, clientToMap(c.x, c.y), c); }
  function fitView() {
    const r = rect(); if (!r.width) return;
    const a = r.width / r.height; let w = MAP_W, h = w / a;
    if (h < MAP_H) { h = MAP_H; w = h * a; }
    state.view = {x: MAP_W/2 - w/2, y: MAP_H/2 - h/2, w, h}; applyView();
  }
  function centerOn(x, y, w) { const v = state.view; if (w) v.w = w; const r = rect(); v.h = v.w * r.height / r.width; v.x = x - v.w/2; v.y = y - v.h/2; applyView(); }
  function zoomToZone(z) {
    const r = rect(), a = r.width / r.height, bw = z.bbox[2] - z.bbox[0], bh = z.bbox[3] - z.bbox[1];
    centerOn((z.bbox[0] + z.bbox[2]) / 2, (z.bbox[1] + z.bbox[3]) / 2, Math.min(state.view.w, Math.max(bw * 2.6, bh * 2.6 * a, r.width / 1.2)));
  }
  function renderScale() {
    const ppu = state.ppu, m = [10,20,25,50,100,200,250,500,1000,2000].find(o => o * ppu >= 56) || 2000;
    $('#scaleBar').style.width = Math.round(m * ppu) + 'px';
    $('#scaleTxt').textContent = m >= 1000 ? `${m/1000} كم` : `${m} م`;
  }

  const pointers = new Map(); let gesture = null;
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  svg.addEventListener('pointerdown', e => {
    try { svg.setPointerCapture(e.pointerId); } catch (_) {}
    pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    if (pointers.size === 1) gesture = {type: 'pan', start: clientToMap(e.clientX, e.clientY), sx: e.clientX, sy: e.clientY, moved: false};
    else if (pointers.size === 2) { const [a, b] = [...pointers.values()]; gesture = {type: 'pinch', d0: dist(a, b) || 1, w0: state.view.w, mid: clientToMap((a.x+b.x)/2, (a.y+b.y)/2)}; stopFollow(); }
  });
  svg.addEventListener('pointermove', e => {
    if (!pointers.has(e.pointerId) || !gesture) return;
    pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    if (gesture.type === 'pan' && pointers.size === 1) {
      if (!gesture.moved && Math.hypot(e.clientX - gesture.sx, e.clientY - gesture.sy) < 6) return;
      if (!gesture.moved) { stopFollow(); state.userMoved = true; }
      gesture.moved = true;
      const p = clientToMap(e.clientX, e.clientY);
      state.view.x += gesture.start.x - p.x; state.view.y += gesture.start.y - p.y; applyView();
    } else if (gesture.type === 'pinch' && pointers.size >= 2) {
      const [a, b] = [...pointers.values()];
      state.userMoved = true;
      zoomTo(gesture.w0 * gesture.d0 / (dist(a, b) || 1), gesture.mid, {x: (a.x+b.x)/2, y: (a.y+b.y)/2});
    }
  });
  function endPointer(e) {
    if (!pointers.has(e.pointerId)) return;
    pointers.delete(e.pointerId);
    if (gesture && gesture.type === 'pan' && !gesture.moved && e.type === 'pointerup') onTap(clientToMap(e.clientX, e.clientY));
    if (pointers.size === 1 && gesture && gesture.type === 'pinch') { const [p] = [...pointers.values()]; gesture = {type: 'pan', start: clientToMap(p.x, p.y), sx: p.x, sy: p.y, moved: true}; }
    else if (pointers.size === 0) gesture = null;
  }
  svg.addEventListener('pointerup', endPointer);
  svg.addEventListener('pointercancel', endPointer);
  svg.addEventListener('wheel', e => { e.preventDefault(); state.userMoved = true; zoomTo(state.view.w * Math.exp(e.deltaY * 0.0015), clientToMap(e.clientX, e.clientY), {x: e.clientX, y: e.clientY}); }, {passive: false});

  /* ---------- position ---------- */
  function updateYou() {
    const p = state.pos, you = $('#you'); if (!you) return;
    if (!p) { you.style.display = 'none'; return; }
    you.style.display = '';
    const acc = $('#acc'); acc.setAttribute('cx', p.x); acc.setAttribute('cy', p.y); acc.setAttribute('r', Math.max(1, p.acc));
    const hd = state.nav && state.nav.phase === 'active' ? state.heading : 0;
    $('#youDot').setAttribute('transform', `translate(${p.x.toFixed(2)} ${p.y.toFixed(2)}) rotate(${hd.toFixed(2)}) scale(${(1/state.ppu).toFixed(4)})`);
  }
  function updatePin() {
    const n = state.nav, pin = $('#destPin'); if (!pin) return;
    if (!n) { pin.style.display = 'none'; return; }
    pin.style.display = '';
    pin.setAttribute('transform', `translate(${n.dest.in[0].toFixed(1)} ${n.dest.in[1].toFixed(1)}) rotate(${state.rot.toFixed(2)}) scale(${(1/state.ppu).toFixed(4)})`);
  }
  function updateFocus() {
    const f = state.focusPoi, g = $('#focusMark'); if (!g) return;
    if (!f || state.nav) { g.style.display = 'none'; return; }
    g.style.display = '';
    g.querySelector('text').textContent = f.label;
    g.setAttribute('transform', `translate(${f.x.toFixed(1)} ${f.y.toFixed(1)}) rotate(${state.rot.toFixed(2)}) scale(${(1/state.ppu).toFixed(4)})`);
  }
  function focusPoi(o) {
    state.focusPoi = o;
    if (o.zone_id && ZM[o.zone_id]) { state.selectedId = o.zone_id; state.follow = false; state.tab = 'site'; renderZones(); renderPanel(); }
    centerOn(o.x, o.y, Math.min(state.view.w, rect().width / 2));
    toast(`هذا مكان ${o.label}`);
  }
  function setGeo(lat, lon, acc, src, o = {}) {
    const m = GEO.toMap(lat, lon), prevPos = state.pos, first = !prevPos;
    state.pos = {lat, lon, acc, src, x: m.x, y: m.y};
    if (o.heading != null) state.heading = o.heading;
    else if (prevPos && !o.jump && Math.hypot(m.x - prevPos.x, m.y - prevPos.y) > 2.5) state.heading = bearing(prevPos, m);
    const prev = state.hereId, z = zoneAt(m);
    state.hereId = z ? z.id : null;
    updateYou(); renderHere();
    if (first && !state.userMoved && !state.nav && pip(m, SITE)) centerOn(m.x, m.y, Math.min(state.view.w, rect().width / NAMES_AT));
    if (prev !== state.hereId) {
      if (state.follow && state.hereId) state.selectedId = state.hereId;
      renderZones();
      if (!panelBusy() && state.tab === 'site') renderPanel();
      if (!o.silent && !state.nav && z && !first) toast(`دخلت الموقع ${z.id} · ${z.name}${z.hz ? ' — ' + HZ[z.hz].label : ''}`, z.hz ? 'danger' : '');
    }
    if (state.nav) navUpdate(!!o.jump);
  }
  function setFromMap(pt, src, acc, o) { const g = GEO.toGeo(pt.x, pt.y); setGeo(g.lat, g.lon, acc, src, o); }

  let watchId = null;
  const btnGps = $('#btnGps');
  function startGps() {
    if (!('geolocation' in navigator)) { toast('هذا الجهاز ما يدعم تحديد الموقع'); return; }
    if (watchId !== null) return;
    setSim(false); btnGps.setAttribute('aria-pressed', 'true');
    watchId = navigator.geolocation.watchPosition(p => {
      const c = p.coords, hd = c.heading != null && !isNaN(c.heading) && (c.speed || 0) > 0.6 ? c.heading : null;
      setGeo(c.latitude, c.longitude, c.accuracy, 'gps', {heading: hd});
    }, err => {
      if (err.code === 1) { stopGps(); $('#hereName').textContent = 'الموقع مقفول'; $('#hereSub').textContent = 'اسمح للمتصفح يستخدم موقعك: من إعدادات المتصفح ← أذونات الموقع، وبعدين اضغط زر GPS.'; toast('ما سمحت للتطبيق يستخدم الموقع'); }
      else toast('إشارة الـGPS ضعيفة. اطلع لمكان مكشوف.');
    }, {enableHighAccuracy: true, maximumAge: 2000, timeout: 15000});
  }
  function stopGps() { if (watchId !== null) navigator.geolocation.clearWatch(watchId); watchId = null; btnGps.setAttribute('aria-pressed', 'false'); }
  btnGps.addEventListener('click', () => { if (watchId !== null) { stopGps(); toast('الـGPS متوقف'); } else startGps(); });
  const btnSim = $('#btnSim');
  function setSim(on) { state.sim = on; btnSim.setAttribute('aria-pressed', String(on)); svg.classList.toggle('sim', on); }
  btnSim.addEventListener('click', () => { const on = !state.sim; if (on) { stopGps(); toast('وضع المحاكاة: اضغط على الخريطة حتى تنقل موقعك'); } setSim(on); });

  function onTap(mp) {
    if (state.draw) { state.draw.pts.push([mp.x, mp.y]); renderDraft(); return; }
    if (state.sim) {
      if (state.nav && state.nav.phase === 'arrived') return;
      stopWalk(); state.follow = true;
      setFromMap(mp, 'sim', 5, {jump: true});
      if (state.nav) renderNavBar();
      else if (state.hereId && state.selectedId !== state.hereId) { state.selectedId = state.hereId; renderZones(); renderPanel(); }
      return;
    }
    if (state.nav) return;
    const z = zoneAt(mp); if (z) selectZone(z.id);
  }
  function selectZone(id, {zoom = false, tab = null} = {}) {
    state.selectedId = id; state.follow = id === state.hereId; state.formOpen = false; state.zoneForm = null; state.delArm = null; state.zoneDelArm = false;
    if (tab) state.tab = tab;
    renderZones(); renderPanel();
    if (zoom && ZM[id]) zoomToZone(ZM[id]);
  }
  function goHere() {
    state.follow = true; state.formOpen = false; state.zoneForm = null;
    if (state.hereId) state.selectedId = state.hereId;
    state.tab = 'site'; renderZones(); renderPanel();
    if (state.pos) centerOn(state.pos.x, state.pos.y); else toast('بعد ما وصل موقعك من الـGPS');
  }

  /* ---------- drawing zones (supervisor) ---------- */
  function renderDraft() {
    const g = $('#draft'); if (!g) return;
    const d = state.draw;
    if (!d) { g.innerHTML = ''; return; }
    const k = 1 / state.ppu;
    g.innerHTML = (d.pts.length > 1 ? `<polygon class="draft-l" points="${pstr(d.pts)}"/>` : '') + d.pts.map(p => `<circle class="draft-v" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${(7 * k).toFixed(2)}"/>`).join('');
    $('#drawTxt').textContent = d.pts.length < 3 ? `اضغط على زوايا الموقع على الخريطة (${d.pts.length} من 3 على الأقل)` : `${d.pts.length} زوايا. كمّل أو اضغط «تم».`;
  }
  function startDraw(mode, zoneId) {
    if (state.nav) return;
    state.draw = {mode, zoneId, pts: []}; setSim(false);
    svg.classList.add('drawing'); $('#drawBar').hidden = false; renderDraft();
    $('.map-wrap').scrollIntoView({block: 'start', behavior: 'smooth'});
    if (mode === 'edit' && ZM[zoneId]) zoomToZone(ZM[zoneId]);
    renderPanel();
  }
  function endDraw() { state.draw = null; svg.classList.remove('drawing'); $('#drawBar').hidden = true; renderDraft(); }
  $('#drawUndo').addEventListener('click', () => { if (state.draw) { state.draw.pts.pop(); renderDraft(); } });
  $('#drawCancel').addEventListener('click', () => { endDraw(); renderPanel(); });
  $('#drawDone').addEventListener('click', async () => {
    const d = state.draw; if (!d) return;
    if (d.pts.length < 3) { toast('لازم 3 زوايا على الأقل'); return; }
    const poly = d.pts.map(m2ll), entry = m2ll(insidePoint(d.pts));
    endDraw();
    if (d.mode === 'edit') {
      await mutate(() => api(`/api/zones/${d.zoneId}`, {method: 'PUT', body: {poly, entry}}), 'انحفظت الحدود الجديدة');
      return;
    }
    state.zoneForm = {mode: 'new', poly, entry}; state.tab = 'site'; state.selectedId = null; renderPanel();
    $('.panel').scrollIntoView({block: 'start', behavior: 'smooth'});
    setTimeout(() => { const t = $('#zName'); if (t) t.focus(); }, 300);
  });

  /* ---------- navigation ---------- */
  const navBar = $('#navBar'), navBanner = $('#navBanner');
  let camRaf = 0, wakeLock = null;
  async function keepAwake(on) {
    try { if (on && 'wakeLock' in navigator && !wakeLock) wakeLock = await navigator.wakeLock.request('screen'); else if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; } } catch (e) { wakeLock = null; }
  }
  const destZone = d => d.isPoi ? (d.zone ? d.zone.id : null) : d.id;
  function setBodyNav() {
    const n = state.nav, b = document.body;
    b.classList.toggle('nav', !!n);
    ['preview','active','arrived'].forEach(ph => b.classList.toggle('nav-' + ph, !!n && n.phase === ph));
    svg.classList.toggle('navmode', !!n && n.phase === 'active');
  }
  function renderRoute() {
    const n = state.nav; let list = [];
    if (n && n.phase === 'preview') list = n.route.pts;
    else if (n && n.phase === 'active') list = [n.q || n.route.pts[0], ...n.route.pts.slice(n.seg + 1)];
    const s = list.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    $('#rCase').setAttribute('points', s); $('#rLine').setAttribute('points', s);
    updatePin();
  }
  const nextMan = n => n.route.man.find(m => m.at > n.prog + 2) || n.route.man[n.route.man.length - 1];
  function openPicker() {
    $('#pickQ').value = ''; renderPick(); $('#pickBack').hidden = false;
    setTimeout(() => { try { $('#pickQ').focus({preventScroll: true}); } catch (e) {} }, 30);
  }
  const closePicker = () => { $('#pickBack').hidden = true; };
  function renderPick() {
    const q = norm($('#pickQ').value), raw = $('#pickQ').value.trim();
    const route = d => { const r = state.pos ? computeRoute(state.pos, d) : null; return {here: !!(r && r.error === 'here'), out: !!(r && r.error === 'outside'), len: r && !r.error ? r.len : Infinity}; };
    let items = [];
    if (q) {
      // labels first: an exact tank name, then names that start with what was typed, then the rest
      POIS.forEach(o => { const rank = o.key === q ? 0 : o.key.startsWith(q) ? 1 : o.key.includes(q) ? 2 : -1; if (rank >= 0) items.push({poi: o, rank, ...route(poiDest(o))}); });
      ZONES.forEach(z => { if (norm(z.name).includes(q) || norm(z.short).includes(q) || String(z.id) === raw) items.push({z, rank: 3, ...route(z)}); });
      items.sort((a, b) => a.rank - b.rank || a.len - b.len);
      items = items.slice(0, 40);
    } else {
      items = ZONES.map(z => ({z, rank: 3, ...route(z)})).sort((a, b) => (a.here ? -1 : 0) - (b.here ? -1 : 0) || a.len - b.len || a.z.id - b.z.id);
    }
    const sub = it => it.here ? 'إنت هنا هسه' : !state.pos ? 'اضغط حتى يبين على الخريطة' : it.out ? 'إنت برا حدود المصفى · اضغط حتى يبين على الخريطة' : isFinite(it.len) ? `${fmtDist(it.len)} · ${walkMin(it.len)} د مشي` : 'ما اكو طريق مرسوم';
    $('#pickList').innerHTML = items.length ? items.map(it => {
      if (it.poi) {
        const z = ZM[it.poi.zone_id];
        return `<button class="row" type="button" data-poi="${it.poi.id}"${it.here ? ' disabled' : ''}><span class="znum sm" style="min-width:auto">${esc(it.poi.label)}</span><span class="row-main"><strong>${esc(it.poi.label)}${z ? ` · ${esc(z.short)}` : ''}</strong><span>${sub(it)}</span></span>${z && z.hz ? `<span class="chip hz">${HZ[z.hz].chip}</span>` : '<span></span>'}</button>`;
      }
      const c = countsFor(it.z.id).total;
      return `<button class="row" type="button" data-dest="${it.z.id}"${it.here ? ' disabled' : ''}><span class="znum sm${it.here ? ' here' : ''}">${it.z.id}</span><span class="row-main"><strong>${esc(it.z.name)}</strong><span>${sub(it)}${c ? ` · ${c} شغل مفتوح` : ''}</span></span>${it.z.hz ? `<span class="chip hz">${HZ[it.z.hz].chip}</span>` : '<span></span>'}</button>`;
    }).join('') : `<p class="empty">ما لكينا «${esc(raw)}». جرّب الاسم مثل ما مكتوب بالمخطط، مثلاً N-6 أو K-3 أو RP-2.</p>`;
  }
  function goTo(dest, poi) {
    const r = state.pos ? computeRoute(state.pos, dest) : null;
    if (r && !r.error) { state.focusPoi = poi || null; startPreview(dest); return; }
    if (r && r.error === 'here') { toast(`إنت هسه بمكان ${dest.short}`); return; }
    if (poi) focusPoi(poi); else selectZone(dest.id, {zoom: true, tab: 'site'});
    if (!state.pos) toast(`هذا مكان ${dest.short}. من يوصل موقعك من الـGPS أكدر أوجهك له.`);
  }
  function startPreview(dz) {
    if (!state.pos) { toast('بعد ما وصل موقعك من الـGPS'); return; }
    if (state.draw) endDraw();
    const r = computeRoute(state.pos, dz);
    if (r && r.error === 'here') { toast(`إنت هسه داخل ${dz.name}`); return; }
    if (!r || r.error) { toast(r && r.error === 'outside' ? 'لازم تكون داخل حدود المصفى حتى أوجهك' : 'ما لكيت طريق لهذا الموقع'); return; }
    state.formOpen = false; state.zoneForm = null;
    state.nav = {phase: 'preview', dest: dz, route: r, prog: 0, seg: 0, q: r.pts[0], follow: true, spoken: new Set(), walk: null, offSince: 0};
    setBodyNav(); renderNavBar(); renderRoute();
    requestAnimationFrame(() => { state.rot = 0; fitRoute(r); });
  }
  function fitRoute(Rt) {
    const r = rect(); if (!r.width) return;
    const xs = Rt.pts.map(p => p.x), ys = Rt.pts.map(p => p.y), b = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    const top = 50, bot = (navBar.offsetHeight || 220) + 30, side = 50;
    const sc = Math.min((r.width - side * 2) / Math.max(b[2] - b[0], 60), Math.max(80, r.height - top - bot) / Math.max(b[3] - b[1], 60));
    const w = clamp(r.width / sc, 160, 6000), s = r.width / w, h = w * r.height / r.width;
    const cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2 + ((bot - top) / 2) / s;
    state.view = {x: cx - w/2, y: cy - h/2, w, h}; applyView();
  }
  function startNav() {
    const n = state.nav; if (!n) return;
    n.phase = 'active'; n.follow = true; n.spoken = new Set();
    state.heading = headingAt(n.route, 0);
    state.view.w = clamp(rect().width / 1.6, 200, 800);
    setBodyNav(); renderNavBar(); keepAwake(true);
    const m = nextMan(n), d = m.at - n.prog;
    let msg = `يلا نمشي إلى ${n.dest.name}. ${n.route.startText}`;
    if (m.type !== 'arrive' && d <= 70) { n.spoken.add('f' + m.i); msg += `، وبعد ${round10(d)} متر ${manText(m, n.dest)}`; }
    say(msg + '.', true);   // inside the tap, so phones allow speech
    if (!camRaf) camRaf = requestAnimationFrame(camLoop);
    navUpdate(false);
  }
  function camLoop() {
    const n = state.nav, active = n && n.phase === 'active';
    const target = active && state.headingUp ? state.heading : 0;
    const d = ((target - state.rot + 540) % 360) - 180;
    state.rot = Math.abs(d) < 0.3 ? target : (state.rot + d * 0.12 + 360) % 360;
    if (active && n.follow && state.pos) {
      const v = state.view, r = rect(); v.h = v.w * r.height / r.width;
      const q = state.headingUp ? rot(0, v.h * 0.2, state.rot) : {x: 0, y: 0};
      v.x = state.pos.x - q.x - v.w/2; v.y = state.pos.y - q.y - v.h/2;
    }
    applyView();
    if (active || Math.abs(((state.rot + 180) % 360) - 180) > 0.3) camRaf = requestAnimationFrame(camLoop);
    else { state.rot = 0; applyView(); camRaf = 0; }
  }
  function stopFollow() { const n = state.nav; if (n && n.phase === 'active' && n.follow) { n.follow = false; $('#btnRecenter').hidden = false; } }
  function resumeFollow() { const n = state.nav; if (!n || n.phase !== 'active') return; n.follow = true; $('#btnRecenter').hidden = true; state.view.w = clamp(rect().width / 1.6, 200, 800); }
  function navUpdate(jump) {
    const n = state.nav; if (!n || !state.pos) return;
    if (n.phase === 'preview') { const r = computeRoute(state.pos, n.dest); if (r && !r.error) { n.route = r; n.q = r.pts[0]; renderRoute(); renderNavBar(); } return; }
    if (n.phase !== 'active') return;
    const p = state.pos, Rt = n.route;
    if (pip(p, n.dest.poly)) { arrive(); return; }
    let best = null;
    const lo = jump ? 0 : Math.max(0, n.seg - 1), hi = jump ? Rt.pts.length - 2 : Math.min(Rt.pts.length - 2, n.seg + 3);
    for (let i = lo; i <= hi; i++) {
      const a = Rt.pts[i], b = Rt.pts[i+1], q = projSeg(p, [a.x, a.y], [b.x, b.y]), d = Math.hypot(p.x - q.x, p.y - q.y);
      if (!best || d < best.d - 0.01) best = {d, i, q, s: Rt.cum[i] + Math.hypot(q.x - a.x, q.y - a.y)};
    }
    if (best.d > Math.max(25, (p.acc || 5) + 15)) {
      const now = performance.now();
      if (jump || (n.offSince && now - n.offSince > 4000)) { reroute(); return; }
      if (!n.offSince) n.offSince = now;
    } else n.offSince = 0;
    if (jump || best.s >= n.prog - 3 || best.d < 8) { n.prog = best.s; n.seg = best.i; n.q = best.q; }
    if (Rt.len - n.prog < 3) { arrive(); return; }
    speakPrompts(n); updateNavLive(); renderRoute();
  }
  function speakPrompts(n) {
    const man = n.route.man;
    for (let k = 0; k < man.length; k++) {
      const m = man[k], d = m.at - n.prog;
      if (d < -2) continue;
      if (m.type === 'arrive') break;
      const segLen = m.at - (k ? man[k-1].at : 0);
      if (d <= 20) { if (!n.spoken.has('n' + m.i)) { n.spoken.add('n' + m.i); n.spoken.add('f' + m.i); say(m.last ? `${n.dest.name} على ${SIDE[m.type]}` : `${TURN[m.type]} هسه`, true); } }
      else if (d <= 80 && segLen >= 70 && !n.spoken.has('f' + m.i)) { n.spoken.add('f' + m.i); say(`بعد ${round10(d)} متر، ${manText(m, n.dest)}`); }
      break;
    }
  }
  function reroute() {
    const n = state.nav, r = computeRoute(state.pos, n.dest);
    if (r && r.error === 'here') { arrive(); return; }
    if (!r || r.error) { toast('طلعت برا حدود المصفى، ما أكدر أوجهك'); return; }
    n.route = r; n.prog = 0; n.seg = 0; n.q = r.pts[0]; n.spoken = new Set(); n.offSince = 0;
    say('طلعت من الطريق، دا أحسبلك طريق جديد', true);
    renderRoute(); updateNavLive();
  }
  function arrive() {
    const n = state.nav; if (!n || n.phase === 'arrived') return;
    stopWalk(); n.phase = 'arrived'; n.follow = false;
    const dz = n.dest, c = dz.isPoi ? (dz.zone ? countsFor(dz.zone.id).total : 0) : countsFor(dz.id).total;
    say(`وصلت إلى ${dz.name}.${dz.hz ? ` انتبه، ${HZ[dz.hz].voice}.` : ''}${c ? ` الأعمال المفتوحة هنا ${c}.` : ''}`, true);
    setBodyNav(); renderNavBar(); renderRoute(); keepAwake(false);
    if (!camRaf) camRaf = requestAnimationFrame(camLoop);
  }
  function endNav(showZone) {
    const n = state.nav; if (!n) return;
    stopWalk(); hush(); keepAwake(false);
    state.nav = null; state.rot = 0;
    setBodyNav(); renderNavBar(); renderRoute();
    requestAnimationFrame(() => {
      applyView();
      if (showZone && destZone(n.dest)) { selectZone(destZone(n.dest), {zoom: true, tab: 'site'}); $('.panel').scrollIntoView({block: 'start'}); }
      else if (state.pos) centerOn(state.pos.x, state.pos.y);
    });
  }
  const WALK_SIM = 14;
  function toggleWalk() {
    const n = state.nav; if (!n || n.phase !== 'active') return;
    if (n.walk) { stopWalk(); renderNavBar(); return; }
    stopGps(); setSim(true); resumeFollow();
    n.walk = {t: null, raf: 0};
    const step = ts => {
      const n2 = state.nav; if (!n2 || !n2.walk || n2.phase !== 'active') return;
      const w = n2.walk, dt = w.t === null ? 0 : Math.min(0.1, (ts - w.t) / 1000); w.t = ts;
      const Rt = n2.route, d = Math.min(n2.prog + dt * WALK_SIM, Rt.len);
      setFromMap(pointOn(Rt, d), 'sim', 5, {heading: headingAt(Rt, Math.min(d + 0.5, Rt.len - 0.01))});
      if (state.nav && state.nav.walk === w) w.raf = requestAnimationFrame(step);
    };
    n.walk.raf = requestAnimationFrame(step);
    renderNavBar();
  }
  function stopWalk() { const n = state.nav; if (n && n.walk) { cancelAnimationFrame(n.walk.raf); n.walk = null; } }
  function updateNavLive() {
    const n = state.nav; if (!n || n.phase !== 'active') return;
    const Rt = n.route, rem = Math.max(0, Rt.len - n.prog), m = nextMan(n), d = Math.max(0, m.at - n.prog);
    const ico = m.type === 'arrive' ? 'arrive' : m.type, nb = $('#nbIco');
    if (nb.dataset.ico !== ico) { nb.innerHTML = ICON[ico]; nb.dataset.ico = ico; }
    $('#nbDist').textContent = fmtDist(d);
    $('#nbText').textContent = m.type === 'arrive' ? `${n.dest.name} قدامك` : manText(m, n.dest);
    const m2 = Rt.man.find(x => x.at > m.at + 0.5), then = $('#navThen');
    if (m.type !== 'arrive' && m2 && m2.at - m.at < 80) { then.hidden = false; then.textContent = `بعدها: ${m2.type === 'arrive' ? 'توصل' : manText(m2, n.dest)}`; } else then.hidden = true;
    const eta = $('#nvEta'); if (eta) { eta.textContent = `${walkMin(rem)} د`; $('#nvSub').textContent = `${fmtDist(rem)} · الوصول ${clock(rem / WALK)}`; }
  }
  function renderNavBar() {
    const n = state.nav;
    if (!n) { navBar.hidden = true; navBanner.hidden = true; $('#navThen').hidden = true; $('#btnRecenter').hidden = true; return; }
    navBar.hidden = false;
    const dz = n.dest, Rt = n.route;
    if (n.phase === 'preview') {
      navBanner.hidden = true; $('#navThen').hidden = true; $('#btnRecenter').hidden = true;
      const turns = Rt.man.filter(m => m.type !== 'arrive').length;
      navBar.innerHTML = `<div class="nv-dest"><span class="znum lg">${dz.isPoi ? esc(dz.short) : dz.id}</span><div style="min-width:0"><strong>${esc(dz.name)}</strong><span class="sub">عبر ${esc(Rt.roads.map(r => r.name).join('، ') || 'طريق مباشر')}</span></div></div>
        <div class="nv-stats"><div class="nv-stat"><b>${walkMin(Rt.len)} د</b><span>مشي</span></div><div class="nv-stat"><b>${carMin(Rt.len)} د</b><span>سيارة · حد 20 كم/س</span></div><div class="nv-stat"><b>${fmtDist(Rt.len)}</b><span>${turnsWord(turns)}</span></div></div>
        ${dz.hz ? `<p class="hz-note"><b>${HZ[dz.hz].label}.</b> ${HZ[dz.hz].note}</p>` : ''}
        <div class="nv-actions"><button class="btn go" type="button" data-nav="go">${NAV_ICO}انطلق</button><button class="btn" type="button" data-nav="cancel">إلغاء</button></div>`;
    } else if (n.phase === 'active') {
      navBanner.hidden = false;
      navBar.innerHTML = `<div class="nv-row"><div class="nv-eta"><b id="nvEta"></b><span id="nvSub"></span></div>
        <div class="nv-btns"><button class="cbtn" type="button" data-nav="mute" aria-pressed="${!speech.on}" aria-label="${speech.on ? 'كتم الصوت' : 'تشغيل الصوت'}">${speech.on ? SPK_ON : SPK_OFF}</button>
        ${isSup() ? `<button class="cbtn" type="button" data-nav="walk" aria-pressed="${!!n.walk}">${n.walk ? 'إيقاف المحاكاة' : 'محاكاة المشي'}</button>` : ''}
        <button class="cbtn end" type="button" data-nav="cancel">إنهاء</button></div></div>`;
      updateNavLive();
    } else {
      navBanner.hidden = false; $('#navThen').hidden = true; $('#btnRecenter').hidden = true;
      const nb = $('#nbIco'); nb.innerHTML = ICON.arrive; nb.dataset.ico = 'arrive';
      $('#nbDist').textContent = 'وصلت'; $('#nbText').textContent = dz.name;
      navBar.innerHTML = `<div class="nv-dest"><span class="znum lg here">${dz.isPoi ? esc(dz.short) : dz.id}</span><div style="min-width:0"><strong>${esc(dz.name)}</strong><span class="sub">${esc(dz.kind)}</span></div></div>
        ${dz.hz ? `<p class="hz-note"><b>${HZ[dz.hz].label}.</b> ${HZ[dz.hz].note}</p>` : ''}
        <div class="nv-actions">${destZone(dz) ? `<button class="btn go" type="button" data-nav="works">الأعمال بهذا الموقع (${countsFor(destZone(dz)).total})</button>` : ''}<button class="btn" type="button" data-nav="cancel">إنهاء</button></div>`;
    }
    requestAnimationFrame(() => document.documentElement.style.setProperty('--barh', navBar.offsetHeight + 'px'));
  }
  navBar.addEventListener('click', e => {
    const b = e.target.closest('button[data-nav]'); if (!b) return;
    const a = b.dataset.nav;
    if (a === 'go') startNav();
    else if (a === 'cancel') endNav(false);
    else if (a === 'works') endNav(true);
    else if (a === 'walk') toggleWalk();
    else if (a === 'mute') { speech.on = !speech.on; if (!speech.on) hush(); renderNavBar(); }
  });
  $('#btnRecenter').addEventListener('click', resumeFollow);
  $('#btnWhere').addEventListener('click', openPicker);
  $('#pickClose').addEventListener('click', closePicker);
  $('#pickBack').addEventListener('click', e => { if (e.target.id === 'pickBack') closePicker(); });
  $('#pickQ').addEventListener('input', renderPick);
  $('#pickList').addEventListener('click', e => {
    const b = e.target.closest('button[data-dest],button[data-poi]'); if (!b || b.disabled) return;
    closePicker();
    if (b.dataset.poi) { const o = POIS.find(x => x.id === +b.dataset.poi); if (o) goTo(poiDest(o), o); }
    else goTo(ZM[+b.dataset.dest]);
  });
  document.addEventListener('keydown', e => { if (e.key !== 'Escape') return; if (!$('#pickBack').hidden) closePicker(); else if (state.nav && state.nav.phase === 'preview') endNav(false); });

  /* ---------- rendering ---------- */
  function renderZones() {
    ZONES.forEach(z => {
      if (!z.el) return;
      const c = countsFor(z.id);
      z.el.classList.toggle('has-active', c.active > 0);
      z.el.classList.toggle('has-plan', c.active === 0 && c.planned > 0);
      z.el.classList.toggle('is-here', z.id === state.hereId);
      z.el.classList.toggle('is-selected', z.id === state.selectedId);
      z.el.classList.toggle('temp', z.temp);
      z.lblEl.classList.toggle('is-here', z.id === state.hereId);
      z.lblEl.classList.toggle('hz', !!z.hz);
      z.lblEl.querySelector('.cnt').innerHTML = c.total ? `<circle class="cb ${c.active ? 'a' : 'p'}" cx="13" cy="-12" r="8.5"/><text class="ct" x="13" y="-12">${c.total}</text>` : '';
    });
  }
  function renderHere() {
    const p = state.pos; if (!p) return;
    const z = state.hereId ? ZM[state.hereId] : null, inSite = pip(p, SITE);
    $('#here').classList.toggle('outside', !z);
    if (z) {
      $('#hereName').innerHTML = `<span class="znum here">${z.id}</span><span>${esc(z.name)}</span>`;
      const np = nearestPoi(p, 35);
      $('#hereSub').innerHTML = `${np ? `قرب <b class="mono">${esc(np.label)}</b> · ` : ''}${esc(z.kind)}${z.temp ? ' · <span class="muted">اسم مؤقت</span>' : ''}`;
    } else if (inSite) {
      const n = nearestZone(p), r = ROADS.length ? nearestOnRoads(p) : null;
      $('#hereName').innerHTML = `<span class="znum road">—</span><span>${r && r.d < 25 ? 'على ' + esc(ROADS[r.ri].name) : 'بين المواقع'}</span>`;
      $('#hereSub').textContent = n.zone ? `أقرب موقع: ${n.zone.id} · ${n.zone.short} (على بعد ${Math.round(n.d)} م)` : '';
    } else {
      const d = polyDist(p, SITE);
      $('#hereName').innerHTML = `<span>خارج حدود المصفى</span>`;
      $('#hereSub').textContent = `تبعد ${d >= 1000 ? (d/1000).toFixed(1) + ' كم' : Math.round(d) + ' م'} عن حدود الخريطة`;
    }
    $('#hereMeta').innerHTML = `<span class="mono" dir="ltr">${p.lat.toFixed(6)}, ${p.lon.toFixed(6)}</span><span>الدقة ± ${Math.round(p.acc)} م</span><span>المصدر: <span class="src">${p.src === 'gps' ? 'GPS' : 'محاكاة'}</span></span>`;
    const warn = $('#hereWarn');
    if (z && z.hz) { warn.hidden = false; $('#hereWarnTxt').innerHTML = `<b>${HZ[z.hz].label}.</b> ${HZ[z.hz].note}`; } else warn.hidden = true;
    const stat = $('#hereStat');
    if (z) { stat.hidden = false; $('#hereCount').textContent = countsFor(z.id).total; } else stat.hidden = true;
  }

  const panelBody = $('#panelBody');
  const panelBusy = () => state.formOpen || !!state.zoneForm || !!state.draw;
  const opts = (o, sel) => Object.entries(o).map(([k, v]) => `<option value="${esc(k)}"${k === sel ? ' selected' : ''}>${esc(v)}</option>`).join('');
  function workCard(w) {
    const crew = (w.crew || []).length ? w.crew.map(n => `<span class="person"><i>${esc(String(n).trim().charAt(0))}</i>${esc(n)}</span>`).join('') : '<span class="small muted">ما انكتبت أسماء العمال</span>';
    let actions = '';
    if (isSup()) {
      const act = w.status === 'planned' ? `<button class="sbtn go" type="button" data-act="start" data-w="${w.id}">بدء الشغل</button>`
        : w.status === 'active' ? `<button class="sbtn go" type="button" data-act="done" data-w="${w.id}">تم الإنجاز</button>`
        : `<button class="sbtn" type="button" data-act="reopen" data-w="${w.id}">إعادة فتح</button>`;
      const armed = state.delArm === w.id;
      actions = `<div class="work-actions">${act}<button class="sbtn del${armed ? ' confirm' : ''}" type="button" data-act="del" data-w="${w.id}">${armed ? 'اضغط مرة ثانية للحذف' : 'حذف'}</button></div>`;
    }
    return `<article class="work st-${w.status}">
      <header><h4>${esc(w.title)}</h4><span class="chip st-${w.status}">${STATUS[w.status]}</span></header>
      <div class="crew">${crew}</div>
      <dl class="meta">
        <div><dt>تصريح العمل</dt><dd>${PERMITS[w.permit] || '—'}${w.ptw ? ` · <span class="mono" dir="ltr">${esc(w.ptw)}</span>` : ''}</dd></div>
        <div><dt>الموعد</dt><dd>${dayLabel(w.day)} · ${SHIFTS[w.shift] || ''}</dd></div>
        <div><dt>المشرف</dt><dd>${esc(w.sup || '—')}</dd></div>
      </dl>${actions}
    </article>`;
  }
  function workFormHTML(z) {
    return `<form class="add" id="addForm" novalidate>
      <p class="add-t">شغل جديد في الموقع ${z.id} · ${esc(z.short)}</p>
      <label for="fTitle">الشغل المطلوب<input id="fTitle" maxlength="160" placeholder="مثال: فحص عزل كيبل المضخة P-102" autocomplete="off"></label>
      <label for="fCrew">أسماء العمال<input id="fCrew" placeholder="افصل بين الأسماء بفاصلة" autocomplete="off"></label>
      <div class="row">
        <label for="fPermit">نوع التصريح<select id="fPermit">${opts(PERMITS, 'cold')}</select></label>
        <label for="fPtw">رقم التصريح<input id="fPtw" maxlength="30" dir="ltr" placeholder="PTW-0000" autocomplete="off"></label>
      </div>
      <div class="row">
        <label for="fDay">الموعد<select id="fDay">${opts({'0':'اليوم','1':'غداً','2':'بعد غد'}, '0')}</select></label>
        <label for="fShift">الوجبة<select id="fShift">${opts(SHIFTS, 'am')}</select></label>
      </div>
      <div class="row">
        <label for="fStatus">الحالة<select id="fStatus">${opts({planned:'مخطط', active:'شغّال الآن'}, 'planned')}</select></label>
        <label for="fSup">المشرف<input id="fSup" maxlength="60" autocomplete="off"></label>
      </div>
      <p class="err" id="fErr" hidden>اكتب وصف الشغل حتى نحفظه.</p>
      <div class="form-actions"><button type="submit" class="sbtn go">حفظ الشغل</button><button type="button" class="sbtn" data-act="cancel">إلغاء</button></div>
    </form>`;
  }
  function zoneFormHTML(z) {
    const hzOpts = {'': 'غير محدد', z1: 'Zone 1', z2: 'Zone 2', hv: 'جهد عالي', restricted: 'منطقة محظورة'};
    const isNewZone = !z;
    return `<form class="add" id="zoneForm" novalidate>
      <p class="add-t">${isNewZone ? 'موقع جديد' : `اسم الموقع ${z.id}`}</p>
      <label for="zName">الاسم الكامل<input id="zName" maxlength="80" value="${z && !z.temp ? esc(z.name) : ''}" placeholder="مثال: خزانات المنتجات الجديدة" autocomplete="off"></label>
      <label for="zShort">اسم مختصر يطلع على الخريطة<input id="zShort" maxlength="30" value="${z && !z.temp ? esc(z.short) : ''}" placeholder="اتركه فارغ إذا الاسم قصير" autocomplete="off"></label>
      <div class="row">
        <label for="zKind">النوع<select id="zKind">${opts(Object.fromEntries(KINDS.map(k => [k, k])), z ? z.kind : 'خزانات')}</select></label>
        <label for="zHz">تصنيف المنطقة<select id="zHz">${opts(hzOpts, z && z.hz || '')}</select></label>
      </div>
      ${z && z.temp ? `<p class="small muted">الاسم المؤقت الحالي: ${esc(z.name)}</p>` : ''}
      <p class="err" id="zErr" hidden>اكتب اسم الموقع.</p>
      <div class="form-actions"><button type="submit" class="sbtn go">${isNewZone ? 'إضافة الموقع' : 'حفظ'}</button><button type="button" class="sbtn" data-act="zcancel">إلغاء</button></div>
    </form>`;
  }
  function siteHTML() {
    if (state.zoneForm && state.zoneForm.mode === 'new') return zoneFormHTML(null);
    if (state.draw) return `<p class="note">${state.draw.mode === 'new' ? 'ارسم الموقع الجديد على الخريطة: اضغط على زواياه وحدة وحدة، وبعدين «تم».' : 'ارسم الحدود الجديدة على الخريطة، وبعدين «تم».'}</p>`;
    const z = ZM[state.selectedId];
    if (!z) return `<p class="empty">اضغط على أي موقع بالخريطة حتى تشوف تفاصيله والعمال اللي بيه.</p>${isSup() ? `<button class="sbtn ghost" type="button" data-act="znew">${PLUS_ICO}إضافة موقع جديد</button>` : ''}`;
    const isHere = z.id === state.hereId, ws = state.works.filter(w => w.zone_id === z.id).sort(byStatus), poisIn = POIS.filter(o => o.zone_id === z.id);
    const sup = isSup();
    return `<div class="zhead"><span class="znum lg${isHere ? ' here' : ''}">${z.id}</span><div style="min-width:0"><h2>${esc(z.name)}</h2><p>${esc(z.kind)}</p></div></div>
      <div class="chips">${isHere ? '<span class="chip you">أنت هنا الآن</span>' : `<button class="sbtn navgo" type="button" data-act="nav">${NAV_ICO}ودّيني هنا</button>`}${z.hz ? `<span class="chip hz">${HZ[z.hz].label}</span>` : ''}${z.isNew ? '<span class="chip new">انبنى بعد 2023</span>' : ''}${z.temp ? '<span class="chip temp">اسم مؤقت</span>' : ''}</div>
      ${poisIn.length ? `<div class="chips"><span class="small muted">اضغط على الاسم حتى أوجهك له:</span>${poisIn.map(o => `<button class="chip tank" type="button" data-poi="${o.id}">${esc(o.label)}</button>`).join('')}</div>` : ''}
      ${sup && state.zoneForm && state.zoneForm.mode === 'edit' ? zoneFormHTML(z) : ''}
      ${sup && !state.zoneForm ? `<div class="chips"><button class="sbtn" type="button" data-act="zedit">${EDIT_ICO}تعديل الاسم</button><button class="sbtn" type="button" data-act="zshape">${SHAPE_ICO}تعديل الحدود</button><button class="sbtn del${state.zoneDelArm ? ' confirm' : ''}" type="button" data-act="zdel">${state.zoneDelArm ? 'اضغط مرة ثانية للحذف' : 'حذف الموقع'}</button></div>` : ''}
      ${z.temp && !state.zoneForm ? `<p class="note">هذا اسم مؤقت، والحدود تقريبية.${sup ? ' إذا تعرف اسمه الصحيح اضغط «تعديل الاسم».' : ''}</p>` : ''}
      ${z.hz ? `<p class="hz-note">${HZ[z.hz].note}</p>` : ''}
      <div class="sec"><h3>الأعمال بهذا الموقع <span class="muted mono">(${ws.length})</span></h3>${sup && !state.formOpen ? '<button class="sbtn go" type="button" data-act="add">إضافة شغل</button>' : ''}</div>
      ${state.formOpen && sup ? workFormHTML(z) : ''}
      <div class="works">${ws.length ? ws.map(workCard).join('') : `<p class="empty">${sup ? 'ما اكو شغل مسجّل بهذا الموقع. اضغط «إضافة شغل» حتى تكتب أسماء العمال والمهمة.' : 'ما اكو شغل مسجّل بهذا الموقع.'}</p>`}</div>
      ${!isHere && state.hereId ? `<button class="sbtn ghost" type="button" data-act="here">ارجع لموقعي الحالي (${state.hereId} · ${esc(ZM[state.hereId] ? ZM[state.hereId].short : '')})</button>` : ''}`;
  }
  function zonesHTML() {
    const named = ZONES.filter(z => !z.temp).length;
    return `<div class="sec"><h3>${named} من ${ZONES.length} عليها اسم صحيح</h3>${isSup() ? `<button class="sbtn go" type="button" data-act="znew">${PLUS_ICO}موقع جديد</button>` : ''}</div>
      <div class="progress" aria-hidden="true"><i style="width:${ZONES.length ? Math.round(named / ZONES.length * 100) : 0}%"></i></div>
      <div class="list">${ZONES.map(z => { const c = countsFor(z.id).total; return `<button class="row" type="button" data-goto="${z.id}"><span class="znum sm${z.id === state.hereId ? ' here' : ''}">${z.id}</span><span class="row-main"><strong>${esc(z.name)}</strong><span>${esc(z.kind)}${c ? ` · ${c} شغل مفتوح` : ''}</span></span>${z.temp ? `<span class="chip ${z.isNew ? 'new' : 'temp'}">${z.isNew ? 'جديد · مؤقت' : 'مؤقت'}</span>` : z.hz ? `<span class="chip hz">${HZ[z.hz].chip}</span>` : '<span class="chip st-done">مسمّى</span>'}</button>`; }).join('')}</div>`;
  }
  function worksShellHTML() {
    const c = {all: state.works.length}; ['active','planned','done'].forEach(k => c[k] = state.works.filter(w => w.status === k).length);
    return `<div class="filters">${['all','active','planned','done'].map(k => `<button class="fchip" type="button" data-filter="${k}" aria-pressed="${state.filter === k}">${k === 'all' ? 'الكل' : STATUS[k]} <b>${c[k]}</b></button>`).join('')}</div>
      <label class="search" for="q"><span class="sr">بحث</span><input id="q" type="search" placeholder="ابحث باسم عامل أو شغل أو رقم موقع" value="${esc(state.q)}" autocomplete="off"></label>
      <div id="worksList" class="list"></div>`;
  }
  function renderWorksList() {
    const q = state.q.trim();
    const list = state.works.filter(w => ZM[w.zone_id])
      .filter(w => state.filter === 'all' || w.status === state.filter)
      .filter(w => !q || w.title.includes(q) || (w.crew || []).some(n => String(n).includes(q)) || String(w.zone_id) === q || ZM[w.zone_id].name.includes(q) || String(w.ptw || '').toLowerCase().includes(q.toLowerCase()))
      .sort(byStatus);
    $('#worksList').innerHTML = list.length ? list.map(w => `<button class="row" type="button" data-goto="${w.zone_id}"><span class="znum sm">${w.zone_id}</span><span class="row-main"><strong>${esc(w.title)}</strong><span>${esc(ZM[w.zone_id].short)} · ${crewWord((w.crew || []).length)} · ${dayLabel(w.day)}</span></span><span class="chip st-${w.status}">${STATUS[w.status]}</span></button>`).join('')
      : `<p class="empty">${state.works.length ? 'ما اكو أعمال تطابق البحث.' : 'ما انضاف أي شغل بعد.'}</p>`;
  }
  function workersHTML() {
    const m = new Map();
    state.works.filter(w => w.status !== 'done' && ZM[w.zone_id]).forEach(w => (w.crew || []).forEach(n => { const k = String(n).trim(); if (!k) return; if (!m.has(k)) m.set(k, []); m.get(k).push(w); }));
    const rows = [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], 'ar'));
    if (!rows.length) return `<p class="empty">ما اكو عمال عندهم شغل مفتوح.</p>`;
    return `<p class="small muted">${rows.length} عامل عندهم شغل مفتوح. اضغط على الاسم حتى تشوف موقعه.</p>
      <div class="list">${rows.map(([n, ws]) => { ws.sort(byStatus); const w = ws[0]; return `<button class="row" type="button" data-goto="${w.zone_id}"><span class="av">${esc(n.charAt(0))}</span><span class="row-main"><strong>${esc(n)}</strong><span>الموقع ${w.zone_id} · ${esc(ZM[w.zone_id].short)} · ${esc(w.title)}${ws.length > 1 ? ` (+${ws.length - 1})` : ''}</span></span><span class="chip st-${w.status}">${STATUS[w.status]}</span></button>`; }).join('')}</div>`;
  }
  function renderPanel() {
    $$('.tab').forEach(t => t.setAttribute('aria-selected', String(t.dataset.tab === state.tab)));
    if (state.tab === 'site') panelBody.innerHTML = siteHTML();
    else if (state.tab === 'zones') panelBody.innerHTML = zonesHTML();
    else if (state.tab === 'works') { panelBody.innerHTML = worksShellHTML(); renderWorksList(); }
    else panelBody.innerHTML = workersHTML();
  }

  /* ---------- data sync ---------- */
  async function refresh() {
    const [site, works] = await Promise.all([api('/api/site'), api('/api/works')]);
    applySite(site); state.works = works || [];
    if (state.pos) { const z = zoneAt(state.pos); state.hereId = z ? z.id : null; }
    renderDyn(); applyView(); renderZones(); renderHere();
    if (state.nav && (state.nav.dest.isPoi ? !POIS.some(o => 'p' + o.id === state.nav.dest.id) : !ZM[state.nav.dest.id])) endNav(false);
    if (!panelBusy()) renderPanel();
  }
  async function mutate(fn, msg) {
    if (state.busy) return; state.busy = true;
    try { await fn(); await refresh(); if (msg) toast(msg); }
    catch (e) {
      if (e.status === 401) { toast('انتهت الجلسة، سجّل دخول مرة ثانية'); showLogin(); }
      else if (e.message === 'zone_has_open_works') toast('بهذا الموقع أعمال مفتوحة. احذفها أو خلّصها قبل ما تحذف الموقع.');
      else if (e.status === 403) toast('هذا الشي للمشرف بس');
      else toast('ما انحفظ. تأكد من الإنترنت وجرّب مرة ثانية.');
    } finally { state.busy = false; }
  }
  let pollT = 0;
  async function poll() {
    clearTimeout(pollT);
    try { const r = await api('/api/version'); if (r.v !== state.version) await refresh(); }
    catch (e) { if (e.status === 401) { showLogin(); return; } }
    pollT = setTimeout(poll, document.hidden ? 60000 : 10000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && state.role) poll(); });

  let delT;
  panelBody.addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.goto) { selectZone(+b.dataset.goto, {zoom: true, tab: 'site'}); return; }
    if (b.dataset.filter) { state.filter = b.dataset.filter; $$('.fchip').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.filter === state.filter))); renderWorksList(); return; }
    const act = b.dataset.act, id = b.dataset.w;
    if (b.dataset.poi) { const o = POIS.find(x => x.id === +b.dataset.poi); if (o) goTo(poiDest(o), o); return; }
    if (act === 'nav') { goTo(ZM[state.selectedId]); return; }
    if (act === 'here') { goHere(); return; }
    if (!isSup()) return;
    if (act === 'znew') { state.tab = 'site'; startDraw('new'); return; }
    if (act === 'zedit') { state.zoneForm = {mode: 'edit'}; state.formOpen = false; renderPanel(); const t = $('#zName'); if (t) t.focus(); return; }
    if (act === 'zshape') { startDraw('edit', state.selectedId); return; }
    if (act === 'zcancel') { state.zoneForm = null; renderPanel(); return; }
    if (act === 'zdel') {
      if (!state.zoneDelArm) { state.zoneDelArm = true; renderPanel(); setTimeout(() => { if (state.zoneDelArm) { state.zoneDelArm = false; renderPanel(); } }, 3500); return; }
      state.zoneDelArm = false; const zid = state.selectedId;
      mutate(() => api(`/api/zones/${zid}`, {method: 'DELETE'}), `انحذف الموقع ${zid}`).then(() => { if (!ZM[zid]) { state.selectedId = null; renderPanel(); } });
      return;
    }
    if (act === 'add') { state.formOpen = true; state.zoneForm = null; state.follow = false; renderPanel(); const t = $('#fTitle'); if (t) t.focus(); return; }
    if (act === 'cancel') { state.formOpen = false; renderPanel(); return; }
    const w = state.works.find(x => x.id === id); if (!w) return;
    const put = status => mutate(() => api(`/api/works/${w.id}`, {method: 'PUT', body: {...w, status}}), status === 'active' ? 'بدأ الشغل' : status === 'done' ? 'تم تسجيل الشغل كمنجز' : 'رجع الشغل للحالة: شغّال');
    if (act === 'start') put('active');
    else if (act === 'done') put('done');
    else if (act === 'reopen') put('active');
    else if (act === 'del') {
      clearTimeout(delT);
      if (state.delArm === id) { state.delArm = null; mutate(() => api(`/api/works/${id}`, {method: 'DELETE'}), 'انحذف الشغل'); }
      else { state.delArm = id; renderPanel(); delT = setTimeout(() => { state.delArm = null; if (!panelBusy()) renderPanel(); }, 3500); }
    }
  });
  panelBody.addEventListener('submit', e => {
    e.preventDefault();
    if (!isSup()) return;
    if (e.target.id === 'zoneForm') {
      const name = $('#zName').value.trim();
      if (!name) { $('#zErr').hidden = false; $('#zName').focus(); return; }
      const body = {name, short: $('#zShort').value.trim() || name, kind: $('#zKind').value, hz: $('#zHz').value || null};
      const f = state.zoneForm;
      if (f && f.mode === 'new') {
        Object.assign(body, {poly: f.poly, entry: f.entry});
        mutate(async () => { const z = await api('/api/zones', {method: 'POST', body}); state.zoneForm = null; state.selectedId = z.id; }, 'انضاف الموقع');
      } else {
        const zid = state.selectedId;
        mutate(async () => { await api(`/api/zones/${zid}`, {method: 'PUT', body}); state.zoneForm = null; }, `انحفظ اسم الموقع ${zid}`);
      }
      return;
    }
    if (e.target.id !== 'addForm') return;
    const title = $('#fTitle').value.trim();
    if (!title) { $('#fErr').hidden = false; $('#fTitle').focus(); return; }
    const body = {zone_id: state.selectedId, title, crew: $('#fCrew').value.split(/[،,\n]+/).map(s => s.trim()).filter(Boolean),
      permit: $('#fPermit').value, ptw: $('#fPtw').value.trim(), shift: $('#fShift').value, status: $('#fStatus').value, sup: $('#fSup').value.trim(), day: iso(+$('#fDay').value)};
    mutate(async () => { await api('/api/works', {method: 'POST', body}); state.formOpen = false; }, `انضاف الشغل للموقع ${body.zone_id}`);
  });
  panelBody.addEventListener('input', e => { if (e.target.id === 'q') { state.q = e.target.value; renderWorksList(); } });
  $$('.tab').forEach(t => t.addEventListener('click', () => { state.tab = t.dataset.tab; state.formOpen = false; state.zoneForm = null; renderPanel(); }));

  /* ---------- controls ---------- */
  const btnPlan = $('#btnPlan');
  function setPlan(on) { state.plan = on; btnPlan.setAttribute('aria-pressed', String(on)); const el = $('#layerPlan'); if (el) el.style.display = on ? '' : 'none'; svg.classList.toggle('plan-on', on); }
  btnPlan.addEventListener('click', () => { setPlan(!state.plan); toast(state.plan ? 'المخطط ظاهر فوق صورة القمر الصناعي' : 'المخطط مخفي'); });
  const btnLayer = $('#btnLayer');
  function setAttrib() { $('#attrib').textContent = state.layer26 ? `Copernicus Sentinel-2 · ${CONFIG && CONFIG.layer2026 ? CONFIG.layer2026.date : ''}` : 'Imagery © Esri, Vantor'; }
  btnLayer.addEventListener('click', () => {
    state.layer26 = !state.layer26;
    btnLayer.setAttribute('aria-pressed', String(state.layer26));
    $('#layer26').style.display = state.layer26 ? '' : 'none';
    setAttrib();
    toast(state.layer26 ? 'صورة تشرين الثاني 2026: أحدث، بس دقتها 10 م فتطلع مضببة' : 'رجعنا لصورة القمر الصناعي الواضحة');
  });
  $('#zIn').addEventListener('click', () => zoomCenter(1/1.5));
  $('#zOut').addEventListener('click', () => zoomCenter(1.5));
  $('#zFit').addEventListener('click', () => { if (state.nav) { stopFollow(); state.rot = 0; fitRoute(state.nav.route); } else fitView(); });
  $('#zMe').addEventListener('click', () => { if (state.nav) resumeFollow(); else goHere(); });
  $('#btnNorth').addEventListener('click', () => {
    if (state.nav && state.nav.phase === 'active') { state.headingUp = !state.headingUp; toast(state.headingUp ? 'الخريطة تدور ويا اتجاه مشيك' : 'الشمال دائماً للأعلى'); }
    else toast('الخريطة تدور ويا اتجاهك وقت التوجيه');
  });
  $('#hereStat').addEventListener('click', goHere);
  $('#btnLogout').addEventListener('click', async () => { try { await api('/api/logout', {method: 'POST'}); } catch (e) {} location.reload(); });

  let toastT;
  function toast(msg, kind = '') { const t = $('#toast'); t.textContent = msg; t.className = 'toast show ' + kind; clearTimeout(toastT); toastT = setTimeout(() => { t.className = 'toast ' + kind; }, 3800); }

  /* ---------- start ---------- */
  function showLogin() {
    clearTimeout(pollT); stopGps();
    $('#loading').hidden = true; $('#app').hidden = true; $('#login').hidden = false;
    setTimeout(() => $('#code').focus(), 50);
  }
  $('#loginForm').addEventListener('submit', async e => {
    e.preventDefault();
    const code = $('#code').value.trim(); if (!code) return;
    const err = $('#loginErr'); err.hidden = true;
    try { const r = await api('/api/login', {method: 'POST', body: {code}}); $('#code').value = ''; start(r.role); }
    catch (x) { err.hidden = false; err.textContent = x.status === 429 ? 'محاولات كثيرة. انتظر 10 دقائق وجرّب.' : x.status === 401 ? 'الرمز غلط. تأكد منه وجرّب مرة ثانية.' : 'ما وصلنا للسيرفر. تأكد من الإنترنت.'; }
  });
  let started = false;
  async function start(role) {
    state.role = role;
    $('#login').hidden = true; $('#loading').hidden = false;
    $('#whoTxt').textContent = role === 'sup' ? 'مشرف' : 'عامل';
    btnSim.hidden = role !== 'sup';
    const [site, works] = await Promise.all([api('/api/site'), api('/api/works')]);
    if (!site.config) { $('#loading').textContent = 'الخريطة بعدها ما انضافت لقاعدة البيانات.'; return; }
    CONFIG = site.config; setupGeo(CONFIG);
    $('#loading').hidden = true; $('#app').hidden = false;
    if (!started) {
      started = true; buildStatic(); new ResizeObserver(() => applyView()).observe(svg);
      $('#layerPlan').addEventListener('error', () => { btnPlan.hidden = true; setPlan(false); });
      setPlan(true);
    }
    applySite(site); state.works = works || [];
    renderDyn(); setAttrib(); fitView(); renderZones(); renderPanel();
    startGps();
    pollT = setTimeout(poll, 10000);
  }
  async function boot() {
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
    try { const me = await api('/api/me'); await start(me.role); }
    catch (e) { if (e.status === 401) showLogin(); else $('#loading').textContent = 'ما وصلنا للسيرفر. تأكد من الإنترنت وحدّث الصفحة.'; }
  }
  boot();
})();
