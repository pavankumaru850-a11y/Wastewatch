# Deployment

## A. Local demo without Docker (Windows, SQLite) - simplest
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          (put a random 32+ char SECRET_KEY in it)
python -m app.seed              (DEV ONLY: prints admin / staff / citizen logins once)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Dashboard: `cd dashboard && npm install && npm run dev` (create `dashboard/.env` with `VITE_API_URL=http://localhost:8000`).
Mobile: `cd mobile && npm install && npx expo start`; copy `mobile/.env.example` to `.env` and set `EXPO_PUBLIC_API_URL`.
Swagger UI at http://localhost:8000/docs. Tests: `cd backend && python -m pytest tests`.

## B. Docker (PostgreSQL + API + dashboard)
```
cp .env.example .env            # set POSTGRES_PASSWORD, SECRET_KEY, PUBLIC_API_URL, CORS_ORIGINS
docker compose up --build
```
Dashboard http://localhost:8080, API http://localhost:8000/api/health. Data lives in the named volumes `pgdata` and `uploads`; trained models are read from `backend/models/` on the host.
Create the first admin (there is deliberately no default account in production):
```
docker compose exec -it backend python -m app.create_admin
```
(asks for email, name and password; the same command works without Docker from `backend/`).
Then create staff from the dashboard (Users & Staff).
Use a **fresh** PostgreSQL database for v2 (the migration helper adds columns, but enum value changes on an old PostgreSQL schema need manual `ALTER TYPE`). The trained model and its Ultralytics/PyTorch runtime are included in the backend requirements and Docker image; allow for the larger image and inference memory use.

> The Docker files were checked by parsing and by reproducing their steps (clean virtualenv from `requirements.txt`, production mode, PostgreSQL, `npm ci`), but **`docker compose up` itself was not run** in the environment where this was written. Run it once and report anything that fails.

## C. Making the phone reach the backend from any network
The app uses one setting, `EXPO_PUBLIC_API_URL`. It must be an **HTTPS** URL for a real deployment:
* Put the API behind a reverse proxy with a certificate (Caddy / nginx + Let's Encrypt) on a domain or a small VPS; set `PUBLIC_API_URL`, `CORS_ORIGINS` accordingly.
* For a quick demo, a tunnel (Cloudflare Tunnel, ngrok) gives an HTTPS URL; put it in `mobile/.env` and restart Expo. Tunnel URLs change, which is why nothing is hard-coded.
* Do not use `http://192.168.x.x:8000` outside the local network. Android release builds block plain HTTP by default.

## D. Production checklist
* `APP_ENV=production` (disables `/docs`, `/openapi.json`, refuses demo seeding and a weak `SECRET_KEY`).
* Strong `SECRET_KEY` and DB password, HTTPS everywhere, `CORS_ORIGINS` set to the dashboard origin only.
* Back up the database and the `uploads` volume. Uploaded photos may contain personal data (faces, number plates); define a retention policy.
* Reverse geocoding (`REVERSE_GEOCODING=true`) sends coordinates to OpenStreetMap Nominatim: mention it in your privacy notice, respect their usage policy, or self-host.
* The login rate limiter and geocoder cache are per process; run one worker or move them to Redis before scaling out.
* Rotate `SECRET_KEY` = everyone must log in again.
