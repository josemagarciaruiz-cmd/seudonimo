#!/usr/bin/env bash
# Prepara los recursos del instalador de Windows (Python embebido, librerías, Tesseract y el
# núcleo) en escritorio/src-tauri/recursos/. Se ejecuta en Linux o Mac; no hace falta Windows.
#
# Necesita en descargas/:
#   python-embed.zip     https://www.python.org/ftp/python/3.13.9/python-3.13.9-embed-amd64.zip
#   tesseract/           carpeta con tesseract.exe, sus DLL y tessdata (spa, eng, osd), o bien
#   tesseract-setup.exe  el instalador de UB Mannheim 5.4 y spa.traineddata (se extrae con 7-Zip)
# Uso:  bash empaquetado/windows/preparar_recursos.sh
set -euo pipefail
D="$(cd "$(dirname "$0")/../.." && pwd)"
DESC="$D/descargas"
REC="$D/escritorio/src-tauri/recursos"
rm -rf "$REC"
mkdir -p "$REC/python/Lib/site-packages" "$REC/tesseract" "$REC/nucleo" "$REC/licencias"

# 1. Python embebido: el núcleo añade su propia carpeta al path al arrancar
unzip -q "$DESC/python-embed.zip" -d "$REC/python"
cat > "$REC/python/python313._pth" <<'EOF'
python313.zip
.
Lib\site-packages
import site
EOF

# 2. Librerías (ruedas binarias para Windows x64)
rm -rf "$DESC/ruedas-win"
python3 -m pip download --quiet --no-deps --dest "$DESC/ruedas-win" --platform win_amd64 --python-version 3.13 \
  --only-binary=:all: -r "$D/requisitos/windows.txt"
for w in "$DESC"/ruedas-win/*.whl; do unzip -q -o "$w" -d "$REC/python/Lib/site-packages"; done
find "$REC/python/Lib/site-packages" -name "__pycache__" -type d -prune -exec rm -rf {} +

# 3. Tesseract (OCR de Windows): carpeta ya preparada o extraída del instalador oficial con 7-Zip
if [ ! -d "$DESC/tesseract" ] && [ -f "$DESC/tesseract-setup.exe" ]; then
  SZ="$(command -v 7z || command -v 7zz)"
  TMP="$(mktemp -d)"
  "$SZ" x -y -o"$TMP" "$DESC/tesseract-setup.exe" >/dev/null
  mkdir -p "$DESC/tesseract/tessdata"
  cp "$TMP"/tesseract.exe "$TMP"/*.dll "$DESC/tesseract/"
  cp -R "$TMP/tessdata/configs" "$TMP/tessdata/tessconfigs" "$TMP/tessdata/eng.traineddata" \
        "$TMP/tessdata/osd.traineddata" "$DESC/tesseract/tessdata/"
  cp "$DESC/spa.traineddata" "$DESC/tesseract/tessdata/"
  mkdir -p "$DESC/tesseract/licencia"
  cp "$TMP/doc/LICENSE" "$TMP/doc/AUTHORS" "$DESC/tesseract/licencia/" 2>/dev/null || true
  rm -rf "$TMP"
fi
cp -R "$DESC/tesseract/." "$REC/tesseract/"

# 4. Núcleo
cp -R "$D/nucleo/." "$REC/nucleo/"
find "$REC/nucleo" -name "__pycache__" -type d -prune -exec rm -rf {} +
cp "$D/THIRD_PARTY_NOTICES.md" "$REC/licencias/"
cp "$REC/python/LICENSE.txt" "$REC/licencias/Python-LICENSE.txt" 2>/dev/null || true
du -sh "$REC"
