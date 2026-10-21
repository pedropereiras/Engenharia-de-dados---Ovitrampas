"""Etapa de extração: leitura do arquivo de origem (Excel ou CSV)."""

from pathlib import Path

import pandas as pd

from config import ARQUIVO_ENTRADA, COLUNAS_PADRAO, PLANILHA


def ler_arquivo_bruto(
    caminho: Path = ARQUIVO_ENTRADA, planilha: str = PLANILHA
) -> pd.DataFrame:
    """Lê o arquivo de origem e devolve um DataFrame com colunas padronizadas.

    O cabeçalho da última coluna da origem (OBS) contém uma legenda embutida;
    as colunas são renomeadas para a lista padronizada do ``config``.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {caminho}")

    sufixo = caminho.suffix.lower()
    if sufixo == ".xlsx":
        df = pd.read_excel(caminho, sheet_name=planilha)
    elif sufixo == ".csv":
        df = pd.read_csv(caminho, sep=";", decimal=",", dtype=str)
    else:
        raise ValueError(f"Formato de arquivo não suportado: {sufixo}")

    df.columns = COLUNAS_PADRAO[: len(df.columns)]
    return df