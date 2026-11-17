# Klasszikus Outlook drag-and-drop – v0.1.1

## Megvalósítás

A v0.1.0 kizárólag a Qt URL/fájlútvonal átadását kezelte; az Outlook virtuális dokumentumai nem ilyenek. A javítás az eredeti felületi elrendezés megtartásával natív Windows `IDropTarget` fogadót regisztrál a Beérkezett dokumentumok panelre és a lista natív viewportjára. A Qt főablakhoz tartozó saját drop targetjét nem cseréljük le: a két natív gyermekablak regisztrációja külön történik, így a Qt saját COM-objektumának élettartamát nem zavarjuk meg. Linuxon a korábbi Qt-fájlbehúzás marad.

A `FileGroupDescriptorW` (és ANSI párja) adja az elemek neveit és sorrendjét. Az indexelt `FileContents` lekérés minden elemnél az eredeti `lindex` értékét használja. Az átadott médium lehet:

- `TYMED_HGLOBAL`: memóriában átadott fájltartalom;
- `TYMED_ISTREAM`: darabonként olvasott adatfolyam (PDF vagy MSG);
- `TYMED_ISTORAGE`: teljes e-mail strukturált MSG-tárolója, `IStorage.CopyTo` és commit segítségével helyi másolatként szerializálva.

Az összes `STGMEDIUM` felszabadítása `ReleaseStgMedium` használatával történik, a forrás saját COM-élettartam-kezelésének tiszteletben tartásával. Az `IDataObject` mutató nem marad használatban a `Drop` visszatérése után. A GUI-t értesítő Qt-jel sorba állítva fut: az OLE callbackben nem nyílik párbeszédablak és nem indul OCR. A sikeres másolatok a meglévő importálót, majd a korábbi OCR-várólistát használják. Nincs Outlook COM-automatizálás, mailboxfigyelés vagy külső szolgáltatás.

A `CF_HDROP` is támogatott; a hagyományos PDF-, MSG- és EML-importot megtartottuk. Az Outlookból átvett fájlok véletlen helyi ideiglenes neveket kapnak, a feladó által közölt útvonalak nem használhatók fájlírásra. Hibás tételek mellett a többi feldolgozható. Méretkorlát: egy virtuális fájl legfeljebb 1 GiB; egy behúzás legfeljebb 1024 leíró. Csak COPY hatás engedélyezett; MOVE és forrástörlés nincs. Az eredeti levelekhez/mellékletekhez nem ír a program.

## Jogosultsági szint

A Windows UIPI/OLE integritási szabályai miatt eltérő jogosultsági szinten futó Outlook és célalkalmazás között a behúzást az operációs rendszer blokkolhatja, mielőtt `DragEnter` eseményt kapnánk. Mindkettőt normál felhasználóként indítsd, ne rendszergazdaként. Ellenőrizd az EXE és a parancsikon Kompatibilitás / Futtatás rendszergazdaként jelölését is. Az alkalmazás `asInvoker` manifesttel készül, nem kér emelést. Nem módosítjuk a Windows üzenetszűrőit, és nem kerülünk meg integritási korlátokat. Regisztrációs hibánál részletes hibaüzenet jelenik meg; a fájlból importálás megmarad.

A normál–emelt és emelt–normál Outlook kombinációk tényleges tesztje célgépen szükséges. A blokkolt behúzás nem javítható egy hibát elnyelő GUI callbackkel, mert nem érkezik meg oda.

## Kompatibilitás és tesztelés

Új külső függőség nincs: Python `ctypes`, OLE32, USER32, KERNEL32 és SHELL32 API-k. A használt API-k a Windows 10 1607 előtti Windows-verziókban is elérhetők. A cél továbbra is Windows 10 x64 1607 (14393); ez nem bizonyítja a teljes Qt/PDFium/OCR-csomag tényleges 1607-kompatibilitását.

A tesztadatok kizárólag programból készített szintetikus PDF-ek és MSG/EML-ek. Privát levelek, dokumentumok és OCR-kimenetek nem kerülnek Gitbe vagy a kiadásba.

