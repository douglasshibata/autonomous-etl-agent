import os
import logging
import numpy as np
import pandas as pd
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger("ETL_Agent.export_data")

WORKING_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "current_state.csv"
)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "output"
)

def _generate_sql_script(df: pd.DataFrame, table_name: str) -> str:
    """
    Gera scripts de criação de tabela (CREATE TABLE) e inserções (INSERT INTO)
    a partir de um DataFrame do Pandas.
    """
    # Mapeamento simples de dtypes Pandas para SQL padrão
    type_mapping = {
        'int64': 'INT',
        'float64': 'DECIMAL(10, 2)',
        'bool': 'BOOLEAN',
        'object': 'VARCHAR(255)'
    }

    columns_def = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        sql_type = 'VARCHAR(255)'
        for pd_type, s_type in type_mapping.items():
            if pd_type in dtype:
                sql_type = s_type
                break
        # Tratar espaços ou caracteres especiais nos nomes das colunas
        safe_col_name = f'"{col}"'
        columns_def.append(f"    {safe_col_name} {sql_type}")

    create_table = f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(columns_def) + "\n);\n\n"

    insert_statements = []
    for _, row in df.iterrows():
        vals = []
        for col in df.columns:
            val = row[col]
            if pd.isnull(val):
                vals.append("NULL")
            # Tratar tipos booleanos do python e numpy de forma robusta
            elif isinstance(val, (bool, np.bool_)) or str(val).lower() in ['true', 'false'] and 'bool' in str(df[col].dtype):
                is_true = str(val).lower() == 'true' if isinstance(val, (str, np.bool_)) else bool(val)
                vals.append("TRUE" if is_true else "FALSE")
            elif isinstance(val, (int, float, np.integer, np.floating)):
                vals.append(str(val))
            else:
                # Escapar aspas simples para segurança SQL
                escaped_val = str(val).replace("'", "''")
                vals.append(f"'{escaped_val}'")

        safe_cols = ", ".join([f'"{c}"' for c in df.columns])
        insert_statements.append(f"INSERT INTO {table_name} ({safe_cols}) VALUES ({', '.join(vals)});")

    return create_table + "\n".join(insert_statements)

@tool
def export_data(format_type: str, output_name: str, table_name: Optional[str] = None) -> str:
    """
    Exporta o DataFrame contido no estado de trabalho atual para o formato especificado.
    Formatos suportados: csv, json, xml, sql.

    Args:
        format_type (str): O formato de saída. Deve ser 'csv', 'json', 'xml' ou 'sql' (case-insensitive).
        output_name (str): O nome do arquivo final de saída (ex: 'vendas_limpas'). O diretório e extensão serão atribuídos automaticamente.
        table_name (str, opcional): Nome da tabela SQL (caso format_type seja 'sql'). Se não fornecido, usará o output_name.

    Returns:
        str: Mensagem de sucesso contendo o caminho absoluto do arquivo exportado e uma breve amostra.
    """
    logger.info(f"Iniciando exportação de dados para o formato: {format_type}")

    if not os.path.exists(WORKING_FILE_PATH):
        return "Erro: Nenhum estado de DataFrame ativo encontrado. Carregue uma planilha primeiro."

    format_type = format_type.strip().lower()
    if format_type not in ['csv', 'json', 'xml', 'sql']:
        return f"Erro: Formato de exportação '{format_type}' não suportado. Use 'csv', 'json', 'xml' ou 'sql'."

    try:
        df = pd.read_csv(WORKING_FILE_PATH)

        # Garantir diretório de saída
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Limpar extensão se fornecida no output_name
        output_name_base = os.path.splitext(output_name)[0]
        output_filename = f"{output_name_base}.{format_type}"
        dest_path = os.path.join(OUTPUT_DIR, output_filename)

        if format_type == 'csv':
            df.to_csv(dest_path, index=False)

        elif format_type == 'json':
            # Exportar como lista de objetos JSON bem formatada
            df.to_json(dest_path, orient='records', indent=2, force_ascii=False)

        elif format_type == 'xml':
            # Exportar para XML estruturado usando pandas built-in (etree parser)
            try:
                df.to_xml(dest_path, index=False, parser='etree')
            except Exception as xml_err:
                # Fallback manual em caso de falha de parser do XML
                logger.warning(f"Erro no to_xml nativo, usando fallback manual: {xml_err}")
                xml_data = ['<data>']
                for _, row in df.iterrows():
                    xml_data.append('  <row>')
                    for col in df.columns:
                        val = row[col]
                        safe_val = "" if pd.isnull(val) else str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        safe_col = str(col).replace(" ", "_")
                        xml_data.append(f'    <{safe_col}>{safe_val}</{safe_col}>')
                    xml_data.append('  </row>')
                xml_data.append('</data>')
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(xml_data))

        elif format_type == 'sql':
            t_name = table_name if table_name else output_name_base
            sql_script = _generate_sql_script(df, t_name)
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(sql_script)

        logger.info(f"Dados exportados com sucesso para {dest_path}")

        # Obter preview do arquivo
        preview_content = ""
        with open(dest_path, 'r', encoding='utf-8', errors='ignore') as f:
            preview_content = "".join(f.readlines()[:15]) # primeiras 15 linhas

        return (
            f"=== SUCESSO NA EXPORTAÇÃO ===\n"
            f"Formato: {format_type.upper()}\n"
            f"Arquivo de Saída: {dest_path}\n"
            f"Tamanho: {os.path.getsize(dest_path)} bytes\n\n"
            f"--- PRÉ-VISUALIZAÇÃO DO ARQUIVO GERADO (PRIMEIRAS LINHAS) ---\n"
            f"{preview_content}\n"
            f"=============================\n"
        )

    except Exception as e:
        logger.exception("Falha ao exportar dados.")
        return f"Erro ao exportar dados: {str(e)}"
