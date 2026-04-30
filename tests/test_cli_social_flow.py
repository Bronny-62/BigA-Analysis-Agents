import inspect
import pytest
from types import SimpleNamespace

import cli.main as cli_main
import cli.utils as cli_utils


class _FakeQuestion:
    def __init__(self, value):
        self.value = value

    def ask(self):
        return self.value


@pytest.mark.unit
def test_step2_done_keeps_eastmoney_browser_open(monkeypatch):
    handle = {"cdp_url": "http://127.0.0.1:9222", "process": None}
    closed = []

    monkeypatch.delenv("SOCIAL_BROWSER_CDP_URL", raising=False)
    monkeypatch.setattr(cli_main.questionary, "select", lambda *args, **kwargs: _FakeQuestion(True))
    monkeypatch.setattr(cli_main, "_open_eastmoney_guba_login_browser", lambda ts_code: handle)
    monkeypatch.setattr(cli_main, "_prompt_after_eastmoney_login", lambda: "done")
    monkeypatch.setattr(cli_main, "_close_social_browser", lambda browser_handle: closed.append(browser_handle))

    result = cli_main.setup_eastmoney_guba_for_analysis("300750.SZ")

    assert result["status"] == "login_confirmed"
    assert result["browser_handle"] is handle
    assert closed == []
    assert cli_main.os.environ["SOCIAL_MONITOR_ENABLED"] == "true"
    assert cli_main.os.environ["SOCIAL_MONITOR_SOURCES"] == "eastmoney_guba"
    assert cli_main.os.environ["SOCIAL_MONITOR_COLLECT_DURING_ANALYSIS"] == "true"
    assert cli_main.os.environ["SOCIAL_BROWSER_CDP_URL"] == "http://127.0.0.1:9222"


@pytest.mark.unit
def test_step2_skip_closes_eastmoney_browser(monkeypatch):
    handle = {"cdp_url": "http://127.0.0.1:9222", "process": None}
    closed = []

    monkeypatch.delenv("SOCIAL_MONITOR_ENABLED", raising=False)
    monkeypatch.delenv("SOCIAL_MONITOR_SOURCES", raising=False)
    monkeypatch.delenv("SOCIAL_MONITOR_COLLECT_DURING_ANALYSIS", raising=False)
    monkeypatch.delenv("SOCIAL_BROWSER_CDP_URL", raising=False)
    monkeypatch.setattr(cli_main.questionary, "select", lambda *args, **kwargs: _FakeQuestion(True))
    monkeypatch.setattr(cli_main, "_open_eastmoney_guba_login_browser", lambda ts_code: handle)
    monkeypatch.setattr(cli_main, "_prompt_after_eastmoney_login", lambda: "skip")
    monkeypatch.setattr(cli_main, "_close_social_browser", lambda browser_handle: closed.append(browser_handle))

    result = cli_main.setup_eastmoney_guba_for_analysis("300750.SZ")

    assert result == {"enabled": False, "status": "login_skipped"}
    assert closed == [handle]
    assert "SOCIAL_BROWSER_CDP_URL" not in cli_main.os.environ


@pytest.mark.unit
def test_step2_enable_prompt_uses_research_depth_select_style(monkeypatch):
    captured = {}

    def fake_select(message, choices, default=None, qmark="?", show_instruction=True):
        captured["message"] = message
        captured["choices"] = choices
        captured["default"] = default
        captured["qmark"] = qmark
        captured["show_instruction"] = show_instruction
        return False

    monkeypatch.setattr(cli_main, "select_with_research_depth_style", fake_select)

    result = cli_main.setup_eastmoney_guba_for_analysis("300750.SZ")

    assert result == {"enabled": False, "status": "skipped"}
    assert captured["message"] == "是否启用东方财富股吧社区情绪链路？"
    assert captured["default"] is None
    assert captured["qmark"] == ""
    assert captured["show_instruction"] is False
    assert [choice.value for choice in captured["choices"]] == [True, False]


