import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, ToolCall, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Importar as ferramentas locais
from tools.analyze_spreadsheet import analyze_spreadsheet
from tools.apply_pandas_transformations import apply_pandas_transformations
from tools.export_data import export_data
from tools.execute_automation_script import execute_automation_script

logger = logging.getLogger("ETL_Agent.agent_orchestrator")
load_dotenv()

# Configuração de chaves
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o")

# Prompt do Sistema do Agente de Dados Meticuloso
SYSTEM_PROMPT = """Você é um Agente Autônomo de ETL (Extract, Transform, Load) e Automação de Dados sênior, agindo como um meticuloso Data Wrangler e Engenheiro de Dados.
Sua missão é processar planilhas brutas de dados sujos, corrigir inconsistências de dados e de estrutura, convertê-las para o formato de entrega solicitado e disparar scripts de automação.

Diretrizes de Raciocínio Meticuloso (Chain of Thought):
1. **Planejamento Prévio:** Antes de aplicar qualquer alteração ou escrever código Pandas, você DEVE analisar minuciosamente o esquema atual usando `analyze_spreadsheet`. Nunca execute suposições sobre nomes de colunas ou tipos.
2. **Prevenção de Perda de Dados:** Garanta que dados críticos não sejam perdidos nas limpezas ou transformações. Por exemplo, ao preencher ou dropar nulos, justifique se isso afeta o dataset.
3. **Segurança de Código:** Use apenas código Pandas padrão na ferramenta `apply_pandas_transformations`. Não tente escapar do ambiente, importar bibliotecas proibidas ou usar métodos privados.
4. **Exportação Confiável:** Converta os dados transformados para o formato desejado (CSV, JSON, XML ou SQL) usando `export_data`.
5. **Automação Segura:** Se solicitado, execute scripts auxiliares na pasta `/scripts` usando `execute_automation_script`. Garanta que os parâmetros passados correspondam aos arquivos gerados.
6. **Relatórios Finais:** Apresente um resumo claro e estruturado de cada etapa realizada, detalhando o que foi alterado e o resultado da execução.
"""

