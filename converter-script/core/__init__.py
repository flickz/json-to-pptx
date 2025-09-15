"""
Core module for the PowerPoint generator.
"""
from .generator import PowerPointGenerator
from .data_parser import DataParser
from .coordinate_converter import CoordinateConverter
from .text_extractor import ContentExtractor
from .image_handler import ImageHandler

from .models import (
    Position, Size, Scale, Rotation, Style,
    Widget, SlideContainer, Frame, TextWidget, ImageWidget,
    ImageResource, ImageCrop, WIDGET_REGISTRY
)

from .coordinate_converter import CoordinateSchema, BoundingBox

from .text_extractor import (
    TextFormat, TextRun, ProcessedText, ExtractedContent
)

__all__ = [
    'PowerPointGenerator',
    'DataParser',
    'CoordinateConverter',
    'ContentExtractor',
    'ImageHandler',

    # Data classes
    'Position', 'Size', 'Scale', 'Rotation', 'Style',
    'Widget', 'SlideContainer', 'Frame', 'TextWidget', 'ImageWidget',
    'ImageResource', 'ImageCrop', 'WIDGET_REGISTRY',

    'CoordinateSchema', 'BoundingBox',

    'TextFormat', 'TextRun', 'ProcessedText', 'ExtractedContent',
]
