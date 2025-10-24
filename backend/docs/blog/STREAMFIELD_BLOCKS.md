# StreamField Blocks Reference

Complete documentation for all content block types in the Plant Community blog system.

## Overview

The blog uses Wagtail's StreamField for flexible, structured content. All blocks are **flat** (no nesting) to simplify both editing and API consumption.

**Key Features**:
- 10 content block types for diverse content needs
- AI-assisted plant content (auto-population from plant database)
- JSON-based storage for headless API delivery
- Template-based rendering for traditional Wagtail pages
- Rich media support (images, video, galleries)

## Block Types

### 1. Heading

**Purpose**: Add section headings to structure content.

**Type**: `CharBlock`

**Fields**:
- `heading` (string, required): The heading text

**Template**: `blog/blocks/heading.html`

**Admin UI**:
```
Icon: title (📄)
Help text: "Add a heading to structure your content"
```

**Code Example**:
```python
from wagtail import blocks

heading = blocks.CharBlock(
    icon="title",
    template="blog/blocks/heading.html",
    help_text="Add a heading to structure your content"
)
```

**API JSON**:
```json
{
  "type": "heading",
  "value": "How to Care for Succulents",
  "id": "abc123"
}
```

**Template Rendering** (`blog/blocks/heading.html`):
```html
<h2 class="blog-heading">{{ value }}</h2>
```

**Use Cases**:
- Section headers in how-to guides
- Chapter divisions in long-form content
- Organizing plant care instructions

---

### 2. Paragraph

**Purpose**: Rich text content with formatting support.

**Type**: `RichTextBlock`

**Fields**:
- `paragraph` (rich text, required): Formatted paragraph content

**Features**:
- Bold, italic, underline, strikethrough
- Links (internal and external)
- Unordered and ordered lists
- Block quotes
- Inline code

**Template**: `blog/blocks/paragraph.html`

**Admin UI**:
```
Icon: pilcrow (¶)
Help text: "Add paragraph text with AI assistance for plant content"
```

**Code Example**:
```python
from wagtail import blocks

paragraph = blocks.RichTextBlock(
    icon="pilcrow",
    template="blog/blocks/paragraph.html",
    help_text="Add paragraph text with AI assistance for plant content"
)
```

**API JSON**:
```json
{
  "type": "paragraph",
  "value": "<p>Succulents are <strong>drought-tolerant</strong> plants that store water in their leaves, stems, or roots. They require <a href=\"/blog/watering-guide\">minimal watering</a> and thrive in bright, indirect light.</p>",
  "id": "def456"
}
```

**Template Rendering** (`blog/blocks/paragraph.html`):
```html
<div class="blog-paragraph richtext">
    {{ value|safe }}
</div>
```

**Security Note**: Always sanitize HTML in frontend (use DOMPurify for React/Flutter).

**Use Cases**:
- Main article content
- Plant descriptions
- Care instructions
- Background information

---

### 3. Image

**Purpose**: Add images with automatic alt text generation.

**Type**: `ImageChooserBlock`

**Fields**:
- `image` (image reference, required): Selected image from media library

**Features**:
- AI-generated alt text for accessibility
- Multiple rendition sizes via API
- Automatic caption from image metadata

**Template**: `blog/blocks/image.html`

**Admin UI**:
```
Icon: image (🖼️)
Help text: "Add images with AI-generated alt text"
```

**Code Example**:
```python
from wagtail.images.blocks import ImageChooserBlock

image = ImageChooserBlock(
    icon="image",
    template="blog/blocks/image.html",
    help_text="Add images with AI-generated alt text"
)
```

**API JSON**:
```json
{
  "type": "image",
  "value": 42,
  "id": "ghi789"
}
```

