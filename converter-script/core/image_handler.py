"""
This module contains the ImageHandler class for managing images.
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageHandler:
    """Handles image downloading, caching, and processing"""

    def __init__(self, cache_dir: str = ".image_cache"):
        """
        Initialize the image handler

        Args:
            cache_dir: Directory to cache downloaded images
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; MiroPPTXConverter/1.0)'
        })

    def get_cache_path(self, url: str) -> Path:
        """
        Generate cache file path for a given URL

        Args:
            url: The image URL

        Returns:
            Path to the cache file
        """
        url_hash = hashlib.md5(url.encode()).hexdigest()

        parsed_url = urlparse(url)
        path = parsed_url.path
        ext = ''

        if '.' in path:
            ext = path.split('.')[-1].lower()
            ext = ext.split('?')[0]
            if ext not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                ext = 'jpg'
        else:
            ext = 'jpg'

        return self.cache_dir / f"{url_hash}.{ext}"

    def download_image(self, url: str, force_download: bool = False) -> Optional[Path]:
        """
        Download an image from URL and cache it

        Args:
            url: The image URL to download
            force_download: Force re-download even if cached

        Returns:
            Path to the downloaded image file, or None if failed
        """
        if not url:
            logger.error("Empty URL provided")
            return None

        cache_path = self.get_cache_path(url)

        if cache_path.exists() and not force_download:
            logger.info("Using cached image: %s", cache_path.name)
            return cache_path

        try:
            logger.info("Downloading image from: %s", url)
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.warning("URL does not appear to be an image: %s", content_type)

            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.info("Image downloaded successfully: %s", cache_path.name)
            return cache_path

        except requests.exceptions.RequestException as e:
            logger.error("Error downloading image from %s: %s", url, str(e))
            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error downloading image: %s", str(e))
            return None

    def get_image_info(self, image_path: Path) -> Optional[Tuple[int, int]]:
        """
        Get image dimensions without loading the full image

        Args:
            image_path: Path to the image file

        Returns:
            Tuple of (width, height) or None if failed
        """
        try:
            with Image.open(image_path) as img:
                return img.size

        except ImportError:
            logger.warning("PIL/Pillow not installed. Cannot get image dimensions.")
            return None
        except Exception as e: 
            logger.error("Error reading image info: %s", str(e))
            return None

    def crop_image(self, image_path: Path, crop_x: float, crop_y: float,
                   crop_width: float, crop_height: float,
                   output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Crop an image to specified dimensions

        Args:
            image_path: Path to the source image
            crop_x: X coordinate of crop rectangle
            crop_y: Y coordinate of crop rectangle
            crop_width: Width of crop rectangle
            crop_height: Height of crop rectangle
            output_path: Optional output path (defaults to cache)

        Returns:
            Path to cropped image or None if failed
        """
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img_width, img_height = img.size

                crop_x = max(0, min(crop_x, img_width))
                crop_y = max(0, min(crop_y, img_height))
                crop_right = min(crop_x + crop_width, img_width)
                crop_bottom = min(crop_y + crop_height, img_height)

                if (crop_x == 0 and crop_y == 0 and
                        crop_right == img_width and crop_bottom == img_height):
                    return image_path

                cropped = img.crop((int(crop_x), int(crop_y),
                                  int(crop_right), int(crop_bottom)))

                if output_path is None:
                    stem = image_path.stem
                    ext = image_path.suffix
                    output_path = (self.cache_dir /
                                   f"{stem}_crop_{int(crop_width)}x{int(crop_height)}{ext}")

                cropped.save(output_path, quality=95)
                logger.info("Image cropped and saved to: %s", output_path.name)

                return output_path

        except ImportError:
            logger.error("PIL/Pillow not installed. Cannot crop images.")
            return None
        except Exception as e:
            logger.error("Error cropping image: %s", str(e))
            return None

    def validate_image(self, image_path: Path) -> bool:
        """
        Validate that a file is a valid image

        Args:
            image_path: Path to the image file

        Returns:
            True if valid image, False otherwise
        """
        if not image_path.exists():
            return False

        file_size = image_path.stat().st_size
        if file_size < 100:
            logger.warning("Image file too small: %s bytes", file_size)
            return False
        if file_size > 50 * 1024 * 1024:
            logger.warning("Image file too large: %s bytes", file_size)
            return False

        info = self.get_image_info(image_path)
        return info is not None

    def clear_cache(self):
        """Clear all cached images"""
        count = 0
        for file in self.cache_dir.glob("*"):
            if file.is_file():
                file.unlink()
                count += 1
        logger.info("Cleared %d cached images", count)

    def get_cache_size(self) -> int:
        """
        Get total size of cached images in bytes

        Returns:
            Total size in bytes
        """
        total_size = 0
        for file in self.cache_dir.glob("*"):
            if file.is_file():
                total_size += file.stat().st_size
        return total_size

    def get_cache_info(self) -> dict:
        """
        Get information about the image cache

        Returns:
            Dictionary with cache information
        """
        files = list(self.cache_dir.glob("*"))
        file_count = len([f for f in files if f.is_file()])
        total_size = self.get_cache_size()

        return {
            'cache_dir': str(self.cache_dir),
            'file_count': file_count,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024)
        }