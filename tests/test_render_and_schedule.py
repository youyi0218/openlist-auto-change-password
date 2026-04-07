from datetime import datetime
from pathlib import Path

from app.config import load_config
from app.template_renderer import build_html_payload, render_html
from app.time_utils import get_next_rotation_time


def test_template_render_and_schedule(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
          "openlist": {"baseUrl": "http://127.0.0.1:5244", "username": "admin", "password": "123456", "timeoutSeconds": 30},
          "passwordPolicy": {"length": 16, "useLowercase": true, "useUppercase": true, "useNumbers": true, "useSymbols": false, "symbols": "!@#$"},
          "targets": [{"path": "/", "createWhenMissing": true, "createDefaults": {"p_sub": false, "write": true, "w_sub": true, "hide": "", "h_sub": false, "readme": "", "r_sub": false, "header": "", "header_sub": false}}],
          "schedule": {"enabled": true, "cron": "0 10 * * 4", "timezone": "Asia/Shanghai", "runOnStart": false},
          "html": {
            "title": "资源站密码",
            "subtitle": "Test Subtitle",
            "passwordHint": "点击密码正文即可复制",
            "templateFile": "templates/password_page.html",
            "outputFile": "dist/index.html",
            "buttons": [
              {"title": "网盘资源", "hint": "点击跳转到资源网盘页面", "url": "https://pan.example.com"},
              {"title": "聚合页", "hint": "点击跳转到聚合页面", "url": "https://portal.example.com"}
            ]
          },
          "state": {"file": "output/state.json"},
          "logging": {"level": "INFO", "file": "logs/app.log", "maxBytes": 1048576, "backupCount": 3, "console": false},
          "cloudflare": {"enabled": false, "projectName": "pan_password", "accountId": "", "apiToken": "", "branch": "main", "createProjectIfMissing": true, "skipCaching": false, "pollAttempts": 20, "pollIntervalSeconds": 3}
        }
        """,
        encoding="utf-8",
    )

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "password_page.html").write_text(
        "TITLE={{TITLE}}\nCUR={{CURRENT_DATE}}\nNEXT={{NEXT_DATE}}\nPW={{PASSWORD}}\nHINT={{PASSWORD_HINT}}\nBTN={{BUTTONS_HTML}}\nDATA={{PAGE_DATA_JSON}}",
        encoding="utf-8",
    )
    (template_dir / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (template_dir / "jingnan-round.ttf").write_bytes(b"font-binary")

    config = load_config(config_path)
    next_time = get_next_rotation_time(
        config.schedule,
        datetime.fromisoformat("2026-04-05T09:00:00+08:00"),
    )
    assert next_time.isoformat() == "2026-04-09T10:00:00+08:00"

    payload = build_html_payload(
        config,
        [{"path": "/", "password": "abc123", "existedBefore": True}],
        datetime.fromisoformat("2026-04-05T10:00:00+08:00"),
        next_time,
    )
    output_path = tmp_path / "dist/index.html"
    render_html(template_dir / "password_page.html", output_path, payload)

    content = output_path.read_text(encoding="utf-8")
    assert "资源站密码" in content
    assert "abc123" in content
    assert "点击密码正文即可复制" in content
    assert "网盘资源" in content
    assert "2026-04-09 10:00:00" in content
    assert (tmp_path / "dist/favicon.svg").exists()
    assert (tmp_path / "dist/jingnan-round.ttf").read_bytes() == b"font-binary"