**Image API Response** (via nested serializer):
```json
{
  "type": "image",
  "value": {
    "id": 42,
    "title": "Echeveria Elegans Succulent",
    "width": 2400,
    "height": 1600,
    "download_url": "/media/images/echeveria-elegans.original.jpg",
    "thumbnail": {
      "url": "/media/images/echeveria-elegans.fill-300x200.jpg",
      "width": 300,
      "height": 200
    },
    "medium": {
      "url": "/media/images/echeveria-elegans.fill-800x600.jpg",
      "width": 800,
      "height": 600
    },
    "large": {
      "url": "/media/images/echeveria-elegans.fill-1200x800.jpg",
      "width": 1200,
      "height": 800
    }
  },
  "id": "ghi789"
}
```

**Template Rendering** (`blog/blocks/image.html`):
```html
{% load wagtailimages_tags %}

<figure class="blog-image">
    {% image value fill-800x600 as img %}
    <img src="{{ img.url }}" alt="{{ value.title }}" width="{{ img.width }}" height="{{ img.height }}">
    {% if value.caption %}
    <figcaption>{{ value.caption }}</figcaption>
    {% endif %}
</figure>
```

**Use Cases**:
- Plant photos
- Step-by-step process images
- Before/after comparisons
- Featured content imagery

---

### 4. Quote

**Purpose**: Highlight quotes or testimonials with attribution.

**Type**: `StructBlock`

**Fields**:
- `quote_text` (rich text, required): The quote content
- `attribution` (string, optional): Who said this quote

**Template**: `blog/blocks/quote.html`

**Admin UI**:
```
Icon: openquote (")
```

**Code Example**:
```python
from wagtail import blocks

quote = blocks.StructBlock([
    ('quote_text', blocks.RichTextBlock()),
    ('attribution', blocks.CharBlock(required=False, help_text="Who said this quote?"))
], icon="openquote", template="blog/blocks/quote.html")
```

**API JSON**:
```json
{
  "type": "quote",
  "value": {
    "quote_text": "<p>The glory of gardening: hands in the dirt, head in the sun, heart with nature.</p>",
    "attribution": "Alfred Austin"
  },
  "id": "jkl012"
}
```

**Template Rendering** (`blog/blocks/quote.html`):
```html
<blockquote class="blog-quote">
    <div class="quote-text">
        {{ value.quote_text|safe }}
    </div>
    {% if value.attribution %}
    <cite class="quote-attribution">— {{ value.attribution }}</cite>
    {% endif %}
</blockquote>
```

**Use Cases**:
- Expert testimonials
- Gardening wisdom
- User success stories
- Historical plant quotes

---

### 5. Code

**Purpose**: Display code snippets with syntax highlighting.

**Type**: `StructBlock`

**Fields**:
- `language` (choice, optional): Programming language for syntax highlighting
- `code` (text, required): Code content

**Supported Languages**:
- Python
- JavaScript
- HTML
- CSS
- Bash
- JSON

**Template**: `blog/blocks/code.html`

**Admin UI**:
```
Icon: code (</>)
```

**Code Example**:
```python
from wagtail import blocks

code = blocks.StructBlock([
    ('language', blocks.ChoiceBlock(choices=[
        ('python', 'Python'),
        ('javascript', 'JavaScript'),
        ('html', 'HTML'),
        ('css', 'CSS'),
        ('bash', 'Bash'),
        ('json', 'JSON'),
    ], required=False)),
    ('code', blocks.TextBlock())
], icon="code", template="blog/blocks/code.html")
```

**API JSON**:
```json
{
  "type": "code",
  "value": {
    "language": "python",
    "code": "def water_plant(plant, amount):\n    if plant.soil_moisture < 30:\n        plant.add_water(amount)\n        return True\n    return False"
  },
  "id": "mno345"
}
```

**Template Rendering** (`blog/blocks/code.html`):
```html
<div class="blog-code">
    <pre><code class="language-{{ value.language|default:'text' }}">{{ value.code }}</code></pre>
</div>
```

**Frontend Integration**:
Use Prism.js or Highlight.js for syntax highlighting:
```javascript
import Prism from 'prismjs';

// After rendering code block
Prism.highlightAll();
```

