# Siguria, privatësia dhe kufizimet

## Kufijtë e të dhënave

Çdo përdorues ka databazën e vet të çmimeve dhe projektet e veta; endpoint-et kontrollojnë pronësinë në server. Ky model nuk përmban ende organizata me role të përbashkëta. Mos i ndani llogaritë. Sesionet përdorin token të rastësishëm në cookie `HttpOnly`; në databazë ruhet hash-i i token-it. Fjalëkalimet ruhen me Argon2. Cookies kanë `SameSite=Strict`; në prodhim kërkohet `Secure` dhe HTTPS. Origjinat e lejuara vendosen shprehimisht në `CORS_ORIGINS`.

Mos vendosni çelësa në frontend, Git, URL publike ose log-e. `.env.example` përmban vetëm shembuj. Kufizoni aksesin te `.env`, backup-et dhe volumi i ngarkimeve. Për prodhim rekomandohet secret manager i ofruesit cloud, kriptim në disk dhe në backup, rotacion kredencialesh dhe monitorim i aksesit.

## Excel

Pranohen `.xlsx` dhe `.xlsm` brenda kufijve të madhësisë. Skedarët trajtohen si të dhëna; makrot nuk ekzekutohen. Importi në bazën e çmimeve mbështet edhe `.xls` binar me `xlrd`, duke lexuar vetëm të dhënat e ruajtura. Importi i BOQ në projekte vazhdon të pranojë `.xlsx` dhe `.xlsm`. Emri i ngarkimit nuk përdoret si shteg ruajtjeje. Parser-i kontrollon strukturën ZIP dhe kufijtë e përpunimit. Eksporti i shabllonit del në `.xlsx` pa makro. Formulat, grafikët, kontrollet dhe lidhjet e veçanta të shablloneve komplekse mund të mos ruhen në mënyrë identike nga openpyxl.

Tekstet në eksport shkruhen si tekst për të kufizuar injektimin e formulave. Kjo nuk e bën çdo workbook origjinal të besuar: mos aktivizoni lidhje të jashtme ose përmbajtje aktive në Excel vetëm sepse skedari është eksportuar nga sistemi. Ruani origjinalet për auditim, me politikë fshirjeje dhe kontroll aksesi. Mos ngarkoni dokumente pa autorizimin e pronarit të të dhënave.

## Informacioni që dërgohet te AI

Me `AI_API_KEY`, `EMBEDDING_MODEL` dhe/ose `AI_MODEL` të konfiguruar, backend-i mund t'i dërgojë ofruesit të `AI_BASE_URL` përshkrimin e përzgjedhur të BOQ-së dhe tekstin e kandidatëve të databazës: kodin, emrin, sinonimet, specifikimet teknike, njësinë dhe shënimet për furnizimin/instalimin. Embedding-et përfaqësojnë semantikën e këtyre teksteve dhe duhen trajtuar si të dhëna biznesi. I gjithë workbook-u, fjalëkalimet, token-et e sesioneve dhe dokumenti binar nuk duhet t'i dërgohen modelit.

Zgjidhni ofrues me kushte ruajtjeje dhe përpunimi të përshtatshme për projektet tuaja. Merrni pëlqimin e nevojshëm para dërgimit të përshkrimeve konfidenciale jashtë organizatës. Për punë pa dërgim të jashtëm lini çelësin/modelin bosh ose përdorni një endpoint të vetëhostuar kompatibël. Mos ndryshoni `AI_BASE_URL` në destinacion të pabesuar. Mbani verifikimin TLS aktiv.

Teksti i dokumentit trajtohet si e dhënë, jo si udhëzim për të ndryshuar politika. Përgjigjja e modelit mund të dështojë ose të gabojë. Kandidati me rezultatin më të lartë miratohet automatikisht pavarësisht besimit; përqindja dhe dallimet teknike mbeten të dukshme për kontroll. Kontrasti ndërmjet llojeve të betonit, kapaciteteve, njësive dhe scope-it të punës kërkon shqyrtim njerëzor. Confidence nuk është probabilitet i garantuar i saktësisë.

## Kufizimet për prodhim

- Rate limiting në memorien e procesit nuk është i përbashkët ndërmjet replikave; për publikim me shumë replika shtoni mekanizëm të përbashkët në gateway/Redis.
- Sigurimi i email-it, rikuperimi i fjalëkalimit, MFA, SSO, organizatat dhe rolet e kompanisë kërkojnë punë të veçantë nëse duhen nga operatori.
- Embedding-et dhe vlerësimi i modelit duhet të provohen me terminologjinë dhe katalogun e organizatës suaj. Nuk ofrohet garanci inxhinierike nga ngjashmëria e tekstit.
- Ruajtja lokale e skedarëve në një volum të vetëm kërkon backup; për shumë replika përdorni një storage të përbashkët dhe politikë përkatëse të aksesit.
- Auditimi i aplikacionit është historik operacional në databazë, jo një regjistër kriptografik i pandryshueshëm. Operatorët me akses të plotë në databazë mund ta modifikojnë.
- Çmimet dhe normat tatimore nuk merren automatikisht nga burime zyrtare. Përdoruesi është përgjegjës për të dhënat, bazat e llogaritjes dhe miratimin profesional.

Përpara përdorimit real kryeni shqyrtim të pavarur të sigurisë, verifikim kontraktual të AI dhe provë rikthimi. Mos raportoni vendosjen, dërgimin real te AI ose rikthimin si të testuar nëse këto operacione nuk janë kryer në instalimin tuaj.
