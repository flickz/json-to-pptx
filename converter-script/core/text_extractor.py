"""
This module contains classes for extracting and processing text from Miro widgets.
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from bs4 import BeautifulSoup, NavigableString, Tag


class TextFormat(Enum):
    """Text formatting options"""
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"


@dataclass
class TextRun:
    """Represents a run of text with consistent formatting"""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    color: Optional[str] = None
    font_size: Optional[int] = None
    font_family: Optional[str] = None


@dataclass
class ProcessedText:
    """Processed text content with formatting runs"""
    runs: List[TextRun] = field(default_factory=list)
    plain_text: str = ""

    def add_run(self, text: str, **formats):
        """Add a text run with formatting"""
        if text:
            self.runs.append(TextRun(text=text, **formats))
            self.plain_text += text


@dataclass
class ExtractedContent:
    """Complete extracted content for a text element"""
    element_id: str
    processed_text: ProcessedText
    base_style: Dict[str, Any]
    text_align: str = "left"
    font_family: str = "Arial"
    font_size: int = 12
    text_color: str = "#000000"
    background_color: Optional[str] = None

    @property
    def plain_text(self) -> str:
        """Returns the plain text content."""
        return self.processed_text.plain_text


class ContentExtractor:
    """Extracts and processes content from Miro text elements"""

    @staticmethod
    def int_to_hex_color(color_int: Optional[int]) -> Optional[str]:
        """Convert Miro integer color to hex string"""
        if color_int is None or color_int < 0:
            return None
        red = (color_int >> 16) & 0xFF
        green = (color_int >> 8) & 0xFF
        blue = color_int & 0xFF
        return f"#{red:02X}{green:02X}{blue:02X}"

    @staticmethod
    def rgb_string_to_hex(rgb_string: str) -> str:
        """Convert 'rgb(r,g,b)' string to hex color"""
        match = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', rgb_string)
        if match:
            red, green, blue = map(int, match.groups())
            return f"#{red:02X}{green:02X}{blue:02X}"
        return "#000000"

    def extract_from_html(self, html_content: str,
                           base_formats: Optional[Dict[str, bool]] = None) -> ProcessedText:
        """Extract text runs from HTML content"""
        if not html_content:
            return ProcessedText()

        base_formats = base_formats or {}
        processed = ProcessedText()

        soup = BeautifulSoup(html_content, 'html.parser')

        self._process_element(soup, processed, base_formats.copy())

        return processed

    def _process_element(self, element, processed: ProcessedText, current_formats: Dict[str, Any]): # pylint: disable=too-many-branches
        """Recursively process HTML elements"""
        if isinstance(element, NavigableString):
            text = str(element)
            if text.strip():
                processed.add_run(text, **current_formats)

        elif isinstance(element, Tag):
            new_formats = current_formats.copy()

            if element.name in ['strong', 'b']:
                new_formats['bold'] = True
            elif element.name in ['em', 'i']:
                new_formats['italic'] = True
            elif element.name == 'u':
                new_formats['underline'] = True
            elif element.name in ['strike', 's', 'del']:
                new_formats['strikethrough'] = True

            if element.get('style'):
                style_dict = self._parse_inline_style(element['style'])
                if 'color' in style_dict:
                    color = style_dict['color']
                    if color.startswith('rgb'):
                        new_formats['color'] = self.rgb_string_to_hex(color)
                    else:
                        new_formats['color'] = color

                if 'font-weight' in style_dict and style_dict['font-weight'] in ['bold', '700']:
                    new_formats['bold'] = True

                if 'font-style' in style_dict and style_dict['font-style'] == 'italic':
                    new_formats['italic'] = True

                if 'text-decoration' in style_dict:
                    if 'underline' in style_dict['text-decoration']:
                        new_formats['underline'] = True
                    if 'line-through' in style_dict['text-decoration']:
                        new_formats['strikethrough'] = True

            for child in element.children:
                self._process_element(child, processed, new_formats)

    def _parse_inline_style(self, style_string: str) -> Dict[str, str]:
        """Parse inline CSS style string"""
        style_dict = {}
        if style_string:
            for item in style_string.split(';'):
                if ':' in item:
                    key, value = item.split(':', 1)
                    style_dict[key.strip().lower()] = value.strip()
        return style_dict

    def extract_content(self, text_widget) -> ExtractedContent:
        """Extract complete content from a text widget"""
        base_style = {}
        font_family = "Arial"
        font_size = 12
        text_color = "#000000"
        text_align = "left"
        background_color = None

        if hasattr(text_widget, 'style') and text_widget.style:
            style = text_widget.style

            font_family = style.font_family or "Arial"

            font_size = style.font_size or 12

            if style.text_color is not None:
                text_color = self.int_to_hex_color(style.text_color)

            if style.background_color is not None:
                background_color = self.int_to_hex_color(style.background_color)

            align_map = {'l': 'left', 'c': 'center', 'r': 'right'}
            text_align = align_map.get(style.text_align, 'left')

            base_style = {
                'bold': style.bold,
                'italic': style.italic,
                'underline': style.underline,
                'strikethrough': style.strike
            }

        html_content = (getattr(text_widget, 'html_content', '') or
                        getattr(text_widget, 'text', ''))
        processed_text = self.extract_from_html(html_content, base_style)

        if not processed_text.runs and html_content:
            plain_text = BeautifulSoup(html_content, 'html.parser').get_text()
            if plain_text.strip():
                processed_text.add_run(plain_text, **base_style)

        return ExtractedContent(
            element_id=text_widget.id,
            processed_text=processed_text,
            base_style=base_style,
            text_align=text_align,
            font_family=font_family,
            font_size=font_size,
            text_color=text_color,
            background_color=background_color
        )

    def get_pptx_font_mapping(self, miro_font: str) -> str:
        """Map Miro font names to PowerPoint-compatible fonts"""
        font_map = {
            'OpenSans': 'Open Sans',
            'NotoSans': 'Noto Sans',
            'Roobert': 'Arial',
            'Arial': 'Arial',
            'Helvetica': 'Arial',
            'Times': 'Times New Roman',
            'Courier': 'Courier New'
        }
        return font_map.get(miro_font, 'Arial')

