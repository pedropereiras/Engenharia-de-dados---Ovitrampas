"""Carregamento de dados no Neon (Postgres) via SQLAlchemy.

Baseado no padrão apresentado na Aula 8. Lê as tabelas tratadas (modelo
dimensional) do SQLite e as envia para o Neon utilizando ``pandas.to_sql``.

Variável de ambiente esperada: ``DATABASE_URL`` no arquivo ``.env``.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config import Config
from database import BancoSQLite


class Load:
    """Classe de carregamento com suporte ao Neon (Postgres)."""

    def __init__(self):
        load_dotenv(Config.ROOT_DIR / ".env")
        self.mongo_uri = os.getenv("MONGO_URI")
        self.access_neon = os.getenv(Config.NEON_DATABASE_URL) or os.getenv(
            "DATABASE_URL"
        )
        self.client = None
        self.engine: Engine | None = None

        if self.access_neon:
            self.engine = create_engine(self.access_neon)

    def load_neon(self, df: pd.DataFrame, nome_tabela: str) -> None:
        """Carrega um DataFrame como tabela no Neon."""
        if self.engine is None:
            raise RuntimeError(
                "Variável DATABASE_URL não encontrada no arquivo .env."
            )
        df.to_sql(nome_tabela, self.engine, if_exists="replace", index=False)
        print(f"Dados salvos no Neon com sucesso na tabela '{nome_tabela}'!")


class ExportadorNeon:
    """Exporta tabelas tratadas do SQLite para o Neon."""

    def __init__(self, banco: BancoSQLite | None = None):
        self.banco = banco or BancoSQLite()
        self.loader = Load()

    def _ler_tabela(self, nome_tabela: str) -> pd.DataFrame:
        self.banco.conectar()
        df = pd.read_sql_query(f"SELECT * FROM {nome_tabela}", self.banco.conexao)
        self.banco.fechar()
        return df

    def exportar_todas(self, tabelas: list[str] | None = None) -> None:
        tabelas = tabelas or [
            "distrito_sanitario",
            "bairro",
            "agente",
            "ovitrampa",
            "tecnico_laboratorio",
            "observacao",
            "monitoramento_ovitrampa",
        ]
        for nome in tabelas:
            df = self._ler_tabela(nome)
            self.loader.load_neon(df, nome)
        if self.loader.engine is not None:
            self.loader.engine.dispose()
