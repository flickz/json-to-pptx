#!/usr/bin/env python3
"""
Main entry point for the JSON to PPTX conversion service.

This script initializes and runs the RabbitMQ consumer and Redis progress publisher.
"""

import sys
import traceback
import logging

from messages import ConversionConsumer

logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    consumer = ConversionConsumer()

    try:
        consumer.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Fatal error: %s", e)
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()