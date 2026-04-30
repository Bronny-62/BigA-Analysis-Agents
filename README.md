# BigA-Analysis-Agents

BigA-Analysis-Agents is a China A-share focused fork of
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents).
It keeps the original multi-agent research workflow, but replaces the original
US-market data assumptions with an A-share spot trading analysis stack.

The system is designed for research and decision support. It does not place
orders, does not provide guaranteed returns, and does not constitute investment,
financial, or trading advice.

## What This Fork Does

BigA-Analysis-Agents analyzes China A-share symbols in Tushare `ts_code` format,
for example:

- `000001.SZ`
- `600000.SH`
- `300750.SZ`

The agent workflow keeps four analyst channels:

- Market: price, volume, valuation, liquidity, technical indicators, money flow,
  limit-up/limit-down context, and optional iFinD real-time enrichment.
- Social: local authorized Eastmoney Guba monitoring, Tushare hotness, iFinD
  smart stock picking / popularity-style signals, news-derived proxy sentiment,
  and explicit coverage diagnostics.
- News: OpenNews query tools with Jin10 MCP fallback.
- Fundamentals: Tushare structured financial data and Cninfo announcement
  queries.

The original US-market tool schemas such as Yahoo Finance, Alpha Vantage,
Reddit, insider transactions, and SPY alpha are not exposed to the active
A-share analyst agents.

## Data Sources

You must apply for and manage your own data-source accounts. This repository
does not include, redistribute, or sublicense any third-party financial data.

