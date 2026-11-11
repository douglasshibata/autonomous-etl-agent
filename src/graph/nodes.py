import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from config.settings import settings
from src.core.state import ETLState
from src.core.sandbox import IsolatedDataEngine
from src.tools.analyzer import profile_tabular_data
from src.tools.exporter import DataExporter

logger = logging.getLogger("ETL_Agent.graph.nodes")

class DeterministicMockLLM(BaseChatModel):
    """
    Mock LLM offline para testes e pipelines sem dependência de credencial OpenAI externa.
    Retorna código Pandas determinístico para resolver inconsistências comuns.
    """
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatResult, ChatGeneration

        last_msg = messages[-1].content if messages else ""

        # Se for feedback de erro (reflection)
        if "Último erro registrado (se houver):" in last_msg and "Falha de execução:" in last_msg:
            # Gerar código corrigido sem o erro anterior
            clean_code = (
                "if 'ID_Pedido' in df.columns:\n"
                "    df = df.dropna(subset=['ID_Pedido'])\n"
                "if 'Cliente' in df.columns:\n"
                "    df['Cliente'] = df['Cliente'].fillna('Consumidor Final')\n"
            )
        else:
            clean_code = (
                "if 'ID_Pedido' in df.columns:\n"
                "    df = df.dropna(subset=['ID_Pedido'])\n"
                "if 'Cliente' in df.columns:\n"
                "    df['Cliente'] = df['Cliente'].fillna('Consumidor Final')\n"
                "if 'Valor_Bruto' in df.columns:\n"
                "    df['Valor_Bruto'] = df['Valor_Bruto'].astype(str).str.replace('R$', '', regex=False)\n"
                "    df['Valor_Bruto'] = df['Valor_Bruto'].str.replace('.', '', regex=False)\n"
                "    df['Valor_Bruto'] = df['Valor_Bruto'].str.replace(',', '.', regex=False)\n"
                "    df['Valor_Bruto'] = pd.to_numeric(df['Valor_Bruto'].str.strip(), errors='coerce')\n"
                "if 'Quantidade' in df.columns:\n"
                "    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0).astype(int)\n"
            )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=clean_code))])

    @property
    def _llm_type(self) -> str:
        return "deterministic_mock_llm"


def get_llm(override_llm: Optional[BaseChatModel] = None) -> BaseChatModel:
    if override_llm is not None:
        return override_llm
    if settings.openai_api_key:
        return ChatOpenAI(
            model=settings.agent_model,
            temperature=settings.temperature,
            api_key=settings.openai_api_key
        )
    return DeterministicMockLLM()


def node_analyze(state: ETLState) -> Dict[str, Any]:
    """Inspeciona o arquivo tabular ou parquet atual e constrói o perfil analítico."""
    current_path = Path(state["current_checkpoint_path"])

    # Se o checkpoint atual for um arquivo bruto (.csv ou .xlsx), converter para .parquet inicial
    if current_path.suffix.lower() in [".csv", ".xlsx", ".xls"]:
        session_dir = current_path.parent
        initial_parquet = session_dir / f"checkpoint_0_raw.parquet"
        if current_path.suffix.lower() == ".csv":
            df = pd.read_csv(current_path)
        else:
            df = pd.read_excel(current_path, sheet_name=0)
        df.to_parquet(initial_parquet, engine="pyarrow", index=False)
        current_path = initial_parquet

    profile = profile_tabular_data(current_path)

    summary_msg = (
        f"Arquivo analisado: {profile['total_rows']} linhas, {profile['total_columns']} colunas.\n"
        f"Inconsistências encontradas: {profile['inconsistencies_detected']}\n"
        f"Nulos por coluna: {profile['missing_percentages']}"
    )

    return {
        "current_checkpoint_path": str(current_path),
        "data_profile": profile,
        "messages": [SystemMessage(content=summary_msg)]
    }


def node_plan_and_transform(state: ETLState, llm: Optional[BaseChatModel] = None) -> Dict[str, Any]:
    """Gera código Pandas para corrigir inconsistências e executa com rollback."""
    chat_llm = get_llm(llm)
    engine = IsolatedDataEngine(memory_limit_mb=settings.sandbox_memory_limit_mb)

    prompt = f"""
Você é um Engenheiro de Dados Sênior. Gere código Python/Pandas para limpar o DataFrame 'df'.

Perfil atual dos dados:
{state.get('data_profile')}

Último erro registrado (se houver):
{state.get('last_error')}

REGRAS INVIOLÁVEIS:
1. O DataFrame chama-se exclusivamente 'df'.
2. NÃO use imports. NÃO faça I/O. NÃO acesse variáveis com dunder '__'.
3. Retorne APENAS o bloco de código Python executável sem formatação markdown ou explicações.
"""

    response = chat_llm.invoke([HumanMessage(content=prompt)])
    clean_code = response.content.replace("```python", "").replace("```", "").strip()

    curr_path = Path(state["current_checkpoint_path"])
    next_path = curr_path.parent / f"step_{uuid.uuid4().hex[:8]}.parquet"

    success, msg, diff = engine.execute_transform(clean_code, curr_path, next_path)

    if success:
        return {
            "current_checkpoint_path": str(next_path),
            "transformation_history": state["transformation_history"] + [clean_code],
            "last_error": None,
            "retry_count": 0,
            "messages": [SystemMessage(content=f"Transformação aplicada com sucesso. Diff: {diff}")]
        }
    else:
        return {
            "last_error": msg,
            "retry_count": state["retry_count"] + 1,
            "messages": [SystemMessage(content=f"Erro na execução da transformação: {msg}")]
        }


def node_export_data(state: ETLState) -> Dict[str, Any]:
    """Exporta o Parquet final para múltiplos formatos higienizados."""
    current_path = Path(state["current_checkpoint_path"])
    df = pd.read_parquet(current_path)
    session_dir = current_path.parent

    artifacts = {
        "parquet": str(DataExporter.to_parquet(df, session_dir / "output.parquet")),
        "json": str(DataExporter.to_json(df, session_dir / "output.json")),
        "csv": str(DataExporter.to_csv(df, session_dir / "output.csv")),
        "sql": str(DataExporter.to_sqlite_dump(df, session_dir / "output_dump", table_name="cleaned_sales")),
        "xml": str(DataExporter.to_xml(df, session_dir / "output.xml"))
    }

    return {
        "exported_artifacts": artifacts,
        "execution_complete": True,
        "messages": [SystemMessage(content=f"Exportação finalizada com sucesso. Artefatos: {list(artifacts.keys())}")]
    }