**Use Cases**:
- Plant care automation scripts
- API integration examples
- Data analysis code
- Configuration snippets

---

### 6. Plant Spotlight

**Purpose**: Highlight a specific plant with auto-populated data from the plant database.

**Type**: `StructBlock`

**Fields**:
- `plant_name` (string, required): Plant common name (triggers auto-population)
- `scientific_name` (string, optional): Auto-populated from database
- `description` (rich text, required): Auto-populated or AI-generated
- `care_difficulty` (choice, required): Easy/Moderate/Difficult (auto-calculated)
- `image` (image, optional): Suggested from database

**AI Features**:
- Searches plant database when `plant_name` is entered
- Auto-fills `scientific_name`, `description`, `care_difficulty`
- Suggests matching images from media library
- Generates description if not found in database

**Template**: `blog/blocks/plant_spotlight.html`

**Admin UI**:
```
Icon: snippet (🌱)
Help text: "Spotlight a specific plant with auto-populated data from our plant database"
```

**Code Example**:
```python
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

plant_spotlight = blocks.StructBlock([
    ('plant_name', blocks.CharBlock(
        help_text="🌱 Enter plant name - auto-population will fill other fields"
    )),
    ('scientific_name', blocks.CharBlock(
        required=False,
        help_text="Scientific name (auto-populated from plant database)"
    )),
    ('description', blocks.RichTextBlock(
        help_text="Plant description (auto-populated from database or AI-generated)"
    )),
    ('care_difficulty', blocks.ChoiceBlock(choices=[
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
        ('difficult', 'Difficult'),
    ], help_text="Care difficulty level (auto-calculated from plant requirements)")),
    ('image', ImageChooserBlock(
        required=False,
        help_text="Plant image (suggestions provided from database)"
    ))
], icon="snippet", template="blog/blocks/plant_spotlight.html")
```

**API JSON**:
```json
{
  "type": "plant_spotlight",
  "value": {
    "plant_name": "Monstera Deliciosa",
    "scientific_name": "Monstera deliciosa",
    "description": "<p>The <strong>Swiss Cheese Plant</strong> is a popular tropical houseplant known for its large, fenestrated leaves. Native to Central American rainforests, it's prized for its dramatic foliage and relatively easy care requirements.</p>",
    "care_difficulty": "easy",
    "image": 73
  },
  "id": "pqr678"
}
```

**Template Rendering** (`blog/blocks/plant_spotlight.html`):
```html
{% load wagtailimages_tags %}

<div class="plant-spotlight">
    {% if value.image %}
    <div class="plant-spotlight-image">
        {% image value.image fill-400x300 %}
    </div>
    {% endif %}
    <div class="plant-spotlight-content">
        <h3>{{ value.plant_name }}</h3>
        {% if value.scientific_name %}
        <p class="scientific-name"><em>{{ value.scientific_name }}</em></p>
        {% endif %}
        <div class="description">{{ value.description|safe }}</div>
        <span class="difficulty-badge difficulty-{{ value.care_difficulty }}">
            {{ value.get_care_difficulty_display }}
        </span>
    </div>
</div>
```

**Use Cases**:
- Featured plant of the month
- Plant profile sections
- Care guide introductions
- Species comparisons

---

### 7. Care Instructions

**Purpose**: Detailed plant care information with auto-populated guidance.

**Type**: `StructBlock`

**Fields**:
- `care_title` (string, required): Plant name (triggers auto-population)
- `watering` (rich text, required): Auto-populated from database
- `lighting` (rich text, required): Auto-populated from database
- `temperature` (string, optional): Auto-populated from hardiness data
- `humidity` (string, optional): Auto-populated or AI-generated
- `fertilizing` (rich text, optional): Auto-populated or AI-generated
- `special_notes` (rich text, optional): AI-generated from plant characteristics

