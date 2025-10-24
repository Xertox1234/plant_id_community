# Blog Admin Guide for Content Editors

Complete guide for creating and managing blog content in the Plant Community Wagtail CMS.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Creating Blog Posts](#creating-blog-posts)
3. [Using Content Blocks](#using-content-blocks)
4. [Working with Images](#working-with-images)
5. [Managing Categories & Series](#managing-categories--series)
6. [Publishing Workflow](#publishing-workflow)
7. [SEO & Social Media](#seo--social-media)
8. [Preview & Testing](#preview--testing)
9. [Common Tasks](#common-tasks)
10. [Tips & Best Practices](#tips--best-practices)

---

## Getting Started

### Accessing the Admin

1. Navigate to: `http://localhost:8000/cms/` (or your production URL)
2. Log in with your Wagtail credentials
3. You'll see the Wagtail admin dashboard

**Important**: The Wagtail CMS admin is at `/cms/`, NOT `/admin/` (which is the Django admin).

### Admin Dashboard Overview

The dashboard shows:
- **Pages**: Your main navigation for blog content
- **Images**: Media library for all images
- **Documents**: File uploads (PDFs, etc.)
- **Snippets**: Reusable content (categories, series)
- **Reports**: Content analytics
- **Settings**: Site configuration

### Your First Blog Post

Quick start:
1. Click **Pages** in the sidebar
2. Navigate to **Blog** (BlogIndexPage)
3. Click **+ Add child page**
4. Select **Blog Post**
5. Fill in the title and introduction
6. Add content blocks
7. Click **Save draft** or **Publish**

---

## Creating Blog Posts

### Basic Information

**Required Fields**:
- **Title**: Post headline (appears in URLs as slug)
- **Author**: Select from user dropdown
- **Publish Date**: When to make post live
- **Introduction**: Brief excerpt (150-300 characters)

**SEO Fields** (expand "SEO Settings"):
- **Meta Description**: Search engine description (160 chars max)
- **Social Image**: Image for social media shares (1200x630px recommended)

### Slug (URL)

The slug is auto-generated from your title:
- Title: "How to Care for Succulents"
- Slug: `how-to-care-for-succulents`

**Editing the slug**:
1. Click "Promote" tab at top
2. Edit "Slug" field
3. Use lowercase, hyphens only (no spaces or special characters)

### Categorization

**Categories** (select multiple):
- Plant Care
- Gardening Tips
- Plant Identification
- Indoor Plants
- Outdoor Plants
- DIY Projects

**Tags** (add custom):
- Type tag name and press Enter
- Examples: "succulents", "beginners", "watering-guide"
- Tags help with search and related posts

**Series** (optional):
- Group related posts (e.g., "Succulent Care Series")
- Set **Series Order** (1, 2, 3, etc.)
- Useful for multi-part guides

### Display Settings

**Featured Image**:
1. Click "Choose an image" button
2. Upload new image OR select from library
3. Image appears on blog index and social shares

**Is Featured**:
- Check this box to highlight post on homepage
- Limit to 3-5 featured posts at a time

**Difficulty Level**:
- Beginner: First-time plant parents
- Intermediate: Some experience required
- Advanced: Expert-level content

**Allow Comments**:
- Checked by default
- Uncheck for announcement-style posts

### Plant-Specific Features

**Related Plant Species**:
1. Click "Choose plant species"
2. Search by common or scientific name
3. Select relevant plants mentioned in post
4. Used for linking to plant database

---

## Using Content Blocks

Content blocks are the heart of your blog post. Think of them as Lego blocks you arrange to build your article.

### Adding a Block

1. Scroll to **Content Blocks** field
2. Click **+ Add** button (blue button at bottom)
3. Select block type from dropdown
4. Fill in block fields
5. Repeat to add more blocks

### Reordering Blocks

- Hover over block header
- Drag the **six-dot handle** (⋮⋮) up or down
- Drop in new position

### Deleting a Block

- Click **trash icon** (🗑️) in block header
- Confirm deletion

### Block Type Guide

#### 1. Heading

**When to use**: Section titles, chapter breaks

**How to fill**:
- Enter heading text (e.g., "Watering Requirements")
- Renders as `<h2>` in frontend

**Tips**:
- Use descriptive headings for SEO
- Keep under 60 characters
- Use sentence case ("How to water", not "How To Water")

---

#### 2. Paragraph

**When to use**: Main article content, explanations

**How to fill**:
- Use rich text editor with formatting toolbar
- Bold: Select text, click **B** button
- Italic: Select text, click **I** button
- Links: Select text, click **link icon**, enter URL
- Lists: Click bullet or numbered list button

**Tips**:
- Keep paragraphs under 3-4 sentences
- Use short sentences for readability
- Link to related content naturally

---

#### 3. Image

**When to use**: Plant photos, process images, diagrams

**How to fill**:
1. Click **Choose an image**
2. Upload new OR select from library
3. Image automatically gets alt text (AI-generated)

**Image Requirements**:
- Format: JPEG, PNG, or WebP
- Max size: 10MB
- Recommended: 1200px wide minimum
- Orientation: Landscape or square preferred

**Tips**:
- Use high-quality, well-lit photos
- Show plants from multiple angles
- Include scale (coins, hands) for size reference

---

#### 4. Quote

**When to use**: Expert testimonials, wisdom, user stories

**How to fill**:
- **Quote Text**: The actual quote (can use formatting)
- **Attribution**: Who said it (optional)

**Example**:
```
Quote: "The glory of gardening: hands in the dirt, head in the sun, heart with nature."
Attribution: "Alfred Austin"
```

**Tips**:
- Use quotes sparingly (1-2 per post)
- Verify attribution accuracy
- Use for credibility or inspiration

---

#### 5. Code

**When to use**: Scripts, configurations, data examples

**How to fill**:
- **Language**: Select from dropdown (Python, JavaScript, etc.)
- **Code**: Paste your code snippet

**Example**:
```python
def water_plant(plant, amount):
    if plant.soil_moisture < 30:
        plant.add_water(amount)
        return True
    return False
```

**Tips**:
- Keep snippets short (< 30 lines)
- Include comments for clarity
- Test code before publishing

---

#### 6. Plant Spotlight ⭐

**When to use**: Featured plant profiles, species highlights

**Magic Feature**: Auto-populates data from plant database!

**How to fill**:
1. **Plant Name**: Type common name (e.g., "Monstera")
2. Wait 2-3 seconds - fields auto-fill!
   - Scientific name appears
   - Description generated
   - Care difficulty calculated
3. **Image**: Select suggested plant photo (or upload new)

**What Gets Auto-Populated**:
- Scientific name from database
- Plant family and characteristics
- Care difficulty (based on water/light needs)
- Description (from PlantNet/Plant.id data)

**Manual Override**:
- Edit any auto-filled field
- Your edits won't be overwritten
- Useful for adding personal experience

**Example**:
```
Plant Name: Fiddle Leaf Fig
Scientific Name: Ficus lyrata (auto-filled)
Description: [AI-generated description about large leaves, bright light needs]
Care Difficulty: Moderate (auto-calculated)
Image: [Suggested from library]
```

**Tips**:
- Use official common names for best auto-fill results
- Verify AI-generated descriptions for accuracy
- Add personal anecdotes to make it unique

---

#### 7. Care Instructions ⭐

**When to use**: Detailed plant care guides

**Magic Feature**: Auto-populates comprehensive care data!

**How to fill**:
1. **Care Title**: Enter plant name (e.g., "Fiddle Leaf Fig Care Guide")
2. Wait 2-3 seconds - all care fields auto-fill!
   - Watering schedule
   - Light requirements
   - Temperature range
   - Humidity preferences
   - Fertilizing schedule
   - Special notes

**What Gets Auto-Populated**:
- **Watering**: Frequency, amount, soil moisture checks
- **Lighting**: Sunlight needs, window placement, rotation tips
- **Temperature**: Ideal range, USDA hardiness zones
- **Humidity**: Percentage range, misting recommendations
- **Fertilizing**: Schedule, type, dilution ratio
- **Special Notes**: Common issues, seasonal care, toxicity warnings

**Manual Override**:
- All fields are editable
- Add your personal experience
- Include regional variations

**Example**:
```
Care Title: Snake Plant Care Guide

Watering: (auto-filled)
"Water every 2-3 weeks, allowing soil to dry completely between waterings.
Overwatering causes root rot - when in doubt, skip a watering."

Lighting: (auto-filled)
"Tolerates low light but thrives in indirect bright light. Avoid direct sun
which can scorch leaves. Rotate monthly for even growth."

Temperature: 60-80°F (15-27°C) (auto-filled)
Humidity: 30-50% - tolerates dry air (auto-filled)

Fertilizing: (auto-filled)
"Feed every 2-3 months during spring/summer with diluted liquid fertilizer
(half strength). No feeding in fall/winter."

Special Notes: (AI-generated)
"Common Issues: Brown tips indicate overwatering or fluoride in tap water.
Use filtered or rainwater if possible. Rarely needs repotting - only when
pot is visibly cracking from root pressure."
```

**Tips**:
- Verify auto-filled data matches your experience
- Add regional climate considerations
- Include troubleshooting for common problems
- Mention plant toxicity if applicable

---

#### 8. Gallery

**When to use**: Multiple related images, before/after, time-lapse

**How to fill**:
- **Gallery Title**: Optional heading (e.g., "Propagation Progress")
- **Images**: Add 2-12 images
  1. Click **+ Add** under Images
  2. Choose image
  3. Repeat for each image
  4. Reorder with drag handles

**Requirements**:
- Minimum: 2 images
- Maximum: 12 images

**Example**:
```
Gallery Title: "Pothos Propagation Timeline"
Images:
1. Week 1 - Cutting preparation
2. Week 2 - Root development
3. Week 4 - Transplanting to soil
4. Week 8 - Established plant
```

**Tips**:
- Use consistent image sizes/orientation
- Tell a visual story (progression, comparison)
- Limit to 6-8 images for mobile performance

---

#### 9. Call to Action

**When to use**: Newsletter signup, product links, community invites

**How to fill**:
- **CTA Title**: Attention-grabbing headline
- **CTA Description**: Supporting text (optional)
- **Button Text**: Action verb ("Join Now", "Download Guide")
- **Button URL**: Destination link
- **Button Style**:
  - Primary (green): Main action
  - Secondary (gray): Supporting action
  - Outline (border): Subtle action

**Example**:
```
CTA Title: "Join Our Plant Parent Community"
Description: "Get weekly care tips, exclusive guides, and connect with 10,000+ plant enthusiasts."
Button Text: "Sign Up Free"
Button URL: https://example.com/signup
Button Style: Primary
```

**Tips**:
- Use action-oriented language
- One CTA per post (max 2)
- Place after valuable content, not immediately
- Test links before publishing

---

#### 10. Video Embed

**When to use**: Tutorials, demonstrations, interviews

**How to fill**:
- **Video Title**: Optional caption
- **Video URL**: YouTube or Vimeo link
- **Description**: Context about the video

**Supported Platforms**:
- YouTube: `https://www.youtube.com/watch?v=VIDEO_ID`
- Vimeo: `https://vimeo.com/VIDEO_ID`

**Example**:
```
Video Title: "How to Propagate Pothos in Water"
Video URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Description: "Step-by-step tutorial showing the water propagation method. Perfect for beginners!"
```

**Tips**:
- Create your own videos or curate quality content
- Provide context in description
- Test video loads before publishing
- Consider adding transcript for accessibility

---

## Working with Images

### Uploading Images

**From Content Block**:
1. Click **Choose an image** in any image block
2. Click **Upload** tab
3. Drag image OR click **Choose file**
4. Image uploads to media library
5. Automatically selected for block

**From Media Library**:
1. Click **Images** in sidebar
2. Click **Add an image**
3. Upload image
4. Fill in title and tags
5. Click **Save**

### Image Best Practices

**File Naming**:
- Use descriptive names: `monstera-deliciosa-leaf.jpg`
- NOT generic: `IMG_1234.jpg`
- Lowercase, hyphens, no spaces

**Image Specifications**:
- **Resolution**: 1200px wide minimum (1920px ideal)
- **Format**: JPEG for photos, PNG for graphics with transparency
- **File Size**: Under 5MB (compress if needed)
- **Aspect Ratio**: 16:9 (landscape) or 1:1 (square) preferred

**Accessibility**:
- **Title**: Brief description (auto-filled from filename)
- **Alt Text**: Generated automatically by AI
- **Tags**: Add relevant keywords for search

### Organizing Images

**Using Tags**:
- Click image in library
- Scroll to "Tags" field
- Add tags: "succulents", "outdoor", "tutorial-images"
- Filter library by tag later

**Collections** (Advanced):
1. Create collection: **Settings** → **Collections**
2. Add new collection: "Blog Post Images"
3. When uploading, select collection
4. Permissions can be set per collection

### Image Editing

**Basic Edits**:
- Wagtail doesn't have built-in editing
- Edit images BEFORE uploading
- Use free tools: GIMP, Photopea, Canva

**Replacing Images**:
1. Find image in library
2. Click to open
3. Click **Replace file** button
4. Upload new image (same dimensions preferred)
5. All posts using this image update automatically

---

## Managing Categories & Series

### Blog Categories

**Viewing Categories**:
1. Click **Snippets** in sidebar
2. Select **Blog Categories**
3. See list of all categories

**Creating a Category**:
1. Click **Add Blog Category**
2. Fill in fields:
   - **Name**: Display name (e.g., "Plant Care")
   - **Slug**: URL-friendly (auto-generated)
   - **Description**: What this category covers
   - **Icon**: CSS class (optional, e.g., "fas fa-leaf")
   - **Color**: Hex code (e.g., "#28a745" for green)
   - **Is Featured**: Check to show on homepage
3. Click **Save**

**Editing Categories**:
- Click category name
- Edit fields
- Click **Save**
- Changes apply to all posts in category

**Tips**:
- Keep categories broad (5-10 total)
- Use tags for specific topics
- Featured categories appear on blog index

### Blog Series

**What is a Series?**
A series groups related posts (e.g., "Beginner Gardening", "Succulent Care 101")

**Creating a Series**:
1. **Snippets** → **Blog Series**
2. Click **Add Blog Series**
3. Fill in:
   - **Title**: Series name
   - **Slug**: URL-friendly name
   - **Description**: What series covers
   - **Image**: Series cover image
   - **Is Completed**: Check when series is finished
4. Click **Save**

**Adding Posts to Series**:
1. Edit blog post
2. Scroll to "Categorization" section
3. Select series from dropdown
4. Set **Series Order** (1, 2, 3, etc.)
5. Save post

**Example**:
```
Series: "Succulent Care for Beginners"
Posts:
1. "Introduction to Succulents" (Series Order: 1)
2. "Choosing Your First Succulent" (Series Order: 2)
3. "Watering Schedules for Succulents" (Series Order: 3)
4. "Common Succulent Problems" (Series Order: 4)
```

**Tips**:
- Plan series outline before writing
- Publish posts in order
- Link between series posts
- Mark completed when done

---

## Publishing Workflow

### Save vs. Publish

**Save Draft**:
- Saves changes without publishing
- Post not visible to public
- You can continue editing later
- Status shows "Draft" in pages list

**Publish**:
- Makes post live immediately
- Visible to all visitors
- Can still edit after publishing
- Status shows "Live" with green dot

**Schedule Publishing**:
1. Set **Publish Date** to future date
2. Click **Publish**
3. Post goes live on that date automatically
4. Status shows "Scheduled"

### Revision History

Every save creates a revision:
1. Click post in pages list
2. Click **History** button (top right)
3. See all past versions
4. Click revision to preview
5. Click **Revert to this revision** if needed

**Use Cases**:
- Recover deleted content
- Compare versions
- Undo unwanted changes
- Review who made edits

### Unpublishing

**Temporary Removal**:
1. Edit post
2. Click **Unpublish** button (top right)
3. Confirm action
4. Post becomes draft (not deleted)

**Deleting Post**:
1. Edit post
2. Click **Delete** button (top right)
3. **Warning**: This is permanent!
4. Confirm deletion

---

## SEO & Social Media

### Meta Description

**What it is**: Text that appears in Google search results

**Best Practices**:
- 150-160 characters max
- Include main keyword
- Describe post value
- Call to action

**Example**:
```
Title: "How to Care for Fiddle Leaf Figs"
Meta Description: "Learn the exact watering, lighting, and fertilizing schedule for thriving fiddle leaf figs. Includes troubleshooting for common problems like brown spots and drooping leaves."
```

### Social Sharing Image

**What it is**: Image shown when post is shared on Facebook, Twitter, LinkedIn

**Specifications**:
- Size: 1200x630 pixels (exact)
- Format: JPEG or PNG
- File size: Under 5MB
- Content: Clear, readable text/image

**Creating Social Images**:
1. Use Canva (free templates)
2. Include post title
3. Add plant photo
4. Your logo/branding
5. Export as 1200x630px

**Setting Social Image**:
1. Edit post
2. Expand "SEO Settings"
3. **Social Image** → Choose image
4. Save post

**Testing**:
- Facebook: Use [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/)
- Twitter: Use [Twitter Card Validator](https://cards-dev.twitter.com/validator)

### URL Structure

Your post URLs follow this pattern:
```
https://plantcommunity.com/blog/how-to-care-for-succulents/
```

**URL Best Practices**:
- Keep slugs short (3-5 words)
- Include primary keyword
- Use hyphens, not underscores
- Lowercase only
- Avoid dates in URL

**Editing Slugs**:
1. Click "Promote" tab
2. Edit "Slug" field
3. Save post
4. **Warning**: Changing published slugs breaks existing links!

### Sitemap

Wagtail automatically generates XML sitemap:
- URL: `https://yoursite.com/sitemap.xml`
- Updates automatically when you publish
- Submit to Google Search Console

---

## Preview & Testing

### Live Preview

**Desktop Preview**:
1. Click **Live preview** button (top right)
2. See real-time rendering
3. Make edits in admin
4. Preview updates automatically

**Mobile Preview**:
1. Click dropdown next to "Live preview"
2. Select **Mobile (Flutter)**
3. See mobile app rendering
4. Test responsive layout

### Headless Preview

For React/Flutter frontends:
1. Save draft (don't need to publish)
2. Click **Preview** button
3. Opens preview URL with token
4. Frontend fetches draft content
5. Test before publishing

**Preview URL Format**:
```
http://localhost:5173/blog/preview/blog.blogpostpage/TOKEN123/
```

### Testing Checklist

Before publishing, verify:
- [ ] Title is compelling and accurate
- [ ] Introduction summarizes post value
- [ ] All images load and have alt text
- [ ] Links work (no 404s)
- [ ] Content blocks render correctly
- [ ] Grammar and spelling checked
- [ ] Categories and tags set
- [ ] Meta description filled in
- [ ] Social image uploaded
- [ ] Preview looks good on mobile
- [ ] Author and date are correct

---

## Common Tasks

### Updating an Existing Post

1. **Pages** → **Blog** → Find post
2. Click post title
3. Click **Edit** button
4. Make changes
5. Click **Publish** (creates new revision)

**Note**: Changes are live immediately. Use "Save draft" to stage changes.

### Copying a Post

1. Edit post you want to copy
2. Click **More** → **Copy** (top right)
3. Choose destination (usually same parent)
4. New draft created with "Copy of" prefix
5. Edit title and content
6. Publish when ready

### Moving a Post

1. **Pages** view → Find post
2. Drag post to new location in tree
3. OR: Edit post → **More** → **Move**
4. Select new parent page
5. Confirm move

**Use Cases**:
- Reorganizing blog structure
- Moving to different blog index
- Archiving old posts

### Searching Posts

**Admin Search**:
1. Click search icon (top right)
2. Type post title or keywords
3. Filter by type: "Blog Post"
4. Click result to edit

**Advanced Search**:
1. **Pages** → **Blog**
2. Use filters (sidebar):
   - Status: Live, Draft, Scheduled
   - Author
   - Date range

### Bulk Actions

**Publishing Multiple Posts**:
1. **Pages** → **Blog**
2. Check boxes next to posts
3. Actions dropdown → **Publish**
4. Confirm bulk publish

**Available Bulk Actions**:
- Publish
- Unpublish
- Delete
- Move to another page

---

## Tips & Best Practices

### Writing Great Content

**Structure**:
1. Start with compelling introduction
2. Use headings to break up content
3. Include images every 2-3 paragraphs
4. End with summary or call-to-action

**Readability**:
- Short paragraphs (3-4 sentences)
- Simple language (avoid jargon)
- Active voice ("Water the plant" not "The plant should be watered")
- Scannable (headings, lists, bold text)

**Engagement**:
- Tell stories (your plant journey, failures, successes)
- Use second person ("you", "your")
- Ask questions
- Include practical takeaways

### Content Planning

**Editorial Calendar**:
1. Plan 1-2 months ahead
2. Schedule posts for consistent cadence
3. Mix content types (how-tos, profiles, Q&A)
4. Align with seasons (spring planting, winter care)

**Post Ideas**:
- Beginner's guides
- Plant profiles
- Seasonal care tips
- Troubleshooting common problems
- Reader Q&A
- Expert interviews
- DIY projects

### Image Strategy

**Photography Tips**:
- Natural light (near window, avoid direct sun)
- Plain background (white wall, neutral surface)
- Multiple angles (top, side, close-up)
- Show scale (use common objects)
- Clean subject (wipe leaves, remove dead foliage)

**Stock Photos**:
- Use only when you don't have original
- Choose realistic images (not overly edited)
- Verify license allows commercial use
- Credit photographer if required

### Collaboration

**Multiple Authors**:
- Assign correct author to each post
- Use comments for internal notes
- Review drafts before publishing
- Maintain consistent voice

**Workflow**:
1. Writer creates draft
2. Editor reviews and comments
3. Writer revises
4. Editor approves and publishes
5. Monitor comments and engagement

### Performance

**Optimize Images**:
- Compress before upload (TinyPNG, ImageOptim)
- Resize to max needed size (1920px wide)
- Use JPEG for photos (smaller file size)

**Content Length**:
- Aim for 800-1500 words for how-to guides
- 500-800 words for plant profiles
- Quality over quantity (comprehensive beats long)

**Loading Speed**:
- Limit to 8-10 images per post
- Use galleries for multiple images
- Embed videos (don't upload large video files)

### Analytics

**Track Performance**:
1. **Reports** → **Page views**
2. See most popular posts
3. Identify top traffic sources
4. Adjust content strategy

**Metrics to Monitor**:
- Page views (popularity)
- Time on page (engagement)
- Bounce rate (content quality)
- Comments (community engagement)

---

## Troubleshooting

### "Page Not Found" After Publishing

**Cause**: Cache not cleared or URL changed

**Fix**:
1. Hard refresh browser (Cmd+Shift+R / Ctrl+Shift+R)
2. Clear site cache (ask developer)
3. Verify post status is "Live"
4. Check publish date isn't in future

### Images Not Showing

**Cause**: File too large, wrong format, or permissions

**Fix**:
1. Verify image uploaded successfully
2. Check file size (under 10MB)
3. Use JPEG, PNG, or WebP only
4. Try uploading different image
5. Clear browser cache

### Auto-Fill Not Working (Plant Spotlight/Care)

**Cause**: Plant not in database or slow connection

**Fix**:
1. Wait 5-10 seconds after entering plant name
2. Try scientific name instead
3. Check internet connection
4. Manually fill fields if no data available
5. Report issue to developer

### Can't Publish Post

**Cause**: Missing required fields or permissions

**Fix**:
1. Verify all required fields filled:
   - Title
   - Author
   - Publish date
   - Introduction
   - At least one content block
2. Check you have "Publish" permission
3. Try "Save draft" first, then "Publish"

### Preview Not Loading

**Cause**: Frontend server not running or CORS issue

**Fix**:
1. Verify frontend is running (http://localhost:5173)
2. Check browser console for errors
3. Try different browser
4. Contact developer if persists

---

## Keyboard Shortcuts

**Editing**:
- `Cmd/Ctrl + S`: Save draft
- `Cmd/Ctrl + Enter`: Publish
- `Cmd/Ctrl + Z`: Undo
- `Cmd/Ctrl + Y`: Redo

**Navigation**:
- `Cmd/Ctrl + K`: Search
- `Esc`: Close modals
- `Tab`: Navigate fields

**Rich Text Editor**:
- `Cmd/Ctrl + B`: Bold
- `Cmd/Ctrl + I`: Italic
- `Cmd/Ctrl + K`: Insert link
- `Cmd/Ctrl + Shift + 7`: Bulleted list
- `Cmd/Ctrl + Shift + 8`: Numbered list

---

## Getting Help

**Documentation**:
- [StreamField Blocks Reference](./STREAMFIELD_BLOCKS.md) - Complete block documentation
- [API Reference](./API_REFERENCE.md) - For developers
- [Wagtail Docs](https://docs.wagtail.org) - Official Wagtail documentation

**Support**:
- Ask your team's content lead
- Developer team for technical issues
- Wagtail community Slack for general questions

**Feedback**:
- Report bugs or suggest features to your development team
- Include screenshots and steps to reproduce issues

---

## Appendix: Content Templates

### Plant Care Guide Template

```
Title: [Plant Name] Care Guide

Introduction:
Brief overview of the plant, why it's popular, difficulty level

Content Blocks:
1. Heading: "About [Plant Name]"
2. Plant Spotlight: [Auto-filled plant data]
3. Heading: "Care Requirements"
4. Care Instructions: [Auto-filled care data]
5. Heading: "Common Problems"
6. Paragraph: Troubleshooting issues
7. Image: Problem examples
8. Heading: "Propagation"
9. Paragraph: How to propagate
10. Gallery: Propagation steps
11. CTA: "Join our plant care community"

Categories: Plant Care, [Plant Type]
Tags: care-guide, [specific plant tags]
Difficulty: [Beginner/Intermediate/Advanced]
```

### Seasonal Guide Template

```
Title: [Season] Plant Care Checklist

Introduction:
What changes in [season], key focus areas

Content Blocks:
1. Heading: "Why [Season] Care Matters"
2. Paragraph: Seasonal overview
3. Heading: "Watering Adjustments"
4. Paragraph: How to adjust watering
5. Heading: "Light & Temperature"
6. Paragraph: Seasonal light changes
7. Heading: "Fertilizing Schedule"
8. Paragraph: Feeding guidance
9. Image: Example setup
10. Heading: "Quick Checklist"
11. Paragraph: Bulleted task list
12. CTA: Download printable checklist

Categories: Gardening Tips, Seasonal Care
Tags: [season], checklist, [plant types]
```

### Problem-Solving Post Template

```
Title: How to Fix [Common Problem]

Introduction:
Describe the problem, how common it is, reader takeaways

Content Blocks:
1. Heading: "Identifying the Problem"
2. Paragraph: Symptoms and causes
3. Image: Example of problem
4. Heading: "Solution"
5. Paragraph: Step-by-step fix
6. Gallery: Solution process
7. Heading: "Prevention"
8. Paragraph: How to avoid in future
9. Quote: Expert tip
10. CTA: "Get more troubleshooting guides"

Categories: Plant Care, Troubleshooting
Tags: problems, [specific issue], beginner
```

---

**Last Updated**: October 24, 2025
**Version**: 1.0
**Maintained By**: Plant Community Content Team
