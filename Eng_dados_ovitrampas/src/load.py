"""Etapa de carga: inserção das tabelas tratadas no banco SQLite."""

import sqlite3

import pandas as pd


def _registros_para_insert(df: pd.DataFrame) -> list[tuple]:
    """Converte o DataFrame em tuplas com nulos tratados (NA/NaT -> None)."""
    dados = df.astype("object").where(pd.notna(df), None)
    registros = []
    for linha in dados.itertuples(index=False, name=None):
        valores = []
        for valor in linha:
            if pd.isna(valor):
                valores.append(None)
            elif hasattr(valor, "date"):
                valores.append(valor.date().isoformat())
            else:
                valores.append(valor)
        registros.append(tuple(valores))
    return registros


def carregar_tabelas(
    conexao: sqlite3.Connection, tabelas: dict[str, pd.DataFrame]
) -> None:
    """Insere os DataFrames nas respectivas tabelas já criadas no banco."""
    cursor = conexao.cursor()
    for nome, df in tabelas.items():
        if df.empty:
            continue
        colunas = ", ".join(df.columns)
        marcadores = ", ".join("?" * len(df.columns))
        sql = f"INSERT INTO {nome} ({colunas}) VALUES ({marcadores})"
        cursor.executemany(sql, _registros_para_insert(df))
    conexao.commit()
    cursor.close()