"""Etapa de transformação: limpeza, ajuste de tipos e organização em tabelas.

A origem é normalizada no modelo dimensional:
- dimensões: ``distrito_sanitario``, ``bairro``, ``agente``, ``ovitrampa``,
  ``tecnico_laboratorio`` e ``observacao``;
- fato: ``monitoramento_ovitrampa``.
"""

import re
import unicodedata

import pandas as pd

from config import DS_ROMANOS, OBSERVACOES

PADRAO_MATRICULA = re.compile(r"^(.+?)(\d+\.\d+-\d)$")
AGENTES_PLACEHOLDER = {"DESCOBERTA", "ÁREA DESCOBERTA"}

COLUNAS_DATA = [
    "dt_coleta",
    "dt_entrega_apoio",
    "dt_entrega_lab",
    "dt_leitura",
    "dt_digitacao",
    "dt_envio_ds",
]

COLUNAS_TEXTO = [
    "bairro",
    "bairro_area",
    "agente_matricula",
    "nm_tecnico_lab",
    "obs",
    "id_ovt",
]


def _limpar_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espaços extras e converte células vazias/em-branco para nulos."""
    for coluna in COLUNAS_TEXTO:
        df[coluna] = (
            df[coluna]
            .astype("string")
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
            .replace({"": pd.NA, "nan": pd.NA})
        )
    df["ds"] = df["ds"].astype("string").str.strip()
    return df


def _ajustar_datas(df: pd.DataFrame) -> pd.DataFrame:
    """Converte as colunas de data para datetime (valores inválidos viram nulos)."""
    for coluna in COLUNAS_DATA:
        df[coluna] = (
            df[coluna]
            .astype("string")
            .replace({"": pd.NA, " ": pd.NA, "nan": pd.NA})
        )
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce", format="mixed")
    return df


def _ajustar_numeros(df: pd.DataFrame) -> pd.DataFrame:
    """Converte ``n_ovos`` e ``qt`` para numérico (células em-branco viram nulos)."""
    df["n_ovos"] = pd.to_numeric(
        df["n_ovos"].astype("string").replace({"": pd.NA, " ": pd.NA}), errors="coerce"
    )
    df["qt"] = pd.to_numeric(
        df["qt"].astype("string").replace({"": pd.NA, " ": pd.NA}), errors="coerce"
    )
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("int64")
    df["ciclo"] = pd.to_numeric(df["ciclo"], errors="coerce").astype("int64")
    return df


def _normalizar_nome(nome) -> str | None:
    """Remove acentos, caixa alta e espaços duplicados (usado para agrupar agentes).

    A grafia original é preservada na tabela; somente a comparação é normalizada.
    """
    if not isinstance(nome, str) or not nome:
        return nome
    sem_acento = "".join(
        ch
        for ch in unicodedata.normalize("NFD", nome)
        if unicodedata.category(ch) != "Mn"
    )
    return " ".join(sem_acento.upper().split())


def diagnosticar_limpeza(
    bruto: pd.DataFrame, df: pd.DataFrame, n_agentes: int
) -> dict[str, int]:
    """Mede o impacto das limpezas aplicadas (retorna contagens para relatório)."""
    raw_agente = bruto["agente_matricula"].astype("string").str.strip()
    sem_barra = ~raw_agente.str.contains("/", na=False)
    coladas = int(raw_agente[sem_barra].str.extract(PADRAO_MATRICULA)[1].notna().sum())
    return {
        "linhas": len(bruto),
        "placeholders_removidos": int(raw_agente.isin(AGENTES_PLACEHOLDER).sum()),
        "matriculas_coladas_extraidas": coladas,
        "sem_matricula": int((df["agente"].notna() & df["matricula"].isna()).sum()),
        "datas_vazias_invalidas": int(df[COLUNAS_DATA].isna().sum().sum()),
        "n_ovos_alto_mil": int((df["n_ovos"] > 1000).sum()),
        "agentes_total": n_agentes,
        "agentes_unificados": int(
            df.loc[df["agente"].notna(), "agente"].nunique()
            - df.loc[df["agente"].notna(), "agente_norm"].nunique()
        ),
    }


def _separar_agente_matricula(df: pd.DataFrame) -> pd.DataFrame:
    """Separa ``agente_matricula`` em ``agente`` (nome) e ``matricula``.

    Trata três casos especiais:
    - matrícula "colada" ao nome sem a barra (ex.: ``ANGÉLICA BRITO79.718-0``);
    - placeholders de "área sem agente responsável" (``DESCOBERTA``/``ÁREA DESCOBERTA``);
    - nomes com espaços duplicados (ex.: ``JÚLIO  CÉSAR``).
    """
    valores = df["agente_matricula"].astype("string")

    partes = valores.str.split("/", n=1, expand=True)
    df["agente"] = partes[0].str.strip().str.replace(r"\s+", " ", regex=True)
    df["matricula"] = partes[1].astype("string").str.strip().replace("S/M", pd.NA)

    # 1) matrícula colada sem barra: extraída por regex ao final do texto
    sem_barra = ~valores.str.contains("/", na=False)
    extraido = valores[sem_barra].str.extract(PADRAO_MATRICULA)
    df.loc[sem_barra, "agente"] = extraido[0].fillna(df.loc[sem_barra, "agente"])
    df.loc[sem_barra, "matricula"] = extraido[1]

    # 2) placeholders de área descoberta viram ausentes
    placeholder = df["agente"].isin(AGENTES_PLACEHOLDER)
    df.loc[placeholder, ["agente", "matricula"]] = pd.NA

    # 3) nome normalizado (sem acento) para agrupar grafias do mesmo agente
    df["agente_norm"] = df["agente"].map(_normalizar_nome)
    return df


def _tabela_distrito_sanitario() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id_ds": list(range(1, 9)),
            "descricao": [f"Distrito Sanitário {i}" for i in range(1, 9)],
        }
    )


def _tabela_bairro(df: pd.DataFrame) -> pd.DataFrame:
    bairros = (
        df[["bairro", "ds"]]
        .dropna(subset=["bairro"])
        .drop_duplicates("bairro")
        .sort_values("bairro")
        .rename(columns={"bairro": "nome", "ds": "id_ds"})
        .reset_index(drop=True)
    )
    bairros.insert(0, "id_bairro", range(1, len(bairros) + 1))
    return bairros


def _tabela_agente(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Dimensão de agentes, mantendo a grafia **canônica** (a mais frequente).

    Retorna a tabela e o mapa ``nome original -> nome canônico`` usado pelo fato.
    """
    base = df[["agente", "agente_norm", "matricula"]].dropna(subset=["agente"])

    canonicos = base.groupby("agente_norm")["agente"].agg(
        lambda s: s.value_counts().index[0]
    )
    mapa_norm_canon = canonicos.to_dict()
    mapa_agente_canon = dict(
        zip(base["agente"], base["agente_norm"].map(mapa_norm_canon))
    )

    agentes = (
        base.assign(nome_canonico=base["agente_norm"].map(mapa_norm_canon))
        .groupby("nome_canonico")["matricula"]
        .first()
        .reset_index()
        .sort_values("nome_canonico")
        .rename(columns={"nome_canonico": "nome"})
        .reset_index(drop=True)
    )
    agentes.insert(0, "id_agente", range(1, len(agentes) + 1))
    return agentes, mapa_agente_canon


