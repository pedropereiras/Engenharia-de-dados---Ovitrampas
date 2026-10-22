import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.config import Config
from src.database import BancoSQLite
from src.extract import COLUNAS_ORIGEM, Extrator
from src.load import Carregador
from src.load_neon import _url_psycopg
from src.transform import Transformador


def dataframe_de_teste() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ano": 2026,
                "ciclo": 1,
                "ds": "I",
                "bairro": "Bairro A",
                "bairro_area": None,
                "agente_matricula": "Agente Teste/12.345-6",
                "qt": "1",
                "id_ovt": "OVT-1",
                "dt_coleta": "2026-01-10",
                "dt_entrega_apoio": None,
                "dt_entrega_lab": None,
                "dt_leitura": None,
                "nm_tecnico_lab": None,
                "dt_digitacao": None,
                "dt_envio_ds": None,
                "n_ovos": "10",
                "obs": None,
            }
        ]
    )


class TransformadorTests(unittest.TestCase):
    def test_same_trap_and_cycle_in_different_years_are_valid(self):
        bruto = dataframe_de_teste()
        segundo_ano = bruto.iloc[0].copy()
        segundo_ano["ano"] = 2027
        segundo_ano["ciclo"] = 1
        bruto = pd.concat([bruto, segundo_ano.to_frame().T], ignore_index=True)

        tabelas = Transformador(bruto).executar()

        self.assertEqual(len(tabelas["monitoramento_ovitrampa"]), 2)

    def test_duplicate_trap_year_cycle_is_rejected(self):
        bruto = pd.concat(
            [dataframe_de_teste(), dataframe_de_teste()],
            ignore_index=True,
        )

        with self.assertRaisesRegex(ValueError, "id_ovt, ano, ciclo"):
            Transformador(bruto).executar()

    def test_unknown_district_is_rejected(self):
        bruto = dataframe_de_teste()
        bruto.loc[0, "ds"] = "IX"

        with self.assertRaisesRegex(ValueError, "fora do mapeamento"):
            Transformador(bruto).executar()

    def test_ambiguous_neighborhood_mapping_is_rejected(self):
        bruto = dataframe_de_teste()
        outro = bruto.iloc[0].copy()
        outro["ds"] = "II"
        outro["id_ovt"] = "OVT-2"
        outro["ciclo"] = 2
        bruto = pd.concat([bruto, outro.to_frame().T], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "bairro\\(s\\) associado"):
            Transformador(bruto).executar()

    def test_ambiguous_trap_mapping_is_rejected(self):
        bruto = dataframe_de_teste()
        outro = bruto.iloc[0].copy()
        outro["bairro"] = "Bairro B"
        outro["ciclo"] = 2
        bruto = pd.concat([bruto, outro.to_frame().T], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "ovitrampa\\(s\\) associada"):
            Transformador(bruto).executar()

    def test_unparseable_nonblank_date_is_reported(self):
        bruto = dataframe_de_teste()
        bruto.loc[0, "dt_coleta"] = "data inválida"
        transformador = Transformador(bruto)

        transformador.executar()

        self.assertEqual(transformador.diagnostico["datas_invalidas"], 1)


class PersistenceTests(unittest.TestCase):
    def test_extractor_falls_back_to_csv_when_xlsx_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "source.csv"
            csv_path.write_text(";".join((*COLUNAS_ORIGEM, "OBS")) + "\n", encoding="utf-8")
            with (
                patch.object(Config, "ARQUIVO_ENTRADA", Path(temp_dir) / "missing.xlsx"),
                patch.object(Config, "ARQUIVO_CSV", csv_path),
            ):
                frame = Extrator().ler()

        self.assertEqual(list(frame.columns), Config.COLUNAS_PADRAO)
        self.assertEqual(len(frame), 0)

    def test_extractor_rejects_reordered_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "source.csv"
            headers = list(COLUNAS_ORIGEM) + ["OBS"]
            headers[0], headers[1] = headers[1], headers[0]
            csv_path.write_text(";".join(headers) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Cabeçalho inesperado"):
                Extrator(csv_path).ler()

    def test_sqlite_schema_creation_preserves_existing_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            banco = BancoSQLite(Path(temp_dir) / "test.db")
            banco.criar_esquema()
            banco.conexao.execute(
                "INSERT INTO distrito_sanitario (id_ds, descricao) VALUES (1, 'original')"
            )
            banco.conexao.commit()

            banco.criar_esquema()

            self.assertEqual(
                banco.consultar("SELECT descricao FROM distrito_sanitario"),
                [("original",)],
            )
            banco.fechar()

    def test_sqlite_load_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            banco = BancoSQLite(Path(temp_dir) / "test.db")
            banco.criar_esquema()
            tabelas = Transformador(dataframe_de_teste()).executar()
            carregador = Carregador(banco)

            carregador.carregar(tabelas)
            banco.conexao.commit()
            carregador.carregar(tabelas)
            banco.conexao.commit()

            self.assertEqual(
                banco.consultar("SELECT COUNT(*) FROM monitoramento_ovitrampa"),
                [(1,)],
            )
            self.assertEqual(
                banco.consultar("SELECT COUNT(*) FROM distrito_sanitario"),
                [(8,)],
            )
            banco.fechar()

    def test_mongo_collection_configuration_exists(self):
        self.assertTrue(Config.MONGO_BANCO)
        self.assertTrue(Config.MONGO_COLECAO)

    def test_neon_urls_use_declared_psycopg_v3_driver(self):
        url = _url_psycopg(
            "postgresql://user:password@localhost/ovitrampas?sslmode=require"
        )
        self.assertEqual(url.drivername, "postgresql+psycopg")

    def test_notebook_has_no_saved_outputs_and_uses_current_key(self):
        notebook = ROOT_DIR / "notebook" / "tratamento_dados_ovitrampas.ipynb"
        document = json.loads(notebook.read_text(encoding="utf-8"))
        source = "\n".join(
            line
            for cell in document["cells"]
            for line in cell.get("source", [])
        )

        self.assertFalse(
            any(cell.get("outputs") for cell in document["cells"])
        )
        self.assertIn("UNIQUE (id_ovt, ano, ciclo)", source)

    def test_neon_ddl_does_not_drop_existing_tables(self):
        from src.load_neon import DDL_NEON

        self.assertTrue(all("DROP TABLE" not in command for command in DDL_NEON))
        self.assertTrue(
            all("CREATE TABLE IF NOT EXISTS" in command for command in DDL_NEON)
        )


if __name__ == "__main__":
    unittest.main()
