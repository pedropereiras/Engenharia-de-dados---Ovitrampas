"""Extensão do pipeline para carregar dados também no Neon (Postgres).

Pode ser executado para enviar as tabelas já tratadas (a partir do SQLite
gerado) ou pode ser integrado ao ``main.py`` conforme desejado.
"""

from src.database import BancoSQLite
from src.load_neon import ExportadorNeon


def main() -> None:
    print("Exportando tabelas tratadas do SQLite para o Neon (DATABASE_URL)...")
    ExportadorNeon(BancoSQLite()).exportar_todas()
    print("Concluído!")


if __name__ == "__main__":
    main()