**AI Features**:
- Queries plant database when `care_title` is entered
- Auto-fills all care fields from PlantNet/Plant.id data
- Generates context-aware special notes
- Calculates optimal conditions from plant family data

**Template**: `blog/blocks/care_instructions.html`

**Admin UI**:
```
Icon: help (?)
Help text: "Detailed plant care instructions with auto-populated guidance"
```

**Code Example**:
```python
from wagtail import blocks

care_instructions = blocks.StructBlock([
    ('care_title', blocks.CharBlock(
        help_text="🌿 Enter plant name in title - care details will auto-populate"
    )),
    ('watering', blocks.RichTextBlock(
        help_text="Watering instructions (auto-populated from plant database)"
    )),
    ('lighting', blocks.RichTextBlock(
        help_text="Lighting requirements (auto-populated from plant database)"
    )),
    ('temperature', blocks.CharBlock(
        required=False,
        help_text="Temperature preferences (auto-populated from hardiness data)"
    )),
    ('humidity', blocks.CharBlock(
        required=False,
        help_text="Humidity requirements (auto-populated or AI-generated)"
    )),
    ('fertilizing', blocks.RichTextBlock(
        required=False,
        help_text="Fertilizing schedule (auto-populated or AI-generated)"
    )),
    ('special_notes', blocks.RichTextBlock(
        required=False,
        help_text="Special care notes (AI-generated from plant characteristics)"
    ))
], icon="help", template="blog/blocks/care_instructions.html")
```

**API JSON**:
```json
{
  "type": "care_instructions",
  "value": {
    "care_title": "Fiddle Leaf Fig Care Guide",
    "watering": "<p>Water when the top 2-3 inches of soil are dry. Typically once per week, but check soil moisture first. Avoid overwatering as this causes root rot.</p>",
    "lighting": "<p>Bright, indirect light is essential. Place near a south or east-facing window with sheer curtains. Rotate weekly for even growth.</p>",
    "temperature": "60-75°F (15-24°C)",
    "humidity": "40-60% relative humidity",
    "fertilizing": "<p>Feed monthly during spring and summer with diluted liquid fertilizer (half strength). Reduce to every 6-8 weeks in fall/winter.</p>",
    "special_notes": "<p><strong>Common Issues:</strong> Brown spots indicate overwatering or inconsistent watering. Drooping leaves suggest underwatering. Dust leaves monthly to maximize photosynthesis.</p>"
  },
  "id": "stu901"
}
```

**Template Rendering** (`blog/blocks/care_instructions.html`):
```html
<div class="care-instructions">
    <h3>{{ value.care_title }}</h3>

    <div class="care-section">
        <h4>💧 Watering</h4>
        {{ value.watering|safe }}
    </div>

    <div class="care-section">
        <h4>☀️ Lighting</h4>
        {{ value.lighting|safe }}
    </div>

    {% if value.temperature %}
    <div class="care-section">
        <h4>🌡️ Temperature</h4>
        <p>{{ value.temperature }}</p>
    </div>
    {% endif %}

    {% if value.humidity %}
    <div class="care-section">
        <h4>💨 Humidity</h4>
        <p>{{ value.humidity }}</p>
    </div>
    {% endif %}

    {% if value.fertilizing %}
    <div class="care-section">
        <h4>🌱 Fertilizing</h4>
        {{ value.fertilizing|safe }}
    </div>
    {% endif %}

    {% if value.special_notes %}
    <div class="care-section special-notes">
        <h4>⚠️ Special Notes</h4>
        {{ value.special_notes|safe }}
    </div>
    {% endif %}
</div>
```

**Use Cases**:
- Complete care guides
- Troubleshooting sections
- Seasonal care calendars
- Beginner-friendly instructions

---

### 8. Gallery

**Purpose**: Display multiple images in a grid layout.

**Type**: `StructBlock`

**Fields**:
- `gallery_title` (string, optional): Gallery heading
- `images` (list of images, required): 2-12 images

