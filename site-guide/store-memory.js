'use strict';
// In-memory store for local development. Optional SEED_FILE (JSON: config, zones, roads, features) and LAYER_FILE (image).
const fs = require('fs');

let v = 1, config = null, zones = [], roads = [], features = [], pois = [], works = [], layer = null;
const bump = () => { v += 1; };

module.exports = {
  async init() {
    if (process.env.SEED_FILE) {
      const s = JSON.parse(fs.readFileSync(process.env.SEED_FILE, 'utf8'));
      config = s.config || null; zones = s.zones || []; roads = s.roads || []; features = s.features || [];
      pois = (s.pois || []).map((p, i) => ({id: i + 1, ...p}));
    }
    if (process.env.LAYER_FILE) layer = {mime: 'image/jpeg', data: fs.readFileSync(process.env.LAYER_FILE)};
  },
  async version() { return v; },
  async site() { return {config, zones, roads, features, pois, version: v}; },
  async works() { return works; },
  async blob() { return layer; },
  async addZone(z) {
    const zone = {id: zones.reduce((m, x) => Math.max(m, x.id), 0) + 1, temp: false, is_new: false, entry: null, ...z};
    zones.push(zone); bump(); return zone;
  },
  async updateZone(id, z) { const zone = zones.find(x => x.id === id); if (!zone) return null; Object.assign(zone, z); bump(); return zone; },
  async deleteZone(id) {
    works = works.filter(w => !(w.zone_id === id && w.status === 'done'));
    if (works.some(w => w.zone_id === id)) { const e = new Error('zone_has_open_works'); e.status = 409; throw e; }
    zones = zones.filter(x => x.id !== id); bump();
  },
  async addWork(w) { works.unshift(w); bump(); return w; },
  async updateWork(id, w) { const i = works.findIndex(x => x.id === id); if (i < 0) return null; works[i] = {...w, id}; bump(); return works[i]; },
  async deleteWork(id) { works = works.filter(w => w.id !== id); bump(); }
};
