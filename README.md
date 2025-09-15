# Setup

### 1. Environment Variables

Create a `.env` file in the project root with the following variables:

```env
RABBITMQ_USER=admin
RABBITMQ_PASS=password
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
REDIS_URL=redis://redis:6379

```

### 2. Directory Structure

The shared directory structure is automatically created by Docker:

```
shared/
├── uploads/
│   └── temp/     # Uploaded JSON files
└── outputs/      # Generated PPTX files
```

### 3. Running the Application

#### Using Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up --build

# Run in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

#### Service URLs

- Web Application: http://localhost:3000
- RabbitMQ Management UI: http://localhost:15672
- Default login: Use credentials from .env file

![image](/docs/ui.png)

### 4. How It Works

1. **File Upload**: Users upload JSON files through the web interface
2. **Queue Message**: The Node.js app publishes a conversion job to RabbitMQ
3. **Processing**: The Python converter consumes the message and processes the file
4. **Output**: The converted PPTX file is saved to the shared outputs directory
5. **Download**: Users can download the converted file from the web interface

Here's the corrected and refined version of your architecture documentation:

# Overall Architecture

![image](/docs/architecture.png)

My choice of architecture, as shown above, is somewhat over-engineered compared to the core deliverables. For example, the introduction of a web user interface was added because I had some extra time, and AI makes it easier to generate quick, simple user interfaces to demo the service.

## Core Components of the Architecture

### RabbitMQ

A conversion request is an I/O blocking operation since it requires communicating with a different service to perform the conversion. The waiting period would cause Node.js to block the event loop, leading to a non-scalable architecture. To scale effectively, we need a way of queuing up our conversion requests so that the converter can process them while the Node.js service continues to handle other requests. Hence, I'm using RabbitMQ, which is one of the most popular queue management services.

### Node.js Server

In this architecture, our Node.js server acts as a producer for the queue. It exposes a `/upload` endpoint for users to upload their JSON files. The original JSON file is uploaded to a temporary location, and a job ID is generated. The job details include the temporary file path of the uploaded document and the PowerPoint default size. The job details are then pushed to the queue.

### Python Converter

The converter acts as a consumer listening to the queue for new jobs to be processed. Once a new job is pushed to the queue, the converter immediately processes the conversion. Details on how the conversion works are explained later in this documentation. I'm using manual acknowledgment to ensure the conversion is completed before the job is dequeued. This also helps in case of potential crashes, the job is not lost, and failed jobs can be retried.

### Redis Pub/Sub Service

While this is not exactly required to meet our specification, I introduced this service for pure messaging communication purposes. My use of a web interface means I need a way of communicating the job status with the Node.js service to update the UI. The Node.js service subscribes to the Redis conversion channel, and the Converter Service publishes the status of the conversion. I kept it simple with just three states: `failed`, `processing`, and `completed`, but it can easily be expanded to provide more granular progress of the conversion. I added an extra route `/progress/stream/:id` which handles Server-Sent Events (SSE) to maintain communication with the UI and update as soon as a job completes.

### Shared Volume

Both output and upload paths are in a shared volume, allowing both the Node.js and Python Converter services to access files between them. This is configured through Docker Compose.

# Conversion Mechanism

The conversion mechanism is the trickiest part of the challenge, specifically, converting Miro’s board coordinate system into PowerPoint’s coordinate system.

### Understanding the Miro Data

The journey began with a single JSON file, `data.json`. This file contained the full export of a Miro board. At first glance, it was overwhelming: deeply nested structures, cryptic field names, and encoded values.

```json
{
  "content": {
    "widgets": [
      {
        "id": "3458764639651442143",
        "canvasedObjectData": {
          "widgetId": null,
          "type": "slidecontainer",
          "json": "{\"rotation\":{\"rotation\":0.0},\"scale\":{\"scale\":1.0},...}",
          "content": null
        }
      }
    ]
  }
}
```

#### Key discoveries

1. **Widget Hierarchy**
   Miro organizes everything as “widgets,” which form a hierarchy:

   - **SlideContainer**: The top-level container holding everything
   - **Frame**: A container for one or more widgets
   - **TextWidget**: Text elements placed inside frames
   - **ImageWidget**: Images placed inside frames

2. **Nested JSON Structure**
   One of the most challenging aspects was that widget properties are stored as JSON strings within JSON. For example:

   ```python
   widget_json = widget["canvasedObjectData"]["json"]
   widget_props = json.loads(widget_json)
   ```

