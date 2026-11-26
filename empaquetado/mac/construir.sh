#!/bin/zsh
# Construye «Áurea Asistente Local.app» y el .dmg para Mac con chip Apple.
# Se ejecuta en un Mac con Rust, Node y las herramientas de línea de órdenes de Xcode.
#
# Necesita, en descargas/python-mac.tar.gz, un Python 3.13 autocontenido para arm64 de
# python-build-standalone («cpython-3.13.x+…-aarch64-apple-darwin-install_only.tar.gz»):
#   https://github.com/astral-sh/python-build-standalone/releases
#
# Uso:  zsh empaquetado/mac/construir.sh
# Resultado: salida/AureaAsistenteLocal-<versión>-Mac.dmg
set -e
D="$(cd "$(dirname "$0")/../.." && pwd)"
V="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$D/nucleo/version.py")"
NOMBRE="Áurea Asistente Local"
REC="$D/construccion/mac/recursos"
rm -rf "$D/construccion/mac"
mkdir -p "$REC"

# 1. Python autocontenido con las librerías del servicio local
tar -xzf "$D/descargas/python-mac.tar.gz" -C "$REC/"
PY="$REC/python/bin/python3"
"$PY" -m pip install -q --disable-pip-version-check --no-warn-script-location -r "$D/requisitos/mac.txt"
"$PY" -m pip uninstall -y -q pip setuptools >/dev/null 2>&1 || true
find "$REC/python/lib" -type d \( -name "test" -o -name "tests" -o -name "idlelib" -o -name "tkinter" -o -name "turtledemo" \) -prune -exec rm -rf {} + 2>/dev/null || true

# 2. El núcleo (servicio local)
mkdir -p "$REC/nucleo"
rsync -a --exclude "__pycache__" "$D/nucleo/" "$REC/nucleo/"

# 3. La ventana de escritorio (Tauri)
cd "$D/escritorio"
[ -d node_modules ] || npm ci --silent
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$V\"/" src-tauri/tauri.conf.json package.json
npx tauri build --bundles app
APP="$D/escritorio/src-tauri/target/release/bundle/macos/$NOMBRE.app"

# 4. Recursos dentro de la aplicación (ditto conserva los enlaces simbólicos de Python)
ditto "$REC" "$APP/Contents/Resources/recursos"
find "$APP" -name "__pycache__" -type d -prune -exec rm -rf {} +
chmod -R u+w "$APP"
xattr -cr "$APP"

# 5. Firma ad hoc (sin certificado de Apple: el sistema avisará la primera vez)
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP" && echo "FIRMA_OK"

# 6. Disco de instalación
STG="$D/construccion/mac/dmg"
mkdir -p "$STG" "$D/salida"
ditto "$APP" "$STG/$NOMBRE.app"
ln -s /Applications "$STG/Aplicaciones"
DMG="$D/salida/AureaAsistenteLocal-$V-Mac.dmg"
rm -f "$DMG"
hdiutil create -volname "$NOMBRE" -srcfolder "$STG" -fs HFS+ -format UDZO -ov "$DMG" >/dev/null
rm -rf "$STG"
du -sh "$APP" "$DMG"

# 7. Inventario de componentes (SBOM CycloneDX) del Python incluido y de los crates de Rust
"$APP/Contents/Resources/recursos/python/bin/python3" -s "$D/empaquetado/sbom.py" \
  "$D/escritorio/src-tauri/Cargo.lock" "$D/salida/AureaAsistenteLocal-$V-SBOM.cdx.json"