def _tabela_ovitrampa(df: pd.DataFrame, bairro: pd.DataFrame) -> pd.DataFrame:
    mapa_bairro = dict(zip(bairro["nome"], bairro["id_bairro"]))
    ovitrampas = (
        df[["id_ovt", "bairro"]]
        .dropna(subset=["id_ovt"])
        .drop_duplicates("id_ovt")
        .reset_index(drop=True)
    )
    ovitrampas["id_bairro"] = ovitrampas["bairro"].map(mapa_bairro)
    return ovitrampas[["id_ovt", "id_bairro"]]


def _tabela_tecnico_laboratorio(df: pd.DataFrame) -> pd.DataFrame:
    tecnicos = (
        df[["nm_tecnico_lab"]]
        .dropna()
        .drop_duplicates()
        .sort_values("nm_tecnico_lab")
        .rename(columns={"nm_tecnico_lab": "nome"})
        .reset_index(drop=True)
    )
    tecnicos.insert(0, "id_tecnico", range(1, len(tecnicos) + 1))
    return tecnicos


def _tabela_observacao(df: pd.DataFrame) -> pd.DataFrame:
    codigos = sorted(df["obs"].dropna().unique())
    return pd.DataFrame(
        {
            "codigo": codigos,
            "descricao": [OBSERVACOES.get(codigo, codigo) for codigo in codigos],
        }
    )


def _tabela_fato(
    df: pd.DataFrame,
    agente: pd.DataFrame,
    tecnico: pd.DataFrame,
    mapa_agente_canon: dict,
) -> pd.DataFrame:
    mapa_agente = dict(zip(agente["nome"], agente["id_agente"]))
    mapa_tecnico = dict(
        zip(tecnico["nome"], tecnico["id_tecnico"])
    )

    fato = df.copy()
    fato["id_agente"] = fato["agente"].map(mapa_agente_canon).map(mapa_agente)
    fato["id_tecnico"] = fato["nm_tecnico_lab"].map(mapa_tecnico)

    colunas = [
        "ano", "ciclo", "id_ovt", "id_agente", "id_tecnico", "obs",
        "bairro_area", "qt", "dt_coleta", "dt_entrega_apoio",
        "dt_entrega_lab", "dt_leitura", "dt_digitacao", "dt_envio_ds",
        "n_ovos",
    ]
    fato = fato[colunas].rename(columns={"obs": "codigo_obs"})
    fato.insert(0, "id_registro", range(1, len(fato) + 1))
    return fato


def tratar_dados(bruto: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    """Executa todo o tratamento e devolve as tabelas e o diagnóstico da limpeza."""
    df = bruto.copy()

    df["ds"] = df["ds"].map(DS_ROMANOS)
    df = _limpar_texto(df)
    df = _ajustar_datas(df)
    df = _ajustar_numeros(df)
    df = _separar_agente_matricula(df)

    agente, mapa_agente_canon = _tabela_agente(df)
    tabelas = {
        "distrito_sanitario": _tabela_distrito_sanitario(),
        "bairro": _tabela_bairro(df),
        "agente": agente,
    }
    tabelas["ovitrampa"] = _tabela_ovitrampa(df, tabelas["bairro"])
    tabelas["tecnico_laboratorio"] = _tabela_tecnico_laboratorio(df)
    tabelas["observacao"] = _tabela_observacao(df)
    tabelas["monitoramento_ovitrampa"] = _tabela_fato(
        df, agente, tabelas["tecnico_laboratorio"], mapa_agente_canon
    )
    return tabelas, diagnosticar_limpeza(bruto, df, len(agente))