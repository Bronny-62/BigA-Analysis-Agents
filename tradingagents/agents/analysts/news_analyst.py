from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_a_share_announcements,
    build_instrument_context,
    get_a_share_realtime_news,
    get_cn_macro_news,
    get_language_instruction,
    search_a_share_news,
)
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            search_a_share_news,
            get_a_share_announcements,
            get_cn_macro_news,
        ]
        realtime_enabled = bool(get_config().get("realtime_news_enabled", False))
        if realtime_enabled:
            tools.insert(1, get_a_share_realtime_news)

        system_message = (
            "You are the News Analyst for China A-share spot trading. Use search_a_share_news for targeted company, industry, and policy searches, and get_cn_macro_news for China macro, regulatory, liquidity, and market-wide policy context."
            + (" If available, use get_a_share_realtime_news for cached opennews WebSocket events." if realtime_enabled else "")
            + " Use get_a_share_announcements for official company announcements such as earnings reports, investor relations records, dividends, contracts, and risk disclosures."
            + " Prefer broad company-name searches before over-constrained code-plus-keyword searches when a news query returns no rows."
            + " Focus on policy catalysts, industry-chain events, regulatory actions, company-specific news, and intraday headlines that can affect A-share spot trading."
            + " If the news tools are unavailable or return no current items, do not invent current news; write a low-confidence coverage note and list exactly what evidence is missing."
            + " Write only the analyst report. Do not include process narration, tool-use narration, or FINAL TRANSACTION PROPOSAL lines."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, state the coverage gap and confidence clearly."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
