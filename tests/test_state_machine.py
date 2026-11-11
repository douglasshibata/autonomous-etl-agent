import uuid
from pathlib import Path
import pandas as pd
import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.language_models.chat_models import BaseChatModel

from src.core.state import ETLState
from src.graph.builder import build_etl_graph, route_after_transform

class FailingThenSucceedingMockLLM(BaseChatModel):
    """
    Mock LLM que intencionalmente gera código com erro na primeira invocação,
    e gera código corrigido na segunda invocação (testando reflection & self-healing).
    """
    def __init__(self):
        super().__init__()
        self._call_count = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._call_count += 1
        if self._call_count == 1:
            # Primeiro: gera KeyError proposital
            code = "df['coluna_inexistente_que_vai_falhar'] = df['inexistente'] + 1"
        else:
            # Segundo: autorreparo bem-sucedido
            code = "df['ID_Pedido'] = df['ID_Pedido'].fillna(9999)"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=code))])

    @property
    def _llm_type(self) -> str:
        return "failing_then_succeeding_mock_llm"


class AlwaysFailingMockLLM(BaseChatModel):
    """
    Mock LLM que sempre falha para testar o limite de retentativas (max_retries).
    """
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        code = "df['non_existent_key_error'] = df['does_not_exist']"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=code))])

    @property
    def _llm_type(self) -> str:
        return "always_failing_mock_llm"


def test_routing_logic_retry_and_termination():
    """Valida a lógica de roteamento condicional sob diferentes cenários de erro e retentativa."""
    # Cenário 1: Sucesso sem erro -> rota para export_data
    state_success: ETLState = {
        "session_id": "test",
        "input_file_path": "",
        "current_checkpoint_path": "",
        "data_profile": None,
        "transformation_history": [],
        "last_error": None,
        "retry_count": 0,
        "max_retries": 3,
        "exported_artifacts": {},
        "messages": [],
        "execution_complete": False
    }
    assert route_after_transform(state_success) == "export_data"

    # Cenário 2: Erro presente mas tentativas restantes -> rota para autorreparo
    state_retry: ETLState = {
        **state_success,
        "last_error": "KeyError: 'foo'",
        "retry_count": 1,
        "max_retries": 3
    }
    assert route_after_transform(state_retry) == "plan_and_transform"

    # Cenário 3: Erro presente e excedeu max_retries -> rota para fim (__end__)
    state_exhausted: ETLState = {
        **state_success,
        "last_error": "KeyError: 'foo'",
        "retry_count": 3,
        "max_retries": 3
    }
    assert route_after_transform(state_exhausted) == "__end__"


def test_state_machine_self_healing_loop(tmp_path):
    """Testa se o grafo do LangGraph se recupera de uma falha através do ciclo de feedback."""
    # Criar um Parquet inicial
    initial_parquet = tmp_path / "initial.parquet"
    df = pd.DataFrame({"ID_Pedido": [1001, None, 1003], "Cliente": ["A", "B", "C"]})
    df.to_parquet(initial_parquet, engine="pyarrow", index=False)

    failing_llm = FailingThenSucceedingMockLLM()
    graph = build_etl_graph(override_llm=failing_llm)

    state: ETLState = {
        "session_id": str(uuid.uuid4()),
        "input_file_path": str(initial_parquet),
        "current_checkpoint_path": str(initial_parquet),
        "data_profile": None,
        "transformation_history": [],
        "last_error": None,
        "retry_count": 0,
        "max_retries": 3,
        "exported_artifacts": {},
        "messages": [],
        "execution_complete": False
    }

    result = graph.invoke(state)

    # Verificações de autorreparo
    assert result["execution_complete"] is True
    assert result["last_error"] is None
    assert len(result["transformation_history"]) == 1
    assert "parquet" in result["exported_artifacts"]
    assert "json" in result["exported_artifacts"]


def test_state_machine_exhausted_retries_termination(tmp_path):
    """Testa se o grafo encerra graciosamente quando atinge o limite máximo de retentativas."""
    initial_parquet = tmp_path / "initial.parquet"
    df = pd.DataFrame({"ID_Pedido": [1001, 1002]})
    df.to_parquet(initial_parquet, engine="pyarrow", index=False)

    always_failing_llm = AlwaysFailingMockLLM()
    graph = build_etl_graph(override_llm=always_failing_llm)

    state: ETLState = {
        "session_id": str(uuid.uuid4()),
        "input_file_path": str(initial_parquet),
        "current_checkpoint_path": str(initial_parquet),
        "data_profile": None,
        "transformation_history": [],
        "last_error": None,
        "retry_count": 0,
        "max_retries": 2,
        "exported_artifacts": {},
        "messages": [],
        "execution_complete": False
    }

    result = graph.invoke(state)

    assert result["execution_complete"] is False
    assert result["retry_count"] >= 2
    assert result["last_error"] is not None
    assert result["exported_artifacts"] == {}
