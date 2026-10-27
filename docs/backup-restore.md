# Kopjet rezervë dhe rikthimi

Databaza PostgreSQL dhe volumi i skedarëve Excel janë dy pjesë të së njëjtës kopje. Backup vetëm i databazës nuk ruan shabllonet origjinale; backup vetëm i volumeve aktive nuk zëvendëson një dump të qëndrueshëm të PostgreSQL.

## Marrja e kopjes

Ruani në mënyrë të veçantë konfigurimin `.env` në një secret manager; script-et nuk e kopjojnë atë. Nga rrënja e projektit:

```bash
# Dritare mirëmbajtjeje: ndaloni hyrjen publike dhe të gjitha shkrimet.
docker compose stop frontend
scripts/backup.sh backups/2026-10-27-before-upgrade
docker compose start frontend
```

Script-i krijon një dosje të re me leje të kufizuara, `database.dump` në formatin custom të PostgreSQL, `uploads.tar.gz` dhe `SHA256SUMS`. Ai nuk mbishkruan një dosje ekzistuese. Backend/db duhet të jenë në punë. Ndalimi i frontend-it është i mjaftueshëm vetëm kur nuk ka hyrje tjetër, automatizime ose klientë direkt në API. Ndryshe ndaloni shkrimet nga të gjitha burimet para backup-it. `pg_dump` është konsistent brenda databazës; qëndrueshmëria ndërmjet dump-it dhe skedarëve kërkon këtë dritare pa shkrime.

Dështimi i komandës duhet të nxisë alarm; mos trajtoni si backup një dosje të krijuar pjesërisht. Kopjojeni paketën në ruajtje të jashtme të enkriptuar (p.sh. objekt storage me versionim). Mos ruani çelësin e dekriptimit vetëm në të njëjtën VM. Për të dhëna reale përcaktoni një politikë ruajtjeje dhe fshirjeje sipas kontratave. Një shembull operimi është kopje ditore, ruajtje 30 ditë dhe provë rikthimi mujore; këto janë objektiva për t'u përshtatur, jo veçori të automatizuara nga repository.

## Rikthimi

**Komanda zëvendëson databazën e synuar.** Provoni fillimisht në një instalim të veçantë, me volume të reja, të njëjtin version madhor PostgreSQL dhe versionin e përshtatshëm të aplikacionit. Merrni backup të gjendjes ekzistuese para se ta zëvendësoni.

```bash
docker compose stop frontend
scripts/restore.sh backups/2026-10-27-before-upgrade --confirm-replace-database
# Rinisni pool-in e lidhjeve dhe aplikoni vetëm migrimet e versionit të synuar:
docker compose restart backend
curl --fail http://127.0.0.1:8080/api/ready
# Vetëm pasi verifikimet të kenë kaluar:
docker compose start frontend
```

Backend dhe db duhet të jenë nisur në instalimin e synuar. Skripti verifikon checksum-et, përdor `pg_restore --single-transaction --clean --if-exists` dhe rikthen skedarët. Riktheni vetëm backup-e të besuara; arkivat dhe SQL-ja përmbajnë të dhëna të kontrolluara nga krijuesi i tyre. Rikthimi i skedarëve nuk fshin skedarët shtesë në volumin ekzistues; për një rikthim të pastër përdorni volum të ri në instalimin e provës. Mos fshini volumin ekzistues pa kopje të verifikuar.

Pas rikthimit kontrolloni:

1. `/api/ready` dhe versionin Alembic (`docker compose exec backend alembic current`).
2. Hyrjen me një llogari të njohur dhe izolimin ndërmjet llogarive.
3. Numrin e projekteve, çmimeve, versionet e preventivave dhe totalet e një kampioni të njohur.
4. Shkarkimin e shabllonit origjinal dhe eksportimin e një preventivi të finalizuar.
5. Miratimet, historikun dhe lidhjet me skedarët.

Dokumentoni kohën e rikthimit dhe humbjen maksimale të mundshme të të dhënave. Rikthimi është i verifikuar vetëm pasi këto prova të përfundojnë; ekzistenca e skedarit backup nuk është provë e rikuperimit.
