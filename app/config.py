from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from croniter import croniter


DEFAULT_CREATE_META = {
    "p_sub": False,
    "write": True,
    "w_sub": True,
    "hide": "",
    "h_sub": False,
    "readme": "",
    "r_sub": False,
    "header": "",
    "header_sub": False,
}


@dataclass(slots=True)
class PasswordPolicy:
    length: int
    use_lowercase: bool
    use_uppercase: bool
    use_numbers: bool
    use_symbols: bool
    symbols: str


@dataclass(slots=True)
class TargetConfig:
    path: str
    create_when_missing: bool
    create_defaults: dict[str, Any]


@dataclass(slots=True)
class ScheduleConfig:
    enabled: bool
    cron: str
    timezone: str
    run_on_start: bool


@dataclass(slots=True)
class HtmlConfig:
    title: str
    subtitle: str
    password_hint: str
    template_file: str
    output_file: str
    buttons: list[dict[str, str]]


@dataclass(slots=True)
class StateConfig:
    file: str


@dataclass(slots=True)
class LoggingConfig:
    level: str
    file: str
    max_bytes: int
    backup_count: int
    console: bool


@dataclass(slots=True)
class CloudflareConfig:
    enabled: bool
    project_name: str
    account_id: str
    api_token: str
    branch: str
    create_project_if_missing: bool
    skip_caching: bool
    poll_attempts: int
    poll_interval_seconds: int


@dataclass(slots=True)
class OpenListConfig:
    base_url: str
    username: str
    password: str
    timeout_seconds: int


@dataclass(slots=True)
class RuntimePaths:
    project_root: Path
    config_file: Path
    state_file: Path
    html_template_file: Path
    html_output_file: Path
    log_file: Path


@dataclass(slots=True)
class AppConfig:
    openlist: OpenListConfig
    password_policy: PasswordPolicy
    targets: list[TargetConfig]
    schedule: ScheduleConfig
    html: HtmlConfig
    state: StateConfig
    logging: LoggingConfig
    cloudflare: CloudflareConfig
    runtime: RuntimePaths


def _resolve_path(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return project_root / path


def _ensure_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    return value


def _ensure_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是布尔值")
    return value


def _ensure_int(value: Any, field_name: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} 必须是整数")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field_name} 不能小于 {minimum}")
    return value


def _load_json(config_file: Path) -> dict[str, Any]:
    return json.loads(config_file.read_text(encoding="utf-8-sig"))


