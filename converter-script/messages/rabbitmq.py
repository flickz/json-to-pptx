#!/usr/bin/env python3
# pylint: disable=too-many-instance-attributes
"""
RabbitMQ Consumer for JSON to PPTX Conversion
Listens to conversion_queue and processes conversion jobs
"""

import json
import os
import time
import logging
import traceback
from pathlib import Path

import pika
from pika.exceptions import AMQPConnectionError

from core.generator import PowerPointGenerator
from core.text_extractor import ContentExtractor
from .redis import ProgressPublisher


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConversionConsumer:
    """Handles RabbitMQ message consumption and PowerPoint conversion"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue_name = 'conversion_queue'

        self.rabbitmq_url = os.getenv('RABBITMQ_URL')

        if not self.rabbitmq_url:
            raise ValueError("RABBITMQ_URL environment variable is not set")

        self.shared_dir = Path('/app/shared')

        self.shared_dir.mkdir(parents=True, exist_ok=True)

        self.default_slide_width = 16
        self.default_slide_height = 9

        self.progress_publisher = ProgressPublisher()

        self.content_extractor = ContentExtractor()

        logger.info("Consumer initialized with queue: %s", self.queue_name)
        logger.info("Shared directory: %s", self.shared_dir)

    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            logger.info("Connecting to RabbitMQ: %s", self.rabbitmq_url)

            parameters = pika.URLParameters(self.rabbitmq_url)
            parameters.heartbeat = 600
            parameters.blocked_connection_timeout = 300

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            self.channel.queue_declare(queue=self.queue_name, durable=True)

            # Set QoS - process one message at a time
            self.channel.basic_qos(prefetch_count=1)

            logger.info("Successfully connected to RabbitMQ")
            return True

        except AMQPConnectionError as e:
            logger.error("Failed to connect to RabbitMQ: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error during connection: %s", e)
            return False

    def process_message(self, ch, method, properties, body):
        """
        Process a conversion job message

        Expected message format:
        {
            "id": "unique-job-id",
            "inputFile": "filename.json",  # relative to uploads dir
            "outputFile": "filename.pptx", # relative to outputs dir
            "slideWidth": 16,              # optional
            "slideHeight": 9               # optional
        }
        """
        job_id = 'unknown'
        try:
            message = json.loads(body)
            job_id = message.get('id', 'unknown')
            logger.info("Processing job %s", job_id)

            if self.progress_publisher and job_id:
                self.progress_publisher.start_job(job_id)

            input_filename = message.get('inputFile', '')
            output_filename = message.get('outputFile', '')
            slide_width = message.get('slideWidth', self.default_slide_width)
            slide_height = message.get('slideHeight', self.default_slide_height)

            if not input_filename or not output_filename:
                raise ValueError("Missing required fields: inputFile or outputFile")


            input_path = self.shared_dir / input_filename
            output_path = self.shared_dir / output_filename


            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")


            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info("Converting %s to %s", input_path, output_path)
            logger.info("Slide dimensions: %sx%s inches", slide_width, slide_height)


            generator = PowerPointGenerator(
                slide_width_inches=slide_width,
                slide_height_inches=slide_height,
                content_extractor=self.content_extractor
            )


            result_path = generator.generate_from_json_data(
                str(input_path),
                str(output_path)
            )


            slide_count = (len(generator.presentation.slides)
                           if hasattr(generator, 'presentation') else 0)


            self.progress_publisher.complete_job(
                job_id,
                str(output_filename),
                slide_count
            )

            logger.info("Successfully converted job %s", job_id)
            logger.info("Output saved to: %s", result_path)


            ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in message: %s", e)
            self.progress_publisher.fail_job(job_id, "Invalid message format", str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except FileNotFoundError as e:
            logger.error("File not found: %s", e)
            self.progress_publisher.fail_job(job_id, "Input file not found", str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing job: %s", e)
            logger.error(traceback.format_exc())

            self.progress_publisher.fail_job(
                job_id,
                "Conversion failed",
                str(e)
            )

            # Reject with requeue - might be a temporary issue
            # You might want to implement a retry limit here
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start_consuming(self):
        """Start consuming messages from the queue"""
        try:
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self.process_message,
                auto_ack=False
            )

            logger.info("Starting to consume from %s", self.queue_name)
            logger.info("Waiting for messages. To exit press CTRL+C")

            self.channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self.stop_consuming()
        except Exception as e:
            logger.error("Error during consumption: %s", e)
            self.stop_consuming()

    def stop_consuming(self):
        """Gracefully stop consuming and close connections"""
        logger.info("Stopping consumer...")

        if hasattr(self, 'progress_publisher') and self.progress_publisher:
            self.progress_publisher.close()

        if self.channel and not self.channel.is_closed:
            try:
                self.channel.stop_consuming()
                self.channel.close()
            except Exception as e:
                logger.error("Error closing channel: %s", e)

        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception as e:
                logger.error("Error closing connection: %s", e)

        logger.info("Consumer stopped")

    def run(self):
        """Main run loop with automatic reconnection"""
        while True:
            try:
                if self.connect():
                    self.start_consuming()
                else:
                    logger.error("Failed to connect, retrying in 5 seconds...")
                    time.sleep(5)
            except Exception as e:
                logger.error("Unexpected error in run loop: %s", e)
                logger.error(traceback.format_exc())
                time.sleep(5)
