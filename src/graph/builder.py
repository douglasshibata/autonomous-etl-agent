from typing import Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.language_models.chat_models import BaseChatModel

from src.core.state import ETLState
from src.graph.nodes import node_analyze, node_plan_and_transform, node_export_data

def route_after_transform(state: ETLState) -> Literal["plan_and_transform", "export_data", "__end__"]:
    """
    Roteador condicional: Se ocorreu erro e ainda há retentativas, retorna para plano & transformação (self-healing loop).
    Se sucesso, prossegue para exportação. Se excedeu retentativas máximas, encerra em falha graciosa.
    """
    if state.get("last_error"):
        if state.get("retry_count", 0) < state.get("max_retries", 3):
            return "plan_and_transform"
        return "__end__"
    return "export_data"

def build_etl_graph(override_llm: Optional[BaseChatModel] = None) -> StateGraph:
    """Compila o grafo do LangGraph com loop cognitivo de autorreparo e reflexão."""
    workflow = StateGraph(ETLState)

    def _plan_and_transform_bound(state: ETLState):
        return node_plan_and_transform(state, llm=override_llm)

    workflow.add_node("analyze", node_analyze)
    workflow.add_node("plan_and_transform", _plan_and_transform_bound)
    workflow.add_node("export_data", node_export_data)

    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "plan_and_transform")
    workflow.add_conditional_edges("plan_and_transform", route_after_transform)
    workflow.add_edge("export_data", END)

    return workflow.compile()
