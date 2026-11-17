# Otthonápolási szerződéskezelő v0.1.1

Magyar nyelvű, offline Windows asztali alkalmazás a szkennelt otthonápolási IX/1–IX/3 mellékletek feldolgozására. A dokumentumok és az OCR-szövegek nem kerülnek külső szolgáltatásba.

## Használat

A Windows-kiadás teljes ZIP-jét bontsd ki írható helyre, és indítsd az `OtthonapolasiSzerzodeskezelo.exe` fájlt. Ne csak az EXE-t másold ki: az `_internal` könyvtár is szükséges. Nincs szükség Python vagy OCR telepítésére. Első indításkor válassz szerződésmappát; lehet meghajtóbetűjeles vagy UNC-útvonal is.

A **Szkennelések feldolgozása** oldalon adj hozzá több PDF-et, MSG-t vagy EML-t. A valódi fájlok és a klasszikus Windows Outlook virtuális PDF-mellékletei, valamint teljes e-mailjei is behúzhatók. Több e-mailből automatikusan kiemeli a PDF-mellékleteket, és a meglévő várólistához adja őket. A felismerés sorban, háttérszálon fut, minden szükséges oldalt megvizsgál. Ellenőrizd a NEAK-kódot, nevet, rövid nevet, mellékletet és a hatályosságot, majd jelöld az ellenőrzést és válaszd a mentést. A rövid nevek a Beállítások / Szolgáltatói törzsadatok menüben szerkeszthetők, és sikeres mentéskor is megjegyzi őket a program.

A mentés másolatot készít, a forrást megőrzi. Névütközéskor másik fájlnevet kell megadni vagy kihagyni a dokumentumot; felülírás nincs. A nyilvántartásban ismert azonos tartalomra figyelmeztet. Hibás hálózati mentés után a tétel nem lesz kész, és újrapróbálható. Az SHA-256 ellenőrzés a másolat integritását is vizsgálja.

A **Szerződések tallózása** oldalon a mappa PDF-jei rekurzívan listázhatók, kereshetők, mellékletre és ePénz-állapotra szűrhetők. A fejléc kattintásával rendezhetők. A fel nem ismert fájlnevek is láthatók. Az állapotot mindig a kijelölt fájlhoz menti; a feltöltés időpontját rögzíti. Ez helyi nyilvántartás, tényleges ePénz-feltöltés nem történik.

Az adatbázis a felhasználó helyi alkalmazásadat-könyvtárában van (`QStandardPaths.AppLocalDataLocation`), nem a hálózati szerződésmappában. Tartalmaz privát metaadatokat: kezeld ennek megfelelően. A levélmellékletek ideiglenes könyvtárba kerülnek, normál kilépéskor törlődnek. Rendellenes leállás után ideiglenes fájlok maradhatnak. A források nem törlődnek.

## Fejlesztés és build

Python 3.10.11 x64 ajánlott. Meglévő checkoutot használj; felhőfeladathoz nem szükséges külön Git worktree.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate; Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python run.py
```

Forrásból futtatáshoz Tesseract 5 és `hun`, `eng` nyelvi adatok szükségesek. A `TESSDATA_PREFIX` támogatott. Az alkalmazás induláskor maximált, a panelarányokat és az utolsó nézetet megjegyzi.

Windows PowerShell: `./scripts/build-windows.ps1`. A szkript ellenőrzött SHA-256 alapján letölti az OCR telepítőjét, helyi ideiglenes könyvtárba bontja ki a telepítő futtatása nélkül, hozzáadja a magyar nyelvet, futtatja a teszteket, majd PyInstaller one-directory EXE-csomagot és ZIP-et készít. A csomagolt EXE saját szintetikus OCR/PDF/SQLite funkcionális tesztet futtat `--self-test` kapcsolóval. A GitHub Actions valódi Windows-runneren hajtja végre ugyanezt. `v0.1.1` tag push esetén a ZIP-et Release-hez csatolja.

## Korlátok és ellenőrzések

A Windows 10 1607 kompatibilitás **nem igazolt**, lásd [COMPATIBILITY](docs/COMPATIBILITY.md). A felhőben Linuxon végzett teszt nem Windows-elfogadási teszt. A klasszikus Outlook közvetlen behúzásához natív Windows OLE integráció készült; a tényleges Outlook-verzióval és Windows 10 1607-en végzendő ellenőrzések állapotát az [Outlook tesztjegyzőkönyv](docs/OUTLOOK.md) tartalmazza. Az Outlookot és az alkalmazást is normál jogosultsággal indítsd: eltérő integritási szinten a Windows a behúzást még az alkalmazás értesítése előtt letilthatja. A hosszú hálózati mappabeolvasás a felületet átmenetileg foglalhatja; az OCR háttérszálon fut. A duplikátumkeresés a korábban regisztrált másolatokra terjed ki; a tallózott teljes archívumot nem hash-eli automatikusan.

Privát mintákat, dokumentumokat, OCR-kimeneteket vagy helyi adatbázist tilos commitolni. Az automatizált tesztek szintetikusak. A specifikáció három név szerinti mintája nincs a feltöltött öt PDF között, ezért azokra dokumentumalapú elfogadás nem állítható.

Technológia: Qt 5/PyQt5 a régi Windows célplatform és a natív asztali felület miatt; PDFium a beépített rendereléshez; Tesseract a helyi magyar OCR-hez; SQLite a felhasználónkénti nyilvántartáshoz. Licencek: [THIRD_PARTY](docs/THIRD_PARTY.md).
