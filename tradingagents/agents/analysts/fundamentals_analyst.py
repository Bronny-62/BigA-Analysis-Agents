from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_a_share_announcements,
    build_instrument_context,
    get_a_share_company_profile,
    get_a_share_financials,
    get_a_share_fundamental_snapshot,
    get_language_instruction,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_a_share_company_profile,
            get_a_share_financials,
            get_a_share_announcements,
            get_a_share_fundamental_snapshot,
        ]

        system_message = (
            "You are the Fundamentals Analyst for China A-share spot trading. Analyze company profile, financial statements, financial indicators, dividends, share float, earnings forecasts or express reports, and Cninfo announcements. Pay special attention to A-share events: earnings preview, annual/interim/quarterly reports, major contracts, restructuring, pledge risk, unlocking pressure, buybacks, dividends, regulatory inquiry letters, and abnormal disclosure risk."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use get_a_share_company_profile, get_a_share_financials, get_a_share_announcements, and get_a_share_fundamental_snapshot. The announcements tool tries Tushare first and falls back to Cninfo when the separate Tushare announcement permission is not available."
            + " Write only the analyst report. Do not include process narration, tool-use narration, or FINAL TRANSACTION PROPOSAL lines."
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
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
