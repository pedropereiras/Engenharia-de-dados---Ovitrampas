"""Ponto de entrada do projeto: delega a execução para ``src/main.py``.

Camada fina para que o pipeline (definido em ``src/``) possa ser executado
tanto por ``python main.py`` (a partir da raiz) quanto por
``python src/main.py``. Toda a lógica permanece nas classes de ``src/``.
"""

import importlib.util
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))

_espec = importlib.util.spec_from_file_location("etl_ovitrampas", SRC / "main.py")
_etl = importlib.util.module_from_spec(_espec)
_espec.loader.exec_module(_etl)


def main() -> None:
    """Executa o pipeline ETL completo e encerra a conexão com o banco."""
    _etl.Pipeline().executar().fechar()


if __name__ == "__main__":
    main()
