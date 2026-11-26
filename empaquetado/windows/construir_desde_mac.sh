#!/bin/zsh
# Construye el instalador de Windows (NSIS, por usuario, sin permisos de administrador) desde
# un Mac, con la cadena de herramientas abierta MinGW-w64 (destino x86_64-pc-windows-gnu).
#
# Antes: bash empaquetado/windows/preparar_recursos.sh  (deja escritorio/src-tauri/recursos)
# Necesita: brew install nsis mingw-w64 ; rustup target add x86_64-pc-windows-gnu
# Uso:  zsh empaquetado/windows/construir_desde_mac.sh
# Resultado: salida/AureaAsistenteLocal-<versión>-Windows.exe
set -e
D="$(cd "$(dirname "$0")/../.." && pwd)"
V="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$D/nucleo/version.py")"
[ -d "$D/escritorio/src-tauri/recursos/python" ] || { echo "Faltan los recursos: ejecuta preparar_recursos.sh"; exit 1; }
cd "$D/escritorio"
[ -d node_modules ] || npm ci --silent
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$V\"/" src-tauri/tauri.conf.json package.json
npx tauri build --target x86_64-pc-windows-gnu --bundles nsis \
  --config '{"bundle":{"resources":["recursos/**/*"]}}'
EXE="$(ls -t src-tauri/target/x86_64-pc-windows-gnu/release/bundle/nsis/*.exe | head -1)"
mkdir -p "$D/salida"
cp "$EXE" "$D/salida/AureaAsistenteLocal-$V-Windows.exe"
ls -la "$D/salida/AureaAsistenteLocal-$V-Windows.exe"
