
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from .models import (
    Position, Size, Scale, Rotation, Style,
    Widget, SlideContainer, Frame, TextWidget, ImageWidget,
    ImageResource, ImageCrop, WIDGET_REGISTRY
)


class DataParser:
    """Parser for Miro board export data""" 
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.widgets: Dict[str, Widget] = {}
        self.root_widgets: List[Widget] = []
        
    def parse(self) -> Dict[str, Widget]:
        """Parse the data file and return structured widgets"""
        # Load main JSON
        with open(self.data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        widgets_data = raw_data.get('content', {}).get('widgets', [])
        
        for widget_data in widgets_data:
            widget = self._parse_widget(widget_data)
            if widget:
                self.widgets[widget.id] = widget
        
        # Second pass: Build parent-child relationships
        self._build_relationships()
        
        # Identify root widgets
        self.root_widgets = [w for w in self.widgets.values() if w.parent_id is None]
        
        return self.widgets
    
    def _parse_widget(self, widget_data: Dict[str, Any]) -> Optional[Widget]:
        """Parse individual widget data"""
        widget_id = widget_data.get('id')
        canvas_data = widget_data.get('canvasedObjectData', {})
        widget_type = canvas_data.get('type')
        
        if not widget_id or not widget_type:
            return None
        
        json_str = canvas_data.get('json', '{}')
        try:
            nested_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Error parsing nested JSON for widget {widget_id}: {e}")
            nested_data = {}
        
        # Get the widget class from registry and create instance
        widget_class = WIDGET_REGISTRY.get(widget_type, Widget)
        
        if widget_class == Widget:
            widget = Widget(id=widget_id, type=widget_type)
        else:
            widget = widget_class.from_data(widget_id, nested_data)
        
        widget.raw_data = {
            'original': widget_data,
            'parsed': nested_data
        }
        
        return widget
    
    
    def _build_relationships(self):
        """Build parent-child relationships between widgets"""
        for widget in self.widgets.values():
            if widget.parent_id and widget.parent_id in self.widgets:
                parent = self.widgets[widget.parent_id]
                if isinstance(parent, (SlideContainer, Frame)):
                    parent.children.append(widget)
    
    def print_hierarchy(self, widget: Optional[Widget] = None, indent: int = 0):
        """Print widget hierarchy for debugging"""
        if widget is None:
            for root in self.root_widgets:
                self.print_hierarchy(root)
            return
        
        indent_str = "  " * indent
        print(f"{indent_str}{widget.type} (ID: {widget.id})")
        
        if isinstance(widget, TextWidget):
            text = widget.text.replace('<p>', '').replace('</p>', '')
            text = text.replace('<strong>', '').replace('</strong>', '')
            text = text[:50] + "..." if len(text) > 50 else text
            print(f"{indent_str}  Text: {text}")
        elif isinstance(widget, ImageWidget):
            print(f"{indent_str}  Image: {widget.title or 'Untitled'}")
            if widget.image_url:
                print(f"{indent_str}  URL: {widget.image_url[:50]}...")
            if widget.resource:
                print(f"{indent_str}  Dimensions: {widget.resource.width:.0f} x {widget.resource.height:.0f}")
        
        if widget.position:
            print(f"{indent_str}  Position: ({widget.position.x:.2f}, {widget.position.y:.2f}) [{widget.position.schema}]")
        
        if widget.size:
            print(f"{indent_str}  Size: {widget.size.width:.2f} x {widget.size.height:.2f}")
        
        if hasattr(widget, 'children'):
            for child in widget.children:
                self.print_hierarchy(child, indent + 1)
