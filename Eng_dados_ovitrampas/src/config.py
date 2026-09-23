"""Configuração do pipeline ETL: caminhos, constantes e dicionários de apoio."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "dados" / "entrada"
ARQUIVO_ENTRADA = DATA_DIR / "ovitrampas_2026.xlsx"
PLANILHA = "CICLO 1"

DB_DIR = ROOT_DIR / "banco"
DB_PATH = DB_DIR / "ovitrampas.db"

# Colunas padronizadas aplicadas ao arquivo bruto (17 colunas).
COLUNAS_PADRAO = [
    "ano",
    "ciclo",
    "ds",
    "bairro",
    "bairro_area",
    "agente_matricula",
    "qt",
    "id_ovt",
    "dt_coleta",
    "dt_entrega_apoio",
    "dt_entrega_lab",
    "dt_leitura",
    "nm_tecnico_lab",
    "dt_digitacao",
    "dt_envio_ds",
    "n_ovos",
    "obs",
]

# Mapeamento do distrito sanitário: numeração romana (fonte) -> inteiro.
DS_ROMANOS = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
}

# Tabela de apoio para o campo OBS (legenda presente no cabeçalho da origem).
OBSERVACOES = {
    "F": "Fechado",
    "E": "Extraviado",
    "R": "Recusado",
    "D": "Desocupado",
    "REC-2025": "Recuperada - coleção 2025",
    "REC-2026": "Recuperada - coleção 2026",
}