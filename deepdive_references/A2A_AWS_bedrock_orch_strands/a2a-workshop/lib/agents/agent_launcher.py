#!/usr/bin/env python3
"""
Universal Agent Launcher

Starts HTTP server for any A2A agent.
Provides a standardized way to run agents with HTTP capabilities.

Architecture:
    - FastAPI HTTP server runs in async event loop (main thread)
    - Single agent instance serves HTTP requests
    - Graceful shutdown handling

Usage:
    Set environment variables:
        AGENT_TYPE=market-analysis (or portfolio-manager, orchestrator)
        AGENT_PORT=8000

    Then run:
        python3 -m agents.common.agent_launcher
"""

import importlib
import logging
import os
import signal
import sys

import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HealthCheckFilter(logging.Filter):
    """Filter out health check endpoint logs"""

    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress logs for /health endpoint
        return "/health" not in record.getMessage()


class AgentLauncher:
    """
    Universal launcher for A2A agents.

    Manages lifecycle of HTTP server,
    ensuring proper startup, operation, and shutdown.
    """

    def __init__(self):
        """Initialize the launcher with environment configuration"""
        self.agent_type = os.getenv("AGENT_TYPE")
        self.agent_port = int(os.getenv("AGENT_PORT", "8000"))

        if not self.agent_type:
            raise ValueError("AGENT_TYPE environment variable must be set")

        self.agent = None
        self.app = None

        # Shutdown flag
        self.shutdown_requested = False

        logger.info(
            f"Agent Launcher initialized: type={self.agent_type}, port={self.agent_port}"
        )

    def load_agent_module(self):
        """
        Dynamically import agent module based on AGENT_TYPE.

        Expects agent module to have:
            - get_agent() -> agent instance
            - get_http_app(agent) -> FastAPI app
        """
        try:
            # Convert agent-type to module name (e.g., "market-analysis" -> "market_analysis")
            module_name = self.agent_type.replace("-", "_")

            # Special case: orchestrator is at top level, not in agents/
            if module_name == "orchestrator":
                agent_module = importlib.import_module("orchestrator.main")
                logger.info("Loaded agent module: orchestrator.main")
            else:
                # Load agent module from agents directory
                agent_module = importlib.import_module(f"agents.{module_name}.main")
                logger.info(f"Loaded agent module: agents.{module_name}.main")

            return agent_module

        except ImportError as e:
            logger.error(f"Failed to import agent module for {self.agent_type}: {e}")
            raise

    def initialize_components(self):
        """Initialize agent and HTTP app"""
        logger.info("Initializing agent components...")

        # Load agent module
        agent_module = self.load_agent_module()

        # Create agent instance
        self.agent = agent_module.get_agent()
        logger.info(f"✓ Agent instance created: {type(self.agent).__name__}")

        # Create FastAPI app
        self.app = agent_module.get_http_app(self.agent)
        logger.info("✓ HTTP app created")

    def start_http_server(self):
        """Start FastAPI HTTP server (blocking call)"""
        logger.info(f"Starting HTTP server on port {self.agent_port}...")

        try:
            # Add health check filter to uvicorn access logger
            uvicorn_logger = logging.getLogger("uvicorn.access")
            uvicorn_logger.addFilter(HealthCheckFilter())

            # Run Uvicorn with async event loop
            # This is a blocking call - runs until shutdown
            uvicorn.run(
                self.app,
                host="0.0.0.0",
                port=self.agent_port,
                workers=1,  # Single worker, async concurrency
                log_level="info",
                access_log=True,
            )

        except Exception as e:
            logger.error(f"HTTP server error: {e}", exc_info=True)
            raise

    def setup_signal_handlers(self):
        """Setup handlers for graceful shutdown on SIGTERM/SIGINT"""

        def shutdown_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
            self.shutdown()

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        logger.info("✓ Signal handlers registered (SIGTERM, SIGINT)")

    def shutdown(self):
        """Gracefully shutdown all components"""
        if self.shutdown_requested:
            return  # Already shutting down

        self.shutdown_requested = True
        logger.info("Initiating graceful shutdown...")

        # HTTP server will be stopped by Uvicorn's own signal handling
        logger.info("✓ Shutdown complete")

    def run(self):
        """
        Main entry point - start all components and run until shutdown.

        Order:
            1. Initialize components (agent, HTTP app)
            2. Setup signal handlers
            3. Start HTTP server (blocking, runs in main thread)
        """
        try:
            logger.info("=" * 60)
            logger.info(f"A2A Agent Launcher - Starting {self.agent_type}")
            logger.info("=" * 60)

            # Initialize
            self.initialize_components()

            # Setup graceful shutdown
            self.setup_signal_handlers()

            logger.info("")
            logger.info("=" * 60)
            logger.info(f"✓ Agent ready: {self.agent_type}")
            logger.info(f"  HTTP endpoint: http://0.0.0.0:{self.agent_port}")
            logger.info("=" * 60)
            logger.info("")

            # Start HTTP server (blocking - runs until shutdown)
            self.start_http_server()

        except Exception as e:
            logger.error(f"Fatal error in agent launcher: {e}", exc_info=True)
            sys.exit(1)

        finally:
            self.shutdown()


def main():
    """Main entry point for the launcher"""
    launcher = AgentLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