**Constraints**:
- Minimum: 2 images
- Maximum: 12 images

**Template**: `blog/blocks/gallery.html`

**Admin UI**:
```
Icon: image (🖼️)
```

**Code Example**:
```python
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

gallery = blocks.StructBlock([
    ('gallery_title', blocks.CharBlock(required=False)),
    ('images', blocks.ListBlock(ImageChooserBlock(), min_num=2, max_num=12))
], icon="image", template="blog/blocks/gallery.html")
```

**API JSON**:
```json
{
  "type": "gallery",
  "value": {
    "gallery_title": "Propagation Progress",
    "images": [15, 16, 17, 18, 19, 20]
  },
  "id": "vwx234"
}
```

**Image API Response** (expanded):
```json
{
  "type": "gallery",
  "value": {
    "gallery_title": "Propagation Progress",
    "images": [
      {
        "id": 15,
        "title": "Week 1 - Cutting preparation",
        "thumbnail": {
          "url": "/media/images/prop-week1.fill-300x300.jpg",
          "width": 300,
          "height": 300
        }
      },
      {
        "id": 16,
        "title": "Week 2 - Root development",
        "thumbnail": {
          "url": "/media/images/prop-week2.fill-300x300.jpg",
          "width": 300,
          "height": 300
        }
      }
      // ... more images
    ]
  },
  "id": "vwx234"
}
```

**Template Rendering** (`blog/blocks/gallery.html`):
```html
{% load wagtailimages_tags %}

<div class="blog-gallery">
    {% if value.gallery_title %}
    <h3>{{ value.gallery_title }}</h3>
    {% endif %}
    <div class="gallery-grid">
        {% for image in value.images %}
        <div class="gallery-item">
            {% image image fill-400x400 %}
        </div>
        {% endfor %}
    </div>
</div>
```

**Frontend Recommendations**:
- Use lightbox library (e.g., PhotoSwipe, GLightbox)
- Lazy load images for performance
- Responsive grid (CSS Grid or Flexbox)

**Use Cases**:
- Time-lapse plant growth
- Before/after transformations
- Multiple plant varieties
- Garden tours

---

### 9. Call to Action

**Purpose**: Drive user engagement with prominent CTA buttons.

**Type**: `StructBlock`

**Fields**:
- `cta_title` (string, required): CTA headline
- `cta_description` (rich text, optional): Supporting text
- `button_text` (string, required): Button label
- `button_url` (URL, required): Link destination
- `button_style` (choice, required): Visual style (primary/secondary/outline)

**Button Styles**:
- `primary`: Main action (green, filled)
- `secondary`: Supporting action (gray, filled)
- `outline`: Subtle action (border only)

**Template**: `blog/blocks/call_to_action.html`

**Admin UI**:
```
Icon: link (🔗)
```

**Code Example**:
```python
from wagtail import blocks

call_to_action = blocks.StructBlock([
    ('cta_title', blocks.CharBlock()),
    ('cta_description', blocks.RichTextBlock(required=False)),
    ('button_text', blocks.CharBlock()),
    ('button_url', blocks.URLBlock()),
    ('button_style', blocks.ChoiceBlock(choices=[
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('outline', 'Outline'),
    ], default='primary'))
], icon="link", template="blog/blocks/call_to_action.html")
```

**API JSON**:
```json
{
  "type": "call_to_action",
  "value": {
    "cta_title": "Join Our Plant Parent Community",
    "cta_description": "<p>Get weekly care tips, exclusive guides, and connect with 10,000+ plant enthusiasts.</p>",
    "button_text": "Sign Up Free",
    "button_url": "https://example.com/signup",
    "button_style": "primary"
  },
  "id": "yza567"
}
```

**Template Rendering** (`blog/blocks/call_to_action.html`):
```html
<div class="blog-cta">
    <div class="cta-content">
        <h3>{{ value.cta_title }}</h3>
        {% if value.cta_description %}
        <div class="cta-description">
            {{ value.cta_description|safe }}
        </div>
        {% endif %}
    </div>
    <a href="{{ value.button_url }}" class="btn btn-{{ value.button_style }}">
        {{ value.button_text }}
    </a>
</div>
```

