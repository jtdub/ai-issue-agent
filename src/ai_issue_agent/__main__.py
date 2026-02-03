"""Entry point for running the AI Issue Agent."""

import asyncio
import sys

import structlog

log = structlog.get_logger()


async def run_agent() -> int:
    """Run the AI Issue Agent."""
    log.info("Starting AI Issue Agent", version="0.1.0")
    # TODO: Implement agent startup
    log.warning("Agent not yet implemented")
    return 0


def main() -> int:
    """Main entry point."""
    try:
        return asyncio.run(run_agent())
    except KeyboardInterrupt:
        log.info("Shutting down gracefully")
        return 0
    except Exception as e:
        log.exception("Fatal error", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
