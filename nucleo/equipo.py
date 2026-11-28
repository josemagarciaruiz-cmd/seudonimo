# -*- coding: utf-8 -*-
"""¿Llega este ordenador? Comprobación de requisitos antes de instalar Ollama y descargar el modelo.

Mide la memoria, el espacio libre, el procesador, la tarjeta gráfica (Windows) y la versión del
sistema, y da un semáforo con frases sencillas:

- verde: cumple los requisitos;
- amarillo: funciona, con matices (memoria justa, sin tarjeta gráfica que acelere…);
- rojo: no llega (Mac con Intel, 8 GB de memoria o menos, sin espacio).

No envía nada a ningún sitio y no necesita permisos: todo se lee del propio sistema."""
import os
import platform
import re
import shutil
import subprocess
import threading

import rutas

GIB = 1024 ** 3
MEMORIA_RECOMENDADA = 16        # GB, la del modelo recomendado (proveedores.CATALOGO)
ESPACIO_MODELO = 13             # GB: el modelo recomendado (unos 8) y margen para descargarlo
ESPACIO_OLLAMA = 3              # GB: Ollama con sus bibliotecas
VRAM_UTIL = 6                   # GB de memoria de vídeo a partir de los que la tarjeta acelera el modelo
_SIN_VENTANA = 0x08000000 if rutas.ES_WINDOWS else 0   # CREATE_NO_WINDOW: que no parpadee una consola

_FIJO = {}
_CERROJO = threading.Lock()


def _ejecutar(orden, espera=6):
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=espera, creationflags=_SIN_VENTANA,
                           stdin=subprocess.DEVNULL)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001 — si no se puede medir, se dice «sin datos»
        return ""


# ------------------------------------------------------------------ medidas

def memoria_gb():
    """Memoria física total, en GB (GiB), o None si no se puede leer."""
    try:
        if rutas.ES_WINDOWS:
            import ctypes

            class Estado(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            e = Estado()
            e.dwLength = ctypes.sizeof(Estado)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e)):
                return e.ullTotalPhys / GIB
            return None
        if rutas.ES_MAC:
            v = _ejecutar(["/usr/sbin/sysctl", "-n", "hw.memsize"])
            return int(v) / GIB if v.isdigit() else None
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / GIB
    except Exception:  # noqa: BLE001
        return None