# ---------------------------------------------------------------------------
# MOCK LLM ENGINE (Para testes automatizados e execuções offline resilientes)
# ---------------------------------------------------------------------------
class MockETLAgentLLM(BaseChatModel):
    """
    Mock LLM de alta fidelidade para o fluxo de ETL.
    Simula perfeitamente a tomada de decisão do agente passo a passo,
    acionando todas as ferramentas sequencialmente em resposta a perguntas de limpeza de dados.
    """

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> ChatResult:
        # Analisar o histórico de mensagens para decidir o próximo passo
        # 1. Identificar se há alguma resposta de ferramenta
        tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]

        if not tool_messages:
            # Caso inicial: O usuário acabou de fazer a solicitação.
            # Decidimos rodar 'analyze_spreadsheet' para entender o arquivo.
            logger.info("[MockLLM] Estado Inicial: Planejando análise da planilha.")

            # Tentar extrair o nome do arquivo da última mensagem, caso contrário usar default
            last_user_msg = messages[-1].content
            file_path = "autonomous-etl-agent/data/input/sales_report_dirty.xlsx"
            if "csv" in last_user_msg.lower():
                file_path = "autonomous-etl-agent/data/input/sales_report_dirty.csv"

            tool_call = ToolCall(
                name="analyze_spreadsheet",
                args={"file_path": file_path},
                id="call_analyze_sp"
            )
            message = AIMessage(
                content="Entendido. Começarei analisando o esquema e a estrutura da planilha bruta para entender as inconsistências e colunas.",
                tool_calls=[tool_call]
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

        # Obter a última mensagem de ferramenta
        last_tool_msg = tool_messages[-1]
        tool_name = last_tool_msg.name

        if tool_name == "analyze_spreadsheet":
            # Passo 2: Analisamos o esquema e planejamos a transformação no Pandas.
            logger.info("[MockLLM] Passo 2: Gerando código Pandas seguro para higienização e conversão.")

            # Código pandas para limpar nulos, formatar moeda para americano (float) e tipos
            pandas_code = (
                "# 1. Tratar valores nulos de ID_Pedido e preencher Cliente vazio\n"
                "df.dropna(subset=['ID_Pedido'], inplace=True)\n"
                "df['Cliente'] = df['Cliente'].fillna('Consumidor Final')\n\n"
                "# 2. Converter Valor_Bruto (Moeda R$) para decimal americano\n"
                "if 'Valor_Bruto' in df.columns:\n"
                "    df['Valor_Bruto'] = df['Valor_Bruto'].astype(str).str.replace('R$', '', regex=False)\n"
                "    df['Valor_Bruto'] = df['Valor_Bruto'].str.replace('.', '', regex=False)\n"
                "    df['Valor_Bruto'] = df['Valor_Bruto'].str.replace(',', '.', regex=False)\n"
                "    df['Valor_Bruto'] = pd.to_numeric(df['Valor_Bruto'].str.strip(), errors='coerce')\n\n"
                "# 3. Converter Quantidade para inteiro\n"
                "if 'Quantidade' in df.columns:\n"
                "    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0).astype(int)\n"
            )

            tool_call = ToolCall(
                name="apply_pandas_transformations",
                args={"pandas_code": pandas_code},
                id="call_apply_pandas"
            )
            message = AIMessage(
                content="Analisei a estrutura. Vou remover linhas onde 'ID_Pedido' é nulo, preencher 'Cliente' ausente como 'Consumidor Final', formatar a moeda da coluna 'Valor_Bruto' para floats válidos e garantir que 'Quantidade' seja do tipo inteiro.",
                tool_calls=[tool_call]
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

        elif tool_name == "apply_pandas_transformations":
            # Passo 3: Com os dados limpos, exportamos para o formato JSON solicitado.
            logger.info("[MockLLM] Passo 3: Dados limpos no estado atual. Planejando exportação para JSON estruturado.")

            tool_call = ToolCall(
                name="export_data",
                args={"format_type": "json", "output_name": "sales_report_clean"},
                id="call_export_json"
            )
            message = AIMessage(
                content="Transformações aplicadas com sucesso! Agora vou exportar esses dados tratados para o formato JSON estruturado.",
                tool_calls=[tool_call]
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

        elif tool_name == "export_data":
            # Passo 4: Rodamos o script de automação 'upload_to_api.py' passando o JSON gerado.
            # Nota importante: Mudamos o nome do argumento de 'args' para 'script_args' para evitar conflito de nomenclatura no Langchain!
            logger.info("[MockLLM] Passo 4: Dados exportados. Planejando execução do script de automação upload_to_api.py.")

            tool_call = ToolCall(
                name="execute_automation_script",
                args={"script_name": "upload_to_api.py", "script_args": ["sales_report_clean.json"]},
                id="call_exec_script"
            )
            message = AIMessage(
                content="Arquivo JSON gerado e salvo com sucesso na pasta de saídas. Agora executarei o script de automação 'upload_to_api.py' de forma isolada para processar ou subir os dados.",
                tool_calls=[tool_call]
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

        elif tool_name == "execute_automation_script":
            # Passo Final: Resumo de todo o trabalho executado
            logger.info("[MockLLM] Passo Final: Sintetizando relatório para o usuário.")

            final_report = (
                "### 🎯 FLUXO DE COMPILAÇÃO E AUTOMAÇÃO ETL COMPLETO COM SUCESSO!\n\n"
                "Olá! Concluí todas as etapas solicitadas para o processamento de sua planilha de vendas suja:\n\n"
                "1. **Leitura e Resumo de Esquema (`analyze_spreadsheet`):** Carreguei a planilha crua, identifiquei as colunas `ID_Pedido`, `Cliente`, `Valor_Bruto`, `Quantidade` e rastreei dados nulos e formatos brasileiros de moeda.\n"
                "2. **Higienização Avançada com Pandas (`apply_pandas_transformations`):** \n"
                "   - Deletei registros onde o identificador `ID_Pedido` estava ausente.\n"
                "   - Substituí clientes não preenchidos por `'Consumidor Final'` para manter a integridade.\n"
                "   - Tratei a coluna monetária `Valor_Bruto`, removendo o prefixo `R$` e convertendo os separadores decimais para o formato numérico americano standard (`float64`).\n"
                "   - Forcei a conversão de `Quantidade` para inteiro (`int`).\n"
                "3. **Exportação Estruturada (`export_data`):** Exportei com sucesso o conjunto limpo de dados para um arquivo JSON estruturado em `/data/output/sales_report_clean.json`.\n"
                "4. **Automação de Envio (`execute_automation_script`):** Executei o script `upload_to_api.py` de forma segura. O script leu o arquivo JSON gerado e simulou a transmissão correta dos dados à API de vendas corporativa.\n\n"
                "Os arquivos gerados estão disponíveis em `/data/output/` para auditoria!"
            )
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=final_report))])

        # Caso genérico de fallback
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Processamento concluído."))])

    @property
    def _llm_type(self) -> str:
        return "mock_etl_agent_llm"

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> Any:
        return self

# ---------------------------------------------------------------------------
# INSTANCIAÇÃO DO AGENTE DE ORQUESTRAÇÃO
# ---------------------------------------------------------------------------
def get_agent():
    """
    Constrói e retorna o grafo executor do agente de dados.
    Configura automaticamente se usará o LLM real do OpenAI ou o Mock de alta fidelidade offline.
    """
    if not OPENAI_API_KEY:
        logger.info("[Orchestrator] Utilizando MockETLAgentLLM para orquestração offline de alta fidelidade.")
        llm = MockETLAgentLLM()
    else:
        logger.info(f"[Orchestrator] Conectando ao OpenAI Chat Model: '{AGENT_MODEL}'")
        llm = ChatOpenAI(model=AGENT_MODEL, temperature=0.1, openai_api_key=OPENAI_API_KEY)

    tools = [
        analyze_spreadsheet,
        apply_pandas_transformations,
        export_data,
        execute_automation_script
    ]

    try:
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=SYSTEM_PROMPT
        )
    except TypeError:
        # Suporte para assinaturas de versões anteriores do LangGraph
        agent = create_react_agent(
            model=llm,
            tools=tools,
            state_modifier=SYSTEM_PROMPT
        )

    return agent
