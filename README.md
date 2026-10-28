# SmartEstimate AI

Platformë për preventivimin e punimeve të ndërtimit dhe instalimeve fotovoltaike. Ndërfaqja është në shqip. React/TypeScript komunikon me FastAPI; PostgreSQL ruan çmimet, projektet, vendimet e përputhjes dhe versionet e preventivave. Excel përpunohet në server me `openpyxl`; makrot nuk ekzekutohen.

## Nisja me Docker

Kërkohen Docker Engine dhe Docker Compose v2. Kopjoni konfigurimin pa e futur në Git:

```bash
cp .env.example .env
# Gjeneroni një fjalëkalim të ri dhe vendoseni te DB_PASSWORD në .env:
openssl rand -hex 32
docker compose up -d --build
docker compose ps
curl --fail http://localhost:8080/api/ready
```

Hapni `http://localhost:8080` dhe regjistroni llogarinë tuaj. Nuk ka përdorues, fjalëkalime ose çmime tregu të paracaktuara. Në prodhim përdorni HTTPS dhe `COOKIE_SECURE=true`; shihni [udhëzuesin e vendosjes](docs/deployment.md). `docker compose down` ndalon shërbimet pa fshirë të dhënat; **mos përdorni `down -v`** për një instalim që përmban të dhëna reale.

## Përdorimi

1. Regjistrohuni dhe shtoni artikuj në databazën e çmimeve. Përcaktoni nëse çmimi përfshin furnizimin, instalimin dhe TVSH-në; çmimi i blerjes nuk barazohet me çmimin e punës së instaluar.
2. Te cilësimet vendosni kurset e nevojshme `EUR:ALL` ose `ALL:EUR`. Sistemi nuk merr një kurs të supozuar dhe nuk bashkon monedha pa konvertim të përcaktuar.
3. Krijoni një projekt. Ngarkoni `.xlsx` ose `.xlsm`, zgjidhni fletën, shikoni pamjen paraprake dhe korrigjoni hartëzimin e kolonave. Origjinali ruhet pa ndryshime. `.xls` nuk mbështetet.
4. Ekzekutoni përputhjen dhe shqyrtoni sugjerimet, njësitë, dallimet teknike dhe kandidatët alternativë. Kandidati me përqindjen më të lartë miratohet automatikisht edhe me besim të ulët; përqindja dhe paralajmërimet mbeten të dukshme. Pa kandidatë, rreshti mbetet pa miratim me “No match found”. Kur konvertimi i njësisë ose monedhës mungon, përputhja miratohet por çmimi mbetet i papërcaktuar dhe totali i paplotë.
5. Miratoni rreshtat, kontrolloni përllogaritjet dhe finalizoni me konfirmim. Çmimet ruhen si fotografi e përzgjedhjes; ndryshimi i databazës nuk ndryshon fshehurazi preventivin.
6. Eksportoni preventivin standard ose një kopje të plotësuar të shabllonit fillestar. Për shabllone komplekse ruajtja e çdo elementi vizual nuk garantohet; kontrolloni skedarin përfundimtar në Excel.

## Importi në bazën e çmimeve

Butoni **Baza e çmimeve → Importo** pranon `.xlsx`, `.xlsm` dhe `.xls` binar përmes `xlrd` (makrot nuk ekzekutohen). Para ruajtjes shfaqen fletët, titujt, hartëzimi dhe gabimet sipas numrit origjinal të rreshtit. Zgjidhet fleta e parë, pavarësisht emrit dhe fletës aktive. Titujt kërkohen në 50 rreshtat e parë; shkronjat e mëdha/vogla, hapësirat, thekset, nënvizat dhe emërtimet e zakonshme shqip/anglisht normalizohen. Për tituj të pazakontë, zgjidhni rreshtin dhe kolonat manualisht, pastaj **Rikontrollo importin**.

Kërkohen njësia, çmimi real dhe të paktën emërtimi ose përshkrimi. Përshkrimi/emërtimi plotësohen nga njëri-tjetri; kodi që mungon gjenerohet nga prefiksi i dukshëm dhe rreshti i Excel-it. Zgjidhni shprehimisht ALL ose EUR kur monedha nuk është në skedar; kjo nuk kryen konvertim valutor. BOQ pa çmime ngarkohen te **Importo preventivin** për vlerësim në projekt, jo si katalog çmimesh. Importi i BOQ-ve në projekt vazhdon të pranojë `.xlsx`/`.xlsm`.

Çmimet e papranueshme, negative, jo të fundme, me më shumë se gjashtë shifra dhjetore ose kodet e dyfishuara bllokojnë ruajtjen e gjithë importit. Nuk ruhet fshehurazi vetëm nëngrupi i vlefshëm. Ndarësit e përzier pranojnë formatet `1.234,56` dhe `1,234.56`; një ndarës i vetëm trajtohet si dhjetor. Tekste të paqarta si `1,234` tregojnë paralajmërim dhe vlerën e saktë të interpretuar për konfirmim. Qelizat numerike të Excel-it nuk kërkojnë hamendësim ndarësish. Gabimet e formulave ose mungesa e një vlere të ruajtur në cache duhet të korrigjohen në Excel; sistemi nuk ekzekuton formula ose makro.

