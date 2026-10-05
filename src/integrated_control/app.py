"""Main entry point for the integrated control application."""

from integrated_control.application.workflows import run_zksz
from integrated_control.bootstrap import build_application
from integrated_control.domain.errors import ConfigurationError


def main() -> int:
    try:
        application = build_application()
    except ConfigurationError as exc:
        print(f"配置错误：{exc}")
        return 2

    try:
        started = application.controller.start()
        if not started.success:
            print(f"设备初始化失败：{started.message}")
            return 1

        result = run_zksz(application)
        if not result.success:
            print(f"zksz 流程失败：{result.message}")
            return 1
        return 0
    finally:
        application.controller.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
