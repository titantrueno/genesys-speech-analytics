#!/usr/bin/env python3
"""Exporta el OpenAPI completo de la API a `backend/openapi.yaml`.

Uso: `python scripts/export_openapi.py` (regenera) o `python scripts/export_openapi.py --check` (código 1 si el
fichero no coincide con el de la app). El test `tests/test_openapi.py` exige que esté al día.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
TARGET = BACKEND / "openapi.yaml"
HEADER = "# Generado por scripts/export_openapi.py a partir de la app FastAPI. No editar a mano.\n"


def main() -> int:
    # El esquema no depende del dataset, pero importar la app lo necesita configurado.
    os.environ.setdefault("DATA_SEED", "42")
    os.environ.setdefault("DATA_REFERENCE_DATE", "2026-09-27")
    sys.path.insert(0, str(BACKEND))
    import yaml
    from app.main import app

    content = HEADER + yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False, width=120)
    if "--check" in sys.argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != content:
            print(f"{TARGET.relative_to(BACKEND.parent)} está desactualizado: ejecuta python scripts/export_openapi.py")
            return 1
        print(f"{TARGET.relative_to(BACKEND.parent)} al día.")
        return 0
    TARGET.write_text(content, encoding="utf-8")
    print(f"Escrito {TARGET.relative_to(BACKEND.parent)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
