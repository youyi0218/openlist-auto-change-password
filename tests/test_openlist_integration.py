from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from app.config import load_config
from app.logging_utils import configure_logging
from app.openlist_client import OpenListClient
from app.service import render_only, rotate_passwords


def _can_connect(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def write_test_config(tmp_path: Path, target_path: str) -> Path:
    config = {
        "openlist": {
            "baseUrl": "http://127.0.0.1:5244",
            "username": "admin",
            "password": "123456",
            "timeoutSeconds": 30,
        },
        "passwordPolicy": {
            "length": 18,
            "useLowercase": True,
            "useUppercase": True,
            "useNumbers": True,
            "useSymbols": True,
            "symbols": "!@#$",
        },
        "targets": [
            {
                "path": target_path,
                "createWhenMissing": True,
                "createDefaults": {
                    "p_sub": True,
                    "write": False,
                    "w_sub": False,
                    "hide": "secret",
                    "h_sub": True,
                    "readme": "readme",
                    "r_sub": True,
                    "header": "header",
                    "header_sub": True,
                },
            }
        ],
        "schedule": {
            "enabled": True,
            "cron": "0 10 * * 4",
            "timezone": "Asia/Shanghai",
            "runOnStart": False,
        },
        "html": {
            "title": "资源站密码",
            "subtitle": "Test Subtitle",
            "passwordHint": "点击密码正文即可复制",
            "templateFile": str((Path.cwd() / "templates/password_page.html").resolve()),
            "outputFile": str((tmp_path / "dist/index.html").resolve()),
            "buttons": [
                {"title": "网盘资源", "hint": "点击跳转到资源网盘页面", "url": "https://pan.example.com"},
                {"title": "聚合页", "hint": "点击跳转到聚合页面", "url": "https://portal.example.com"}
            ],
        },
        "state": {"file": str((tmp_path / "output/state.json").resolve())},
        "logging": {
            "level": "INFO",
            "file": str((tmp_path / "logs/app.log").resolve()),
            "maxBytes": 1048576,
            "backupCount": 1,
            "console": False,
        },
        "cloudflare": {
            "enabled": False,
            "projectName": "pan_password",
            "accountId": "",
            "apiToken": "",
            "branch": "main",
            "createProjectIfMissing": True,
            "skipCaching": False,
            "pollAttempts": 20,
            "pollIntervalSeconds": 3,
        },
    }
    config_path = tmp_path / "config.test.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config_path


def test_openlist_password_rotation_preserves_other_fields(tmp_path: Path):
    if not _can_connect("127.0.0.1", 5244):
        pytest.skip("本地 OpenList 测试服务未启动，跳过集成测试")

    target_path = f"/auto-test-{tmp_path.name}"
    config_path = write_test_config(tmp_path, target_path)
    config = load_config(config_path)
    logger = configure_logging(config.logging)
    client = OpenListClient(config.openlist, logger=logger)

    try:
        first_result = rotate_passwords(config)
        created_meta = client.find_meta_by_path(target_path)
        assert created_meta is not None
        assert created_meta["write"] is False
        assert created_meta["w_sub"] is False
        assert created_meta["hide"] == "secret"
        assert created_meta["readme"] == "readme"
        assert created_meta["header"] == "header"
        assert created_meta["password"] == first_result["items"][0]["password"]

        snapshot = dict(created_meta)
        second_result = rotate_passwords(config)
        updated_meta = client.find_meta_by_path(target_path)
        assert updated_meta is not None
        assert updated_meta["password"] == second_result["items"][0]["password"]
        assert updated_meta["password"] != snapshot["password"]
        for field in ["path", "p_sub", "write", "w_sub", "hide", "h_sub", "readme", "r_sub", "header", "header_sub"]:
            assert updated_meta[field] == snapshot[field]

        html_content = Path(config.html.output_file).read_text(encoding="utf-8")
        assert "资源站密码" in html_content
        assert second_result["items"][0]["password"] in html_content
        assert "网盘资源" in html_content
        assert "聚合页" in html_content

        render_only(config)
        rendered_again = Path(config.html.output_file).read_text(encoding="utf-8")
        assert "当前密码更换日期" in rendered_again
    finally:
        meta = client.find_meta_by_path(target_path)
        if meta and meta.get("id"):
            client.delete_meta(meta["id"])