def procesador():
    """(nombre legible, es_apropiado). En Mac, apropiado = chip Apple; en Windows, 64 bits."""
    maquina = platform.machine().lower()
    if rutas.ES_MAC:
        nombre = _ejecutar(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor()
        # bajo Rosetta, platform.machine() diría x86_64 aunque el chip sea Apple
        apple = maquina == "arm64" or _ejecutar(["/usr/sbin/sysctl", "-n", "hw.optional.arm64"]) == "1"
        return (nombre or ("chip Apple" if apple else "Intel")), apple
    if rutas.ES_WINDOWS:
        nombre = ""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                nombre = str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except Exception:  # noqa: BLE001
            nombre = platform.processor()
        arq = (os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE") or maquina).upper()
        return re.sub(r"\s+", " ", nombre) or arq, arq in ("AMD64", "ARM64", "X86_64")
    return platform.processor() or maquina, True


def graficas():
    """Tarjetas gráficas: [{"nombre", "vram_gb" (o None), "acelera"}]. Solo se mira en Windows:
    en un Mac con chip Apple el modelo usa siempre la gráfica integrada."""
    if not rutas.ES_WINDOWS:
        return []
    res = []
    smi = shutil.which("nvidia-smi") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe")
    if os.path.isfile(smi):
        for linea in _ejecutar([smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]).splitlines():
            partes = [p.strip() for p in linea.split(",")]
            if len(partes) >= 2 and partes[0]:
                try:
                    vram = float(partes[1]) / 1024
                except ValueError:
                    vram = None
                res.append({"nombre": partes[0], "vram_gb": vram, "acelera": bool(vram and vram >= VRAM_UTIL)})
    vistos = {g["nombre"].lower() for g in res}
    lista = _ejecutar(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                       "(Get-CimInstance Win32_VideoController).Name"], espera=12)
    for nombre in lista.splitlines():
        nombre = nombre.strip()
        if nombre and nombre.lower() not in vistos and "basic" not in nombre.lower():
            vistos.add(nombre.lower())
            res.append({"nombre": nombre, "vram_gb": None, "acelera": False})
    return res


def sistema():
    """(nombre legible, actualizado). Ollama pide Windows 10 22H2 (compilación 19045) o posterior."""
    if rutas.ES_WINDOWS:
        try:
            compilacion = int(platform.version().split(".")[2])
        except (IndexError, ValueError):
            compilacion = 0
        nombre = ("Windows 11" if compilacion >= 22000 else "Windows 10") if compilacion else "Windows"
        return "%s (compilación %s)" % (nombre, compilacion or "?"), (compilacion == 0 or compilacion >= 19045)
    if rutas.ES_MAC:
        v = platform.mac_ver()[0]
        return "macOS %s" % v, True
    return platform.system(), True


def espacio_libre_gb():
    base = os.path.join(os.path.expanduser("~"), ".ollama")
    while not os.path.exists(base):
        base = os.path.dirname(base)
    return shutil.disk_usage(base).free / 1e9


# ------------------------------------------------------------------ veredicto

def _fijos():
    """Lo que no cambia mientras la aplicación está abierta (la gráfica tarda un par de segundos)."""
    with _CERROJO:
        if not _FIJO:
            nombre_cpu, cpu_ok = procesador()
            nombre_so, so_ok = sistema()
            _FIJO.update(memoria_gb=memoria_gb(), procesador=nombre_cpu, procesador_ok=cpu_ok,
                         sistema=nombre_so, sistema_ok=so_ok, graficas=graficas())
        return dict(_FIJO)


def precalentar():
    threading.Thread(target=_fijos, daemon=True).start()


def _gb(x):
    return ("%.0f" % x) if x >= 10 else ("%.1f" % x).replace(".", ",")


def comprobar(ollama_instalado=True, modelo_instalado=False):
    d = _fijos()
    libre = espacio_libre_gb()
    hace_falta = (0 if modelo_instalado else ESPACIO_MODELO) + (0 if ollama_instalado else ESPACIO_OLLAMA)
    rojos, amarillos = [], []

    if rutas.ES_MAC and not d["procesador_ok"]:
        rojos.append("Este Mac tiene procesador Intel. Seudónimo necesita un Mac con chip Apple (M1 o posterior).")
    elif rutas.ES_WINDOWS and not d["procesador_ok"]:
        rojos.append("Este Windows no es de 64 bits, y el modelo de IA lo necesita.")

    mem = d["memoria_gb"]
    if mem is not None:
        redondeo = round(mem)
        if mem < 11:
            rojos.append("Tiene %s GB de memoria y el modelo necesita %s. Con tan poca memoria no puede funcionar."
                         % (redondeo, MEMORIA_RECOMENDADA))
        elif mem < 14.5:
            amarillos.append("Tiene %s GB de memoria y se recomiendan %s. Funcionará, pero lento: cierra los demás "
                             "programas mientras trabaja." % (redondeo, MEMORIA_RECOMENDADA))

    if hace_falta and libre < hace_falta:
        rojos.append("Hay %s GB libres en el disco y hacen falta unos %s. Libera espacio antes de seguir."
                     % (_gb(libre), hace_falta))

    if rutas.ES_WINDOWS:
        if not any(g["acelera"] for g in d["graficas"]):
            amarillos.append("No tiene una tarjeta gráfica que acelere la IA. Funcionará, pero más despacio: "
                             "un documento puede tardar varios minutos.")
        if not d["sistema_ok"]:
            amarillos.append("Windows no está al día. Actualízalo (Windows Update) antes de instalar Ollama.")

    if rojos:
        nivel, titulo = "rojo", "Este ordenador no llega para usar Seudónimo."
    elif amarillos:
        nivel, titulo = "amarillo", "Este ordenador puede usar Seudónimo, con matices."
    else:
        nivel, titulo = "verde", "Este ordenador cumple los requisitos."

    return {
        "nivel": nivel, "titulo": titulo, "motivos": rojos + amarillos,
        "memoria_gb": round(mem, 1) if mem is not None else None, "memoria_recomendada_gb": MEMORIA_RECOMENDADA,
        "espacio_libre_gb": round(libre, 1), "espacio_necesario_gb": hace_falta,
        "procesador": d["procesador"], "sistema": d["sistema"],
        "graficas": d["graficas"], "plataforma": "Windows" if rutas.ES_WINDOWS else ("Mac" if rutas.ES_MAC else "Linux"),
    }
