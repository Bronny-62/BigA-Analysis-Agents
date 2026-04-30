from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_a_share_indicators,
    get_a_share_market_snapshot,
    get_a_share_moneyflow,
    get_a_share_ohlcv,
    get_language_instruction,
)


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_a_share_ohlcv,
            get_a_share_market_snapshot,
            get_a_share_indicators,
            get_a_share_moneyflow,
        ]

        system_message = (
            """You are the Market Analyst for China A-share spot trading. Analyze price action, liquidity, volatility, limit-up/limit-down context, money flow, turnover, and sector-style momentum for the given ts_code.

Use the A-share tools only:
- get_a_share_ohlcv for daily/weekly/monthly OHLCV history.
- get_a_share_market_snapshot for the trading-date snapshot, valuation, liquidity, and limit-price context.
- get_a_share_indicators for indicators such as close_20_sma, close_60_sma, macd, rsi, boll, atr, vr, and volume-price confirmation.
- get_a_share_moneyflow for capital flow and dragon-tiger list context where available.

Focus on actionable A-share evidence: trend structure, support/resistance, abnormal volume, turnover, liquidity crowding, daily limit risk, and whether price behavior confirms or contradicts the trade thesis."""
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
            "market_report": report,
        }

    return market_analyst_node