**Use Cases**:
- Newsletter signups
- Product recommendations
- Community invitations
- External resources
- Related content links

---

### 10. Video Embed

**Purpose**: Embed YouTube or Vimeo videos.

**Type**: `StructBlock`

**Fields**:
- `video_title` (string, optional): Video caption
- `video_url` (URL, required): YouTube or Vimeo URL
- `description` (rich text, optional): Context about the video

**Supported Platforms**:
- YouTube (youtube.com, youtu.be)
- Vimeo (vimeo.com)

**Template**: `blog/blocks/video_embed.html`

**Admin UI**:
```
Icon: media (🎬)
Help text: "YouTube or Vimeo URL"
```

**Code Example**:
```python
from wagtail import blocks

video_embed = blocks.StructBlock([
    ('video_title', blocks.CharBlock(required=False)),
    ('video_url', blocks.URLBlock(help_text="YouTube or Vimeo URL")),
    ('description', blocks.RichTextBlock(required=False))
], icon="media", template="blog/blocks/video_embed.html")
```

**API JSON**:
```json
{
  "type": "video_embed",
  "value": {
    "video_title": "How to Propagate Pothos in Water",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "description": "<p>Step-by-step tutorial showing the water propagation method. Perfect for beginners!</p>"
  },
  "id": "bcd890"
}
```

**Template Rendering** (`blog/blocks/video_embed.html`):
```html
<div class="blog-video">
    {% if value.video_title %}
    <h3>{{ value.video_title }}</h3>
    {% endif %}

    {% if value.description %}
    <div class="video-description">
        {{ value.description|safe }}
    </div>
    {% endif %}

    <div class="video-wrapper">
        {% include 'blog/includes/video_embed.html' with url=value.video_url %}
    </div>
</div>
```

**Frontend Implementation** (React example):
```javascript
import ReactPlayer from 'react-player';

function VideoBlock({ value }) {
  return (
    <div className="blog-video">
      {value.video_title && <h3>{value.video_title}</h3>}
      {value.description && (
        <div
          className="video-description"
          dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(value.description) }}
        />
      )}
      <div className="video-wrapper">
        <ReactPlayer
          url={value.video_url}
          controls
          width="100%"
        />
      </div>
    </div>
  );
}
```

**Use Cases**:
- Plant care tutorials
- Time-lapse growth videos
- Expert interviews
- Garden tours
- Product demonstrations

---

## Working with StreamField

### Adding Blocks in Wagtail Admin

1. Navigate to blog post edit page
2. Scroll to "Content blocks" field
3. Click "+ Add" button
4. Select block type from dropdown
5. Fill in block fields
6. Reorder blocks with drag handles
7. Delete blocks with trash icon

### API Consumption

**Fetch blog post with content blocks**:
```
GET /api/v2/blog-posts/123/
```

**Response structure**:
```json
{
  "id": 123,
  "title": "Succulent Care Guide",
  "content_blocks": [
    {
      "type": "heading",
      "value": "Introduction to Succulents",
      "id": "abc123"
    },
    {
      "type": "paragraph",
      "value": "<p>Succulents are...</p>",
      "id": "def456"
    },
    {
      "type": "plant_spotlight",
      "value": {
        "plant_name": "Echeveria",
        "scientific_name": "Echeveria elegans",
        "description": "<p>Beautiful rosette-forming...</p>",
        "care_difficulty": "easy",
        "image": 42
      },
      "id": "ghi789"
    }
  ]
}
```

### React/Flutter Rendering