| Channel | Source | Used For | Credential | Application / Docs |
| --- | --- | --- | --- | --- |
| Market | Tushare Pro | Daily/weekly/monthly OHLCV, daily basic, money flow, limit data, financial tables | `TUSHARE_TOKEN` | [Tushare Pro](https://tushare.pro), [token guide](https://tushare.pro/document/1?doc_id=39) |
| Market / Social | iFinD QuantAPI | Optional real-time quote and smart stock picking / popularity-style enrichment | `IFIND_ACCESS_TOKEN`, `IFIND_REFRESH_TOKEN` | [iFinD QuantAPI examples](https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/example.html), [help center](https://ftwc.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center.html) |
| News | OpenNews MCP / REST | News search and latest market information | `OPENNEWS_TOKEN` | [opennews-mcp README](https://github.com/6551Team/opennews-mcp/blob/main/docs/README_ZH.md), [token portal](https://6551.io/mcp) |
| News fallback | Jin10 MCP | Flash/news fallback when OpenNews is unavailable or empty | `JIN10_MCP_TOKEN` | [Jin10 MCP docs](https://mcp.jin10.com/app/doc.html) |
| Fundamentals | Cninfo / Juchao WebAPI | Public company announcements and disclosure links | usually no local API key | [Cninfo](https://www.cninfo.com.cn/), [Cninfo WebAPI](https://webapi.cninfo.com.cn/#/apiDoc) |
| Social | Eastmoney Guba | Authorized browser-session forum post monitoring | local browser login only | [Eastmoney Guba](https://guba.eastmoney.com.cn/) |
| Social optional | Xueqiu | Experimental browser-session monitoring; may be blocked by verification | local browser login only | [Xueqiu](https://xueqiu.com/) |

### Social Data Compliance

The social monitor uses a local Playwright browser profile and manual login. It
does not implement captcha bypass, proxy pools, fingerprint spoofing, credential
sharing, or anti-bot circumvention. If a platform requires verification or blocks
automation, the collector records a structured failure and the agents continue
with available signals.

## Installation

Python 3.13 is recommended.

Always enter the virtual environment before installing dependencies or starting
the CLI. `pip install -e .` installs the Python dependencies declared by the
project, including Playwright. The launch scripts then ensure Playwright's
Chromium runtime is present before entering the CLI, so users do not need to run
any separate Playwright install command.

```bash
git clone https://github.com/<your-account>/BigA-Analysis-Agents.git
cd BigA-Analysis-Agents
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Recommended launch sequence:

```bash
source .venv/bin/activate
pip install -e .
./start.sh
```

On Windows:

```bat
.venv\Scripts\activate
pip install -e .
start.bat
```

## Configuration

Copy the example environment file and fill in only the credentials you actually
use:

```bash
cp .env.example .env
```

Core A-share data variables:

```env
TUSHARE_TOKEN=

OPENNEWS_TOKEN=
OPENNEWS_API_BASE=https://ai.6551.io
OPENNEWS_WSS_URL=wss://ai.6551.io/open/news_wss
OPENNEWS_MCP_URL=

JIN10_MCP_TOKEN=
JIN10_MCP_URL=https://mcp.jin10.com/mcp

IFIND_ENABLED=true
IFIND_API_BASE=https://quantapi.51ifind.com/api/v1
IFIND_ACCESS_TOKEN=
IFIND_REFRESH_TOKEN=
IFIND_TIMEOUT_SECONDS=20

SOCIAL_MONITOR_ENABLED=false
SOCIAL_BROWSER_PROFILE_DIR=~/.tradingagents/social_browser
SOCIAL_MONITOR_SOURCES=eastmoney_guba,xueqiu
SOCIAL_MONITOR_INTERVAL_SECONDS=300
SOCIAL_MONITOR_MAX_POSTS_PER_SYMBOL=200
SOCIAL_MONITOR_MAX_PAGES=3
SOCIAL_EASTMONEY_PAGE_SETTLE_MS=1200
SOCIAL_EASTMONEY_ENABLE_SCROLL=false
```

LLM provider keys are also configured through `.env`, for example
`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`, or other supported
providers.

Never commit `.env`, browser profiles, SQLite databases, JSONL caches, exported
reports, cookies, HAR files, or trace archives.

## CLI Usage

Start the interactive analysis flow:

```bash
python -m cli.main analyze
```

Then enter an A-share `ts_code`, for example `300750.SZ`.
During Step 2, the CLI asks whether to enable Eastmoney Guba community
sentiment. If you choose yes, Chrome opens the stock's Guba page.
Log in with your own Eastmoney account, complete any manual
verification, return to the terminal, and choose `I have completed login` to run
a one-time local collection before the analysis continues.

Convenience launch scripts are also provided:

```bash
./start.sh
```

On Windows:

```bat
start.bat
```

Run data-source smoke tests:

```bash
python -m cli.main ifind-smoke --symbol 300750.SZ
```

Manual social login:

```bash
python -m cli.main social-login
```

Collect Eastmoney Guba / Xueqiu posts with the local browser session:

```bash
python -m cli.main social-monitor --symbols 300750.SZ --once --sources eastmoney_guba
```

For continuous monitoring:

```bash
python -m cli.main social-monitor --symbols 300750.SZ,000001.SZ --loop --sources eastmoney_guba
```

## Python Usage

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.4"
config["quick_think_llm"] = "gpt-5.4-mini"

graph = TradingAgentsGraph(debug=True, config=config)
state, decision = graph.propagate("300750.SZ", "2026-04-28")
print(decision)
```

## Architecture Notes

The active A-share tool set is:

- `get_a_share_ohlcv`
- `get_a_share_market_snapshot`
- `get_a_share_indicators`
- `get_a_share_moneyflow`
- `get_a_share_social_sentiment`
- `get_a_share_hotness`
- `get_social_monitoring_coverage`
- `search_a_share_news`
- `get_cn_macro_news`
- `get_a_share_company_profile`
- `get_a_share_financials`
- `get_a_share_announcements`
- `get_a_share_fundamental_snapshot`

Real-time OpenNews WebSocket ingestion is disabled by default. The default news
path uses query tools; WebSocket caching can be enabled separately when needed.

iFinD is enabled as an optional enrichment source by default. If iFinD returns an
error or no rows, the main analysis continues and the report includes diagnostic
fields such as endpoint, HTTP status, error code, and message.

## Local State

Runtime state is written under `~/.tradingagents` by default:

- cache files for Tushare, OpenNews, Jin10, Cninfo, and social events
- social monitor SQLite database
- browser profile for authorized forum monitoring
- memory log for prior decisions and reflections

These files are local-only and must not be published.

## Testing

```bash
python -m pytest -q
```

Targeted A-share dataflow tests:

```bash
python -m pytest tests/test_a_share_dataflows.py -q
```

## Open Source Attribution

This project is a derivative work of
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents),
which is licensed under the Apache License 2.0. The upstream framework, agent
workflow, and portions of the original codebase remain credited to their
original authors.

Major changes in this fork include:

- China A-share `ts_code` symbol normalization.
- Tushare/iFinD/OpenNews/Jin10/Cninfo dataflow integration.
- Eastmoney Guba authorized browser-session social monitoring.
- A-share specific analyst prompts and tool schemas.
- CSI 300 benchmark reflection instead of SPY-based alpha.

## License

This repository is distributed under the Apache License 2.0. See
[LICENSE](LICENSE).

## Disclaimer

BigA-Analysis-Agents is for research, education, and personal analytical workflow
experiments only. The outputs may be incomplete, delayed, inaccurate, or affected
by model hallucination and third-party data-source availability. You are solely
responsible for verifying all information and for any investment or trading
decisions you make.