**Konfirmo importin** ruan në mënyrë atomike vetëm pamjen paraprake të kontrolluar. Pamjet paraprake janë private për llogarinë, skadojnë pas 30 minutash dhe nuk mbishkruajnë çmime ekzistuese. Endpoint-i i vjetër `/api/prices/import` mbetet për klientët ekzistues; ndërfaqja përdor `/preview` dhe `/commit`. Formati i eksportit nuk ndryshon. Docker zbaton migrimin e ri automatikisht gjatë nisjes; lokalisht ekzekutoni `alembic upgrade head` përpara nisjes së backend-it.

## Struktura

```text
backend/
  app/                 API, autentikim, modele dhe shërbime
    services/          Excel, përputhje, njësi dhe llogaritje
  alembic/             migrimet e skemës
  tests/               teste pytest
frontend/
  src/                 ndërfaqja React/TypeScript
compose.yaml           PostgreSQL + backend + frontend
scripts/               kopje rezervë dhe rikthim
docs/                  zhvillim, vendosje dhe siguri
```

## Zhvillimi dhe testet

[Udhëzuesi i zhvillimit](docs/development.md) shpjegon instalimin lokal, migrimet dhe testet. Komandat bazë:

```bash
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r backend/requirements.lock
cd backend
DATABASE_URL=sqlite:///./test-local.db ../.venv/bin/python -m pytest -q
cd ../frontend
npm ci
npm test -- --run
npm run build
```

SQLite shërben për testet e izoluara; në zhvillim dhe prodhim përdorni PostgreSQL me pgvector. Verifikimi me PostgreSQL dhe migrimet kërkohet veçmas nga testet SQLite. Rezultatet e ekzekutimit në mjedisin e zhvillimit raportohen nga procesi i ndërtimit; ky dokument nuk pretendon një vendosje cloud të verifikuar.

## Llogaritjet dhe përputhja

Shumat llogariten me `Decimal`, me rrumbullakim `ROUND_HALF_UP` në dy shifra për rresht dhe shtesë. Rendi është: rreshtat e miratuar → shpenzime të përgjithshme → fitim → zbritje → tarifa të tjera → TVSH. `direct` llogarit shpenzimet e përgjithshme dhe fitimin mbi nëntotalin; `subtotal` llogarit fitimin mbi nëntotalin plus shpenzimet e përgjithshme. Baza në të dy mënyrat përbëhet nga çmimet neto të zgjedhura dhe miratuara; emri teknik `direct` nuk nënkupton që çdo çmim i zgjedhur është kosto direkte. Kontrolloni llojin e çdo çmimi (blerje, kosto direkte, punim i instaluar ose shitje) përpara shtesave. Fitimi është përqindje shtese mbi bazën (**markup**), jo marzh bruto. Çmimet për njësi të konvertuara ruhen me gjashtë shifra dhjetore; vlera e parrumbullakuar dhe rregulli ruhen në fotografinë e çmimit. Importi refuzon sasi ose çmime me më shumë se gjashtë shifra dhjetore domethënëse për të shmangur ndryshime të heshtura. Kostoja e burimeve shpjegon çmimin dhe nuk i shtohet sërish çmimit përfundimtar. Rreshtat e pamiratuar ose pa çmim e shënojnë rezultatin të paplotë.

Përputhja përdor kodin, normalizimin e tekstit, sinonimet teknike, ngjashmërinë semantike dhe, kur konfigurohet, krahasimin me model gjuhësor. Rezultati është sugjerim me besueshmëri relative, jo garanci teknike. Diferencat e betonit, kapacitetit, përmasave, furnizimit, instalimit dhe njësive kërkojnë shqyrtim.

Konfigurimi AI është vetëm në backend: `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, `EMBEDDING_MODEL`. Pa AI vazhdojnë përputhja me kod/tekst, kërkimi manual dhe llogaritjet. Shihni [sigurinë dhe privatësinë](docs/security.md) për të dhënat që dërgohen te ofruesi.

## Teknologjitë dhe operimi

Python 3.12; FastAPI 0.162.0; SQLAlchemy 2.0.40; Alembic 1.15.2; psycopg 3.2.6; openpyxl 3.1.5; xlrd 2.0.2 për çmime `.xls`; pgvector Python 0.4.1; PostgreSQL 16 me zgjerimin pgvector. Varësitë kryesore Python janë deklaruar në `backend/requirements.txt`; të gjitha varësitë transitore dhe hash-et fiksohen në `backend/requirements.lock`; versionet e frontend-it fiksohen nga `frontend/package-lock.json`. Imazhet bazë në Dockerfile përdorin versione konkrete; për një proces publikimi të kontrolluar regjistroni edhe digest-in e çdo imazhi të ndërtuar dhe të databazës.

- [Zhvillimi lokal](docs/development.md)
- [Vendosja në cloud](docs/deployment.md)
- [Kopjet rezervë dhe rikthimi](docs/backup-restore.md)
- [Siguria, AI dhe kufizimet](docs/security.md)

Përpara përdorimit me kontrata reale: testoni shabllonet tuaja, konfirmoni çmimet/kurset, bëni një provë rikthimi dhe kryeni shqyrtim të pavarur të sigurisë dhe të rezultateve inxhinierike.
