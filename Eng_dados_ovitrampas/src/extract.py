from pathlib import Path

import pandas as pd

if __package__:
    from .config import Config
else:
    from config import Config


COLUNAS_ORIGEM = (
    "ANO",
    "CICLOS",
    "DS",
    "BAIRRO",
    "BAIRRO_AREA",
    "AGENTE / MATRICULA",
    "QT",
    "ID_OVT",
    "DT_COLETA",
    "DT_ENTREGA_APOIO",
    "DT_ENTREGA_LAB",
    "DT_LEITURA",
    "NM_TEC_LAB",
    "DT_DIG",
    "DT_ENVIO_DS",
    "N_OVOS",
)


class Extrator:
    

    def __init__(
        self,
        caminho: Path | str | None = None,
        planilha: str = Config.PLANILHA,
    ):
        if caminho is None:
            caminho = (
                Config.ARQUIVO_ENTRADA
                if Config.ARQUIVO_ENTRADA.exists()
                else Config.ARQUIVO_CSV
            )
        self.caminho = Path(caminho)
        self.planilha = planilha
        self.df: pd.DataFrame | None = None

    def ler(self) -> pd.DataFrame:
        
        if not self.caminho.exists():
            raise FileNotFoundError(f"Arquivo de entrada não encontrado: {self.caminho}")

        sufixo = self.caminho.suffix.lower()
        if sufixo == ".xlsx":
            df = pd.read_excel(self.caminho, sheet_name=self.planilha)
        elif sufixo == ".csv":
            df = pd.read_csv(self.caminho, sep=";", decimal=",", dtype=str)
        else:
            raise ValueError(f"Formato de arquivo não suportado: {sufixo}")

        cabecalhos = [
            " ".join(str(coluna).replace("\n", " ").upper().split())
            for coluna in df.columns
        ]
        cabecalhos_esperados = list(COLUNAS_ORIGEM)
        if (
            len(cabecalhos) != len(Config.COLUNAS_PADRAO)
            or tuple(cabecalhos[: len(COLUNAS_ORIGEM)]) != COLUNAS_ORIGEM
            or not cabecalhos[-1].startswith("OBS")
        ):
            raise ValueError(
                f"Cabeçalho inesperado em '{self.caminho.name}'. "
                f"Esperadas as colunas de origem {cabecalhos_esperados} "
                "seguidas pela coluna OBS."
            )
        df.columns = Config.COLUNAS_PADRAO
        self.df = df
        return df