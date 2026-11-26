# -*- coding: utf-8 -*-
"""Cifrado de las tablas de correspondencias.

Cada proyecto tiene su propia clave (Fernet: AES-128-CBC + HMAC-SHA256). La clave se guarda en
el almacén de credenciales del sistema: el Llavero (Keychain) en Mac y el Administrador de
credenciales en Windows. Si el almacén no está disponible, la clave se guarda en un archivo de
la carpeta de datos con permisos solo para el usuario, y la aplicación lo advierte."""
import base64
import os
import stat

from cryptography.fernet import Fernet, InvalidToken

import rutas

SERVICIO = "Seudónimo"
SERVICIO_ANTERIOR = "Áurea Asistente Local"   # nombre de la aplicación hasta la 0.1.x

try:
    import keyring
    from keyring.errors import KeyringError
except Exception:  # noqa
    keyring = None
    KeyringError = Exception


class ErrorCifrado(Exception):
    pass


def _archivo_clave(proyecto):
    return os.path.join(rutas.PROYECTOS, str(proyecto), ".clave")


def _almacen_sistema():
    """True si hay un almacén de credenciales real (el de «fallo» de keyring tiene prioridad 0)."""
    if keyring is None:
        return False
    try:
        return getattr(keyring.get_keyring(), "priority", 0) > 0
    except Exception:
        return False


def donde_se_guarda_la_clave():
    return "almacén de credenciales del sistema" if _almacen_sistema() else "archivo local protegido"


def clave(proyecto, crear=True):
    usuario = "proyecto-%s" % proyecto
    if _almacen_sistema():
        try:
            k = keyring.get_password(SERVICIO, usuario)
            if k:
                return k.encode()
            k = keyring.get_password(SERVICIO_ANTERIOR, usuario)
            if k:                     # clave creada con el nombre anterior: se pasa al nuevo
                try:
                    keyring.set_password(SERVICIO, usuario, k)
                    keyring.delete_password(SERVICIO_ANTERIOR, usuario)
                except Exception:
                    pass
                return k.encode()
            if not crear:
                return None
            k = Fernet.generate_key()
            keyring.set_password(SERVICIO, usuario, k.decode())
            return k
        except KeyringError:
            pass
        except Exception:
            pass
    ruta = _archivo_clave(proyecto)
    if os.path.isfile(ruta):
        return open(ruta, "rb").read().strip()
    if not crear:
        return None
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    k = Fernet.generate_key()
    with open(ruta, "wb") as f:
        f.write(k)
    try:
        os.chmod(ruta, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return k


def borrar_clave(proyecto):
    """Al borrar la clave, la tabla cifrada deja de poder leerse (borrado criptográfico)."""
    if keyring is not None:
        try:
            keyring.delete_password(SERVICIO, "proyecto-%s" % proyecto)
        except Exception:
            pass
        try:
            keyring.delete_password(SERVICIO_ANTERIOR, "proyecto-%s" % proyecto)
        except Exception:
            pass
    try:
        os.remove(_archivo_clave(proyecto))
    except OSError:
        pass


def cifrar(proyecto, datos: bytes) -> bytes:
    return Fernet(clave(proyecto)).encrypt(datos)


def descifrar(proyecto, datos: bytes) -> bytes:
    k = clave(proyecto, crear=False)
    if not k:
        raise ErrorCifrado("No encuentro la clave de este proyecto: la tabla no se puede abrir.")
    try:
        return Fernet(k).decrypt(datos)
    except InvalidToken:
        raise ErrorCifrado("La tabla de correspondencias no corresponde a la clave de este proyecto o está dañada.")


def huella(datos: bytes) -> str:
    import hashlib
    return base64.b32encode(hashlib.sha256(datos).digest()[:10]).decode().rstrip("=")
