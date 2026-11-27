# -*- coding: utf-8 -*-
"""Vista de página de los documentos de Office (Word, PowerPoint y Excel).

Seudónimo no sabe dibujar un .docx; sí sabe hacerlo el programa que el usuario ya tiene
instalado. Si hay Microsoft Office (Mac o Windows) o Pages (Mac), se le pide que exporte la
COPIA seudonimizada a un PDF temporal, dentro de este ordenador, solo para enseñar sus páginas
en la revisión. Nunca se abre el original. Si no hay ningún programa, la copia se ve en texto."""
import hashlib
import os
import shutil
import subprocess
import tempfile

import rutas

EXTS = {".docx": "word", ".pptx": "powerpoint", ".xlsx": "excel"}
TIEMPO_MAX = 120

_APPS_MAC = {
    "word": ("/Applications/Microsoft Word.app", "Microsoft Word"),
    "powerpoint": ("/Applications/Microsoft PowerPoint.app", "Microsoft PowerPoint"),
    "excel": ("/Applications/Microsoft Excel.app", "Microsoft Excel"),
}


def _carpeta():
    c = os.path.join(rutas.DATOS, "vistas")
    os.makedirs(c, exist_ok=True)
    return c


def _tiene_mac(app):
    return os.path.isdir(_APPS_MAC[app][0])


def _tiene_windows(progid):
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid))
        return True
    except Exception:  # noqa
        return False


def programa(ext):
    """Qué programa dibujaría este documento, o None."""
    app = EXTS.get(ext.lower())
    if not app:
        return None
    if rutas.ES_MAC:
        if _tiene_mac(app):
            return _APPS_MAC[app][1]
        if app == "word" and os.path.isdir("/Applications/Pages.app"):
            return "Pages"
        return None
    if rutas.ES_WINDOWS:
        prog = {"word": "Word.Application", "powerpoint": "PowerPoint.Application", "excel": "Excel.Application"}[app]
        return prog.split(".")[0] if _tiene_windows(prog) else None
    return None


def disponible(ext):
    return programa(ext) is not None


def _escape_as(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _mac(app, origen, destino):
    o, d = _escape_as(origen), _escape_as(destino)
    nombre = _APPS_MAC.get(app, (None, None))[1]
    if app == "word" and nombre and _tiene_mac("word"):
        script = f'''tell application "{nombre}"
  set doc to open file name "{o}" with read only
  save as doc file name "{d}" file format format PDF
  close doc saving no
end tell'''
    elif app == "word":
        script = f'''tell application "Pages"
  set doc to open POSIX file "{o}"
  export doc to POSIX file "{d}" as PDF
  close doc saving no
end tell'''
    elif app == "powerpoint":
        script = f'''tell application "{nombre}"
  open POSIX file "{o}"
  save active presentation in POSIX file "{d}" as save as PDF
  close active presentation saving no
end tell'''
    else:
        script = f'''tell application "{nombre}"
  open POSIX file "{o}"
  save workbook as active workbook filename "{d}" file format PDF file format with overwrite
  close active workbook saving no
end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=TIEMPO_MAX)
    if r.returncode != 0 and not os.path.isfile(destino):
        raise RuntimeError((r.stderr or "").strip()[:300] or "el programa no ha respondido")


def _windows(app, origen, destino):
    o, d = origen.replace("'", "''"), destino.replace("'", "''")
    if app == "word":
        ps = (f"$a=New-Object -ComObject Word.Application; $a.Visible=$false; $a.DisplayAlerts=0; "
              f"$doc=$a.Documents.Open('{o}', $false, $true); $doc.ExportAsFixedFormat('{d}', 17); $doc.Close(0); $a.Quit()")
    elif app == "powerpoint":
        ps = (f"$a=New-Object -ComObject PowerPoint.Application; "
              f"$p=$a.Presentations.Open('{o}', -1, 0, 0); $p.SaveAs('{d}', 32); $p.Close(); $a.Quit()")
    else:
        ps = (f"$a=New-Object -ComObject Excel.Application; $a.Visible=$false; $a.DisplayAlerts=$false; "
              f"$w=$a.Workbooks.Open('{o}', 0, $true); $w.ExportAsFixedFormat(0, '{d}'); $w.Close($false); $a.Quit()")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True,
                       timeout=TIEMPO_MAX, creationflags=rutas.SIN_VENTANA)
    if r.returncode != 0 and not os.path.isfile(destino):
        raise RuntimeError((r.stderr or "").strip()[:300] or "el programa no ha respondido")


def a_pdf(ruta):
    """PDF temporal con las páginas de la copia (en la carpeta de datos de la aplicación), o None.
    Se reutiliza mientras la copia no cambie."""
    ext = os.path.splitext(ruta)[1].lower()
    app = EXTS.get(ext)
    if not app or not disponible(ext) or not os.path.isfile(ruta):
        return None
    firma = hashlib.sha256(("%s|%s" % (os.path.abspath(ruta), os.path.getmtime(ruta))).encode("utf-8")).hexdigest()[:24]
    destino = os.path.join(_carpeta(), firma + ".pdf")
    if os.path.isfile(destino):
        return destino
    # las aplicaciones de Office no abren rutas con caracteres raros con la misma fiabilidad: copia temporal
    tmp = tempfile.mkdtemp(prefix="vista-", dir=_carpeta())
    try:
        origen = os.path.join(tmp, "copia" + ext)
        shutil.copy2(ruta, origen)
        salida = os.path.join(tmp, "copia.pdf")
        if rutas.ES_MAC:
            _mac(app, origen, salida)
        elif rutas.ES_WINDOWS:
            _windows(app, origen, salida)
        else:
            return None
        if not os.path.isfile(salida):
            return None
        shutil.move(salida, destino)
        return destino
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def limpiar(max_archivos=40):
    """Las vistas son temporales: se quedan las últimas."""
    c = _carpeta()
    pdfs = sorted((os.path.join(c, f) for f in os.listdir(c) if f.endswith(".pdf")), key=os.path.getmtime)
    for f in pdfs[:-max_archivos]:
        try:
            os.remove(f)
        except OSError:
            pass
