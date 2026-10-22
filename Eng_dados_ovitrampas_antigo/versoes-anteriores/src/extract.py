from pathlib import Path

import pandas as pd

from config import Config


class Extrator:
    """Responsável por ler o arquivo bruto e padronizar os nomes das colunas."""

    def __init__(
        self,
        caminho: Path | str = Config.ARQUIVO_ENTRADA,
        planilha: str = Config.PLANILHA,
    ):
        self.caminho = Path(caminho)
        self.planilha = planilha
        self.df: pd.DataFrame | None = None

    def ler(self) -> pd.DataFrame:
        """Lê o arquivo de origem e devolve um DataFrame com colunas padronizadas.

        O cabeçalho da última coluna da origem (OBS) contém uma legenda embutida;
        as colunas são renomeadas para a lista padronizada do ``Config``.
        """
        if not self.caminho.exists():
            raise FileNotFoundError(f"Arquivo de entrada não encontrado: {self.caminho}")

        sufixo = self.caminho.suffix.lower()
        if sufixo == ".xlsx":
            df = pd.read_excel(self.caminho, sheet_name=self.planilha)
        elif sufixo == ".csv":
            df = pd.read_csv(self.caminho, sep=";", decimal=",", dtype=str)
        else:
            raise ValueError(f"Formato de arquivo não suportado: {sufixo}")

        if len(df.columns) != len(Config.COLUNAS_PADRAO):
            raise ValueError(
                f"Esperadas {len(Config.COLUNAS_PADRAO)} colunas em "
                f"'{self.caminho.name}', mas o arquivo tem {len(df.columns)}. "
                "Confira se o cabeçalho da origem mudou."
            )
        df.columns = Config.COLUNAS_PADRAO
        self.df = df
        return df