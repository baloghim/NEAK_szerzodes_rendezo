# Harmadik féltől származó grafikai elemek

## Everaldo Crystal Clear

Szerző: Everaldo Coelho. Eredeti honlap: http://www.everaldo.com/ (történeti forrás). Felhasznált, szerzőt és licencet kifejezetten megnevező forrástükör:
https://github.com/niko-yanev/crystal-clear/tree/46e58e37e175ff22b6b11fd0e5dcbaeb571bfaa1

A készlet README-je minden ikonra LGPL 2.1 vagy újabb engedélyt ad. A változatlan eredeti PNG-k az assets/icons/crystal-clear könyvtárban találhatók. A README és a teljes licencszöveg megmaradt: assets/licenses/CrystalClear-README.txt és assets/licenses/LGPL-2.1.txt. Az eredeti fájlok SHA-256 lenyomata és műveletenkénti forrása az assets/icons/catalog.json fájlban szerepel. A futás közbeni méretezés, illetve a feldolgozásikon elforgatott megjelenítése nem módosítja a terjesztett eredeti PNG-ket.

A választott Crystal Clear kiadásból több, a terven szereplő pontos motívum hiányzik. A közeli megfelelők tételes listáját a docs/ICON_MAPPING.md tartalmazza; nem állítjuk például, hogy az önálló zöld plusz eredeti dokumentum-plusz ikon, vagy az üres lomtár seprű.

## KDE Crystal SVG – csak PDF

Szerző: KDE Artists, 2002 és azt követő évek. Készlet: **Crystal SVG, nem Oxygen**.

A tényleges forrás a régi KDE ikonkészletet megőrző Trinity tdelibs forrástükör:
https://github.com/Fat-Zer/tdelibs/tree/80a04dbf8a7f10fd9d78fdf85374fcf1d4ab93e9/pics/crystalsvg

A könyvtárhoz külön, kifejezetten minden CrystalSVG képet lefedő licencnyilatkozat tartozik:
https://github.com/Fat-Zer/tdelibs/blob/80a04dbf8a7f10fd9d78fdf85374fcf1d4ab93e9/pics/LICENSE.crystalsvg

Licenc: LGPL 2.1, a CrystalSVG műalkotás-könyvtárra vonatkozó kiegészítéssel. A kiegészítés a GUI-ban történő használatot és a forrásként szolgáló SVG/PNG állományok megőrzését is tárgyalja. A teljes nyilatkozat: assets/licenses/CrystalSVG-NOTICE.txt; LGPL szöveg: assets/licenses/LGPL-2.1.txt.

Felhasznált fájlok: cr16/cr22/cr32/cr48/cr64/cr128-mime-pdf.png, valamint az eredeti crsc-mime-pdf.svgz. Ezek változtatás nélkül kerültek a repositoryba. A PDF-forrás ténylegesen a CrystalSVG könyvtárban van, a rajz piros-fehér PDF-lap; a szerkesztett Oxygen/Plasma témákból nem vettünk át helyettesítőt.

## Saját alkalmazásgrafika

Az assets/branding/application.png a felhasználó által a feladathoz mellékelt alkalmazásikon grafikai koncepciójának háttérleválasztott változata. Az ICO ugyanezen grafika technikai, hétméretes átalakítása. Ez az alkalmazás saját arculati eszköze, nem állítjuk, hogy eredeti Everaldo/KDE ikonfájl. Generatív képszerkesztés kizárólag ennél a felhasználói logónál történt, a háttér leválasztására; műveleti ikon nem készült mesterséges intelligenciával.

## Programkönyvtárak

A Python, Qt/PyQt5, PDFium, Pillow, extract-msg és Tesseract korábbi licencjegyzéke változatlanul a docs/THIRD_PARTY.md fájlban található. Az ikonokat külön fájlokként, eredeti forrásukkal és licencükkel együtt terjesztjük. Az alkalmazás nem tölt le ikonokat futás közben.

A Windows ZIP-ben a futtatókörnyezet grafikai állományai és licencei az `_internal/assets/` könyvtárban találhatók; a forrás-repositoryban az `assets/` alatt.
