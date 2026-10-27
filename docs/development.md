# Zhvillimi lokal

## Parakushtet

Përdorni Python 3.12, Node.js 22 LTS dhe PostgreSQL 16 me pgvector. Rekomandohet që databaza të nisë me Compose, ndërsa backend dhe frontend të nisen lokalisht për rifreskim gjatë punës. Mos krijoni Git worktree vetëm për instalim; përdorni checkout-in ekzistues të mjedisit të izoluar.

## Varianti i plotë me Docker

Nga rrënja e projektit:

```bash
cp .env.example .env
# Redaktoni DB_PASSWORD; mos publikoni skedarin .env.
docker compose up -d --build
docker compose logs --tail=100 backend
curl --fail http://localhost:8080/api/health
curl --fail http://localhost:8080/api/ready
```

`/api/health` kontrollon procesin; `/api/ready` kontrollon gatishmërinë e databazës. Hyrja e backend-it aplikon migrimet para nisjes së Uvicorn. PostgreSQL nuk ekspozohet publikisht. Volumet `postgres_data` dhe `uploads` ruhen ndërmjet rinisjeve; sesionet janë në databazë.

## Backend jashtë Docker

Krijoni një databazë dhe përdorues lokal, pastaj vendosni URL-në përkatëse në `.env`. Për PostgreSQL-in e Compose mund të shtoni përkohësisht një override lokal që ekspozon vetëm `127.0.0.1:5432:5432`; mos ekspozoni portën në internet. Nisni vetëm databazën me `docker compose up -d db`.

```bash
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r backend/requirements.lock
# Vendosni DATABASE_URL/STORAGE_DIR/CORS_ORIGINS në backend/.env
# ose eksportojini nga konfigurimi juaj lokal pa i printuar.
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Skedari `.env` lexohet nga dosja aktuale e backend-it. URL shembull: `postgresql+psycopg://USER:PASSWORD@localhost:5432/smartestimate`. Kodoni karakteret e veçanta të fjalëkalimit në URL. Mos përdorni shembullin si kredencial prodhimi. `STORAGE_DIR` duhet të jetë dosje e shkrueshme vetëm për procesin e aplikacionit. `COOKIE_SECURE=false` lejohet vetëm për HTTP lokal.

## Frontend

Në terminal tjetër:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Vite përcjell `/api` te backend-i në portën 8000. Nuk nevojiten çelësa API në frontend. Pas ndryshimeve:

```bash
cd backend
DATABASE_URL=sqlite:///./test-local.db ../.venv/bin/python -m pytest -q
cd ../frontend
npm test -- --run
npm run build
```

Testet e AI përdorin përgjigje të kontrolluara dhe nuk kërkojnë pagesë te një ofrues real. Ato nuk provojnë saktësi inxhinierike në dokumente të paparë. Për migrimet dhe operatorët vektorialë, përsëritni testet përkatëse me një databazë PostgreSQL të dedikuar testimi; mos përdorni databazën e prodhimit.

## Migrimet

```bash
cd backend
../.venv/bin/alembic current
../.venv/bin/alembic upgrade head
```

Krijoni migrim të ri për çdo ndryshim të skemës. Mos ndryshoni migrimet që janë zbatuar tashmë në prodhim. Para çdo migrimi merrni kopje rezervë dhe provoni migrimin në një kopje të databazës. Mos përdorni `create_all` si zëvendësim të historikut Alembic në prodhim.

## Proxy korporativ gjatë ndërtimit

Në rrjete që kërkojnë proxy HTTPS, përcillni konfigurimin ekzistues përmes argumenteve të posaçme të Docker-it; mos shkruani kredenciale në Dockerfile. Dockerfile-et mbështesin opsionalisht sekretin BuildKit `build_ca` me një bundle CA të besuar:

```bash
docker build --build-arg HTTP_PROXY --build-arg HTTPS_PROXY \
  --secret id=build_ca,src=/path/to/trusted-ca-bundle.pem \
  -t smartestimate-backend:local backend
docker build --build-arg HTTP_PROXY --build-arg HTTPS_PROXY \
  --secret id=build_ca,src=/path/to/trusted-ca-bundle.pem \
  -t smartestimate-frontend:local frontend
```

Dockerfile përdor bundle-in vetëm gjatë instalimit dhe nuk e kopjon në imazh. DNS/emri i proxy-t duhet të jetë i arritshëm nga motori Docker. Nëse proxy-t i duhet një lidhje e përcaktuar host/IP, përdorni `--add-host` me vlerën e ofruar nga administratori. Mos përdorni `--trusted-host`, `strict-ssl=false` ose `verify=False` për të anashkaluar verifikimin. Një CA shtesë për trafikun e runtime-it është konfigurim i veçantë i operatorit, jo efekt i sekretit të build-it.

## Prova e shfletuesit

Me backend-in dhe Vite të nisur, databazën e migruar dhe pa AI aktiv:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

Testi krijon një përdorues dhe të dhëna prove; ekzekutojeni vetëm mbi databazë zhvillimi/testimi. Ai kryen regjistrim, katalog, projekt, ngarkim/hartëzim Excel, miratim njerëzor, finalizim dhe shkarkim, si dhe kontroll të navigimit në tablet. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` mund të tregojë Chromium-in e instaluar. CI nis shërbimet përmes `scripts/test-browser.sh`; për përdorim lokal aktivizoni mjedisin Python para këtij skripti dhe lini portat 8000/5173 të lira.
