"""Extensão do pipeline para carregar dados também no Neon (Postgres).

Pode ser executado para enviar as tabelas já tratadas (a partir do SQLite
gerado) ou pode ser integrado ao ``main.py`` conforme desejado.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))

try:
    from load_neon import ExportadorNeon
    from database import BancoSQLite
except Exception:
    # fallback
    from src.load_neon import ExportadorNeon
    from src.database import BancoSQLite


def main() -> None:
    print("Exportando tabelas tratadas do SQLite para o Neon (DATABASE_URL)...")
    ExportadorNeon(BancoSQLite()).exportar_todas()
    print("Concluído!")


if __name__ == "__main__":
    main()
