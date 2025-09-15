"""
Progress Publisher uses Redis for Conversion Updates
Publishes real-time progress updates during PowerPoint generation
"""

import redis
import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ProgressPublisher:
    """Publishes conversion progress updates to Redis"""
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis publisher
        
        Args:
            redis_url: Redis connection URL (defaults to env var REDIS_URL)
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL')
        self.redis_client = None
        self.current_job_id = None
        
        try:
            self.connect()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Don't fail if Redis is unavailable - progress updates are optional
    
    def connect(self):
        """Establish Redis connection"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis_client = None
            raise
    
    def start_job(self, job_id: str):
        """Publish that the job has started."""
        self.publish_status(job_id, "processing", {"details": "Conversion has started."})

    def publish_status(self, job_id: str, status: str, message_data: Dict):
        """
        Publish status change to Redis
        
        Args:
            job_id: Unique job identifier
            status: Status (processing, completed, failed)
            message_data: Data associated with the status
        """
        if not self.redis_client:
            return
        
        try:
            channel = f"conversion:{job_id}"
            
            payload = {
                "status": status,
                "message": message_data
            }
            
            self.redis_client.publish(channel, json.dumps(payload))
            
        except Exception as e:
            logger.error(f"Failed to publish status: {e}")
    
    def complete_job(self, job_id: str, output_path: str, slide_count: int):
        """Mark job as completed with result data"""
        result = {
            "outputFile": output_path,
            "slideCount": slide_count,
        }
        
        self.publish_status(job_id, "completed", result)
    
    def fail_job(self, job_id: str, error_message: str, error_details: Optional[str] = None):
        """Mark job as failed with error information"""
        error_data = {
            "code": "CONVERSION_FAILED",
            "message": error_message,
            "details": error_details
        }
        
        self.publish_status(job_id, "failed", error_data)
        
    def close(self):
        """Close Redis connection"""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
