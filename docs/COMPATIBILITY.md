# Windows-kompatibilitás

Cél: Windows 10 x64 1607, build 14393 vagy újabb. **Az 1607-en végzett futtatás még nem igazolt.** A GitHub Actions windows-2022 teszt nem helyettesíti ezt.

A Python 3.10.11 Windows 8.1 vagy újabb rendszert támogat (python.org Python 3.10 Windows dokumentáció). A Qt 5.15.2 Windows 7 vagy újabb x64 rendszerekre készült (Qt 5.15 supported platforms); ezért Qt 6 helyett Qt 5 a választás. A PyQt5-Qt5 futtatókörnyezet külön rögzített, hogy a pip ne válasszon újabb Qt-verziót. A cryptography 41.0.7 és cffi 1.17.1 szintén rögzített. A Pillow 10.4 Python 3.10-es kereket használ.

A PDFium (pypdfium2 4.30.0), a Tesseract 5.3.3 UB Mannheim bináris és az összes betöltött DLL 14393-as működésére nincs ebben a környezetben igazoló mérés. Ezek a kiadás kompatibilitási kockázatai. Nincs ismerten Windows 11-et vagy Qt 6-ot megkövetelő fő komponens, de ez nem bizonyítja a teljes csomag 1607-kompatibilitását.

Elfogadási teszt tiszta 14393 x64 virtuális gépen, Python és Tesseract nélkül: ZIP kibontása nem rendszergazdai felhasználóval; EXE indítás; PDF-ek importja; hun+eng OCR; többoldalas betekintő; mentés helyi és elérhető UNC-mappába; ütközés és hálózatszakadás; SQLite-állapot újraindítás után. Az eredményt a build azonosítójával és tényleges operációsrendszer-verzióval kell rögzíteni. Amíg ez nincs kész, a csomag kipróbálásra szánt kiadás.
