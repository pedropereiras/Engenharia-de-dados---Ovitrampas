import sqlite3
from pathlib import Path

if __package__:
    from .config import Config
else:
    from config import Config


class BancoSQLite:
    """Gerencia a conexão, o schema e as consultas no SQLite."""

    DDL = """
CREATE TABLE IF NOT EXISTS distrito_sanitario (
    id_ds      INTEGER PRIMARY KEY,
    descricao  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bairro (
    id_bairro  INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE,
    id_ds      INTEGER NOT NULL REFERENCES distrito_sanitario (id_ds)
);

CREATE TABLE IF NOT EXISTS agente (
    id_agente  INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE,
    matricula  TEXT
);

CREATE TABLE IF NOT EXISTS ovitrampa (
    id_ovt     TEXT PRIMARY KEY,
    id_bairro  INTEGER NOT NULL REFERENCES bairro (id_bairro)
);

CREATE TABLE IF NOT EXISTS tecnico_laboratorio (
    id_tecnico INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS observacao (
    codigo     TEXT PRIMARY KEY,
    descricao  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitoramento_ovitrampa (
    id_registro         INTEGER PRIMARY KEY,
    ano                 INTEGER NOT NULL,
    ciclo               INTEGER NOT NULL,
    id_ovt              TEXT NOT NULL REFERENCES ovitrampa (id_ovt),
    id_agente           INTEGER REFERENCES agente (id_agente),
    id_tecnico          INTEGER REFERENCES tecnico_laboratorio (id_tecnico),
    codigo_obs          TEXT REFERENCES observacao (codigo),
    bairro_area         TEXT,
    qt                  INTEGER,
    dt_coleta           DATE,
    dt_entrega_apoio    DATE,
    dt_entrega_lab      DATE,
    dt_leitura          DATE,
    dt_digitacao        DATE,
    dt_envio_ds         DATE,
    n_ovos              INTEGER,
    UNIQUE (id_ovt, ano, ciclo)
);
"""

    def __init__(self, caminho: Path | str = Config.DB_PATH):
        self.caminho = Path(caminho)
        self.connection: sqlite3.Connection | None = None

    def conectar(self) -> sqlite3.Connection:
        """Abre a conexão (criando a pasta de destino quando necessário).

        Usa ``WAL`` (write-ahead log) e um ``timeout`` generoso para permitir
        que o pipeline reescreva o banco mesmo com a sessão do notebook aberta
        lendo o mesmo arquivo (leitores não bloqueiam o escritor no WAL).
        """
        if self.connection is None:
            if self.caminho.parent and not self.caminho.parent.exists():
                self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.caminho, timeout=30)
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.execute("PRAGMA journal_mode = WAL")
        return self.connection

    @property
    def conexao(self) -> sqlite3.Connection:
        
        return self.conectar()

    def criar_esquema(self) -> None:
        conexao = self.conectar()
        if conexao.in_transaction:
            raise RuntimeError("Não é possível criar o esquema dentro de outra transação.")
        conexao.execute("BEGIN")
        for comando in self.DDL.split(";"):
            if comando.strip():
                conexao.execute(comando)

    def consultar(self, sql: str, params: tuple = ()) -> list[tuple]:
        
        cursor = self.conectar().execute(sql, params)
        linhas = cursor.fetchall()
        cursor.close()
        return linhas

    def fechar(self) -> None:
        
        if self.connection is not None:
            self.connection.close()
            self.connection = None