**React Component Pattern**:
```javascript
import DOMPurify from 'dompurify';

function ContentBlocks({ blocks }) {
  return (
    <div className="content-blocks">
      {blocks.map((block) => {
        switch (block.type) {
          case 'heading':
            return <h2 key={block.id}>{block.value}</h2>;

          case 'paragraph':
            return (
              <div
                key={block.id}
                className="paragraph"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(block.value)
                }}
              />
            );

          case 'image':
            return (
              <figure key={block.id}>
                <img
                  src={block.value.medium.url}
                  alt={block.value.title}
                  width={block.value.medium.width}
                  height={block.value.medium.height}
                />
              </figure>
            );

          case 'plant_spotlight':
            return <PlantSpotlight key={block.id} data={block.value} />;

          // ... other block types

          default:
            console.warn(`Unknown block type: ${block.type}`);
            return null;
        }
      })}
    </div>
  );
}
```

**Flutter Widget Pattern**:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_html/flutter_html.dart';

class ContentBlocks extends StatelessWidget {
  final List<dynamic> blocks;

  const ContentBlocks({required this.blocks});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: blocks.map((block) {
        switch (block['type']) {
          case 'heading':
            return Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Text(
                block['value'],
                style: Theme.of(context).textTheme.headline5,
              ),
            );

          case 'paragraph':
            return Html(data: block['value']);

          case 'image':
            return Image.network(
              block['value']['medium']['url'],
              width: double.infinity,
            );

          case 'plant_spotlight':
            return PlantSpotlightCard(data: block['value']);

          default:
            return SizedBox.shrink();
        }
      }).toList(),
    );
  }
}
```

## Performance Considerations

### Database Queries

StreamField content is stored as JSON in a single field:
- **No extra queries**: All blocks loaded with post
- **Efficient serialization**: JSON format is API-ready
- **Index support**: PostgreSQL jsonb field with GIN indexes

### Caching Strategy

Blog post responses are cached for 24 hours:
```python
# Cache key includes content_blocks hash
cache_key = f"blog:post:{slug}:{content_hash}"
cached_data = cache.get(cache_key, timeout=86400)
```

**Cache invalidation** triggers:
- Post save
- Post publish/unpublish
- Post delete
- Related image update

### Image Optimization

Multiple rendition sizes generated:
- **Thumbnail**: 300x200 (list views)
- **Medium**: 800x600 (detail views)
- **Large**: 1200x800 (full-screen)
- **Social**: 1200x630 (Open Graph)

**Lazy loading** recommended:
```html
<img
  src="placeholder.jpg"
  data-src="actual-image.jpg"
  loading="lazy"
  alt="Plant photo"
>
```

## Security Notes

### HTML Sanitization

All rich text content MUST be sanitized on the frontend:

**React (DOMPurify)**:
```javascript
import DOMPurify from 'dompurify';

<div dangerouslySetInnerHTML={{
  __html: DOMPurify.sanitize(block.value)
}} />
```

**Flutter (flutter_html)**:
```dart
Html(
  data: block['value'],
  // Built-in XSS protection
)
```

### URL Validation

External URLs in CTA and video blocks are validated:
- Protocol check (http/https only)
- Domain allowlist for embedded content
- CSP headers for iframe protection

### Image Security

- File type validation (JPEG, PNG, WebP only)
- Size limits (10MB max upload)
- Automatic virus scanning (ClamAV integration)
- Signed URLs for private content

## Testing Block Rendering

### Unit Test Example

```python
from django.test import TestCase
from wagtail.models import Page
from apps.blog.models import BlogPostPage, BlogIndexPage

