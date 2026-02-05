"""Entry point for running the AI Issue Agent.

This module provides the main entry point for the AI Issue Agent.
It handles:
- Configuration loading
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


def setup_logging(debug: bool = False) -> None:
    """Configure structured logging.

    Args:
        debug: Enable debug logging if True
    """
    import logging

    level = logging.DEBUG if debug else logging.INFO

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
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

    return parser.parse_args()


async def run_agent(config_path: Path, dry_run: bool = False) -> int:
    """Run the AI Issue Agent.

    Args:
        config_path: Path to configuration file
        dry_run: If True, only validate config without starting

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

        if dry_run:
            log.info("dry_run_mode_config_valid")
            return 0

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

    # Setup logging
    setup_logging(debug=args.debug)

    try:
        return asyncio.run(run_agent(args.config, args.dry_run))
    except KeyboardInterrupt:
        log.info("shutting_down_gracefully")
        return 0


if __name__ == "__main__":
    sys.exit(main())