@pytest.mark.unit
def test_step2_login_confirmation_uses_select_not_numeric_prompt(monkeypatch):
    captured = {}

    def fake_select(message, choices, default=None, qmark="?", show_instruction=True):
        captured["message"] = message
        captured["choices"] = choices
        captured["default"] = default
        captured["qmark"] = qmark
        captured["show_instruction"] = show_instruction
        return "done"

    monkeypatch.setattr(cli_main, "select_with_research_depth_style", fake_select)
    monkeypatch.setattr(cli_main.typer, "prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("typer.prompt should not be used")))

    assert cli_main._prompt_after_eastmoney_login() == "done"
    assert captured["message"] == "选择下一步操作："
    assert captured["default"] is None
    assert captured["qmark"] == ""
    assert captured["show_instruction"] is False
    assert [choice.value for choice in captured["choices"]] == ["done", "skip", "exit"]


@pytest.mark.unit
def test_shared_select_helper_matches_research_depth_rendering(monkeypatch):
    captured = {}

    def fake_questionary_select(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeQuestion("ok")

    monkeypatch.setattr(cli_utils.questionary, "select", fake_questionary_select)

    result = cli_utils.select_with_research_depth_style(
        "Prompt:",
        choices=[cli_utils.questionary.Choice("OK", value="ok")],
        default="ok",
    )

    assert result == "ok"
    assert captured["args"] == ("Prompt:",)
    assert captured["kwargs"]["instruction"] == "\n- Use arrow keys to navigate\n- Press Enter to select"
    assert captured["kwargs"]["default"] == "ok"
    style_rules = captured["kwargs"]["style"].style_rules
    assert ("selected", "fg:yellow noinherit") in style_rules
    assert ("highlighted", "fg:yellow noinherit") in style_rules
    assert ("pointer", "fg:yellow noinherit") in style_rules


@pytest.mark.unit
def test_shared_select_helper_can_hide_step2_instruction_and_qmark(monkeypatch):
    captured = {}

    def fake_questionary_select(*args, **kwargs):
        captured["kwargs"] = kwargs
        return _FakeQuestion(False)

    monkeypatch.setattr(cli_utils.questionary, "select", fake_questionary_select)

    assert (
        cli_utils.select_with_research_depth_style(
            "Prompt:",
            choices=[cli_utils.questionary.Choice("No", value=False)],
            qmark="",
            show_instruction=False,
        )
        is False
    )
    assert captured["kwargs"]["qmark"] == ""
    assert captured["kwargs"]["instruction"] == " "
    assert "default" not in captured["kwargs"]


@pytest.mark.unit
def test_browser_executable_resolver_uses_configured_path(monkeypatch, tmp_path):
    executable = tmp_path / "Chrome"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("SOCIAL_BROWSER_EXECUTABLE_PATH", str(executable))
    playwright = SimpleNamespace(chromium=SimpleNamespace(executable_path=str(tmp_path / "missing-playwright-chrome")))

    assert cli_main._resolve_browser_executable_path(playwright) == str(executable)


@pytest.mark.unit
def test_browser_executable_resolver_falls_back_when_playwright_cache_missing(monkeypatch, tmp_path):
    fallback = tmp_path / "System Chrome"
    fallback.write_text("#!/bin/sh\n", encoding="utf-8")
    fallback.chmod(0o755)
    playwright_missing = tmp_path / "missing-playwright-chrome"
    playwright = SimpleNamespace(chromium=SimpleNamespace(executable_path=str(playwright_missing)))
    monkeypatch.delenv("SOCIAL_BROWSER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr(
        cli_main,
        "_browser_executable_candidates",
        lambda _playwright: [str(playwright_missing), str(fallback)],
    )

    assert cli_main._resolve_browser_executable_path(playwright) == str(fallback)


@pytest.mark.unit
def test_browser_executable_resolver_installs_missing_playwright_chromium(monkeypatch, tmp_path):
    playwright_binary = tmp_path / "ms-playwright" / "chromium" / "chrome"
    playwright = SimpleNamespace(chromium=SimpleNamespace(executable_path=str(playwright_binary)))
    calls = []

    def fake_install(quiet=False):
        calls.append(quiet)
        playwright_binary.parent.mkdir(parents=True)
        playwright_binary.write_text("#!/bin/sh\n", encoding="utf-8")
        playwright_binary.chmod(0o755)
        return True

    monkeypatch.delenv("SOCIAL_BROWSER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr(
        cli_main,
        "_browser_executable_candidates",
        lambda _playwright: [str(playwright_binary)],
    )
    monkeypatch.setattr("cli.install_runtime_deps.install_chromium", fake_install)

    assert cli_main._resolve_browser_executable_path(playwright) == str(playwright_binary)
    assert calls == [True]


@pytest.mark.unit
def test_step2_reuses_existing_social_browser_cdp(monkeypatch, tmp_path):
    opened = []

    monkeypatch.setattr(cli_main, "_existing_social_browser_cdp_candidates", lambda profile: ["http://127.0.0.1:64719"])
    monkeypatch.setattr(cli_main, "_cdp_endpoint_ready", lambda cdp_url: True)
    monkeypatch.setattr(
        cli_main,
        "_open_url_in_existing_cdp",
        lambda cdp_url, target_url: opened.append((cdp_url, target_url)),
    )

    handle = cli_main._reuse_existing_social_browser(tmp_path, "https://guba.eastmoney.com/list,300750.html")

    assert handle == {
        "process": None,
        "cdp_url": "http://127.0.0.1:64719",
        "profile": str(tmp_path),
        "owned": False,
    }
    assert opened == [("http://127.0.0.1:64719", "https://guba.eastmoney.com/list,300750.html")]


@pytest.mark.unit
def test_running_social_browser_cdp_candidates_parse_profile_process(monkeypatch, tmp_path):
    process_list = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        f"--user-data-dir={tmp_path} --remote-debugging-port=54321 "
        "https://guba.eastmoney.com/list,300750.html\n"
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        "--user-data-dir=/tmp/other --remote-debugging-port=11111\n"
    )

    monkeypatch.setattr(cli_main.subprocess, "check_output", lambda *args, **kwargs: process_list)

    assert cli_main._running_social_browser_cdp_candidates(tmp_path) == ["http://127.0.0.1:54321"]


@pytest.mark.unit
def test_close_social_browser_does_not_terminate_reused_process():
    class FakeProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    process = FakeProcess()

    cli_main._close_social_browser({"process": process, "owned": False})

    assert process.terminated is False


@pytest.mark.unit
def test_browser_unavailable_prompt_uses_step2_select_style(monkeypatch):
    captured = {}

    def fake_select(message, choices, default=None, qmark="?", show_instruction=True):
        captured["message"] = message
        captured["choices"] = choices
        captured["qmark"] = qmark
        captured["show_instruction"] = show_instruction
        return "continue"

    monkeypatch.setattr(cli_main, "select_with_research_depth_style", fake_select)

    cli_main._handle_social_browser_unavailable(RuntimeError("missing browser"))

    assert captured["message"] == "请选择："
    assert captured["qmark"] == ""
    assert captured["show_instruction"] is False
    assert [choice.value for choice in captured["choices"]] == ["continue", "exit"]


@pytest.mark.unit
def test_run_analysis_uses_default_rich_live_refresh_path():
    source = inspect.getsource(cli_main.run_analysis)

    assert "screen=True" not in source
    assert "auto_refresh=False" not in source
    assert "console=live_console" not in source
    assert "create_live_console()" not in source
    assert 'vertical_overflow="crop"' in source
    assert "live.update(layout, refresh=True)" not in source
    assert "live.refresh()" not in source
    assert "start_footer_timer(" not in source
    assert "_TradingAgentsLiveLogCapture" not in source
    assert "build_live_header_panel" not in source
    assert "StableLiveFrame" not in inspect.getsource(cli_main)


@pytest.mark.unit
def test_rendering_experiment_helpers_are_removed():
    assert not hasattr(cli_main, "start_footer_timer")
    assert not hasattr(cli_main, "build_live_header_panel")
    assert not hasattr(cli_main, "_TradingAgentsLiveLogCapture")
    assert not hasattr(cli_main, "create_live_console")


@pytest.mark.unit
def test_progress_separator_does_not_use_ellipsis_prone_full_width_rule():
    source = inspect.getsource(cli_main.update_display)

    assert '"─" * 20' not in source
    assert '"─" * 10' in source


@pytest.mark.unit
def test_live_message_preview_flattens_multiline_tool_tables():
    content = """## Company profile

| ts_code | symbol | name |
| ------- | ------ | ---- |
| 000001.SZ | 000001 | 平安银行 |
"""

    preview = cli_main.format_message_preview(content, max_length=80)

    assert "\n" not in preview
    assert "## Company profile | ts_code | symbol | name |" in preview
    assert len(preview) <= 80


@pytest.mark.unit
def test_live_messages_panel_uses_bounded_single_line_rows():
    source = inspect.getsource(cli_main.update_display)

    assert "get_messages_panel_capacity()" in source
    assert 'no_wrap=True, ratio=1' in source
    assert 'Text(content, overflow="ellipsis", no_wrap=True)' in source
    assert 'Text(content, overflow="fold")' not in source