class BlogStreamBlocksTestCase(TestCase):
    def setUp(self):
        # Create blog index
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Blog", slug="blog")
        root.add_child(instance=self.blog_index)

    def test_heading_block_renders(self):
        """Test heading block appears in content_blocks."""
        blog_post = BlogPostPage(
            title="Test Post",
            slug="test-post",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>Test intro</p>",
            content_blocks=[
                {
                    'type': 'heading',
                    'value': 'Test Heading'
                }
            ]
        )
        self.blog_index.add_child(instance=blog_post)

        # Verify block structure
        self.assertEqual(len(blog_post.content_blocks), 1)
        self.assertEqual(blog_post.content_blocks[0].block_type, 'heading')
        self.assertEqual(blog_post.content_blocks[0].value, 'Test Heading')

    def test_plant_spotlight_block_structure(self):
        """Test plant spotlight block with all fields."""
        blog_post = BlogPostPage(
            title="Test Post",
            slug="test-post-2",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>Test intro</p>",
            content_blocks=[
                {
                    'type': 'plant_spotlight',
                    'value': {
                        'plant_name': 'Monstera',
                        'scientific_name': 'Monstera deliciosa',
                        'description': '<p>Popular houseplant</p>',
                        'care_difficulty': 'easy',
                        'image': None
                    }
                }
            ]
        )
        self.blog_index.add_child(instance=blog_post)

        # Verify nested structure
        block = blog_post.content_blocks[0]
        self.assertEqual(block.block_type, 'plant_spotlight')
        self.assertEqual(block.value['plant_name'], 'Monstera')
        self.assertEqual(block.value['care_difficulty'], 'easy')
```

## Common Issues

### Issue: Images not appearing in API

**Cause**: ImageChooserBlock returns image ID, not serialized data

**Solution**: Use custom serializer with ImageRenditionField:
```python
from wagtail.images.api.fields import ImageRenditionField

# In serializer
image_field = ImageRenditionField('fill-800x600', source='featured_image')
```

### Issue: Rich text showing HTML tags

**Cause**: Not using `|safe` filter or sanitization

**Solution**:
- **Template**: `{{ value|safe }}`
- **React**: `dangerouslySetInnerHTML` with DOMPurify
- **Flutter**: Use `flutter_html` package

### Issue: Block IDs changing on save

**Cause**: Wagtail generates new UUIDs if not provided

**Solution**: Include `id` field when creating blocks programmatically:
```python
import uuid

content_blocks = [
    {
        'type': 'heading',
        'value': 'My Heading',
        'id': str(uuid.uuid4())  # Stable ID
    }
]
```

## Best Practices

### Content Organization

1. **Start with heading**: Structure content with clear sections
2. **Alternate media**: Mix text, images, and videos for engagement
3. **Limit nesting**: Keep blocks flat for easier API consumption
4. **Use plant blocks**: Leverage auto-population for accuracy

### Performance

1. **Lazy load images**: Use `loading="lazy"` attribute
2. **Optimize videos**: Use external platforms (YouTube/Vimeo)
3. **Cache aggressively**: 24-hour TTL for blog posts
4. **Prefetch relations**: Use `select_related()` in queries

### Accessibility

1. **Alt text**: Always provide for images (AI-assisted)
2. **Heading hierarchy**: Use semantic heading levels
3. **Descriptive links**: Avoid "click here" in CTAs
4. **Video captions**: Include transcripts when possible

### SEO

1. **Structured data**: Use Schema.org Article markup
2. **Open Graph**: Set `social_image` for sharing
3. **Meta descriptions**: Auto-generated from introduction
4. **Readable URLs**: Use descriptive slugs

## Future Enhancements

**Planned block types** (Phase 5):
- `table`: Data tables with CSV import
- `comparison`: Side-by-side plant comparisons
- `checklist`: Interactive task lists
- `timeline`: Growth timeline visualization
- `map`: Plant hardiness zone maps

**AI Features** (Phase 6):
- Real-time content suggestions as you type
- Automatic image alt text generation
- Smart content recommendations based on topic
- Auto-linking to related plant species
- Grammar and readability analysis

## Related Documentation

- [API Reference](./API_REFERENCE.md) - Complete API endpoint documentation
- [Admin Guide](./ADMIN_GUIDE.md) - Content editor instructions
- [Performance Guide](../performance/week2-performance.md) - Optimization strategies
- [Security Patterns](../../SECURITY_PATTERNS_CODIFIED.md) - Security best practices
