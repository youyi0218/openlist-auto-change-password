from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from app.time_utils import format_datetime


def _render_buttons(buttons: list[dict]) -> str:
    parts: list[str] = []
    for button in buttons:
        parts.append(
            (
                '<a class="liquid-button" href="{url}" target="_blank" rel="noreferrer">'
                '<span class="liquid-button__title">{title}</span>'
                '<span class="liquid-button__hint">{hint}</span>'
                "</a>"
            ).format(
                url=html.escape(button["url"], quote=True),
                title=html.escape(button["title"]),
                hint=html.escape(button["hint"]),
            )
        )
    return "\n".join(parts)


def render_html(template_path: Path, output_path: Path, payload: dict) -> None:
    template = template_path.read_text(encoding="utf-8")
    page_data_json = json.dumps(
        {
            "nextRotationAt": payload.get("nextRotationAt"),
            "timezone": payload.get("timezone"),
            "copyText": payload.get("password", ""),
        },
        ensure_ascii=False,
    )

    replacements = {
        "{{TITLE}}": html.escape(payload.get("title") or "资源站密码"),
        "{{CURRENT_DATE}}": html.escape(payload.get("generatedAtText") or ""),
        "{{NEXT_DATE}}": html.escape(payload.get("nextRotationAtText") or "未启用"),
        "{{PASSWORD}}": html.escape(payload.get("password") or "暂无密码"),
        "{{PASSWORD_HINT}}": html.escape(
            payload["passwordHint"] if "passwordHint" in payload and payload.get("passwordHint") is not None else "点击密码正文即可复制"
        ),
        "{{BUTTONS_HTML}}": _render_buttons(payload.get("buttons") or []),
        "{{BACKGROUND_LANDSCAPE}}": html.escape(payload.get("backgroundLandscape") or ""),
        "{{BACKGROUND_PORTRAIT}}": html.escape(payload.get("backgroundPortrait") or ""),
        "{{PAGE_DATA_JSON}}": page_data_json,
    }

    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    favicon_source = template_path.with_name("favicon.svg")
    if favicon_source.exists():
        shutil.copy2(favicon_source, output_path.parent / "favicon.svg")


def build_html_payload(config, items: list[dict], generated_at, next_rotation_at) -> dict:
    password = items[0]["password"] if items else ""
    return {
        "title": config.html.title or "密码页",
        "generatedAtText": format_datetime(generated_at, config.schedule.timezone),
        "nextRotationAtText": format_datetime(next_rotation_at, config.schedule.timezone),
        "nextRotationAt": next_rotation_at.isoformat() if next_rotation_at else None,
        "timezone": config.schedule.timezone,
        "password": password,
        "passwordHint": config.html.password_hint,
        "buttons": config.html.buttons,
        "backgroundLandscape": "",
        "backgroundPortrait": "",
    }
