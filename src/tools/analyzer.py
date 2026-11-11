from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import pyarrow.parquet as pq

from src.core.state import DataProfile

def profile_tabular_data(file_path: Path) -> DataProfile:
    """
    Inspeciona arquivo tabular (Parquet, CSV, Excel) e constrói perfil analítico estruturado
    contendo dimensões, tipos, percentuais de nulos, amostra e inconsistências detectadas.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {file_path}")

    ext = path.suffix.lower()
    if ext == ".parquet":
        df = pd.read_parquet(path)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(path, sheet_name=0)
    elif ext == ".csv":
        for encoding in ['utf-8', 'latin1', 'iso-8859-1']:
            try:
                df = pd.read_csv(path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            df = pd.read_csv(path)
    else:
        raise ValueError(f"Extensão de arquivo não suportada para profiling: {ext}")

    total_rows, total_cols = df.shape
    columns: Dict[str, str] = {str(col): str(df[col].dtype) for col in df.columns}
    missing_percentages: Dict[str, float] = {}
    inconsistencies_detected: List[str] = []

    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        null_pct = (null_count / total_rows * 100.0) if total_rows > 0 else 0.0
        missing_percentages[str(col)] = round(null_pct, 2)
        if null_count > 0:
            inconsistencies_detected.append(
                f"Coluna '{col}' possui {null_count} valores ausentes ({null_pct:.1f}%)."
            )

        # Detectar formatação monetária (ex: R$, $, separadores com vírgula)
        if df[col].dtype == object:
            sample_non_null = df[col].dropna().astype(str).head(10).tolist()
            has_currency = any(('R$' in s or '$' in s) for s in sample_non_null)
            has_numeric_with_comma = any((',' in s and any(c.isdigit() for c in s)) for s in sample_non_null)
            if has_currency:
                inconsistencies_detected.append(
                    f"Coluna '{col}' detectada com formato monetário / texto que requer conversão para float."
                )
            elif has_numeric_with_comma and not has_currency:
                inconsistencies_detected.append(
                    f"Coluna '{col}' possui separador decimal com vírgula."
                )

    # Obter amostra segura convertendo tipos datetime/timestamp para ISO
    sample_df = df.head(5).copy()
    sample_records = sample_df.to_dict(orient="records")
    # Sanitizar objetos que não são serializáveis diretamente
    sanitized_sample = []
    for row in sample_records:
        sanitized_row = {}
        for k, v in row.items():
            if pd.isna(v):
                sanitized_row[str(k)] = None
            elif hasattr(v, 'isoformat'):
                sanitized_row[str(k)] = v.isoformat()
            else:
                sanitized_row[str(k)] = v
        sanitized_sample.append(sanitized_row)

    profile: DataProfile = {
        "total_rows": total_rows,
        "total_columns": total_cols,
        "columns": columns,
        "missing_percentages": missing_percentages,
        "sample_data": sanitized_sample,
        "inconsistencies_detected": inconsistencies_detected
    }
    return profile
