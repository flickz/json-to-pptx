"""
Data models for Miro JSON parsing and PowerPoint generation.

This module contains all the dataclasses used to represent Miro board elements
including widgets, positions, styles, and other structural data.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class Position:
    """Represents position information from Miro data"""
    x: float
    y: float
    schema: str  # e.g., "canvasOffsetPx", "parentOffsetPx"
    ref_id: Optional[str] = None
    string_index: Optional[str] = None


@dataclass
class Size:
    """Represents size dimensions"""
    width: float
    height: float


@dataclass
class Scale:
    """Represents scaling information"""
    scale: float
    relative_scale: float = 1.0


@dataclass
class Rotation:
    """Represents rotation information"""
    rotation: float
    relative_rotation: float = 0.0


@dataclass
class Style:
    """Represents style properties for widgets"""
    font_family: Optional[str] = None  # ffn
    font_size: Optional[int] = None    # fs
    text_color: Optional[int] = None   # tc
    background_color: Optional[int] = None  # bc
    text_align: Optional[str] = None   # ta
    bold: bool = False                 # b
    italic: bool = False               # i
    underline: bool = False            # u
    strike: bool = False               # s
    
    @classmethod
    def from_style_string(cls, style_str: str) -> 'Style':
        """Parse style string into Style object"""
        try:
            style_data = json.loads(style_str) if isinstance(style_str, str) else style_str
            return cls(
                font_family=style_data.get('ffn'),
                font_size=style_data.get('fs', style_data.get('st')),
                text_color=style_data.get('tc'),
                background_color=style_data.get('bc'),
                text_align=style_data.get('ta'),
                bold=bool(style_data.get('b', 0)),
                italic=bool(style_data.get('i', 0)),
                underline=bool(style_data.get('u', 0)),
                strike=bool(style_data.get('s', 0))
            )
        except Exception as e:
            print(f"Error parsing style string: {e}")
            return cls()


@dataclass
class Widget:
    """Base class for all widget types"""
    id: str
    type: str
    parent_id: Optional[str] = None
    position: Optional[Position] = None
    size: Optional[Size] = None
    scale: Optional[Scale] = None
    rotation: Optional[Rotation] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_data(cls, widget_id: str, data: Dict[str, Any]) -> 'Widget':
        """Create widget instance from parsed data"""
        raise NotImplementedError(f"Widget type {cls.__name__} must implement from_data method")
    
    def render(self, slide, generator, coord_converter, frame_bounds):
        """Render this widget to the slide"""
        pass  # Default: do nothing
    
    def _parse_position(self, pos_data: Dict[str, Any]) -> Position:
        """Parse position data - helper method for subclasses"""
        schema = pos_data.get('schema', '')
        
        if schema == 'canvasOffsetPx' or schema == 'parentOffsetPx':
            offset_px = pos_data.get('offsetPx', {})
            return Position(
                x=offset_px.get('x', 0),
                y=offset_px.get('y', 0),
                schema=schema
            )
        elif schema == 'stringIndex2dPosition':
            return Position(
                x=0,
                y=0,
                schema=schema,
                ref_id=pos_data.get('refId'),
                string_index=pos_data.get('stringIndex')
            )
        else:
            return Position(x=0, y=0, schema='unknown')


@dataclass
class SlideContainer(Widget):
    """Represents a slide container widget"""
    padding: float = 0.0
    direction: int = 2
    children: List[Widget] = field(default_factory=list)
    
    @classmethod
    def from_data(cls, widget_id: str, data: Dict[str, Any]) -> 'SlideContainer':
        """Create SlideContainer from parsed data"""
        container = cls(
            id=widget_id,
            type='slidecontainer',
            padding=data.get('padding', 0.0),
            direction=data.get('direction', 2)
        )
        
        if '_position' in data:
            container.position = container._parse_position(data['_position'])
        
        if 'scale' in data:
            container.scale = Scale(scale=data['scale'].get('scale', 1.0))
        if 'rotation' in data:
            container.rotation = Rotation(rotation=data['rotation'].get('rotation', 0.0))
        
        return container


@dataclass
class Frame(Widget):
    """Represents a frame widget"""
    style: Optional[Style] = None
    name: str = ""
    presentation_order: Optional[str] = None
    children: List[Widget] = field(default_factory=list)
    
    @classmethod
    def from_data(cls, widget_id: str, data: Dict[str, Any]) -> 'Frame':
        """Create Frame from parsed data"""
        frame = cls(
            id=widget_id,
            type='frame',
            name=data.get('name', ''),
            presentation_order=data.get('presentationOrder')
        )
        
        if '_parent' in data and data['_parent']:
            frame.parent_id = data['_parent'].get('id')
        
        if '_position' in data:
            frame.position = frame._parse_position(data['_position'])
        
        if 'size' in data:
            frame.size = Size(
                width=data['size'].get('width', 0),
                height=data['size'].get('height', 0)
            )
        
        if 'style' in data:
            frame.style = Style.from_style_string(data['style'])
        
        if 'scale' in data:
            frame.scale = Scale(
                scale=data['scale'].get('scale', 1.0),
                relative_scale=data.get('relativeScale', 1.0)
            )
        
        return frame


@dataclass
class TextWidget(Widget):
    """Represents a text widget"""
    text: str = ""
    html_content: str = ""
    style: Optional[Style] = None
    
    @classmethod
    def from_data(cls, widget_id: str, data: Dict[str, Any]) -> 'TextWidget':
        """Create TextWidget from parsed data"""
        text_widget = cls(
            id=widget_id,
            type='text',
            text=data.get('text', ''),
            html_content=data.get('text', '')
        )
        
        if '_parent' in data and data['_parent']:
            text_widget.parent_id = data['_parent'].get('id')
        
        if '_position' in data:
            text_widget.position = text_widget._parse_position(data['_position'])
        
        if 'size' in data:
            text_widget.size = Size(
                width=data['size'].get('width', 0),
                height=data['size'].get('height', 0)
            )
        
        if 'style' in data:
            text_widget.style = Style.from_style_string(data['style'])
        
        if 'scale' in data:
            text_widget.scale = Scale(
                scale=data['scale'].get('scale', 1.0),
                relative_scale=data.get('relativeScale', 1.0)
            )
        if 'rotation' in data:
            text_widget.rotation = Rotation(
                rotation=data['rotation'].get('rotation', 0.0),
                relative_rotation=data.get('relativeRotation', 0.0)
            )
        
        return text_widget
    
    def render(self, slide, generator, coord_converter, frame_bounds):
        """Render text widget to slide"""
        import logging
        logger = logging.getLogger(__name__)
        
        content = generator.content_extractor.extract_content(self)
        
        text_align = self.style.text_align if self.style and self.style.text_align else 'l'
        left, top, width, height = coord_converter.get_text_box_position(
            self.position.x,
            self.position.y,
            self.size.width,
            self.size.height,
            self.scale.scale if self.scale else 1.0,
            frame_bounds,
            text_align
        )
        
        font_size = coord_converter.calculate_font_size(
            content.font_size,
            self.scale.scale if self.scale else 1.0
        )
        
        generator.add_text_box(left, top, width, height, content, font_size)
        
        logger.info(f"  ✓ Added: {content.plain_text[:40]}...")
        logger.info(f"    Position: ({left:.2f}\", {top:.2f}\") Size: {width:.2f}\" x {height:.2f}\"")
        logger.info(f"    Font: {generator.content_extractor.get_pptx_font_mapping(content.font_family)} {font_size}pt")
        if content.background_color:
            logger.info(f"    Background: {content.background_color}")


@dataclass
class ImageResource:
    """Image resource information"""
    id: str
    width: float
    height: float
    name: str = ""
    board_id: Optional[str] = None
    generated: bool = False


@dataclass
class ImageCrop:
    """Image crop settings"""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    shape: str = "custom"


@dataclass
class ImageWidget(Widget):
    """Represents an image widget"""
    resource: Optional[ImageResource] = None
    crop: Optional[ImageCrop] = None
    image_url: str = ""
    title: str = ""
    alt_text: str = ""
    style: Optional[Style] = None
    animated: bool = False
    
    @classmethod
    def from_data(cls, widget_id: str, data: Dict[str, Any]) -> 'ImageWidget':
        """Create ImageWidget from parsed data"""
        image_widget = cls(
            id=widget_id,
            type='image',
            title=data.get('title', ''),
            alt_text=data.get('altText', '')
        )
        
        if '_parent' in data and data['_parent']:
            image_widget.parent_id = data['_parent'].get('id')
        
        if '_position' in data:
            image_widget.position = image_widget._parse_position(data['_position'])
        
        if 'resource' in data:
            resource_data = data['resource']
            image_widget.resource = ImageResource(
                id=resource_data.get('id', ''),
                width=resource_data.get('width', 0),
                height=resource_data.get('height', 0),
                name=resource_data.get('name', ''),
                board_id=resource_data.get('boardId'),
                generated=resource_data.get('generated', False)
            )
        
        if 'crop' in data:
            crop_data = data['crop']
            image_widget.crop = ImageCrop(
                x=crop_data.get('x', 0),
                y=crop_data.get('y', 0),
                width=crop_data.get('width', 0),
                height=crop_data.get('height', 0),
                shape=crop_data.get('shape', 'custom')
            )
        
        # Parse image URL
        if 'image' in data:
            image_data = data['image']
            image_widget.image_url = image_data.get('externalLink', '')
            image_widget.animated = image_data.get('animated', False)
        
        if 'style' in data:
            image_widget.style = Style.from_style_string(data['style'])
        
        if 'scale' in data:
            image_widget.scale = Scale(
                scale=data['scale'].get('scale', 1.0),
                relative_scale=data.get('relativeScale', 1.0)
            )
        if 'rotation' in data:
            image_widget.rotation = Rotation(
                rotation=data['rotation'].get('rotation', 0.0),
                relative_rotation=data.get('relativeRotation', 0.0)
            )
        
        return image_widget
    
    def render(self, slide, generator, coord_converter, frame_bounds):
        """Render image widget to slide"""
        import logging
        logger = logging.getLogger(__name__)
        
        if self.resource:
            original_width = self.resource.width
            original_height = self.resource.height
        else:
            original_width = 100
            original_height = 100
        
        crop_x = self.crop.x if self.crop else 0
        crop_y = self.crop.y if self.crop else 0
        crop_width = self.crop.width if self.crop else original_width
        crop_height = self.crop.height if self.crop else original_height
        
        img_left, img_top, img_width, img_height = coord_converter.get_image_position(
            self.position.x,
            self.position.y,
            original_width,
            original_height,
            self.scale.scale if self.scale else 1.0,
            crop_x, crop_y, crop_width, crop_height,
            frame_bounds
        )
        
        generator.add_image(img_left, img_top, img_width, img_height, self)
        
        logger.info(f"  ✓ Processing image: {self.title or 'Untitled'}")
        logger.info(f"    Original size: {original_width:.0f} x {original_height:.0f}")
        logger.info(f"    Scale: {self.scale.scale if self.scale else 1.0:.4f}")


# Widget type registry - maps Miro widget types to their corresponding classes
WIDGET_REGISTRY = {
    'text': TextWidget,
    'image': ImageWidget,
    'frame': Frame,
    'slidecontainer': SlideContainer,
    # Add new widget types here: e.g. 'shape': ShapeWidget,
}
