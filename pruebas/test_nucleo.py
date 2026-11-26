# -*- coding: utf-8 -*-
"""Pruebas unitarias del núcleo (sin modelo): python -m pytest pruebas"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nucleo"))
os.environ.setdefault("AUREA_DATOS", tempfile.mkdtemp())

import motor  # noqa: E402
import registro  # noqa: E402


def test_etiquetas_estables_y_variantes():
    r = registro.Registro(1)
    r.incorporar([{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA"}, {"texto": "FERRER GIL, LUCÍA", "tipo": "PERSONA"},
                  {"texto": "12345678Z", "tipo": "DNI"}])
    r.incorporar([{"texto": "12.345.678-Z", "tipo": "DNI"}])
    marcadores = {e["marcador"] for e in r.entidades}
    assert marcadores == {"[PERSONA_001]", "[DNI_001]"}
    t = motor.reemplazar_texto("Doña Lucía Ferrer Gil (DNI 12 345 678 Z). Ferrer Gil, Lucía.", r.mapa())
    assert "Ferrer" not in t and "12" not in t


def test_no_fusiona_homonimos_ni_nombres_de_pila():
    r = registro.Registro(1)
    r.incorporar([{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA"}, {"texto": "Marcos Ferrer Cabrera", "tipo": "PERSONA"}])
    n = r.incorporar([{"texto": "Ferrer", "tipo": "PERSONA"}, {"texto": "Lucía", "tipo": "PERSONA"}])
    assert all(x["marcador"] not in ("[PERSONA_001]", "[PERSONA_002]") for x in n)
    assert r.entidades[-2].get("ambigua")


def test_descartados_no_vuelven():
    r = registro.Registro(1)
    r.incorporar([{"texto": "Oficina Técnica", "tipo": "DEPARTAMENTO"}])
    r.descartar(0)
    assert r.incorporar([{"texto": "Oficina Técnica", "tipo": "DEPARTAMENTO"}]) == []
    assert r.mapa() == []


def test_marcadores_no_son_datos():
    assert motor.detectar_regex("Código [CSV_001] y [PERSONA_002]") == []
    assert motor.MARCADOR_OCR.sub("#", "CSV: tcsv_001") == "CSV: #"
    assert motor.MARCADOR_OCR.sub("#", "persona 12 años") == "persona 12 años"
    # lecturas reales del OCR de Vision sobre marcadores tachados (regresión del 26/11/2026)
    for leido in ("ICCC.0011", "C.C.C.: ICCC.0011", "(PERSONA_002)", "[DNI.003]", "lIBAN_0011", "[CSV_001]"):
        assert "CCC" not in motor.MARCADOR_OCR.sub("#", leido).replace("C.C.C.", "")
        assert not motor.detectar_regex(motor.MARCADOR_OCR.sub(lambda m: " " * len(m.group(0)), leido))


def test_fragmentar_con_desfase_cambia_los_cortes():
    texto = "\n".join("línea %d con algo de texto" % i for i in range(400))
    a = motor.fragmentar(texto)
    b = motor.fragmentar(texto, desfase=1250)
    assert "".join(a) == "".join(b) == texto + "\n"
    assert len(a[0]) != len(b[0])


def test_cifrado_ida_y_vuelta():
    import cifrado
    datos = registro.Registro(7)
    datos.incorporar([{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA"}])
    sellado = cifrado.cifrar(7, datos.a_bytes())
    assert b"Ferrer" not in sellado
    otra = registro.Registro.de_bytes(cifrado.descifrar(7, sellado), 7)
    assert otra.buscar("Lucía Ferrer Gil")["marcador"] == "[PERSONA_001]"
    cifrado.borrar_clave(7)
