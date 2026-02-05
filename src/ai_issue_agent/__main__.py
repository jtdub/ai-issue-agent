"""Entry point for running the AI Issue Agent.

This module provides the main entry point for the AI Issue Agent.
It handles:
- Configuration loading
- Logging setup with secret sanitization
- Adapter instantiation
- Agent lifecycle management
- Signal handling for graceful shutdown
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog

from ai_issue_agent._version import __version__

log = structlog.get_logger()


def setup_logging(
    debug: bool = False,
    log_format: str = "console",
    file_path: Path | None = None,
    file_enabled: bool = False,
) -> None:
    """Configure structured logging with secret sanitization.

    Args:
        debug: Enable debug logging if True
        log_format: Output format ("json" or "console")
        file_path: Path to log file (if file logging enabled)
        file_enabled: Whether to enable file logging
    """
    from ai_issue_agent.utils.logging import LogFormat, LogLevel, configure_logging

    level = LogLevel.DEBUG if debug else LogLevel.INFO
    fmt = LogFormat(log_format.lower()) if isinstance(log_format, str) else log_format

    configure_logging(
        level=level,
        log_format=fmt,
        file_path=file_path,
        file_enabled=file_enabled,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed argument namespace
    """
    parser = argparse.ArgumentParser(
        prog="ai-issue-agent",
        description="AI Issue Agent - Automatic issue triage from chat tracebacks",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config/config.yaml"),
        help="Path to configuration file (default: config/config.yaml)",
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse config and validate without starting the agent",
    )

    parser.add_argument(
        "--format",
        choices=["json", "console"],
        default="console",
        help="Log output format (default: console)",
    )

    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run health check and exit",
    )

    return parser.parse_args()


async def run_agent(
    config_path: Path,
    dry_run: bool = False,
    health_check: bool = False,
) -> int:
    """Run the AI Issue Agent.

    Args:
        config_path: Path to configuration file
        dry_run: If True, only validate config without starting
        health_check: If True, run health check and exit

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    log.info(
        "starting_ai_issue_agent",
        version=__version__,
        config_path=str(config_path),
    )

    try:
        # Load configuration
        from ai_issue_agent.config.loader import load_config

        log.info("loading_configuration", path=str(config_path))
        config = load_config(config_path)
        log.info("configuration_loaded")

        # Reconfigure logging from config file settings
        from ai_issue_agent.utils.logging import configure_logging

        configure_logging(
            level=config.logging.level,
            log_format=config.logging.format,
            file_path=config.logging.file.path if config.logging.file.enabled else None,
            file_enabled=config.logging.file.enabled,
        )

        if dry_run:
            log.info("dry_run_mode_config_valid")
            return 0

        if health_check:
            # Run health check
            from ai_issue_agent.utils.health import HealthChecker

            checker = HealthChecker(config)
            result = await checker.run_all_checks()

            if result.healthy:
                log.info("health_check_passed", details=result.details)
                return 0
            else:
                log.error("health_check_failed", details=result.details)
                return 1

        # Create and start agent
        from ai_issue_agent.core.agent import create_agent

        log.info("creating_agent")
        agent = await create_agent(config)

        log.info("starting_agent")
        await agent.start()

        return 0

    except FileNotFoundError as e:
        log.error("configuration_file_not_found", path=str(config_path), error=str(e))
        return 1
    except ValueError as e:
        log.error("configuration_invalid", error=str(e))
        return 1
    except KeyboardInterrupt:
        log.info("keyboard_interrupt_received")
        return 0
    except Exception as e:
        log.exception("fatal_error", error=str(e))
        return 1


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging with CLI options
    setup_logging(
        debug=args.debug,
        log_format=args.format,
    )

    try:
        return asyncio.run(run_agent(args.config, args.dry_run, args.health_check))
    except KeyboardInterrupt:
        log.info("shutting_down_gracefully")
        return 0


if __name__ == "__main__":
    sys.exit(main())
