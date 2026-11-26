#!/bin/zsh
# Compila whisper-cli (whisper.cpp) para Mac con chip Apple: estático, con Metal y su biblioteca
# de sombreadores incrustada, para que funcione dentro de la aplicación sin dependencias externas.
# Necesita: cmake y las herramientas de Xcode. Resultado: descargas/whisper-mac/whisper-cli
set -e
D="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION_WHISPER="b5454"     # whisper.cpp 1.9.5 (6/10/2026); la misma compilación que la de Windows
SRC="$D/descargas/whisper.cpp"
if [ ! -d "$SRC/.git" ]; then
  git clone --quiet --depth 1 --branch "$VERSION_WHISPER" https://github.com/ggml-org/whisper.cpp "$SRC"
fi
cmake -S "$SRC" -B "$SRC/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
  -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DGGML_NATIVE=OFF -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF -DWHISPER_SDL2=OFF >/dev/null
cmake --build "$SRC/build" --config Release -j 8 --target whisper-cli >/dev/null
mkdir -p "$D/descargas/whisper-mac"
cp "$SRC/build/bin/whisper-cli" "$D/descargas/whisper-mac/whisper-cli"
cp "$SRC/LICENSE" "$D/descargas/whisper-mac/LICENSE-whisper.cpp.txt"
otool -L "$D/descargas/whisper-mac/whisper-cli" | tail -n +2
