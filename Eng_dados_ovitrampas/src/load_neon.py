import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.engine import Engine, URL, make_url

if __package__:
    from .config import Config
    from .database import BancoSQLite
else:
    from config import Config
    from database import BancoSQLite


TABELAS_NEON = (
    "distrito_sanitario",
    "bairro",
    "agente",
    "ovitrampa",
    "tecnico_laboratorio",
    "observacao",
    "monitoramento_ovitrampa",
)

DDL_NEON = (
    """
    CREATE TABLE IF NOT EXISTS distrito_sanitario (
        id_ds INTEGER PRIMARY KEY,
        descricao TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bairro (
        id_bairro INTEGER PRIMARY KEY,
        nome TEXT NOT NULL UNIQUE,
        id_ds INTEGER NOT NULL REFERENCES distrito_sanitario (id_ds)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agente (
        id_agente INTEGER PRIMARY KEY,
        nome TEXT NOT NULL UNIQUE,
        matricula TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ovitrampa (
        id_ovt TEXT PRIMARY KEY,
        id_bairro INTEGER NOT NULL REFERENCES bairro (id_bairro)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tecnico_laboratorio (
        id_tecnico INTEGER PRIMARY KEY,
        nome TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS observacao (
        codigo TEXT PRIMARY KEY,
        descricao TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS monitoramento_ovitrampa (
        id_registro INTEGER PRIMARY KEY,
        ano INTEGER NOT NULL,
        ciclo INTEGER NOT NULL,
        id_ovt TEXT NOT NULL REFERENCES ovitrampa (id_ovt),
        id_agente INTEGER REFERENCES agente (id_agente),
        id_tecnico INTEGER REFERENCES tecnico_laboratorio (id_tecnico),
        codigo_obs TEXT REFERENCES observacao (codigo),
        bairro_area TEXT,
        qt INTEGER,
        dt_coleta DATE,
        dt_entrega_apoio DATE,
        dt_entrega_lab DATE,
        dt_leitura DATE,
        dt_digitacao DATE,
        dt_envio_ds DATE,
        n_ovos INTEGER,
        UNIQUE (id_ovt, ano, ciclo)
    )
    """,
)


def _url_psycopg(url: str) -> URL:
    
    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    elif parsed.drivername == "postgresql+psycopg2":
        parsed = parsed.set(drivername="postgresql+psycopg")
    elif parsed.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL deve usar o driver PostgreSQL.")
    return parsed


class Load:
   
    def __init__(self):
        load_dotenv(Config.ROOT_DIR / ".env")
        self.access_neon = os.getenv(Config.NEON_DATABASE_URL)
        if not self.access_neon:
            raise RuntimeError(
                "Variável DATABASE_URL não encontrada no arquivo .env."
            )
        self.engine: Engine = create_engine(_url_psycopg(self.access_neon))


class ExportadorNeon:
    """Cria o schema ausente e acrescenta apenas registros ainda não existentes."""

    def __init__(self, banco: BancoSQLite | None = None):
        self.banco = banco or BancoSQLite()
        self.loader = Load()

    def _ler_tabelas(self) -> dict[str, pd.DataFrame]:
        conexao = self.banco.conectar()
        try:
            return {
                nome: pd.read_sql_query(f"SELECT * FROM {nome}", conexao)
                for nome in TABELAS_NEON
            }
        finally:
            self.banco.fechar()

    def exportar_todas(self) -> None:
        self._carregar_dimensional(self._ler_tabelas())

    def _carregar_dimensional(
        self, tabelas: dict[str, pd.DataFrame]
    ) -> None:
        """Cria o schema ausente e insere registros sem duplicar chaves existentes."""
        try:
            with self.loader.engine.begin() as conexao:
                for comando in DDL_NEON:
                    conexao.execute(text(comando))
                metadata = MetaData()
                for nome in TABELAS_NEON:
                    df = tabelas[nome]
                    if df.empty:
                        continue
                    tabela = Table(nome, metadata, autoload_with=conexao)
                    registros = (
                        df.astype("object")
                        .where(pd.notna(df), None)
                        .to_dict(orient="records")
                    )
                    for registro in registros:
                        for coluna, valor in registro.items():
                            if isinstance(valor, pd.Timestamp):
                                registro[coluna] = valor.to_pydatetime()
                    comando = postgres_insert(tabela).on_conflict_do_nothing()
                    for inicio in range(0, len(registros), 1000):
                        conexao.execute(comando, registros[inicio : inicio + 1000])
            print("Dados novos carregados no Neon; registros existentes foram preservados.")
        finally:
            self.loader.engine.dispose()
