# Vendosja në cloud

Ky udhëzim përdor një VM Ubuntu 24.04 LTS në Hetzner Cloud; e njëjta strukturë vlen për një VM AWS Lightsail ose DigitalOcean. Është udhëzim vendosjeje, jo dëshmi që një vendosje publike është kryer. Filloni me 2 vCPU, 4 GB RAM dhe disk SSD; dimensiononi sipas madhësisë së Excel-eve dhe përdoruesve. Nuk ofrohet disponueshmëri e lartë nga konfigurimi me një VM.

## Përgatitja

1. Krijoni VM-në, përdorni çelës SSH dhe kufizoni SSH-në sipas IP-së administrative. Lejoni vetëm portat 80/443 për publikun. Mbani 5432/8000/8080 pa akses publik.
2. Instaloni Docker Engine dhe plugin-in Compose nga [depoja zyrtare e Docker për Ubuntu](https://docs.docker.com/engine/install/ubuntu/), me verifikimin e nënshkrimit të paketave. Mos çaktivizoni TLS ose kontrollet e nënshkrimeve.
3. Krijoni përdorues për vendosjen dhe klononi repository-n në një dosje me akses të kufizuar. Anëtarësimi në grupin `docker` jep praktikisht privilegje administratori; kufizojeni.
4. Kopjoni `.env.example` në `.env`, `chmod 600 .env`, vendosni `DB_PASSWORD` të rastësishëm, `COOKIE_SECURE=true` dhe `CORS_ORIGINS=https://estimate.example.com`. Mbani `HTTP_BIND=127.0.0.1`.
5. Vendosni DNS-në e domenit te IP-ja e VM-së. Çelësat AI janë opsionalë; ruajini në secret manager ose në `.env` të mbrojtur. Mos i futni në Git ose në build argumente të frontend-it.

```bash
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8080/api/ready
```

## HTTPS

Instaloni Caddy duke ndjekur [udhëzimin zyrtar për paketat](https://caddyserver.com/docs/install#debian-ubuntu-raspbian), ose përdorni proxy-n TLS të ofruesit cloud. Caddyfile në host:

```caddyfile
estimate.example.com {
    encode gzip
    reverse_proxy 127.0.0.1:8080
}
```

Verifikoni konfigurimin me `caddy validate --config /etc/caddy/Caddyfile`, rinisni shërbimin dhe provoni regjistrimin, hyrjen, importin dhe eksportin në domenin HTTPS. Mos përdorni `COOKIE_SECURE=false` si zgjidhje për një proxy të konfiguruar gabim. Certifikata duhet të rinovohet automatikisht dhe portat 80/443 duhet të jenë të arritshme për lëshimin e saj.

## Kontrolli para hapjes

- Krijoni llogari prove dhe konfirmoni se një llogari tjetër nuk mund të lexojë projektet ose çmimet e saj.
- Verifikoni që cookies kanë `HttpOnly`, `SameSite=Strict` dhe `Secure` në HTTPS.
- Importoni një BOQ të përfaqësueshëm, kontrolloni të paktën një përputhje të papajtueshme dhe një pa çmim, finalizoni një preventiv dhe hapni të dy eksportet në Excel.
- Konfirmoni se mungesa e AI nuk pengon kërkimin, përputhjen me kod dhe llogaritjet manuale.
- Ekzekutoni [provën e rikthimit](backup-restore.md) në një instalim të veçantë. Konfiguroni monitorim dhe njoftime për hapësirën e diskut, `/api/ready`, dështimet e backup-it dhe skadimin e certifikatave.

## Përditësimet

Planifikoni dritare mirëmbajtjeje. Ruani tag-un/commit-in dhe digest-et e imazheve aktuale; merrni backup të databazës dhe skedarëve. Testoni commit-in e ri dhe migrimet në staging. Në server:

```bash
git fetch origin
# Zgjidhni një tag/commit të shqyrtuar, jo një ndryshim të paprovuar.
git checkout RELEASE_TAG
docker compose build
docker compose up -d
curl --fail http://127.0.0.1:8080/api/ready
docker compose logs --tail=100 backend
```

Nisja e backend-it zbaton migrimet. Për një instalim me shumë replika përdorni një job migrimi të vetëm para nisjes, jo migrime konkurruese në secilën replikë. Rikthimi vetëm i imazhit nuk rikthen skemën: përdorni migrim të verifikuar rikthimi ose backup-in e provuar.

`pgvector/pgvector:pg16` ndjek linjën PostgreSQL 16. Para një publikimi regjistroni dhe fiksoni digest-in e imazhit të testuar; mos kaloni në PostgreSQL 17/18 duke ripërdorur të njëjtin volum pa procedurën e migrimit. Ndryshimi i `DB_PASSWORD` në `.env` nuk ndryshon automatikisht fjalëkalimin në një volum PostgreSQL ekzistues; bëni rotacion në databazë dhe përditësoni konfigurimin në të njëjtën dritare mirëmbajtjeje.

Mbani kopje rezervë jashtë VM-së. Mos përdorni logim të trupave të kërkesave, kredencialeve ose përmbajtjes së dokumenteve. Për shumë punëtorë API, limiter-i në memorien e procesit duhet plotësuar me kufizim të përbashkët në proxy/Redis. Para ekspozimit publik të regjistrimit përdorni mbrojtje kundër abuzimit në proxy dhe politikë operacionale për llogaritë.