3. **Coordinate System**
   According to the [Miro board documentation](https://developers.miro.com/docs/boards#position-and-coordinates):

   - **Origin**: Center of the widget (unlike most systems that use top-left)
   - **Units**: Pixels
   - **Parent-relative**: Positions are relative to parent widgets

4. **Style Encoding**
   Text styling is encoded in a compact format within the style string:

   ```json
   "style": "{\"fs\":14,\"tc\":16777215,\"bc\":-1,\"ta\":\"c\",\"ffn\":\"NotoSans\"}"
   ```

   Where:

   - `fs`: Font size
   - `tc`: Text color (integer)
   - `bc`: Background color
   - `ta`: Text alignment
   - `ffn`: Font family name

I wanted to model the data in a way that could be easily extended to support additional widget types in the future.

---

### Parsing and Modeling Data

I used Python dataclasses to model the Miro data structure. This approach provided type safety and made serialization and deserialization straightforward. Each widget type knows how to parse itself from the raw data.

```python
@dataclass
class Widget:
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
        """Create a widget instance from parsed data"""
        raise NotImplementedError(f"Widget type {cls.__name__} must implement from_data method")

    def render(self, slide, generator, coord_converter, frame_bounds):
        """Render this widget to the slide"""
        pass
```

#### Parsing Flow

1. Load JSON data from the Miro export file.
2. Extract the `widgets` array from the nested structure.
3. For each widget:

   - Extract the widget ID and type from `canvasedObjectData`.
   - Parse the nested JSON string containing widget properties.
   - Use the widget registry to locate the appropriate class.
   - Delegate creation to the widget’s `from_data()` method.
   - Store the widget in the collection.

---

### Coordinate Conversion

The next phase, coordinate conversion, was by far the most challenging. This was not just a matter of unit conversion, but a full transformation of how positions and sizes are calculated.

#### Understanding the Systems

**Miro’s Coordinate System**

- Origin: Center of each widget
- Units: Pixels
- Positioning: Relative to parent
- Scale: Multiplicative factor

**PowerPoint’s Coordinate System**

- Origin: Top-left corner
- Units: Inches (points for fonts)
- Positioning: Absolute to the slide
- Scale: Built into dimensions

#### Conversion Mathematics

1. **Origin Transformation**
   The key challenge was converting from Miro’s center-origin to PowerPoint’s top-left origin.

   ```python
   def get_text_box_position(self, center_x, center_y,
                             width, height, scale,
                             frame_bounds,
                             text_align='left'):
       """Convert Miro center position to PowerPoint top-left position"""

       # Apply scale to dimensions
       scaled_width = width * scale
       scaled_height = height * scale

       # Convert center to top-left
       top_left_x = center_x - (scaled_width / 2)
       top_left_y = center_y - (scaled_height / 2)
   ```

2. **Unit Conversion**
   Converting pixels to inches while preserving aspect ratios:

   ```python
   def _pixels_to_inches(self, pixels, is_horizontal):
       """Convert pixels to inches maintaining aspect ratio"""
       if is_horizontal:
           ratio = self.slide_width_inches / self.frame_width_pixels
       else:
           ratio = self.slide_height_inches / self.frame_height_pixels

       return pixels * ratio
   ```

3. **Frame-to-Slide Mapping**
   Since Miro frames don’t always match PowerPoint slide dimensions, intelligent scaling was required:

   ```python
   def get_frame_bounds(self):
       """Calculate how the Miro frame maps to a PowerPoint slide"""

       frame_aspect = self.frame_width_pixels / self.frame_height_pixels
       slide_aspect = self.slide_width_inches / self.slide_height_inches

       if frame_aspect > slide_aspect:
           # Frame is wider — fit to width
           scale = self.slide_width_inches / self.frame_width_pixels
           used_height = self.frame_height_pixels * scale

           # Center vertically
           top_offset = (self.slide_height_inches - used_height) / 2

           return {
               'left': 0,
               'top': top_offset,
               'right': self.slide_width_inches,
               'bottom': top_offset + used_height
           }
   ```

---

### Content Extraction

The goal was to extract text content and map Miro’s styling system to PowerPoint’s.

#### Miro’s Text Storage

Miro stores text as HTML:

```json
{
  "text": "<p>Lorem ipsum <strong>dolor sit</strong> amet, <em>consectetur</em> adipiscing elit.</p>",
  "style": "{\"fs\":14,\"tc\":16777215,\"bc\":-1,\"ta\":\"c\",\"ffn\":\"NotoSans\",\"b\":0,\"i\":0,\"u\":0}"
}
```

Challenges included:

1. HTML-encoded content with inline formatting.
2. Compact style strings with abbreviated property names.
3. Integer-based color values (sometimes negative).
4. Font-family mappings.

Parsing required both BeautifulSoup for HTML and custom logic for Miro’s compact style format:

```python
style_mapping = {
    'fs': 'font_size',
    'tc': 'text_color',
    'bc': 'background_color',
    'ta': 'text_align',
    'ffn': 'font_family',
    'b': 'bold',
    'i': 'italic',
    'u': 'underline',
    's': 'strikethrough'
}
```

Color conversion was another step:

```python
def int_to_hex_color(self, color_int: int) -> Optional[str]:
    """Convert Miro integer color to hex string"""
    if color_int == -1:
        return None

    # Handle negative values using two's complement
    if color_int < 0:
        color_int += (1 << 32)

    return f"#{color_int:06X}"
```

And font mappings:

```python
font_mappings = {
    'OpenSans': 'Open Sans',
    'NotoSans': 'Noto Sans',
    'Roobert': 'Arial',  # Fallback for unavailable fonts
}

def get_pptx_font_mapping(self, miro_font: str) -> str:
    """Map Miro font to a PowerPoint font"""
    return self.font_mappings.get(miro_font, 'Arial')
```

---

### PowerPoint Generation

With parsing, coordinate conversion, and content extraction in place, the final step was generating PowerPoint presentations using `python-pptx`.

#### Frame-Centric Processing

Miro frames map naturally to PowerPoint slides:

```python
def generate_from_json_data(self, data_path: str, output_path: str = "output.pptx"):
    parser = DataParser(data_path)
    widgets = parser.parse()

    frames = [w for w in widgets.values() if isinstance(w, Frame)]

    # Sort by presentation order
    frames.sort(key=lambda f: f.presentation_order or "")
```

#### Hierarchical Widget Processing

Widgets were processed hierarchically, respecting parent-child relationships: a frame and all its children were processed together to build the corresponding slide.

---

## Future Improvements

- Add more unit tests to improve maintainability.
- Expand testing with more diverse input data to handle additional widget types.

---

### Use of AI

I relied heavily on AI to help make sense of the data and refine parts of the conversion logic.
