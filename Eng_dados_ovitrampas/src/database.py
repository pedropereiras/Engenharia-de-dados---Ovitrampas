"""Criação da estrutura (schema) do banco SQLite."""

import sqlite3
from pathlib import Path

from config import DB_PATH

DDL = """
DROP TABLE IF EXISTS monitoramento_ovitrampa;
DROP TABLE IF EXISTS observacao;
DROP TABLE IF EXISTS ovitrampa;
DROP TABLE IF EXISTS tecnico_laboratorio;
DROP TABLE IF EXISTS agente;
DROP TABLE IF EXISTS bairro;
DROP TABLE IF EXISTS distrito_sanitario;

CREATE TABLE distrito_sanitario (
    id_ds      INTEGER PRIMARY KEY,
    descricao  TEXT NOT NULL
);

CREATE TABLE bairro (
    id_bairro  INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE,
    id_ds      INTEGER NOT NULL REFERENCES distrito_sanitario (id_ds)
);

CREATE TABLE agente (
    id_agente  INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE,
    matricula  TEXT
);

CREATE TABLE ovitrampa (
    id_ovt     TEXT PRIMARY KEY,
    id_bairro  INTEGER NOT NULL REFERENCES bairro (id_bairro)
);

CREATE TABLE tecnico_laboratorio (
    id_tecnico INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE
);

CREATE TABLE observacao (
    codigo     TEXT PRIMARY KEY,
    descricao  TEXT NOT NULL
);

CREATE TABLE monitoramento_ovitrampa (
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
    UNIQUE (id_ovt, ciclo)
);
"""


def conectar(caminho: Path | str = DB_PATH) -> sqlite3.Connection:
    """Abre a conexão com o banco, criando a pasta de destino quando necessário."""
    caminho = Path(caminho)
    if caminho.parent and not caminho.parent.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_esquema(conexao: sqlite3.Connection) -> None:
    """Cria (recriando) toda a estrutura de tabelas do banco."""
    conexao.executescript(DDL)
    conexao.commit()