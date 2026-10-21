"""Pipeline ETL: Ovitrampas 2026 (Excel -> SQLite).

Executa extração, tratamento/organização dos dados e carga no banco SQLite.
"""

import sqlite3

from config import DB_PATH
from database import conectar, criar_esquema
from extract import ler_arquivo_bruto
from load import carregar_tabelas
from transform import tratar_dados


def _resumo_limpeza(diag: dict[str, int]) -> None:
    """Exibe as contagens do que a etapa de limpeza corrigiu."""
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


def _resumo(conexao: sqlite3.Connection, total_origem: int) -> None:
    """Exibe a contagem de registros de cada tabela e uma amostra do fato."""
    tabelas = [
        "distrito_sanitario",
        "bairro",
        "agente",
        "ovitrampa",
        "tecnico_laboratorio",
        "observacao",
        "monitoramento_ovitrampa",
    ]
    cursor = conexao.cursor()
    print("\n=== Registros por tabela ===")
    for nome in tabelas:
        (quantidade,) = cursor.execute(f"SELECT COUNT(*) FROM {nome}").fetchone()
        print(f"{nome:<26} {quantidade:>6}")

    (total_fato,) = cursor.execute(
        "SELECT COUNT(*) FROM monitoramento_ovitrampa"
    ).fetchone()
    print(f"\nTotal na origem:          {total_origem}")
    print(f"Total no fato:            {total_fato}")
    assert total_fato == total_origem, "Perda de registros na carga!"

    print("\n=== Amostra (monitoramento_ovitrampa) ===")
    cursor.execute(
        "SELECT id_registro, ano, ciclo, id_ovt, dt_coleta, n_ovos, codigo_obs "
        "FROM monitoramento_ovitrampa LIMIT 5"
    )
    for linha in cursor.fetchall():
        print(linha)
    cursor.close()


def executar_pipeline() -> sqlite3.Connection:
    """Roda o pipeline completo e devolve a conexão com o banco pronto."""
    bruto = ler_arquivo_bruto()
    print(f"Origem: {bruto.shape[0]} linhas x {bruto.shape[1]} colunas")

    tabelas, diag = tratar_dados(bruto)
    _resumo_limpeza(diag)

    conexao = conectar(DB_PATH)
    criar_esquema(conexao)
    carregar_tabelas(conexao, tabelas)

    _resumo(conexao, total_origem=len(bruto))
    print(f"\nBanco gerado em: {DB_PATH}")
    return conexao


if __name__ == "__main__":
    executor = executar_pipeline()
    executor.close()