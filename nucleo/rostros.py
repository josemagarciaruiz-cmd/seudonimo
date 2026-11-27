# -*- coding: utf-8 -*-
"""Caras en las imágenes, siempre en el propio ordenador.

En Mac se usa la detección de caras del sistema (Vision). En Windows, OpenCV con el modelo
YuNet (licencia MIT, 230 KB, va en nucleo/modelos). Si no hay ninguno de los dos, no se detecta
nada y se avisa (DISPONIBLE = False).

Devuelve rectángulos en píxeles de la imagen, ya ampliados para cubrir pelo, frente y barbilla:
una foto de carné tapada a medias sigue identificando."""
import io
import os

MODELO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelos", "face_detection_yunet_2023mar.onnx")
MARCA = "[CARA]"
LADO_MAX = 1600        # las imágenes grandes se reducen para detectar (más rápido y igual de fiable)
MARGEN = 0.30          # ampliación de cada cara por cada lado

try:
    import Vision  # noqa: F401  (solo en Mac)
    from Foundation import NSData
    _VISION = True
except Exception:  # pragma: no cover
    _VISION = False

try:
    import cv2  # noqa: F401
    import numpy as np  # noqa: F401
    try:
        cv2.setLogLevel(0)
    except Exception:  # noqa
        pass
    _CV = True
except Exception:  # pragma: no cover
    _CV = False

if os.environ.get("SEUDONIMO_CARAS") == "opencv":
    _VISION = False
MOTOR = "Vision" if _VISION else ("YuNet" if _CV and os.path.isfile(MODELO) else ("Haar" if _CV else None))
DISPONIBLE = MOTOR is not None


def _vision(img):
    import Vision
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    datos = NSData.dataWithBytes_length_(png, len(png))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(datos, None)
    req = Vision.VNDetectFaceRectanglesRequest.alloc().init()
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        return []
    W, H = img.size
    res = []
    for obs in list(req.results() or []):
        bb = obs.boundingBox()
        x, y, w, h = bb.origin.x, bb.origin.y, bb.size.width, bb.size.height
        res.append((x * W, (1 - y - h) * H, (x + w) * W, (1 - y) * H))
    return res


_YUNET = None


def _yunet(img):
    global _YUNET
    import cv2
    import numpy as np
    arr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    h, w = arr.shape[:2]
    if _YUNET is None:
        _YUNET = cv2.FaceDetectorYN.create(MODELO, "", (w, h), 0.75, 0.3, 5000)
    _YUNET.setInputSize((w, h))
    _, caras = _YUNET.detect(arr)
    if caras is None:
        return []
    return [(float(c[0]), float(c[1]), float(c[0] + c[2]), float(c[1] + c[3])) for c in caras]


def _haar(img):
    import cv2
    import numpy as np
    gris = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    res = []
    for nombre in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        ruta = os.path.join(cv2.data.haarcascades, nombre)
        if not os.path.isfile(ruta):
            continue
        clas = cv2.CascadeClassifier(ruta)
        lado = max(24, min(gris.shape[:2]) // 20)
        for (x, y, w, h) in clas.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=6, minSize=(lado, lado)):
            res.append((float(x), float(y), float(x + w), float(y + h)))
    return res


def caras(img):
    """Caras de una imagen PIL: [(x0, y0, x1, y1)] en píxeles, ampliadas."""
    if not DISPONIBLE or img is None:
        return []
    W, H = img.size
    if W < 24 or H < 24:
        return []
    f = 1.0
    trabajo = img
    if max(W, H) > LADO_MAX:
        f = LADO_MAX / float(max(W, H))
        trabajo = img.resize((max(1, int(W * f)), max(1, int(H * f))))
    trabajo = trabajo.convert("RGB")
    try:
        if MOTOR == "Vision":
            cajas = _vision(trabajo)
        elif MOTOR == "YuNet":
            cajas = _yunet(trabajo)
        else:
            cajas = _haar(trabajo)
    except Exception:  # noqa  (un fallo del detector no debe parar la seudonimización)
        return []
    res = []
    for x0, y0, x1, y1 in cajas:
        x0, y0, x1, y1 = x0 / f, y0 / f, x1 / f, y1 / f
        mx, my = (x1 - x0) * MARGEN, (y1 - y0) * MARGEN
        res.append((max(0.0, x0 - mx), max(0.0, y0 - my * 1.6), min(float(W), x1 + mx), min(float(H), y1 + my)))
    return res
