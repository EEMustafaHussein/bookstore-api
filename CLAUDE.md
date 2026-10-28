# bookstore-api

Two projects live here:
- the original Bookstore API (root `app/`, `main.py`)
- **«ملابس الأحلام»** women's clothing store in `dreams-store/` (FastAPI + SQLModel, Arabic RTL pages). Its README is in Arabic.

The owner writes in Iraqi Arabic; answer in Arabic. Store text for customers addresses women; dashboard text stays neutral.

## Working on dreams-store
- Run tests from `dreams-store/`: `pip install -r requirements-dev.txt && pytest`
- Same suite on PostgreSQL: `TEST_DATABASE_URL=postgresql://... pytest`
- Local run: copy `.env.example` to `.env`, then `uvicorn app.main:app --reload`

## Deploying dreams-store for free (Render + Neon)
The owner asked for a free public deployment. Use the Render and Neon connectors when they are connected:

1. **Neon**: create a project named `dreams-store` in AWS Europe Central 1 (Frankfurt) and take its connection string (`postgresql://...?sslmode=require`; pooled is fine).
2. **Render**: create a web service from `EEMustafaHussein/bookstore-api`, branch `claude/compassionate-pasteur-qbubqj` (or `main` once merged), same settings as `render.yaml`:
   - runtime python, plan **free**, region frankfurt, root directory `dreams-store`
   - build `pip install -r requirements.txt`
   - start `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`
   - env: `PYTHON_VERSION=3.13.5`, `SECRET_KEY` (random, 48+ chars), `DATABASE_URL` (Neon link), `MEDIA_STORAGE=database`, `COOKIE_SECURE=true`, `PAYMENT_DEMO_MODE=false`, `OWNER_EMAIL`, `OWNER_PASSWORD`, `OWNER_NAME`
3. Ask the owner for the email to use. Generate a strong temporary password, give it to them once, and tell them to change it at `/account` after the first login.
4. Check the deploy logs, then that `/`, `/robots.txt` and `/sitemap.xml` answer on the public URL. The app refuses to start on Render without `DATABASE_URL` (by design).
5. Give the owner the public URL and the Google Search Console steps from `dreams-store/README.md` (paste the HTML tag in dashboard → إعدادات المتجر, then submit `sitemap.xml`).

Render needs access to the GitHub repo (the owner signs in to Render with GitHub). Never print the Neon connection string or passwords into the repo.
