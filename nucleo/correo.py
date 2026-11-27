# -*- coding: utf-8 -*-
"""Correos y chats: los convierte a texto plano para seudonimizarlos.

- .eml (Outlook, Apple Mail, Thunderbird): cabeceras, cuerpo y nombres de los adjuntos.
- .msg (Outlook en Windows): se lee el contenedor OLE con olefile (licencia BSD), sin
  programas de terceros.
- .zip exportado de WhatsApp («Exportar chat»): solo el texto del chat; las fotos y audios
  que trae el .zip no se tratan y se avisa.

La copia seudonimizada se entrega como .txt. Los adjuntos de un correo no se extraen: si
hacen falta, hay que guardarlos aparte y añadirlos al proyecto."""
import email
import email.policy
import html
import os
import re
import zipfile

EXTENSIONES = {".eml", ".msg", ".zip"}


class ErrorCorreo(Exception):
    pass


def _html_a_texto(h):
    h = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</h\d>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t ]+", " ", h)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", h).strip()


def _cabeceras(pares):
    return "\n".join("%s: %s" % (k, v) for k, v in pares if v)


def eml_a_texto(ruta):
    with open(ruta, "rb") as f:
        msg = email.message_from_binary_file(f, policy=email.policy.default)
    cab = _cabeceras([("De", msg.get("From")), ("Para", msg.get("To")), ("CC", msg.get("Cc")),
                      ("Fecha", msg.get("Date")), ("Asunto", msg.get("Subject"))])
    cuerpo = msg.get_body(preferencelist=("plain", "html"))
    texto = ""
    if cuerpo is not None:
        texto = cuerpo.get_content()
        if cuerpo.get_content_type() == "text/html":
            texto = _html_a_texto(texto)
    adjuntos = [p.get_filename() for p in msg.iter_attachments() if p.get_filename()]
    pie = ("\n\nAdjuntos (no incluidos): " + ", ".join(adjuntos)) if adjuntos else ""
    return cab + "\n\n" + texto.strip() + pie, adjuntos


def msg_a_texto(ruta):
    try:
        import olefile
    except ImportError:
        raise ErrorCorreo("Falta el lector de correos de Outlook (olefile).")
    if not olefile.isOleFile(ruta):
        raise ErrorCorreo("El archivo .msg no es un correo de Outlook válido.")
    with olefile.OleFileIO(ruta) as ole:
        def prop(codigo, raiz=""):
            for tipo, cod in (("001F", "utf-16-le"), ("001E", "cp1252")):
                nombre = raiz + "__substg1.0_%s%s" % (codigo, tipo)
                if ole.exists(nombre):
                    return ole.openstream(nombre).read().decode(cod, errors="replace").rstrip("\x00")
            return ""
        cab = _cabeceras([("De", " ".join(x for x in (prop("0C1A"), "<%s>" % prop("5D01") if prop("5D01") else "") if x)),
                          ("Para", prop("0E04")), ("CC", prop("0E03")), ("Asunto", prop("0037"))])
        texto = prop("1000")
        if not texto.strip():
            nombre = "__substg1.0_10130102"           # cuerpo HTML binario
            if ole.exists(nombre):
                texto = _html_a_texto(ole.openstream(nombre).read().decode("utf-8", errors="replace"))
        adjuntos = []
        for entrada in ole.listdir(streams=False, storages=True):
            if entrada and entrada[0].startswith("__attach_version1.0_") and len(entrada) == 1:
                n = prop("3707", entrada[0] + "/") or prop("3704", entrada[0] + "/")
                if n:
                    adjuntos.append(n)
    pie = ("\n\nAdjuntos (no incluidos): " + ", ".join(adjuntos)) if adjuntos else ""
    return cab + "\n\n" + texto.strip() + pie, adjuntos


def chat_de_zip(ruta):
    """Texto del chat de un .zip exportado de WhatsApp. None si el .zip no es un chat."""
    try:
        with zipfile.ZipFile(ruta) as z:
            chats = [n for n in z.namelist() if n.lower().endswith(".txt") and not n.startswith("__MACOSX")]
            if not chats:
                return None, 0
            principal = sorted(chats, key=lambda n: (not os.path.basename(n).lower().startswith("_chat"), n))[0]
            datos = z.read(principal)
            otros = len([n for n in z.namelist() if not n.endswith("/") and n != principal])
    except zipfile.BadZipFile:
        raise ErrorCorreo("El .zip está dañado o protegido con contraseña.")
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return datos.decode(enc), otros
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1"), otros


def es_chat_zip(ruta):
    try:
        with zipfile.ZipFile(ruta) as z:
            return any(n.lower().endswith(".txt") and not n.startswith("__MACOSX") for n in z.namelist())
    except Exception:
        return False


def _adjuntos(n):
    if not n:
        return ""
    if n == 1:
        return " Su adjunto no se ha tratado: añádelo aparte si hace falta."
    return " Sus %d adjuntos no se han tratado: añádelos aparte si hacen falta." % n


def a_texto(ruta, carpeta):
    """Convierte el correo o el chat a .txt en la carpeta de trabajo. Devuelve (ruta, aviso)."""
    ext = os.path.splitext(ruta)[1].lower()
    aviso = None
    if ext == ".eml":
        texto, adj = eml_a_texto(ruta)
        aviso = "El correo se entrega como texto (.txt)." + _adjuntos(len(adj))
    elif ext == ".msg":
        texto, adj = msg_a_texto(ruta)
        aviso = "El correo de Outlook se entrega como texto (.txt)." + _adjuntos(len(adj))
    elif ext == ".zip":
        texto, otros = chat_de_zip(ruta)
        if texto is None:
            raise ErrorCorreo("El .zip no contiene un chat exportado de WhatsApp.")
        aviso = "Se ha tratado el texto del chat." + (
            " Las fotos, audios u otros archivos del .zip (%d) no se han tratado." % otros if otros > 1 else
            " La foto, audio u otro archivo que trae el .zip no se ha tratado." if otros == 1 else "")
    else:
        raise ErrorCorreo("Formato de correo no admitido: %s" % ext)
    if not texto.strip():
        raise ErrorCorreo("No he encontrado texto en el correo.")
    salida = os.path.join(carpeta, os.path.splitext(os.path.basename(ruta))[0] + ".txt")
    with open(salida, "w", encoding="utf-8") as f:
        f.write(texto)
    return salida, aviso
