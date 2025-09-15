"""
This module contains the PowerPointGenerator class for creating presentations.
"""
import logging
from typing import Optional, Tuple

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum import text as text_enum

from .data_parser import DataParser
from .models import Frame
from .coordinate_converter import CoordinateConverter
from .text_extractor import ContentExtractor, ExtractedContent
from .image_handler import ImageHandler

logger = logging.getLogger(__name__)


class PowerPointGenerator:
    """Generates PowerPoint presentations from Miro data"""

    def __init__(self, slide_width_inches: float = 10.0, slide_height_inches: float = 5.625,
                 image_cache_dir: str = ".image_cache",
                 content_extractor: Optional[ContentExtractor] = None):
        """
        Initialize the PowerPoint generator

        Args:
            slide_width_inches: Width of the slide in inches
            slide_height_inches: Height of the slide in inches
            image_cache_dir: Directory for caching downloaded images
            content_extractor: Instance of ContentExtractor
        """
        self.slide_width_inches = slide_width_inches
        self.slide_height_inches = slide_height_inches
        self.presentation = None
        self.slide = None
        self.image_handler = ImageHandler(cache_dir=image_cache_dir)
        self.content_extractor = content_extractor or ContentExtractor()


    def create_presentation(self):
        """Create a new presentation with custom slide size"""
        self.presentation = Presentation()

        self.presentation.slide_width = Inches(self.slide_width_inches)
        self.presentation.slide_height = Inches(self.slide_height_inches)

        blank_slide_layout = self.presentation.slide_layouts[6]
        self.slide = self.presentation.slides.add_slide(blank_slide_layout)

    def set_slide_background(self, hex_color: str):
        """Set the slide background color"""
        hex_color = hex_color.lstrip('#')
        red = int(hex_color[0:2], 16)
        green = int(hex_color[2:4], 16)
        blue = int(hex_color[4:6], 16)

        background = self.slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(red, green, blue)

    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def add_text_box(self, left_inches: float, top_inches: float,
                     width_inches: float, height_inches: float,
                     content: ExtractedContent, font_size_pt: int):
        """
        Add a text box to the slide with content and styling

        Args:
            left_inches: Left position in inches
            top_inches: Top position in inches
            width_inches: Width in inches
            height_inches: Height in inches
            content: Extracted content with text and styling
            font_size_pt: Calculated font size in points
        """
        min_height = 0.3
        if height_inches < min_height:
            top_inches = top_inches - (min_height - height_inches) / 2
            height_inches = min_height

        left = Inches(left_inches)
        top = Inches(top_inches)
        width = Inches(width_inches)
        height = Inches(height_inches)

        text_box = self.slide.shapes.add_textbox(left, top, width, height)
        text_frame = text_box.text_frame

        if height_inches < 0.5:
            text_frame.margin_left = Inches(0.05)
            text_frame.margin_right = Inches(0.05)
            text_frame.margin_top = Inches(0.02)
            text_frame.margin_bottom = Inches(0.02)
        else:
            text_frame.margin_left = Inches(0.1)
            text_frame.margin_right = Inches(0.1)
            text_frame.margin_top = Inches(0.05)
            text_frame.margin_bottom = Inches(0.05)

        text_frame.word_wrap = True

        if content.background_color:
            fill = text_box.fill
            fill.solid()
            red, green, blue = self.hex_to_rgb(content.background_color)
            fill.fore_color.rgb = RGBColor(red, green, blue)

        text_frame.clear()
        paragraph = text_frame.paragraphs[0]

        if content.text_align == 'center':
            paragraph.alignment = text_enum.PP_ALIGN.CENTER 
        elif content.text_align == 'right':
            paragraph.alignment = text_enum.PP_ALIGN.RIGHT 
        else:
            paragraph.alignment = text_enum.PP_ALIGN.LEFT 

        if content.text_align == 'center':
            text_frame.vertical_anchor = text_enum.MSO_ANCHOR.MIDDLE 
        else:
            text_frame.vertical_anchor = text_enum.MSO_ANCHOR.TOP 

        if content.processed_text.runs:
            for i, run_data in enumerate(content.processed_text.runs):
                if i == 0:
                    run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
                    run.text = run_data.text
                else:
                    run = paragraph.add_run()
                    run.text = run_data.text

                font = run.font
                font.name = self.content_extractor.get_pptx_font_mapping(content.font_family)
                font.size = Pt(font_size_pt)

                if run_data.color:
                    red, green, blue = self.hex_to_rgb(run_data.color)
                else:
                    red, green, blue = self.hex_to_rgb(content.text_color)
                font.color.rgb = RGBColor(red, green, blue)

                font.bold = run_data.bold
                font.italic = run_data.italic
                font.underline = run_data.underline
        else:
            run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
            run.text = content.plain_text

            font = run.font
            font.name = self.content_extractor.get_pptx_font_mapping(content.font_family)
            font.size = Pt(font_size_pt)

            red, green, blue = self.hex_to_rgb(content.text_color)
            font.color.rgb = RGBColor(red, green, blue)

            if content.base_style:
                font.bold = content.base_style.get('bold', False)
                font.italic = content.base_style.get('italic', False)
                font.underline = content.base_style.get('underline', False)

    def add_image(self, left_inches: float, top_inches: float,
                  width_inches: float, height_inches: float,
                  image_widget):
        """
        Add an image to the slide

        Args:
            left_inches: Left position in inches
            top_inches: Top position in inches
            width_inches: Width in inches
            height_inches: Height in inches
            image_widget: ImageWidget with image data
        """
        if not image_widget.image_url:
            logger.warning("Warning: No image URL for widget %s", image_widget.id)
            return

        image_path = self.image_handler.download_image(image_widget.image_url)
        if not image_path:
            logger.error("Error: Failed to download image from %s", image_widget.image_url)
            return

        if (image_widget.crop and # pylint: disable=too-many-boolean-expressions
                image_widget.crop.width > 0 and
                image_widget.crop.height > 0 and
                (image_widget.crop.x > 0 or
                 image_widget.crop.y > 0 or
                 image_widget.crop.width != image_widget.resource.width or
                 image_widget.crop.height != image_widget.resource.height)):

            cropped_path = self.image_handler.crop_image(
                image_path,
                image_widget.crop.x,
                image_widget.crop.y,
                image_widget.crop.width,
                image_widget.crop.height
            )
            if cropped_path:
                image_path = cropped_path

        try:
            left = Inches(left_inches)
            top = Inches(top_inches)
            width = Inches(width_inches)
            height = Inches(height_inches)

            self.slide.shapes.add_picture(str(image_path), left, top, width, height)


            logger.info("  ✓ Added image: %s", image_widget.title or 'Untitled')
            logger.info("    Position: (%.2f\", %.2f\")", left_inches, top_inches)
            logger.info("    Size: %.2f\" x %.2f\"", width_inches, height_inches)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error adding image to slide: %s", str(e))

    def generate_from_json_data(self, data_path: str, output_path: str = "output.pptx"):
        """
        Generate PowerPoint from Miro data file

        Args:
            data_path: Path to the Miro data JSON file
            output_path: Path for the output PowerPoint file
        """
        logger.info("Generating PowerPoint from %s", data_path)
        logger.info("=" * 60)

        parser = DataParser(data_path)
        widgets = parser.parse()

        frames = [w for w in widgets.values() if isinstance(w, Frame)]

        if not frames:
            raise ValueError("No frames found in the data")

        frames.sort(key=lambda f: f.presentation_order or "")

        logger.info("Found %d frame(s) to process", len(frames))

        self.presentation = Presentation()

        self.presentation.slide_width = Inches(self.slide_width_inches)
        self.presentation.slide_height = Inches(self.slide_height_inches)

        for frame_idx, frame in enumerate(frames):
            logger.info("\n%s", '='*60)
            logger.info("Processing Frame %d of %d", frame_idx + 1, len(frames))
            logger.info("Frame name: %s", frame.name or 'Unnamed')
            logger.info("Frame size: %.2f x %.2f px", frame.size.width, frame.size.height)
            logger.info("Presentation order: %s", frame.presentation_order or 'None')

            coord_converter = CoordinateConverter(frame.size.width, frame.size.height,
                                                 self.slide_width_inches, self.slide_height_inches)

            blank_slide_layout = self.presentation.slide_layouts[6]
            self.slide = self.presentation.slides.add_slide(blank_slide_layout)

            if frame.style and frame.style.background_color is not None:
                bg_color = self.content_extractor.int_to_hex_color(frame.style.background_color)
                if bg_color:
                    self.set_slide_background(bg_color)
                    logger.info("Slide background set to %s", bg_color)

            frame_bounds = coord_converter.get_frame_bounds()

            logger.info("\nAdding elements to slide:")
            for child in frame.children:
                child.render(self.slide, self, coord_converter, frame_bounds)

        self.presentation.save(output_path)

        logger.info("\n%s", '='*60)
        logger.info("✅ Presentation saved to: %s", output_path)
        logger.info("📊 Total slides created: %d", len(frames))

        return output_path
