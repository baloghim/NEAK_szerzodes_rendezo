param([ValidateSet('all','dependencies','ocr','package','verify')][string]$Stage = 'all')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$ocr = Join-Path $env:TEMP 'neak-ocr-5.3.3'
if ($Stage -in @('all','dependencies')) {
    python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE) { throw 'Dependency installation failed' }
    python -m pytest -q
    if ($LASTEXITCODE) { throw 'Tests failed' }
}
if ($Stage -in @('all','ocr')) {
    $installer = Join-Path $env:TEMP 'neak-tesseract-5.3.3.exe'
    Invoke-WebRequest 'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe' -OutFile $installer -TimeoutSec 120
    # Published in microsoft/winget-pkgs, UB-Mannheim.TesseractOCR 5.3.3.20231005.
    $expected = '79AF1F9153B8FF988BAFFAA164FC70799950078F887E2C93DC3FA7EFED674B21'
    if ((Get-FileHash $installer -Algorithm SHA256).Hash -ne $expected) { throw 'Tesseract checksum mismatch' }
    # Unpack NSIS without running its installer or downloading optional components.
    7z x $installer "-o$ocr" -y
    if ($LASTEXITCODE) { throw 'Tesseract archive extraction failed' }
    if (-not (Test-Path "$ocr/tesseract.exe")) { throw 'Tesseract executable missing from archive' }
    New-Item -ItemType Directory -Force "$ocr/tessdata" | Out-Null
    Invoke-WebRequest 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/hun.traineddata' -OutFile "$ocr/tessdata/hun.traineddata" -TimeoutSec 120
    Invoke-WebRequest 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/eng.traineddata' -OutFile "$ocr/tessdata/eng.traineddata" -TimeoutSec 120
    & "$ocr/tesseract.exe" --version
    if ($LASTEXITCODE) { throw 'Extracted Tesseract cannot run' }
}
if ($Stage -in @('all','package')) {
    python -m PyInstaller --noconfirm --clean --windowed --onedir --name OtthonapolasiSzerzodeskezelo --collect-all pypdfium2 --collect-all extract_msg --copy-metadata extract-msg --add-data "$ocr;ocr" run.py
    if ($LASTEXITCODE) { throw 'PyInstaller failed' }
    python -m scripts.check_manifest dist/OtthonapolasiSzerzodeskezelo/OtthonapolasiSzerzodeskezelo.exe
    if ($LASTEXITCODE) { throw 'Executable privilege manifest check failed' }
}
if ($Stage -in @('all','verify')) {
    $exe = 'dist/OtthonapolasiSzerzodeskezelo/OtthonapolasiSzerzodeskezelo.exe'
    $smoke = Start-Process $exe -ArgumentList '--self-test' -PassThru
    if (-not $smoke.WaitForExit(180000)) { $smoke.Kill(); throw 'Packaged executable timed out' }
    if ($smoke.ExitCode -ne 0) { Get-Content self-test-result.json -ErrorAction SilentlyContinue; throw 'Packaged executable smoke test failed' }
    Get-Content self-test-result.json
    Copy-Item README.md,LICENSE,docs/COMPATIBILITY.md,docs/THIRD_PARTY.md,docs/OUTLOOK.md -Destination dist/OtthonapolasiSzerzodeskezelo
    Compress-Archive -Path 'dist/OtthonapolasiSzerzodeskezelo' -DestinationPath 'dist/OtthonapolasiSzerzodeskezelo-v0.1.1-windows-x64.zip' -Force
}
