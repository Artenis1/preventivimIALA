# Skedarë për testimin e importit të çmimeve

Këta skedarë përmbajnë të dhëna artificiale vetëm për testim. Nuk janë oferta, çmime tregu ose supozime për projekte reale.

- `canonical_first_sheet.xlsx`: kolona angleze me shkronja të mëdha; fleta aktive është e dyta, ndërsa katalogu është fleta e parë.
- `albanian_merged_title.xlsx`: titull i bashkuar, rresht bosh, tituj shqip me thekse/BOM/hapësira Unicode dhe çmime me presje dhjetore.
- `english_reordered.xlsx`: renditje tjetër kolonash dhe kolonë shtesë e furnitorit.
- `ambiguous_prices.xlsx`: dy kolona të njohura si çmim; kërkohet hartëzim manual.
- `legacy_albanian.xls`: skedar binar real BIFF8/OLE, me titull të bashkuar dhe dy fletë. U gjenerua një herë me `xlwt==1.3.0`; `xlwt` nuk nevojitet për aplikacionin ose ekzekutimin e testeve. Leximi përdor `xlrd==2.0.2` pa ekzekutim makrosh.
