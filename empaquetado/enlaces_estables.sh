#!/bin/zsh
# Publica en una versión ya creada en GitHub dos copias de los instaladores con nombre fijo
# (Seudonimo-Windows.exe y Seudonimo-Mac.dmg), añade sus huellas al SHA256SUMS de la versión
# y la marca como la más reciente. Así estos enlaces descargan siempre la última versión:
#   https://github.com/josemagarciaruiz-cmd/seudonimo/releases/latest/download/Seudonimo-Windows.exe
#   https://github.com/josemagarciaruiz-cmd/seudonimo/releases/latest/download/Seudonimo-Mac.dmg
# Uso: zsh empaquetado/enlaces_estables.sh 0.8.2
set -euo pipefail
V="${1:?Indica la versión, por ejemplo 0.8.2}"
cd "$(dirname "$0")/.."
S=salida
E="$S/estable-$V"
rm -rf "$E"; mkdir -p "$E"
cp "$S/Seudonimo-$V-Windows.exe" "$E/Seudonimo-Windows.exe"
cp "$S/Seudonimo-$V-Mac.dmg" "$E/Seudonimo-Mac.dmg"
SUMAS="$S/SHA256SUMS-$V.txt"
grep -v -e ' Seudonimo-Windows.exe$' -e ' Seudonimo-Mac.dmg$' "$SUMAS" > "$E/SHA256SUMS-$V.txt"
(cd "$E" && shasum -a 256 Seudonimo-Mac.dmg Seudonimo-Windows.exe) >> "$E/SHA256SUMS-$V.txt"
cp "$E/SHA256SUMS-$V.txt" "$SUMAS"
gh release upload "v$V" "$E/Seudonimo-Windows.exe" "$E/Seudonimo-Mac.dmg" "$SUMAS" --clobber
gh release edit "v$V" --prerelease=false --latest
rm -rf "$E"
echo "Enlaces estables publicados para la versión $V"
