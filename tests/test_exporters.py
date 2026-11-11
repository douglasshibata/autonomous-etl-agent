import json
import sqlite3
from pathlib import Path
import pandas as pd
import pytest

from src.tools.exporter import DataExporter

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "nome": ["Empresa Alfa", "O'Connor & Sons", "Tech Corp"],
        "valor": [1500.50, 2300.00, 99.99],
        "ativo": [True, False, True],
        "data_cadastro": pd.to_datetime(["2026-01-10 10:00:00", "2026-02-15 14:30:00", "2026-03-20 09:15:00"])
    })

def test_export_to_parquet(sample_df, tmp_path):
    parquet_path = tmp_path / "test.parquet"
    res = DataExporter.to_parquet(sample_df, parquet_path)
    assert res.exists()
    loaded_df = pd.read_parquet(res)
    assert loaded_df.shape == (3, 5)
    assert list(loaded_df["id"]) == [1, 2, 3]

def test_export_to_json_iso_timestamps(sample_df, tmp_path):
    json_path = tmp_path / "test.json"
    res = DataExporter.to_json(sample_df, json_path)
    assert res.exists()
    with open(res, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 3
    # Verifica sanitização ISO 8601
    assert "2026-01-10T10:00:00" in data[0]["data_cadastro"]
    assert data[1]["nome"] == "O'Connor & Sons"

def test_export_to_csv(sample_df, tmp_path):
    csv_path = tmp_path / "test.csv"
    res = DataExporter.to_csv(sample_df, csv_path)
    assert res.exists()
    loaded_df = pd.read_csv(res)
    assert len(loaded_df) == 3

def test_export_to_sqlite_dump_safe_sql(sample_df, tmp_path):
    sql_path = tmp_path / "test_dump.sql"
    res = DataExporter.to_sqlite_dump(sample_df, sql_path, table_name="vendas_corporativas")
    assert res.exists()
    with open(res, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CREATE TABLE" in content
    assert "vendas_corporativas" in content
    # Verifica escape correto de aspas no iterdump SQLite
    assert "O''Connor & Sons" in content

    # Testar re-execução do dump em um banco sqlite real
    test_db = sqlite3.connect(":memory:")
    test_db.executescript(content)
    cursor = test_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM vendas_corporativas")
    count = cursor.fetchone()[0]
    assert count == 3
    test_db.close()

def test_export_to_xml(sample_df, tmp_path):
    xml_path = tmp_path / "test.xml"
    res = DataExporter.to_xml(sample_df, xml_path, root_element="vendas", row_element="item")
    assert res.exists()
    with open(res, "r", encoding="utf-8") as f:
        content = f.read()
    assert "<vendas>" in content
    assert "<item>" in content
    assert "Empresa Alfa" in content
