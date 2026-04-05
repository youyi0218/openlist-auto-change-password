import argparse

from app.config import load_config
from app.logging_utils import configure_console_utf8, configure_logging, get_logger
from app.scheduler import run_schedule_loop
from app.service import render_only, rotate_passwords


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenList 元信息密码自动修改工具")
    parser.add_argument(
        "command",
        choices=["validate-config", "run-once", "render-only", "daemon"],
        help="要执行的命令",
    )
    parser.add_argument(
        "--config",
        default="config/config.json",
        help="配置文件路径，默认是 config/config.json",
    )
    return parser


def main() -> int:
    configure_console_utf8()
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    configure_logging(config.logging)
    logger = get_logger()

    if args.command == "validate-config":
        logger.info("配置校验通过：%s", config.runtime.config_file)
        return 0

    if args.command == "run-once":
        result = rotate_passwords(config)
        logger.info("单次执行完成，共处理 %s 个路径。", len(result["items"]))
        return 0

    if args.command == "render-only":
        state = render_only(config)
        logger.info("HTML 页面已重新生成：%s", config.html.output_file)
        logger.info("当前页面展示 %s 个路径的密码。", len(state["items"]))
        return 0

    if args.command == "daemon":
        logger.info("定时任务已启动，Cron=%s，时区=%s", config.schedule.cron, config.schedule.timezone)
        run_schedule_loop(config, rotate_passwords)
        return 0

    parser.error(f"未知命令：{args.command}")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger = get_logger()
        logger.warning("已收到中断信号，程序退出。")
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        configure_console_utf8()
        logger = get_logger()
        logger.exception("程序执行失败：%s", exc)
        raise SystemExit(1)
