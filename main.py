from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create a custom config
config = DEFAULT_CONFIG.copy()
config["deep_think_llm"] = "gpt-5.4-mini"  # Use a different model
config["quick_think_llm"] = "gpt-5.4-mini"  # Use a different model
config["max_debate_rounds"] = 1  # Increase debate rounds

# Configure China A-share data vendors
config["data_vendors"] = {
    "market": "tushare",
    "social": "social_cache",
    "news": "opennews,jin10",
    "fundamentals": "cninfo,tushare",
}

# Initialize with custom config
ta = TradingAgentsGraph(debug=True, config=config)

# forward propagate
_, decision = ta.propagate("000001.SZ", "2024-05-10")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
