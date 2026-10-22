if __package__:
    from .config import Config
    from .database import BancoSQLite
    from .extract import Extrator
    from .load import Carregador
    from .transform import Transformador
    from .load_neon import ExportadorNeon
else:
    from config import Config
    from database import BancoSQLite
    from extract import Extrator
    from load import Carregador
    from transform import Transformador
    from load_neon import ExportadorNeon


class Pipeline:

    def __init__(self):
        self.banco = BancoSQLite(Config.DB_PATH)
        self.exportador_neon: ExportadorNeon | None = None
        self.extrator = Extrator()
        self.carregador = Carregador(self.banco)
        self.transformador: Transformador | None = None
        self.bruto = None

    # ------------------------------------------------------------- execução

    def executar(self) -> BancoSQLite:

        self.bruto = self.extrator.ler()
        print(f"Origem: {self.bruto.shape[0]} linhas x {self.bruto.shape[1]} colunas")

        self.transformador = Transformador(self.bruto)
        tabelas = self.transformador.executar()
        self._imprimir_limpeza()

        try:
            self.banco.criar_esquema()
            self.carregador.carregar(tabelas)
            violations = self.banco.consultar("PRAGMA foreign_key_check")
            if violations:
                raise RuntimeError(f"Violação de chave estrangeira: {violations[:5]}")
            self._imprimir_resumo()
            self.banco.conexao.commit()
        except Exception:
            self.banco.conexao.rollback()
            raise

        print(f"\nBanco gerado em: {Config.DB_PATH}")
        return self.banco

    # -------------------------------------------------------------- relatório

    def _imprimir_limpeza(self) -> None:
       
        diag = self.transformador.diagnostico
        print("\n=== Limpeza aplicada ===")
        linhas = [
            ("Placeholders de área descoberta -> nulo", "placeholders_removidos"),
            ("Matrículas 'coladas' ao nome extraídas", "matriculas_coladas_extraidas"),
            ("Registros sem matrícula (mantidos)", "sem_matricula"),
            ("Datas em branco (células)", "datas_vazias_invalidas"),
            ("Datas não vazias inválidas (sinalizadas)", "datas_invalidas"),
            ("Valores numéricos inválidos (sinalizados)", "numericos_invalidos"),
            ("n_ovos > 1000 (apenas sinalizado)", "n_ovos_alto_mil"),
            ("Grafias de agentes unificadas (acentos)", "agentes_unificados"),
        ]
        for texto, chave in linhas:
            print(f"{texto:<42} {diag[chave]:>8}")
        print(f"{'Total de agentes após unificação':<42} {diag['agentes_total']:>8}")

    def _imprimir_resumo(self) -> None:
   
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
        print(
            "Os registros de origem são inseridos sem duplicar chaves já "
            "existentes no banco."
        )

        print("\n=== Amostra (monitoramento_ovitrampa) ===")
        amostra = self.banco.consultar(
            "SELECT id_registro, ano, ciclo, id_ovt, dt_coleta, n_ovos, codigo_obs "
            "FROM monitoramento_ovitrampa LIMIT 5"
        )
        for linha in amostra:
            print(linha)

    def executar_neon(self) -> None:
        if not self.transformador:
            raise RuntimeError("Pipeline não executado; não há dados para exportar.")
        tabelas = self.transformador.tabelas
        if self.exportador_neon is None:
            self.exportador_neon = ExportadorNeon(self.banco)
        self.exportador_neon._carregar_dimensional(tabelas)

        
if __name__ == "__main__":
    pipeline = Pipeline()
    pipeline.executar().fechar()