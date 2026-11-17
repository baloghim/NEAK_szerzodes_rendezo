# Otthonápolási szerződéskezelő v0.1.3

Magyar nyelvű, offline Windows asztali alkalmazás a szkennelt otthonápolási IX/1–IX/3 mellékletek feldolgozására. A dokumentumok és az OCR-szövegek nem kerülnek külső szolgáltatásba.

## Használat

A Windows-kiadás teljes ZIP-jét bontsd ki írható helyre, és indítsd az `OtthonapolasiSzerzodeskezelo.exe` fájlt. Ne csak az EXE-t másold ki: az `_internal` könyvtár is szükséges. Nincs szükség Python vagy OCR telepítésére. Első indításkor a Beállítások ablakban válassz szerződésmappát; lehet meghajtóbetűjeles vagy UNC-útvonal is.

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

Windows PowerShell: `./scripts/build-windows.ps1`. A szkript ellenőrzött SHA-256 alapján letölti az OCR telepítőjét, helyi ideiglenes könyvtárba bontja ki a telepítő futtatása nélkül, hozzáadja a magyar nyelvet, futtatja a teszteket, majd PyInstaller one-directory EXE-csomagot és ZIP-et készít. A csomagolt EXE saját szintetikus OCR/PDF/SQLite funkcionális tesztet futtat `--self-test` kapcsolóval. A GitHub Actions valódi Windows-runneren hajtja végre ugyanezt. `v0.1.2` tag push esetén a ZIP-et Release-hez csatolja.

## Korlátok és ellenőrzések

A Windows 10 1607 kompatibilitás **nem igazolt**, lásd [COMPATIBILITY](docs/COMPATIBILITY.md). A felhőben Linuxon végzett teszt nem Windows-elfogadási teszt. A klasszikus Outlook közvetlen behúzásához natív Windows OLE integráció készült; a tényleges Outlook-verzióval és Windows 10 1607-en végzendő ellenőrzések állapotát az [Outlook tesztjegyzőkönyv](docs/OUTLOOK.md) tartalmazza. Az Outlookot és az alkalmazást is normál jogosultsággal indítsd: eltérő integritási szinten a Windows a behúzást még az alkalmazás értesítése előtt letilthatja. A hosszú hálózati mappabeolvasás a felületet átmenetileg foglalhatja; az OCR háttérszálon fut. A duplikátumkeresés a korábban regisztrált másolatokra terjed ki; a tallózott teljes archívumot nem hash-eli automatikusan.

Privát mintákat, dokumentumokat, OCR-kimeneteket vagy helyi adatbázist tilos commitolni. Az automatizált tesztek szintetikusak. A specifikáció három név szerinti mintája nincs a feltöltött öt PDF között, ezért azokra dokumentumalapú elfogadás nem állítható.

Technológia: Qt 5/PyQt5 a régi Windows célplatform és a natív asztali felület miatt; PDFium a beépített rendereléshez; Tesseract a helyi magyar OCR-hez; SQLite a felhasználónkénti nyilvántartáshoz. Licencek: [THIRD_PARTY](docs/THIRD_PARTY.md).


## v0.1.2 újdonságok

Az OCR a táblázatos és több sorba tördelt mezőket is értelmezi; oldalanként keresi a 0/90/180/270 fokos helyes tájolást. Az értelmezhető mezők alapján választ, nem a felismert szöveg hosszából. Megbízható, helyesen álló oldalon egy OCR elegendő. A hibás oldal mellett a többi oldal adatai kézzel javíthatók maradnak.

A betekintőben a **Forgatás balra/jobbra** mindig az aktuális oldalt módosítja. Feldolgozás közben a forrás változatlan: a **Forgatás mentése** jelzi, hogy a tájolást a végleges másolat mentése fogja rögzíteni. Szerződéstári PDF esetén külön felülírási megerősítés kell; a program ellenőrzött ideiglenes PDF-et készít és csak utána cseréli le az eredetit. A képtartalmat nem raszterizálja újra. A forgatások dokumentumonként, oldalanként megmaradnak az aktuális munkamenetben; a feldolgozás alatti beállítások csak a végleges másolattal kerülnek tartósan a PDF-be.

A célmappa csak a **Beállítások → Beállítások…** ablakban változtatható. Ugyanitt állítható az alapnézet, az OCR automatikus tájolásfelismerése és a felismert tájolás betekintőbeli alkalmazása. Ha ez utóbbi ki van kapcsolva, az automatikus ajánlás nem kerül sem a nézetbe, sem a végleges másolatba; a kézi forgatás továbbra is érvényes. A főoldalon az útvonal csak tájékoztató, teljes tartalma tooltipben látszik. Minden beállítás a meglévő felhasználói SQLite-adatbázisban tárolódik.

Felismerés alatt kék, félkövér, finoman pulzáló **Feldolgozás** állapot látható; utána Felismerve / Ellenőrizendő / Feldolgozási hiba. A teljes fül- és panelcímekhez a méretezés javult; keskeny betekintőben az eszköztár nyílmenüje kínálja a további műveleteket. Tesztek és korlátok: [v0.1.2 jegyzőkönyv](docs/V012.md).


## v0.1.3 funkcionális frissítés

A szerződéstallózó bal oldalán az új évszűrő **Összes év** értékről indul. Az aktuális naptári évtől 2024-ig kínál éveket; a lista frissítéskor és percenként, fájlbeolvasás nélkül követi az évváltást. A fájlnévben szereplő hatályossági évre szűr, a többi keresési/melléklet/ePénz szűrővel együtt. A hibás és hiányzó dátumú fájlok az Összes év nézetben megmaradnak. A dátumoszlop **Hatályosság kezdete**, megjelenítése `ÉÉÉÉ.HH.NN.`, rendezése valódi dátumértékkel történik.

Jobb kattintás a szerződéslista egyik sorára: **Megjelölés feltöltöttként**, **Nincs feltöltve**, **Ellenőrizendő**, **Ismeretlen**. Mindig csak a kattintott dokumentum változik; a PDF érintetlen marad. A Feltöltve állapothoz időpont tartozik, más állapotnál ez már nem aktuális feltöltési időpont. A korábbi állapotválasztó és mentőgomb is működik.

A **Lista ürítése** az egész feldolgozási adatlapot és előnézetet alaphelyzetbe állítja, a mentést letiltja. A célmappa, a beállítások, a törzsadatok, a korábban mentett PDF-ek és az ePénz-állapotok megmaradnak. A háttérben már futó OCR befejezheti a munkáját, de eredménye érvénytelen: sem a kiürített lapot, sem ugyanannak a fájlnak az újraimportált tételét nem írhatja felül. A program nem állít le erőszakkal natív PDF/OCR műveletet.

Tesztjegyzőkönyv: [v0.1.3](docs/V013.md). A grafikus arculat és a GUI-keretrendszer változatlan.
