# -*- coding: utf-8 -*-
"""SBOM CycloneDX 1.5 (JSON) de lo que se redistribuye: paquetes de Python del intérprete
incluido y crates de Rust de la ventana (Cargo.lock).

Uso:  <python del paquete> empaquetado/sbom.py <Cargo.lock> <salida.json>
Se ejecuta con el Python que va dentro del instalador, para inventariar exactamente sus paquetes."""
import json
import sys
import time
import uuid
from importlib import metadata


def licencia(dist):
    m = dist.metadata
    lic = m.get("License-Expression") or ""
    if not lic:
        clas = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
        lic = "; ".join(clas) or (m.get("License") or "").split("\n")[0][:120]
    return lic


def componentes_python():
    res = []
    for d in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        n, v = d.metadata["Name"], d.version
        c = {"type": "library", "name": n, "version": v, "purl": "pkg:pypi/%s@%s" % (n.lower(), v)}
        lic = licencia(d)
        if lic:
            c["licenses"] = [{"license": {"name": lic}}]
        res.append(c)
    res.append({"type": "application", "name": "python", "version": "%d.%d.%d" % sys.version_info[:3],
                "licenses": [{"license": {"id": "PSF-2.0"}}]})
    return res


def componentes_rust(lock):
    res, actual = [], {}
    for linea in open(lock, encoding="utf-8"):
        linea = linea.strip()
        if linea == "[[package]]":
            if actual.get("name"):
                res.append(actual)
            actual = {}
        elif "=" in linea and not linea.startswith("["):
            k, v = [x.strip() for x in linea.split("=", 1)]
            if k in ("name", "version"):
                actual[k] = v.strip('"')
    if actual.get("name"):
        res.append(actual)
    return [{"type": "library", "name": p["name"], "version": p["version"],
             "purl": "pkg:cargo/%s@%s" % (p["name"], p["version"])} for p in res]


if __name__ == "__main__":
    lock, salida = sys.argv[1], sys.argv[2]
    bom = {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": "urn:uuid:%s" % uuid.uuid4(), "version": 1,
           "metadata": {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "component": {"type": "application", "name": "Áurea Asistente Local"}},
           "components": componentes_python() + componentes_rust(lock)}
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(bom, f, ensure_ascii=False, indent=1)
    print("%d componentes" % len(bom["components"]))
