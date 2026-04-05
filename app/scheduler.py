from __future__ import annotations

from app.logging_utils import get_logger
from app.time_utils import format_datetime, get_next_rotation_time, now_in_timezone, sleep_until


def run_schedule_loop(config, callback) -> None:
    logger = get_logger()
    if not config.schedule.enabled:
        raise ValueError("schedule.enabled 为 false，不能启动 daemon")

    if config.schedule.run_on_start:
        logger.info("已启用 runOnStart，程序启动后立即执行一次。")
        callback(config)

    while True:
        current = now_in_timezone(config.schedule.timezone)
        next_time = get_next_rotation_time(config.schedule, current)
        if next_time is None:
            raise ValueError("无法计算下一次执行时间")
        logger.info(
            "下一次自动改密时间：%s（时区：%s）",
            format_datetime(next_time, config.schedule.timezone),
            config.schedule.timezone,
        )
        sleep_until(next_time)
        callback(config)
