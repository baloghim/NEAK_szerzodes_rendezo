# Változásnapló

## v0.1.3

- Aktuális évtől 2024-ig frissülő, a meglévő szűrőkkel együtt működő évszűrés.
- Formázott Hatályosság kezdete oszlop, valódi dátum szerinti rendezéssel.
- Sorhoz kötött jobb gombos ePénz-állapotmenü, tartós mentéssel és helyes feltöltési időponttal.
- Teljes feldolgozási adatlap- és PDF-reset listaürítéskor; munkamenet/tételazonosítóval védett késői OCR-eredmények.
- A beállítások, törzsadatok, mentett fájlok és állapotok változatlan megőrzése.
- Windows EXE funkcionális próbával bővített szintetikus regressziós tesztek; új függőség és arculatváltás nélkül.

## v0.1.2

- Rugalmasabb IX/1–IX/3 adatkinyerés: sorokra tördelt és táblázatos mezők, részleges adatok megőrzése.
- Oldalankénti automatikus tájolás 0/90/180/270 fokra, mezőalapú értékeléssel és korai kilépéssel.
- Oldalankénti kézi PDF-forgatás, PDF-metaadatként mentve; feldolgozás alatt másolat készül, a tárban megerősítéses, atomikus csere.
- PDFium-hívások szálbiztos sorosítása, miközben a Tesseract háttérben fut.
- Teljes fül- és panelcímek, olvasható eszköztár, kék félkövér pulzáló feldolgozási állapot és külön hibaállapot.
- Külön beállítási ablak; tájékoztató célmappa a főoldalon, felhasználói SQLite-ban megőrzött nézet/OCR beállítások.
- Szintetikus elforgatott IX/3 és többoldalas PDF teszt a csomagolt Windows EXE-ben is.

## v0.1.1

- Natív Windows OLE átvétel klasszikus Outlook virtuális PDF-, MSG- és EML-dokumentumaihoz.
- HGLOBAL, IStream, IStorage, többes átvétel, COPY-only viselkedés; változatlan korábbi import.

## v0.1.0

- Első offline OCR/PDF/SQLite szerződéskezelő, kétoldalas magyar felülettel és Windows ZIP-pel.
