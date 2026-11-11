import os
import logging
import pandas as pd
from typing import Dict, Any, Optional
from langchain_core.tools import tool

logger = logging.getLogger("ETL_Agent.analyze_spreadsheet")

# Configurar o arquivo temporário que servirá como banco de dados em memória persistente em disco
WORKING_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "current_state.csv"
)

@tool
def analyze_spreadsheet(file_path: str, sheet_name: Optional[str] = None) -> str:
    """
    Carrega uma planilha (.xlsx, .xls ou .csv), salva como estado de trabalho atual
    e retorna um resumo completo do esquema (colunas, tipos, valores nulos e primeiras 5 linhas).

    Args:
        file_path (str): O caminho relativo ou absoluto para o arquivo de planilha.
        sheet_name (str, opcional): Nome da aba da planilha (caso seja Excel). Se omitido, carrega a primeira aba (índice 0).

    Returns:
        str: Um resumo descritivo do arquivo de dados analisado.
    """
    logger.info(f"Iniciando análise do arquivo: {file_path}")

    if not os.path.exists(file_path):
        error_msg = f"Erro: O arquivo '{file_path}' não foi encontrado no caminho especificado."
        logger.error(error_msg)
        return error_msg

    try:
        # Detectar formato do arquivo
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.xlsx', '.xls']:
            # Se sheet_name for None, usamos 0 para ler a primeira aba por padrão, evitando retornar um dicionário
            s_name = sheet_name if sheet_name is not None else 0
            df = pd.read_excel(file_path, sheet_name=s_name)
        elif ext in ['.csv']:
            # Tentar ler com codificações comuns
            for encoding in ['utf-8', 'latin1', 'iso-8859-1']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                df = pd.read_csv(file_path)
        else:
            return f"Erro: Formato de arquivo '{ext}' não suportado. Use .csv, .xlsx ou .xls."

        # Salvar cópia no arquivo de trabalho de estado atual
        os.makedirs(os.path.dirname(WORKING_FILE_PATH), exist_ok=True)
        df.to_csv(WORKING_FILE_PATH, index=False)
        logger.info(f"Arquivo carregado com sucesso ({df.shape[0]} linhas, {df.shape[1]} colunas). Estado salvo em {WORKING_FILE_PATH}")

        # Coletar informações do esquema
        total_rows, total_cols = df.shape
        schema_info = []
        for col in df.columns:
            null_count = int(df[col].isnull().sum())
            null_pct = (null_count / total_rows) * 100 if total_rows > 0 else 0.0
            dtype = str(df[col].dtype)
            schema_info.append(f" - '{col}' ({dtype}): {null_count} nulos ({null_pct:.1f}%)")

        columns_summary = "\n".join(schema_info)
        head_summary = df.head(5).to_string()

        summary = (
            f"=== RESUMO DA PLANILHA CARREGADA ===\n"
            f"Caminho original: {file_path}\n"
            f"Estrutura: {total_rows} linhas x {total_cols} colunas\n\n"
            f"--- ESQUEMA DE COLUNAS e TIPOS ---\n"
            f"{columns_summary}\n\n"
            f"--- PRIMEIRAS 5 LINHAS (AMOSTRA) ---\n"
            f"{head_summary}\n"
            f"====================================\n"
        )
        return summary

    except Exception as e:
        logger.exception("Erro ao ler ou processar planilha.")
        return f"Erro ao analisar planilha: {str(e)}"
