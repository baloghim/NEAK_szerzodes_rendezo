Otthonápolási szerződéskezelő v0.1.3 – funkcionális frissítés, változatlan arculattal.

- Aktuális évtől 2024-ig automatikusan frissülő évszűrő, Összes év alapértékkel; a meglévő szűrőkkel együtt működik.
- Hatályosság kezdete oszlop ÉÉÉÉ.HH.NN. formátumban, valódi dátum szerinti rendezéssel.
- Jobb gombos, egyetlen sorra vonatkozó ePénz-állapotváltás és tartós feltöltési időpont.
- Teljes adatlap-/előnézet-reset listaürítéskor, késői OCR-válaszok biztonságos érvénytelenítésével. A célmappa, beállítások, törzsadatok, mentett PDF-ek és állapotok megmaradnak.

A teljes ZIP-et bontsd ki új mappába, és indítsd az OtthonapolasiSzerzodeskezelo.exe fájlt. Külön Python vagy OCR telepítése nem szükséges. Az alkalmazás a meglévő felhasználói SQLite-adatbázist használja.

A Windows 10 x64 1607 célplatformon nem történt tényleges teszt. Új függőség nem került a csomagba. Részletes tesztek és korlátok: V013.md a ZIP-ben, docs/V013.md a forrásban. Privát tesztdokumentum nem része a csomagnak.
