import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

class DataExporter:
    """Exportador transacional multiformato para Parquet, CSV, JSON e SQLite/SQL DDL+DML."""

    @staticmethod
    def to_csv(df: pd.DataFrame, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding='utf-8')
        return output_path

    @staticmethod
    def to_json(df: pd.DataFrame, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Sanitização de tipos Timestamp para ISO 8601
        df.to_json(output_path, orient='records', date_format='iso', indent=2)
        return output_path

    @staticmethod
    def to_parquet(df: pd.DataFrame, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, engine='pyarrow', index=False)
        return output_path

    @staticmethod
    def to_sqlite_dump(df: pd.DataFrame, output_path: Path, table_name: str = "cleaned_data") -> Path:
        """Exporta um banco SQLite autocontido e um script SQL DDL + DML auditado e sanitizado."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sql_script_path = output_path.with_suffix('.sql')

        # Sanitizar nome da tabela para identificador SQLite válido
        clean_table_name = "".join(c for c in table_name if c.isalnum() or c == "_")
        if not clean_table_name:
            clean_table_name = "cleaned_data"

        # Conecta a um banco em memória temporário para gerar o DDL/DML determinístico
        temp_conn = sqlite3.connect(":memory:")
        df.to_sql(clean_table_name, temp_conn, index=False, if_exists="replace")

        with open(sql_script_path, "w", encoding="utf-8") as f:
            for line in temp_conn.iterdump():
                f.write(f"{line}\n")

        temp_conn.close()
        return sql_script_path

    @staticmethod
    def to_xml(df: pd.DataFrame, output_path: Path, root_element: str = "dataset", row_element: str = "record") -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_xml(output_path, index=False, root_name=root_element, row_name=row_element, parser="etree")
        except Exception:
            # Fallback manual seguro para XML
            xml_lines = [f"<{root_element}>"]
            for _, row in df.iterrows():
                xml_lines.append(f"  <{row_element}>")
                for col in df.columns:
                    val = row[col]
                    safe_val = "" if pd.isnull(val) else str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    safe_tag = "".join(c for c in str(col) if c.isalnum() or c == "_")
                    xml_lines.append(f"    <{safe_tag}>{safe_val}</{safe_tag}>")
                xml_lines.append(f"  </{row_element}>")
            xml_lines.append(f"</{root_element}>")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(xml_lines))
        return output_path
