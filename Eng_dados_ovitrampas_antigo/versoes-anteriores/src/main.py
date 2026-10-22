from config import Config
from database import BancoSQLite
from extract import Extrator
from load import Carregador
from transform import Transformador


class Pipeline:
    """Orquestra as etapas do ETL: extrair, transformar e carregar."""

    def __init__(self):
        self.banco = BancoSQLite(Config.DB_PATH)
        self.extrator = Extrator()
        self.carregador = Carregador(self.banco)
        self.transformador: Transformador | None = None
        self.bruto = None

    # ------------------------------------------------------------- execução

    def executar(self) -> BancoSQLite:
        """Roda o pipeline completo e devolve a conexão com o banco pronto."""
        self.bruto = self.extrator.ler()
        print(f"Origem: {self.bruto.shape[0]} linhas x {self.bruto.shape[1]} colunas")

        self.transformador = Transformador(self.bruto)
        tabelas = self.transformador.executar()
        self._imprimir_limpeza()

        self.banco.criar_esquema()
        self.carregador.carregar(tabelas)
        self._imprimir_resumo()

        print(f"\nBanco gerado em: {Config.DB_PATH}")
        return self.banco

    # -------------------------------------------------------------- relatório

    def _imprimir_limpeza(self) -> None:
        """Exibe as contagens do que a etapa de limpeza corrigiu."""
        diag = self.transformador.diagnostico
        print("\n=== Limpeza aplicada ===")
        linhas = [
            ("Placeholders de área descoberta -> nulo", "placeholders_removidos"),
            ("Matrículas 'coladas' ao nome extraídas", "matriculas_coladas_extraidas"),
            ("Registros sem matrícula (mantidos)", "sem_matricula"),
            ("Datas em branco (células)", "datas_vazias_invalidas"),
            ("n_ovos > 1000 (apenas sinalizado)", "n_ovos_alto_mil"),
            ("Grafias de agentes unificadas (acentos)", "agentes_unificados"),
        ]
        for texto, chave in linhas:
            print(f"{texto:<42} {diag[chave]:>8}")
        print(f"{'Total de agentes após unificação':<42} {diag['agentes_total']:>8}")

    def _imprimir_resumo(self) -> None:
        """Exibe a contagem de registros de cada tabela e uma amostra do fato."""
        nomes_tabelas = [
            "distrito_sanitario",
            "bairro",
            "agente",
            "ovitrampa",
            "tecnico_laboratorio",
            "observacao",
            "monitoramento_ovitrampa",
        ]
        print("\n=== Registros por tabela ===")
        for nome in nomes_tabelas:
            (quantidade,) = self.banco.consultar(f"SELECT COUNT(*) FROM {nome}")[0]
            print(f"{nome:<26} {quantidade:>6}")

        (total_fato,) = self.banco.consultar(
            "SELECT COUNT(*) FROM monitoramento_ovitrampa"
        )[0]
        print(f"\nTotal na origem:          {len(self.bruto)}")
        print(f"Total no fato:            {total_fato}")
        if total_fato != len(self.bruto):
            raise RuntimeError("Perda de registros na carga!")

        print("\n=== Amostra (monitoramento_ovitrampa) ===")
        amostra = self.banco.consultar(
            "SELECT id_registro, ano, ciclo, id_ovt, dt_coleta, n_ovos, codigo_obs "
            "FROM monitoramento_ovitrampa LIMIT 5"
        )
        for linha in amostra:
            print(linha)


if __name__ == "__main__":
    pipeline = Pipeline()
    pipeline.executar().fechar()