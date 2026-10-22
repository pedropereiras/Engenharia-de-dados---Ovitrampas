import re
import unicodedata

import pandas as pd

from config import Config


class Transformador:
    """Executa a limpeza e organiza o DataFrame bruto no modelo dimensional.

    Uso típico::

        transformador = Transformador(df_bruto)
        tabelas = transformador.executar()
        transformador.diagnostico  # contagens da limpeza aplicada
    """

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

    def __init__(self, bruto: pd.DataFrame):
        self.bruto = bruto
        self.df = bruto.copy()
        self.tabelas: dict[str, pd.DataFrame] = {}
        self.diagnostico: dict[str, int] = {}
        self._mapa_agente_canon: dict = {}

    # ------------------------------------------------------------------ fluxo

    def executar(self) -> dict[str, pd.DataFrame]:
        """Aplica todo o tratamento e devolve as tabelas prontas para o banco."""
        self._limpar_textos()
        self._normalizar_ds()
        self._ajustar_datas()
        self._ajustar_numeros()
        self._separar_agente()
        self._montar_modelo_dimensional()
        self._gerar_diagnostico()
        return self.tabelas

    # ------------------------------------------------------------- limpezas

    def _normalizar_ds(self) -> None:
        """Converte a numeração romana do distrito sanitário (I..VIII -> 1..8)."""
        self.df["ds"] = self.df["ds"].map(Config.DS_ROMANOS)

    def _limpar_textos(self) -> None:
        """Remove espaços extras e converte células vazias/em-branco para nulos."""
        for coluna in self.COLUNAS_TEXTO:
            self.df[coluna] = (
                self.df[coluna]
                .astype("string")
                .str.strip()
                .str.replace(r"\s+", " ", regex=True)
                .replace({"": pd.NA, "nan": pd.NA})
            )
        self.df["ds"] = self.df["ds"].astype("string").str.strip()

    def _ajustar_datas(self) -> None:
        """Converte as colunas de data para datetime (valores inválidos viram nulos)."""
        for coluna in self.COLUNAS_DATA:
            serie = (
                self.df[coluna]
                .astype("string")
                .replace({"": pd.NA, " ": pd.NA, "nan": pd.NA})
            )
            self.df[coluna] = pd.to_datetime(serie, errors="coerce", format="mixed")

    def _ajustar_numeros(self) -> None:
        """Converte campos numéricos (n_ovos/qt como float; ano/ciclo como int)."""
        self.df["n_ovos"] = pd.to_numeric(
            self.df["n_ovos"].astype("string").replace({"": pd.NA, " ": pd.NA}),
            errors="coerce",
        )
        self.df["qt"] = pd.to_numeric(
            self.df["qt"].astype("string").replace({"": pd.NA, " ": pd.NA}),
            errors="coerce",
        )
        self.df["ano"] = pd.to_numeric(self.df["ano"], errors="coerce").astype("int64")
        self.df["ciclo"] = pd.to_numeric(self.df["ciclo"], errors="coerce").astype(
            "int64"
        )

    def _separar_agente(self) -> None:
        """Separa ``agente_matricula`` em ``agente`` (nome) e ``matricula``.

        Três casos especiais:
        - matrícula "colada" ao nome sem a barra (ex.: ``ANGÉLICA BRITO79.718-0``);
        - placeholders de "área sem agente responsável"
          (``DESCOBERTA``/``ÁREA DESCOBERTA``);
        - nomes com espaços duplicados (ex.: ``JÚLIO  CÉSAR``).
        """
        valores = self.df["agente_matricula"].astype("string")

        partes = valores.str.split("/", n=1, expand=True)
        self.df["agente"] = partes[0].str.strip().str.replace(r"\s+", " ", regex=True)
        self.df["matricula"] = (
            partes[1].astype("string").str.strip().replace("S/M", pd.NA)
        )

        # 1) matrícula colada sem barra: extraída por regex ao final do texto
        sem_barra = ~valores.str.contains("/", na=False)
        extraido = valores[sem_barra].str.extract(self.PADRAO_MATRICULA)
        self.df.loc[sem_barra, "agente"] = extraido[0].fillna(
            self.df.loc[sem_barra, "agente"]
        )
        self.df.loc[sem_barra, "matricula"] = extraido[1]

        # 2) placeholders de área descoberta viram ausentes
        placeholder = self.df["agente"].isin(self.AGENTES_PLACEHOLDER)
        self.df.loc[placeholder, ["agente", "matricula"]] = pd.NA

        # 3) nome normalizado (sem acento) para agrupar grafias do mesmo agente
        self.df["agente_norm"] = self.df["agente"].map(self._normalizar_nome)

    # ------------------------------------------------------------ modelagem

    def _montar_modelo_dimensional(self) -> None:
        """Constrói todas as dimensões e a tabela fato a partir do dado limpo."""
        distrito = self._tabela_distrito_sanitario()
        bairro = self._tabela_bairro()
        agente, self._mapa_agente_canon = self._tabela_agente()
        ovitrampa = self._tabela_ovitrampa(bairro)
        tecnico = self._tabela_tecnico()
        observacao = self._tabela_observacao()
        fato = self._tabela_fato(agente, tecnico)

        self.tabelas = {
            "distrito_sanitario": distrito,
            "bairro": bairro,
            "agente": agente,
            "ovitrampa": ovitrampa,
            "tecnico_laboratorio": tecnico,
            "observacao": observacao,
            "monitoramento_ovitrampa": fato,
        }

    def _tabela_distrito_sanitario(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "id_ds": list(range(1, 9)),
                "descricao": [f"Distrito Sanitário {i}" for i in range(1, 9)],
            }
        )

    def _tabela_bairro(self) -> pd.DataFrame:
        bairros = (
            self.df[["bairro", "ds"]]
            .dropna(subset=["bairro", "ds"])
            .drop_duplicates("bairro")
            .sort_values("bairro")
            .rename(columns={"bairro": "nome", "ds": "id_ds"})
            .reset_index(drop=True)
        )
        bairros.insert(0, "id_bairro", range(1, len(bairros) + 1))
        return bairros

    def _tabela_agente(self) -> tuple[pd.DataFrame, dict]:
        """Dimensão de agentes, mantendo a grafia canônica (a mais frequente).

        Retorna a tabela e o mapa ``nome original -> nome canônico`` usado pelo fato.
        """
        base = self.df[["agente", "agente_norm", "matricula"]].dropna(
            subset=["agente"]
        )

        canonicos = base.groupby("agente_norm")["agente"].agg(
            lambda serie: serie.value_counts().index[0]
        )
        mapa_norm_canon = canonicos.to_dict()
        mapa_agente_canon = dict(
            zip(base["agente"], base["agente_norm"].map(mapa_norm_canon))
        )

        agentes = (
            base.assign(nome_canonico=base["agente_norm"].map(mapa_norm_canon))
            .groupby("nome_canonico")["matricula"]
            .agg(self._matricula_canonica)
            .reset_index()
            .sort_values("nome_canonico")
            .rename(columns={"nome_canonico": "nome"})
            .reset_index(drop=True)
        )
        agentes.insert(0, "id_agente", range(1, len(agentes) + 1))
        return agentes, mapa_agente_canon

    def _tabela_ovitrampa(self, bairro: pd.DataFrame) -> pd.DataFrame:
        mapa_bairro = dict(zip(bairro["nome"], bairro["id_bairro"]))
        ovitrampas = (
            self.df[["id_ovt", "bairro"]]
            .dropna(subset=["id_ovt"])
            .drop_duplicates("id_ovt")
            .reset_index(drop=True)
        )
        ovitrampas["id_bairro"] = ovitrampas["bairro"].map(mapa_bairro)
        return ovitrampas[["id_ovt", "id_bairro"]]

    def _tabela_tecnico(self) -> pd.DataFrame:
        tecnicos = (
            self.df[["nm_tecnico_lab"]]
            .dropna()
            .drop_duplicates()
            .sort_values("nm_tecnico_lab")
            .rename(columns={"nm_tecnico_lab": "nome"})
            .reset_index(drop=True)
        )
        tecnicos.insert(0, "id_tecnico", range(1, len(tecnicos) + 1))
        return tecnicos

    def _tabela_observacao(self) -> pd.DataFrame:
        codigos = sorted(self.df["obs"].dropna().unique())
        return pd.DataFrame(
            {
                "codigo": codigos,
                "descricao": [Config.OBSERVACOES.get(codigo, codigo) for codigo in codigos],
            }
        )

    def _tabela_fato(
        self, agente: pd.DataFrame, tecnico: pd.DataFrame
    ) -> pd.DataFrame:
        mapa_agente = dict(zip(agente["nome"], agente["id_agente"]))
        mapa_tecnico = dict(zip(tecnico["nome"], tecnico["id_tecnico"]))

        fato = self.df.copy()
        fato["id_agente"] = (
            fato["agente"].map(self._mapa_agente_canon).map(mapa_agente)
        )
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

    # ----------------------------------------------------------- diagnóstico

    def _gerar_diagnostico(self) -> None:
        """Mede o impacto das limpezas aplicadas (para o relatório final)."""
        raw_agente = self.bruto["agente_matricula"].astype("string").str.strip()
        sem_barra = ~raw_agente.str.contains("/", na=False)
        coladas = int(
            raw_agente[sem_barra].str.extract(self.PADRAO_MATRICULA)[1].notna().sum()
        )
        agentes = self.tabelas["agente"]
        self.diagnostico = {
            "linhas": len(self.bruto),
            "placeholders_removidos": int(
                raw_agente.isin(self.AGENTES_PLACEHOLDER).sum()
            ),
            "matriculas_coladas_extraidas": coladas,
            "sem_matricula": int(
                (self.df["agente"].notna() & self.df["matricula"].isna()).sum()
            ),
            "datas_vazias_invalidas": int(
                self.df[self.COLUNAS_DATA].isna().sum().sum()
            ),
            "n_ovos_alto_mil": int((self.df["n_ovos"] > 1000).sum()),
            "agentes_total": int(agentes["id_agente"].nunique()),
            "agentes_unificados": int(
                self.df.loc[self.df["agente"].notna(), "agente"].nunique()
                - self.df.loc[self.df["agente"].notna(), "agente_norm"].nunique()
            ),
        }

    # ----------------------------------------------------------- helpers

    @staticmethod
    def _normalizar_nome(nome) -> str | None:
        """Remove acentos, caixa alta e espaços duplicados (agrupa agentes).

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

    @staticmethod
    def _matricula_canonica(matri: pd.Series) -> str | None:
        """Matrícula mais frequente e não nula do agente (NA quando não existe)."""
        matri = matri.dropna()
        if matri.empty:
            return pd.NA
        return matri.value_counts().index[0]