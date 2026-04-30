import inspect
from unittest.mock import MagicMock

import pytest

from cli import main as cli_main
from tradingagents.agents.managers import portfolio_manager, research_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.schemas import (
    PortfolioDecision,
    PortfolioRating,
    ResearchPlan,
    render_pm_decision,
    render_research_plan,
)
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG


USER_VISIBLE_AGENT_MODULES = [
    "tradingagents.agents.analysts.market_analyst",
    "tradingagents.agents.analysts.social_media_analyst",
    "tradingagents.agents.analysts.news_analyst",
    "tradingagents.agents.analysts.fundamentals_analyst",
    "tradingagents.agents.researchers.bull_researcher",
    "tradingagents.agents.researchers.bear_researcher",
    "tradingagents.agents.managers.research_manager",
    "tradingagents.agents.trader.trader",
    "tradingagents.agents.risk_mgmt.aggressive_debator",
    "tradingagents.agents.risk_mgmt.conservative_debator",
    "tradingagents.agents.risk_mgmt.neutral_debator",
    "tradingagents.agents.managers.portfolio_manager",
]


def _base_debate_state():
    return {
        "investment_debate_state": {
            "history": "",
            "bull_history": "",
            "bear_history": "",
            "current_response": "",
            "count": 0,
        },
        "market_report": "市场报告",
        "sentiment_report": "情绪报告",
        "news_report": "新闻报告",
        "fundamentals_report": "基本面报告",
    }


@pytest.mark.unit
@pytest.mark.parametrize("module_path", USER_VISIBLE_AGENT_MODULES)
def test_user_visible_agents_include_language_instruction(module_path):
    module = __import__(module_path, fromlist=["dummy"])
    assert "get_language_instruction" in inspect.getsource(module)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("factory", "history_key", "speaker", "route_prefix"),
    [
        (create_bull_researcher, "bull_history", "多方研究员", "Bull Analyst"),
        (create_bear_researcher, "bear_history", "空方研究员", "Bear Analyst"),
    ],
)
def test_researchers_follow_chinese_output_language(factory, history_key, speaker, route_prefix):
    set_config({**DEFAULT_CONFIG, "output_language": "Chinese"})
    try:
        captured = {}
        llm = MagicMock()
        llm.invoke.side_effect = lambda prompt: (
            captured.__setitem__("prompt", prompt)
            or MagicMock(content="请基于证据给出研究观点。")
        )

        result = factory(llm)(_base_debate_state())
    finally:
        set_config(DEFAULT_CONFIG.copy())

    debate_state = result["investment_debate_state"]
    assert "Write your entire response in Chinese" in captured["prompt"]
    assert f"{speaker}: 请基于证据给出研究观点。" in debate_state[history_key]
    assert debate_state["current_response"].startswith(f"{route_prefix}:")
    assert f"{route_prefix}: 请基于证据给出研究观点。" in debate_state["history"]


@pytest.mark.unit
def test_research_manager_prompt_and_render_follow_chinese_language():
    set_config({**DEFAULT_CONFIG, "output_language": "Chinese"})
    try:
        assert "get_language_instruction" in inspect.getsource(research_manager)
        md = render_research_plan(
            ResearchPlan(
                recommendation=PortfolioRating.OVERWEIGHT,
                rationale="多方证据略占优。",
                strategic_actions="小幅增持并设置止损。",
            )
        )
    finally:
        set_config(DEFAULT_CONFIG.copy())

    assert "**投资建议**: 增持" in md
    assert "**理由**: 多方证据略占优。" in md
    assert "**行动计划**: 小幅增持并设置止损。" in md
    assert "Recommendation" not in md


@pytest.mark.unit
def test_portfolio_manager_render_follow_chinese_language():
    set_config({**DEFAULT_CONFIG, "output_language": "Chinese"})
    try:
        assert "get_language_instruction" in inspect.getsource(portfolio_manager)
        md = render_pm_decision(
            PortfolioDecision(
                rating=PortfolioRating.SELL,
                executive_summary="降低风险暴露。",
                investment_thesis="资金面和技术面转弱。",
                price_target=10.5,
                time_horizon="1-2周",
            )
        )
    finally:
        set_config(DEFAULT_CONFIG.copy())

    assert "**评级**: 卖出" in md
    assert "**执行摘要**: 降低风险暴露。" in md
    assert "**投资逻辑**: 资金面和技术面转弱。" in md
    assert "**目标价**: 10.5" in md
    assert "**投资期限**: 1-2周" in md
    assert "Executive Summary" not in md


@pytest.mark.unit
def test_cli_report_labels_follow_chinese_language():
    set_config({**DEFAULT_CONFIG, "output_language": "Chinese"})
    try:
        assert cli_main.localized_report_label("Research Team Decision") == "研究团队决策"
        assert cli_main.localized_report_label("Research Manager Decision") == "研究经理决策"
        assert cli_main.localized_report_label("Trading Team Plan") == "交易团队计划"
        assert cli_main.localized_report_label("Portfolio Manager Decision") == "投资组合经理决策"
    finally:
        set_config(DEFAULT_CONFIG.copy())
