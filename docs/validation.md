# Evidenca e verifikimit

Në mjedisin e zhvillimit u provua një instalim Docker Compose i izoluar me PostgreSQL 16/pgvector, backend Python dhe frontend Nginx. Ky verifikim lokal nuk është vendosje cloud publike ose provë e një modeli AI real.

## Prova funksionale në Docker

Përmes Nginx dhe API-së HTTP u kryen me sukses:

- Regjistrimi dhe krijimi i sesionit me cookie.
- Krijimi i një çmimi EUR dhe projekti të ri.
- Ngarkimi i një workbook-u Excel real me shkronja shqipe, zgjedhja e fletës dhe hartëzimi i kolonave.
- Importi i një rreshti dhe përputhja sipas kodit; çmimi mbeti i pacaktuar deri në miratimin njerëzor.
- Miratimi, llogaritja financiare dhe finalizimi. Rasti i kontrolluar: sasi 10 × 25.50 EUR = 255.00 EUR; shpenzime të përgjithshme 10%, fitim 5% mbi bazën direkte, TVSH 20% → total 351.90 EUR.
- Shkarkimi dhe rihapja me openpyxl e të dy eksporteve `.xlsx`: standard dhe shablloni origjinal.
- `/api/ready` dha HTTP 200 nga jashtë konteinerit përmes Nginx.

## Backup dhe rikthim

Script-et `scripts/backup.sh` dhe `scripts/restore.sh` u ekzekutuan mbi instalimin e izoluar me të dhëna prove. U verifikuan checksum-et e dump-it dhe arkivit. Një projekt sentinel u krijua pas backup-it; pas rikthimit numri i sentinelëve ishte zero dhe gatishmëria e API-së u rikthye në HTTP 200. Kjo provë nuk zëvendëson provën periodike me kopjet dhe storage-in e instalimit të prodhimit.

## Ndërtimi dhe konfigurimi

- Ndërtimi i imazhit backend kaloi me instalim nga `requirements.lock` dhe verifikim të hash-eve; importimi i aplikacionit kaloi.
- Ndërtimi i imazhit frontend kaloi me TypeScript/Vite 6.4.5; `npm ci` raportoi zero cenueshmëri.
- `docker compose config --quiet` kaloi.
- `bash -n scripts/backup.sh scripts/restore.sh` kaloi.
- Backend-i në konteiner ekzekutohet si UID 10001 dhe volumi i ngarkimeve është i shkrueshëm nga ky përdorues.
- Të tre shërbimet Docker arritën gjendjen `healthy`; pas verifikimit instalimi i izoluar i provës u ndal duke ruajtur volumet.
- Pas zhvendosjes së dosjes së backup-it, rikthimi kaloi sërish me checksum-e relative të vlefshme.

Rrjeti i këtij mjedisi kërkoi proxy dhe CA të besuar gjatë build-it. U përdorën argumentet standarde të proxy-t dhe një sekret BuildKit CA; verifikimi TLS nuk u çaktivizua. Probe-t lokale të shëndetit anashkalojnë proxy-n për adresat loopback.

Rezultatet e suitave pytest/Vitest dhe kontrollet e migrimeve raportohen veçmas gjatë implementimit. Verifikimi i modelit AI me çelës real, vendosja HTTPS në një ofrues cloud dhe kontrolli i eksportit në Microsoft Excel desktop mbeten përgjegjësi e validimit në instalimin përfundimtar.