| Ellenőrzés | Módszer | Állapot |
| --- | --- | --- |
| Unicode/ANSI fájlleírók, több elem, hibás leíró, COPY-only | platformfüggetlen automatizált teszt | Linuxon sikeres |
| Egy PDF, több PDF | valódi Windows COM, szintetikus IDataObject és IDropTarget ABI, HGLOBAL/IStream | Sikeres Windows Server 2022-n, szintetikus OLE-adatokkal |
| Egy teljes e-mail, több e-mail | szintetikus, valódi strukturált MSG IStorage és CopyTo | Sikeres Windows Server 2022-n, szintetikus OLE-adatokkal |
| MSG IStream/HGLOBAL és vegyes PDF+MSG | natív OLE és tényleges extract-msg import | Sikeres Windows Server 2022-n, szintetikus OLE-adatokkal |
| Korábbi PDF/MSG/EML fájlok | natív CF_HDROP és korábbi importáló | Sikeres Windows Server 2022-n, szintetikus OLE-adatokkal |
| Meglévő várólistához hozzáadás és OCR | csomagolt EXE saját szintetikus OLE funkcionális tesztje | Sikeres Windows Server 2022-n, szintetikus OLE-adatokkal |
| Fizikai egérbehúzás klasszikus Outlookból, valamennyi fenti eset | valódi Outlookkal | **Célgépen még nem tesztelt** |
| Windows 10 1607 és eltérő jogosultságok | tényleges célrendszerrel | **Célgépen még nem tesztelt** |

A GitHub Windows-runneren nincs használható Outlook-profil. A szintetikus COM-teszt nem helyettesíti a valódi Outlook és Windows egérbehúzási útvonal tesztjét; ezt nem állítjuk igazoltnak.

Ellenőrzött build: [GitHub Actions 44066501299](https://github.com/baloghim/NEAK_szerzodes_rendezo/actions/runs/44066501299), `21dcaee` forrásverzió. Windows alatt mind a 26 automatizált teszt sikeres; Linux alatt 25 sikeres és 1 Windows-specifikus teszt kihagyva. A csomagolt EXE a ténylegesen regisztrált natív panel-drop-target COM vtable-ján kapta a szintetikus adatokat; a Qt-jelen keresztül 10 további PDF került a korábban nem üres várólistára és OCR-be. A teszt nem fizikai egérbehúzást szimulál, és nem futtat Outlookot.

Az elkészült EXE PE-manifestjét külön ellenőrzés igazolja: `requestedExecutionLevel=asInvoker`, `uiAccess=false`. Az SMB/UNC mentési regressziós teszt szintén sikeres. A tényleges Outlook-integritási szint kombinációk és Windows 10 1607 tesztje továbbra is a fenti célgépes sorokban marad.

## Célgépes elfogadási lista

1. Jegyezd fel a Windows buildszámát, az Outlook verzióját/bitnessét és a program kiadását.
2. Normál felhasználóként futó klasszikus Outlookból húzz egy PDF-et a beérkező lista üres részére, majd egy meglévő sor fölé. Mindkettő jelenjen meg és induljon OCR.
3. Húzz egyszerre több kijelölt PDF-mellékletet.
4. Húzz egy teljes e-mailt, majd több kijelölt e-mailt. A bennük lévő PDF-ek kerüljenek a várólistába.
5. Ismételd meg nem üres várólistán; a régi tételek maradjanak meg. Próbáld ki a PDF/MSG/EML fájlbehúzást és a Hozzáadás gombot is.
6. Ellenőrizd, hogy a forráslevelek és mellékletek változatlanul az Outlookban maradtak.
7. Ismételd meg a két eltérő jogosultsági kombinációval; az OS általi blokkolást jegyezd fel, majd mindkét program normál újraindítása után ismét ellenőrizd.
8. Ismételd meg Windows 10 1607-en a teljes kibontott ZIP-pel, külön Python/OCR telepítése nélkül.
