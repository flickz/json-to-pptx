from dataclasses import dataclass
from typing import Tuple, Optional
from enum import Enum
import math


class CoordinateSchema(Enum):
    """Types of coordinate schemas in Miro data"""
    CANVAS_OFFSET_PX = "canvasOffsetPx"
    PARENT_OFFSET_PX = "parentOffsetPx"
    STRING_INDEX_2D = "stringIndex2dPosition"


@dataclass
class BoundingBox:
    """Represents a bounding box with position and size"""
    left: float
    top: float
    width: float
    height: float
    
    @property
    def right(self) -> float:
        return self.left + self.width
    
    @property
    def bottom(self) -> float:
        return self.top + self.height
    
    @property
    def center_x(self) -> float:
        return self.left + self.width / 2
    
    @property
    def center_y(self) -> float:
        return self.top + self.height / 2


class CoordinateConverter:
    """Converts between Miro and PowerPoint coordinate systems"""
    
    # Standard PowerPoint slide dimensions in inches
    PPTX_WIDTH_INCHES = 10.0  
    PPTX_HEIGHT_INCHES = 5.625
    POINTS_PER_INCH = 72
    
    def __init__(self, frame_width: float, frame_height: float, 
                 slide_width_inches: float = None, slide_height_inches: float = None):
        """
        Initialize converter with frame dimensions
        
        Args:
            frame_width: Width of the Miro frame in pixels
            frame_height: Height of the Miro frame in pixels
            slide_width_inches: Custom slide width (defaults to standard 10")
            slide_height_inches: Custom slide height (defaults to standard 5.625")
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        self.slide_width_inches = slide_width_inches or self.PPTX_WIDTH_INCHES
        self.slide_height_inches = slide_height_inches or self.PPTX_HEIGHT_INCHES
        
        self.slide_width_points = self.slide_width_inches * self.POINTS_PER_INCH
        self.slide_height_points = self.slide_height_inches * self.POINTS_PER_INCH
        
        self.scale_x = self.slide_width_points / frame_width
        self.scale_y = self.slide_height_points / frame_height
        
        self.uniform_scale = min(self.scale_x, self.scale_y)
        
        # Calculate offsets for centering if aspect ratios don't match
        self.offset_x = (self.slide_width_points - frame_width * self.uniform_scale) / 2
        self.offset_y = (self.slide_height_points - frame_height * self.uniform_scale) / 2
    
    def pixels_to_points(self, pixels: float) -> float:
        """Convert pixels to points using uniform scaling"""
        return pixels * self.uniform_scale
    
    def pixels_to_inches(self, pixels: float) -> float:
        """Convert pixels to inches"""
        return self.pixels_to_points(pixels) / self.POINTS_PER_INCH
    
    def miro_to_pptx_position(self, x: float, y: float, 
                              width: float, height: float,
                              scale: float = 1.0,
                              parent_bounds: Optional[BoundingBox] = None,
                              schema: str = "parentOffsetPx",
                              text_align: str = "l") -> BoundingBox:
        """
        Convert Miro position to PowerPoint position
        
        Args:
            x, y: Position in Miro coordinates
            width, height: Size in Miro coordinates
            scale: Element's scale factor
            parent_bounds: Parent element's bounds (for relative positioning)
            schema: Coordinate schema type
            text_align: Text alignment ('l', 'c', 'r')
        
        Returns:
            BoundingBox in PowerPoint points
        """
        # Apply element scale to dimensions
        scaled_width = width * scale
        scaled_height = height * scale
        
        if schema == CoordinateSchema.PARENT_OFFSET_PX.value and parent_bounds:
            if text_align == 'c':
                left = parent_bounds.left + self.pixels_to_points(x - scaled_width / 2)
                top = parent_bounds.top + self.pixels_to_points(y - scaled_height / 2)
            else:
                left = parent_bounds.left + self.pixels_to_points(x - scaled_width / 2)
                top = parent_bounds.top + self.pixels_to_points(y - scaled_height / 2)
        elif schema == CoordinateSchema.CANVAS_OFFSET_PX.value:
            left = self.offset_x + self.pixels_to_points(x)
            top = self.offset_y + self.pixels_to_points(y)
        else:
            left = self.offset_x
            top = self.offset_y
        
        pptx_width = self.pixels_to_points(scaled_width)
        pptx_height = self.pixels_to_points(scaled_height)
        
        return BoundingBox(left=left, top=top, width=pptx_width, height=pptx_height)
    
    def get_text_box_position(self, miro_x: float, miro_y: float,
                              miro_width: float, miro_height: float,
                              scale: float = 1.0,
                              parent_bounds: Optional[BoundingBox] = None,
                              text_align: str = "l") -> Tuple[float, float, float, float]:
        """
        Get PowerPoint text box position in inches
        
        Returns:
            Tuple of (left, top, width, height) in inches
        """
        bbox = self.miro_to_pptx_position(
            miro_x, miro_y, miro_width, miro_height, 
            scale, parent_bounds, "parentOffsetPx", text_align
        )
        
        return (
            bbox.left / self.POINTS_PER_INCH,
            bbox.top / self.POINTS_PER_INCH,
            bbox.width / self.POINTS_PER_INCH,
            bbox.height / self.POINTS_PER_INCH
        )
    
    def calculate_font_size(self, base_font_size: int, scale: float = 1.0) -> int:
        """
        Calculate adjusted font size considering scale
        
        Args:
            base_font_size: Base font size from style
            scale: Element's scale factor
        
        Returns:
            Adjusted font size in points
        """
        adjusted_size = base_font_size * scale * 0.75  # 0.75 is an approximation factor
        return int(round(adjusted_size))
    
    def get_image_position(self, miro_x: float, miro_y: float,
                          original_width: float, original_height: float,
                          scale: float = 1.0,
                          crop_x: float = 0, crop_y: float = 0,
                          crop_width: float = 0, crop_height: float = 0,
                          parent_bounds: Optional[BoundingBox] = None) -> Tuple[float, float, float, float]:
        """
        Get PowerPoint image position in inches
        
        Args:
            miro_x, miro_y: Position in Miro coordinates
            original_width, original_height: Original image dimensions
            scale: Image scale factor
            crop_x, crop_y, crop_width, crop_height: Crop rectangle
            parent_bounds: Parent element's bounds
        
        Returns:
            Tuple of (left, top, width, height) in inches
        """
        if crop_width > 0 and crop_height > 0:
            width = crop_width
            height = crop_height
        else:
            width = original_width
            height = original_height
        
        scaled_width = width * scale
        scaled_height = height * scale
        
        if parent_bounds:
            left = parent_bounds.left + self.pixels_to_points(miro_x - scaled_width / 2)
            top = parent_bounds.top + self.pixels_to_points(miro_y - scaled_height / 2)
        else:
            left = self.offset_x + self.pixels_to_points(miro_x - scaled_width / 2)
            top = self.offset_y + self.pixels_to_points(miro_y - scaled_height / 2)
        
        pptx_width = self.pixels_to_points(scaled_width)
        pptx_height = self.pixels_to_points(scaled_height)
        
        return (
            left / self.POINTS_PER_INCH,
            top / self.POINTS_PER_INCH,
            pptx_width / self.POINTS_PER_INCH,
            pptx_height / self.POINTS_PER_INCH
        )
    
    def calculate_image_fit(self, image_width: float, image_height: float,
                           max_width: float, max_height: float,
                           maintain_aspect_ratio: bool = True) -> Tuple[float, float]:
        """
        Calculate dimensions to fit image within bounds
        
        Args:
            image_width, image_height: Original image dimensions
            max_width, max_height: Maximum allowed dimensions
            maintain_aspect_ratio: Whether to maintain aspect ratio
        
        Returns:
            Tuple of (width, height) that fits within bounds
        """
        if not maintain_aspect_ratio:
            return (max_width, max_height)
        
        # Calculate scale factors
        scale_x = max_width / image_width
        scale_y = max_height / image_height
        
        # Use smaller scale to fit within bounds
        scale = min(scale_x, scale_y)
        
        return (image_width * scale, image_height * scale)
    
    def get_frame_bounds(self) -> BoundingBox:
        """Get the frame bounds in PowerPoint coordinates"""
        return BoundingBox(
            left=self.offset_x,
            top=self.offset_y,
            width=self.pixels_to_points(self.frame_width),
            height=self.pixels_to_points(self.frame_height)
        )
    
    def debug_info(self) -> str:
        """Get debug information about the conversion"""
        return f"""
                Coordinate Converter Debug Info:
                - Frame Size: {self.frame_width} x {self.frame_height} px
                - Slide Size: {self.slide_width_inches}" x {self.slide_height_inches}" ({self.slide_width_points} x {self.slide_height_points} pts)
                - Scale Factors: X={self.scale_x:.4f}, Y={self.scale_y:.4f}, Uniform={self.uniform_scale:.4f}
                - Centering Offset: ({self.offset_x:.2f}, {self.offset_y:.2f}) pts
                - Frame in PPT: {self.get_frame_bounds()}
                """

