from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from app.background_fetcher import fetch_and_store_backgrounds
from app.cloudflare_pages import CloudflarePagesClient
from app.logging_utils import get_logger
from app.openlist_client import OpenListClient
from app.password_generator import generate_password
from app.state_store import load_state, save_state
from app.template_renderer import build_html_payload, render_html
from app.time_utils import get_next_rotation_time, now_in_timezone


def _build_create_payload(target, password: str) -> dict:
    payload = deepcopy(target.create_defaults)
    payload["path"] = target.path
    payload["password"] = password
    return payload


def rotate_passwords(config) -> dict:
    logger = get_logger()
    generated_at = now_in_timezone(config.schedule.timezone)
    next_rotation_at = get_next_rotation_time(config.schedule, generated_at)
    openlist_client = OpenListClient(config.openlist, logger)
    items: list[dict] = []

    for target in config.targets:
        password = generate_password(config.password_policy)
        existing_meta = openlist_client.find_meta_by_path(target.path)
        if existing_meta:
            update_payload = deepcopy(existing_meta)
            update_payload["password"] = password
            openlist_client.update_meta(update_payload)
            logger.info("已修改现有元信息密码：%s", target.path)
            items.append(
                {
                    "path": target.path,
                    "password": password,
                    "metaId": existing_meta.get("id"),
                    "existedBefore": True,
                }
            )
            continue

        if not target.create_when_missing:
            raise ValueError(f"路径 {target.path} 的元信息不存在，且 createWhenMissing=false")

        openlist_client.create_meta(_build_create_payload(target, password))
        created_meta = openlist_client.find_meta_by_path(target.path)
        logger.info("元信息不存在，已自动创建并设置密码：%s", target.path)
        items.append(
            {
                "path": target.path,
                "password": password,
                "metaId": (created_meta or {}).get("id"),
                "existedBefore": False,
            }
        )

    state = {
        "generatedAt": generated_at.isoformat(),
        "nextRotationAt": next_rotation_at.isoformat() if next_rotation_at else None,
        "timezone": config.schedule.timezone,
        "items": items,
    }
    state["backgrounds"] = fetch_and_store_backgrounds(config.runtime.html_output_file.parent, logger)
    save_state(config.runtime.state_file, state)
    html_payload = build_html_payload(config, items, generated_at, next_rotation_at)
    html_payload["backgroundLandscape"] = state["backgrounds"]["landscape"]
    html_payload["backgroundPortrait"] = state["backgrounds"]["portrait"]
    render_html(config.runtime.html_template_file, config.runtime.html_output_file, html_payload)
    logger.info("HTML 页面已生成：%s", config.runtime.html_output_file)

    deploy_result = {"deployed": False, "reason": "cloudflare disabled"}
    if config.cloudflare.enabled:
        cf_client = CloudflarePagesClient(config.cloudflare, logger)
        deploy_result = cf_client.deploy_directory(config.runtime.html_output_file.parent)
        logger.info("Cloudflare Pages 发布完成：%s", deploy_result.get("url") or deploy_result.get("alias"))

    return {**state, "deploy": deploy_result}


def render_only(config) -> dict:
    logger = get_logger()
    state = load_state(config.runtime.state_file)
    if state is None:
        raise FileNotFoundError("还没有 state 文件，请先执行一次 run-once")
    generated_at = datetime.fromisoformat(state["generatedAt"])
    next_rotation_at = (
        datetime.fromisoformat(state["nextRotationAt"])
        if state.get("nextRotationAt")
        else get_next_rotation_time(config.schedule, generated_at)
    )
    html_payload = build_html_payload(
        config,
        state["items"],
        generated_at,
        next_rotation_at,
    )
    backgrounds = state.get("backgrounds") or {}
    html_payload["backgroundLandscape"] = backgrounds.get("landscape", "")
    html_payload["backgroundPortrait"] = backgrounds.get("portrait", "")
    render_html(config.runtime.html_template_file, config.runtime.html_output_file, html_payload)
    logger.info("已根据现有 state 重新生成 HTML 页面。")
    return state
