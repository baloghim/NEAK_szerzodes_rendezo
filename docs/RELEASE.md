Klasszikus Outlook drag-and-drop javítás, v0.1.1.

Natív Windows OLE IDropTarget kezeli a virtuális PDF-mellékleteket és a teljes e-maileket. Több elem egyszerre átvehető; FileGroupDescriptorW/ANSI, indexelt FileContents, HGLOBAL, IStream és IStorage támogatott. Az e-mailek PDF-mellékletei a meglévő OCR-várólistába kerülnek. A korábbi PDF/MSG/EML import és a felületi elrendezés megmaradt. A források nem módosulnak.

A teljes ZIP-et bontsd ki, majd indítsd az OtthonapolasiSzerzodeskezelo.exe fájlt. Nincs szükség külön Python vagy Tesseract telepítésére. Az Outlookot és az alkalmazást is normál jogosultsággal indítsd: eltérő integritási szinten a Windows blokkolhatja a behúzást.

Tényleges klasszikus Outlookkal és Windows 10 1607-en végzett teszt még nem igazolt. A natív Windows és a csomagolt EXE szintetikus ellenőrzéseinek részletei: docs/OUTLOOK.md a forrásban és a ZIP-ben.

Windows Server 2022-n mind a 26 automatizált teszt, a csomagolt EXE natív OLE → várólista → OCR funkcionális tesztje, az asInvoker-manifest ellenőrzése és az SMB/UNC mentési regressziós teszt sikeres. Ezek szintetikus adatokkal végzett ellenőrzések, tényleges Outlookot nem futtattak.
