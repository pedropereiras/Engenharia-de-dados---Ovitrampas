"""Carrega o CSV de ovitrampas no MongoDB Atlas.

Requisitos:
    1. Criar um cluster gratuito (M0) no MongoDB Atlas;
    2. Criar um usuário (username/senha) em Database Access;
    3. Liberar acesso de IP (em Network Access permitir o seu IP, ou 0.0.0.0/0
       em ambiente de teste);
    4. Copiar a connection string (mongodb+srv://...);
    5. Gravar a URI no arquivo .env do projeto:

        MONGODB_URI=mongodb+srv://usuario:senha@grupo123.xxxxx.mongodb.net/?retryWrites=true&w=majority

Depois é só executar:  python src/carregar_mongodb.py
"""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parent.parent
ARQUIVO_ENTRADA = ROOT_DIR / "dados" / "entrada" / "ovitrampas_2026.csv"

BANCO = "ovitrampas"
COLECAO = "monitoramento"

COLUNAS_DATA = [
    "dt_coleta", "dt_entrega_apoio", "dt_entrega_lab", "dt_leitura",
    "dt_digitacao", "dt_envio_ds",
]
DS_ROMANOS = {
    "I": 1, "II": 2, "III": 3, "IV": 4,
    "V": 5, "VI": 6, "VII": 7, "VIII": 8,
}


def tratar(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica o mesmo tratamento do pipeline antes de enviar ao MongoDB."""
    df = df.rename(columns=lambda c: c.strip().lower().replace(" ", "_"))
    df.columns = [
        "ano", "ciclo", "ds", "bairro", "bairro_area", "agente_matricula",
        "qt", "id_ovt", "dt_coleta", "dt_entrega_apoio", "dt_entrega_lab",
        "dt_leitura", "nm_tecnico_lab", "dt_digitacao", "dt_envio_ds",
        "n_ovos", "obs",
    ][: len(df.columns)]

    for col in ["bairro", "bairro_area", "agente_matricula", "nm_tecnico_lab", "id_ovt", "obs"]:
        df[col] = df[col].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA})

    df["ds"] = df["ds"].astype("string").str.strip().map(DS_ROMANOS)

    df["dt_envio_ds"] = df["dt_envio_ds"].replace(" ", pd.NA)
    for col in COLUNAS_DATA:
        df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")

    df["n_ovos"] = pd.to_numeric(df["n_ovos"].astype("string").replace({" ": pd.NA}), errors="coerce")
    df["qt"] = pd.to_numeric(df["qt"].astype("string").replace({" ": pd.NA}), errors="coerce")

    partes = df["agente_matricula"].str.split("/", n=1, expand=True)
    df["agente"] = partes[0].str.strip().str.replace(r"\s+", " ", regex=True)
    df["matricula"] = partes[1].astype("string").str.strip().replace("S/M", pd.NA)

    # matrícula "colada" ao nome sem a barra (ex.: ANGÉLICA BRITO79.718-0)
    sem_barra = ~df["agente_matricula"].str.contains("/", na=False)
    extraido = df.loc[sem_barra, "agente_matricula"].str.extract(
        r"^(.+?)(\d+\.\d+-\d)$"
    )
    df.loc[sem_barra, "agente"] = extraido[0].fillna(df.loc[sem_barra, "agente"])
    df.loc[sem_barra, "matricula"] = extraido[1]

    # placeholders de "área sem agente responsável" viram ausentes
    df.loc[df["agente"].isin(["DESCOBERTA", "ÁREA DESCOBERTA"]), ["agente", "matricula"]] = pd.NA
    return df


def para_mongo(df: pd.DataFrame) -> list[dict]:
    """Converte o DataFrame em documentos BSON (datetime e numéricos corretos)."""
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
    return documentos


def principal() -> None:
    load_dotenv(ROOT_DIR / ".env")
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError(
            "Variável MONGODB_URI não encontrada. Crie o arquivo .env na raiz "
            "do projeto com a connection string do Atlas."
        )

    df = tratar(pd.read_csv(ARQUIVO_ENTRADA, sep=";"))
    documentos = para_mongo(df)
    print(f"CSV lido com {len(documentos)} registros.")

    with MongoClient(uri) as cliente:
        colecao = cliente[BANCO][COLECAO]
        colecao.delete_many({})
        colecao.insert_many(documentos, ordered=False)
        print(f"Inseridos: {colecao.count_documents({})} documentos.")
        print(f"Banco '{BANCO}' / coleção '{COLECAO}' no MongoDB Atlas.")
        print("Amostra:", colecao.find_one({}, {"_id": 0}))


if __name__ == "__main__":
    principal()