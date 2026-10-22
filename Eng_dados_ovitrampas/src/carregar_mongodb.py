import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

if __package__:
    from .config import Config
    from .extract import Extrator
    from .transform import Transformador
else:
    from config import Config
    from extract import Extrator
    from transform import Transformador


class ExportadorMongoDB:

    def __init__(
        self,
        uri: str | None = None,
        arquivo: Path | str = Config.ARQUIVO_CSV,
    ):
        self.uri = uri
        self.arquivo = Path(arquivo)
        self.documentos: list[dict] = []

    # ------------------------------------------------------------ tratamento

    def tratar(self, df: pd.DataFrame) -> pd.DataFrame:
        
        transformador = Transformador(df)
        transformador.executar()
        return transformador.df.drop(columns=["agente_norm"])

    # --------------------------------------------------------------- conversão

    def para_mongo(self, df: pd.DataFrame) -> list[dict]:
        
        documentos = []
        for registro in df.to_dict(orient="records"):
            doc = {}
            for chave, valor in registro.items():
                if pd.isna(valor):
                    doc[chave] = None
                elif isinstance(valor, pd.Timestamp):
                    doc[chave] = valor.to_pydatetime()
                elif isinstance(valor, float) and float(valor).is_integer():
                    doc[chave] = int(valor)
                else:
                    doc[chave] = valor
            documentos.append(doc)
        self.documentos = documentos
        return documentos

    # --------------------------------------------------------------- execução

    def executar(self) -> None:
        
        load_dotenv(Config.ROOT_DIR / ".env")
        uri = self.uri or os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError(
                "Variável MONGODB_URI não encontrada. Crie o arquivo .env na raiz "
                "do projeto com a connection string do Atlas."
            )

        bruto = Extrator(self.arquivo).ler()
        df = self.tratar(bruto)
        documentos = self.para_mongo(df)
        print(f"Arquivo lido com {len(documentos)} registros.")

        with MongoClient(uri) as cliente:
            colecao = cliente[Config.MONGO_BANCO][Config.MONGO_COLECAO]
            colecao.delete_many({})
            colecao.insert_many(documentos, ordered=False)
            print(f"Inseridos: {colecao.count_documents({})} documentos.")
            print(f"Banco '{Config.MONGO_BANCO}' / coleção '{Config.MONGO_COLECAO}' "
                  "no MongoDB Atlas.")
            print("Amostra:", colecao.find_one({}, {"_id": 0}))


if __name__ == "__main__":
    ExportadorMongoDB().executar()
