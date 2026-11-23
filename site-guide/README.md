# Site guide

A phone web app for one industrial site: live GPS position on a satellite map, voice turn-by-turn directions between units, and work orders that a supervisor assigns and workers see.

No site data lives in this folder. The map bounds, units (zones), internal roads and work orders are stored in PostgreSQL and served only after login.

## Run

```
npm install
DATABASE_URL=postgres://... WORKER_CODE=... SUPERVISOR_PASSWORD=... SESSION_SECRET=... npm start
```

Without `DATABASE_URL` the server keeps data in memory (for local development); `SEED_FILE` can point to a JSON file with `config`, `zones`, `roads`, `features`.

## Roles

- Worker code: read-only map, GPS, directions and work orders.
- Supervisor password: also adds, renames, redraws and deletes units, and manages work orders.

Satellite imagery: Esri World Imagery (attribution shown in the app). For production use, an ArcGIS Location Platform account is recommended.
