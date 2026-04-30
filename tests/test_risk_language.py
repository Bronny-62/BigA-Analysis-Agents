from unittest.mock import MagicMock

import pytest

from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG


def _risk_state():
    return {
        "risk_debate_state": {
            "history": "",
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "count": 0,
        },
        "market_report": "市场报告",
        "sentiment_report": "情绪报告",
        "news_report": "新闻报告",
        "fundamentals_report": "基本面报告",
        "trader_investment_plan": "交易员计划",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("factory", "history_key", "speaker"),
    [
        (create_aggressive_debator, "aggressive_history", "激进风险分析师"),
        (create_conservative_debator, "conservative_history", "保守风险分析师"),
        (create_neutral_debator, "neutral_history", "中性风险分析师"),
    ],
)
def test_risk_debators_follow_chinese_output_language(factory, history_key, speaker):
    set_config({**DEFAULT_CONFIG, "output_language": "Chinese"})
    try:
        captured = {}
        llm = MagicMock()
        llm.invoke.side_effect = lambda prompt: (
            captured.__setitem__("prompt", prompt)
            or MagicMock(content="请用风险视角评估该交易计划。")
        )

        result = factory(llm)(_risk_state())
    finally:
        set_config(DEFAULT_CONFIG.copy())

    assert "Write your entire response in Chinese" in captured["prompt"]
    assert f"{speaker}: 请用风险视角评估该交易计划。" in result["risk_debate_state"][history_key]