def load_config(config_path: str | Path = "config/config.json") -> AppConfig:
    project_root = Path.cwd()
    config_file = _resolve_path(project_root, str(config_path))
    data = _load_json(config_file)

    openlist_data = data.get("openlist", {})
    password_policy_data = data.get("passwordPolicy", {})
    schedule_data = data.get("schedule", {})
    html_data = data.get("html", {})
    state_data = data.get("state", {})
    logging_data = data.get("logging", {})
    cloudflare_data = data.get("cloudflare", {})

    openlist = OpenListConfig(
        base_url=_ensure_non_empty_string(openlist_data.get("baseUrl"), "openlist.baseUrl").rstrip("/"),
        username=_ensure_non_empty_string(openlist_data.get("username"), "openlist.username"),
        password=_ensure_non_empty_string(openlist_data.get("password"), "openlist.password"),
        timeout_seconds=_ensure_int(openlist_data.get("timeoutSeconds", 30), "openlist.timeoutSeconds", minimum=1),
    )

    password_policy = PasswordPolicy(
        length=_ensure_int(password_policy_data.get("length", 16), "passwordPolicy.length", minimum=1),
        use_lowercase=_ensure_bool(password_policy_data.get("useLowercase", True), "passwordPolicy.useLowercase"),
        use_uppercase=_ensure_bool(password_policy_data.get("useUppercase", True), "passwordPolicy.useUppercase"),
        use_numbers=_ensure_bool(password_policy_data.get("useNumbers", True), "passwordPolicy.useNumbers"),
        use_symbols=_ensure_bool(password_policy_data.get("useSymbols", False), "passwordPolicy.useSymbols"),
        symbols=str(password_policy_data.get("symbols", "!@#$%^&*()-_=+[]{};:,.?")),
    )
    if not any(
        [
            password_policy.use_lowercase,
            password_policy.use_uppercase,
            password_policy.use_numbers,
            password_policy.use_symbols,
        ]
    ):
        raise ValueError("passwordPolicy 至少要启用一种字符类型")

    targets_data = data.get("targets", [])
    if not isinstance(targets_data, list) or not targets_data:
        raise ValueError("targets 至少需要配置一个路径")
    target_paths: set[str] = set()
    targets: list[TargetConfig] = []
    for index, item in enumerate(targets_data):
        if not isinstance(item, dict):
            raise ValueError(f"targets[{index}] 必须是对象")
        target_path = _ensure_non_empty_string(item.get("path"), f"targets[{index}].path")
        if target_path in target_paths:
            raise ValueError(f"targets 中路径重复：{target_path}")
        target_paths.add(target_path)
        create_defaults = {**DEFAULT_CREATE_META, **(item.get("createDefaults") or {})}
        for bool_field in ["p_sub", "write", "w_sub", "h_sub", "r_sub", "header_sub"]:
            _ensure_bool(create_defaults.get(bool_field), f"targets[{index}].createDefaults.{bool_field}")
        for text_field in ["hide", "readme", "header"]:
            if not isinstance(create_defaults.get(text_field), str):
                raise ValueError(f"targets[{index}].createDefaults.{text_field} 必须是字符串")
        targets.append(
            TargetConfig(
                path=target_path,
                create_when_missing=_ensure_bool(item.get("createWhenMissing", True), f"targets[{index}].createWhenMissing"),
                create_defaults=create_defaults,
            )
        )

    schedule = ScheduleConfig(
        enabled=_ensure_bool(schedule_data.get("enabled", False), "schedule.enabled"),
        cron=str(schedule_data.get("cron", "0 10 * * 4")),
        timezone=_ensure_non_empty_string(schedule_data.get("timezone", "Asia/Shanghai"), "schedule.timezone"),
        run_on_start=_ensure_bool(schedule_data.get("runOnStart", False), "schedule.runOnStart"),
    )
    if schedule.enabled and not croniter.is_valid(schedule.cron):
        raise ValueError("schedule.cron 不是合法的 cron 表达式")

    html = HtmlConfig(
        title=_ensure_non_empty_string(html_data.get("title", "密码页"), "html.title"),
        subtitle=str(html_data.get("subtitle", "")),
        password_hint=str(html_data.get("passwordHint", "")),
        template_file=str(html_data.get("templateFile", "templates/password_page.html")),
        output_file=str(html_data.get("outputFile", "dist/index.html")),
        buttons=list(html_data.get("buttons", [])),
    )
    if not isinstance(html.buttons, list):
        raise ValueError("html.buttons 必须是数组")
    normalized_buttons: list[dict[str, str]] = []
    for index, button in enumerate(html.buttons):
        if not isinstance(button, dict):
            raise ValueError(f"html.buttons[{index}] 必须是对象")
        normalized_buttons.append(
            {
                "title": _ensure_non_empty_string(button.get("title"), f"html.buttons[{index}].title"),
                "hint": _ensure_non_empty_string(button.get("hint"), f"html.buttons[{index}].hint"),
                "url": _ensure_non_empty_string(button.get("url"), f"html.buttons[{index}].url"),
            }
        )
    html.buttons = normalized_buttons

    state = StateConfig(file=str(state_data.get("file", "output/state.json")))

    logging_config = LoggingConfig(
        level=str(logging_data.get("level", "INFO")).upper(),
        file=str(logging_data.get("file", "logs/app.log")),
        max_bytes=_ensure_int(logging_data.get("maxBytes", 1048576), "logging.maxBytes", minimum=1),
        backup_count=_ensure_int(logging_data.get("backupCount", 3), "logging.backupCount", minimum=0),
        console=_ensure_bool(logging_data.get("console", True), "logging.console"),
    )

    cloudflare = CloudflareConfig(
        enabled=_ensure_bool(cloudflare_data.get("enabled", False), "cloudflare.enabled"),
        project_name=_ensure_non_empty_string(cloudflare_data.get("projectName", "pan_password"), "cloudflare.projectName"),
        account_id=str(cloudflare_data.get("accountId", "")),
        api_token=str(cloudflare_data.get("apiToken", "")),
        branch=_ensure_non_empty_string(cloudflare_data.get("branch", "main"), "cloudflare.branch"),
        create_project_if_missing=_ensure_bool(
            cloudflare_data.get("createProjectIfMissing", True),
            "cloudflare.createProjectIfMissing",
        ),
        skip_caching=_ensure_bool(cloudflare_data.get("skipCaching", False), "cloudflare.skipCaching"),
        poll_attempts=_ensure_int(cloudflare_data.get("pollAttempts", 20), "cloudflare.pollAttempts", minimum=1),
        poll_interval_seconds=_ensure_int(
            cloudflare_data.get("pollIntervalSeconds", 3),
            "cloudflare.pollIntervalSeconds",
            minimum=1,
        ),
    )

    runtime = RuntimePaths(
        project_root=project_root,
        config_file=config_file,
        state_file=_resolve_path(project_root, state.file),
        html_template_file=_resolve_path(project_root, html.template_file),
        html_output_file=_resolve_path(project_root, html.output_file),
        log_file=_resolve_path(project_root, logging_config.file),
    )

    return AppConfig(
        openlist=openlist,
        password_policy=password_policy,
        targets=targets,
        schedule=schedule,
        html=html,
        state=state,
        logging=logging_config,
        cloudflare=cloudflare,
        runtime=runtime,
    )
