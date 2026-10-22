from pathlib import Path

import pandas as pd

if __package__:
    from .config import Config
    from .database import BancoSQLite
else:
    from config import Config
    from database import BancoSQLite


class ExportadorCSV:
    """Exporta a tabela fato enriquecida com as dimensões para um arquivo CSV."""

    CONSULTA = """
SELECT m.id_registro,
       m.ano,
       m.ciclo,
       d.id_ds        AS ds,
       d.descricao    AS descricao_ds,
       b.id_bairro,
       b.nome         AS bairro,
       m.bairro_area,
       m.id_ovt,
       a.id_agente,
       a.nome         AS agente,
       a.matricula,
       t.id_tecnico,
       t.nome         AS tecnico_lab,
       m.codigo_obs,
       ob.descricao   AS obs_descricao,
       m.qt,
       m.dt_coleta,
       m.dt_entrega_apoio,
       m.dt_entrega_lab,
       m.dt_leitura,
       m.dt_digitacao,
       m.dt_envio_ds,
       m.n_ovos
FROM monitoramento_ovitrampa m
JOIN ovitrampa o              ON o.id_ovt = m.id_ovt
JOIN bairro b                 ON b.id_bairro = o.id_bairro
JOIN distrito_sanitario d     ON d.id_ds = b.id_ds
LEFT JOIN agente a            ON a.id_agente = m.id_agente
LEFT JOIN tecnico_laboratorio t ON t.id_tecnico = m.id_tecnico
LEFT JOIN observacao ob       ON ob.codigo = m.codigo_obs
"""

    def __init__(self, banco: BancoSQLite | None = None, saida: Path | str = Config.SAIDA_CSV):
        self.banco = banco or BancoSQLite()
        self.saida = Path(saida)

    def exportar(self) -> Path:
        
        self.banco.conectar()
        df = pd.read_sql_query(self.CONSULTA, self.banco.conexao)

        df["n_ovos"] = pd.to_numeric(df["n_ovos"], errors="coerce")
        df["qt"] = pd.to_numeric(df["qt"], errors="coerce")
        colunas_inteiras = [
            "ano", "ciclo", "ds", "id_bairro", "id_agente", "id_tecnico",
            "qt", "n_ovos",
        ]
        for coluna in colunas_inteiras:
            df[coluna] = df[coluna].astype("Int64")

        self.saida.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.saida, sep=";", index=False, encoding="utf-8-sig")

        print(f"CSV gerado: {self.saida}")
        self._analisar(df)
        return self.saida

    def _analisar(self, df: pd.DataFrame) -> None:
        
        print(f"Registros: {len(df):,}")
        print(f"Colunas:   {len(df.columns)}")
        print("\nValores ausentes por coluna:")
        nulos = df.isna().sum()
        for coluna in df.columns:
            if nulos[coluna] > 0:
                print(
                    f"  {coluna:<22} {nulos[coluna]:>6} "
                    f"({nulos[coluna] / len(df):.1%})"
                )
        print("\nDistintos:")
        for coluna in ["ds", "bairro", "bairro_area", "id_ovt", "agente", "tecnico_lab", "codigo_obs"]:
            print(f"  {coluna:<22} {df[coluna].nunique():>5}")
        print(
            "\nDatas (min lido -> max lido):",
            df["dt_leitura"].min(),
            "->",
            df["dt_leitura"].max(),
        )
        print(
            "n_ovos: total", int(df["n_ovos"].sum()),
            "| média %.1f" % df["n_ovos"].mean(),
            "| máx", int(df["n_ovos"].max()),
        )


if __name__ == "__main__":
    ExportadorCSV().exportar()