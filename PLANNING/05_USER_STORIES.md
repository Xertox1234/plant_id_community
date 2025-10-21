# User Stories - Plant ID Community

**Version**: 1.0  
**Last Updated**: October 21, 2025  
**Purpose**: Comprehensive user stories for mobile and web platforms to guide UI/UX design and development

---

## Table of Contents

1. [User Personas](#user-personas)
2. [Mobile App User Stories](#mobile-app-user-stories)
3. [Web App User Stories](#web-app-user-stories)
4. [Shared Features](#shared-features)
5. [Admin User Stories](#admin-user-stories)
6. [Story Mapping & Priorities](#story-mapping--priorities)

---

## User Personas

### Primary Personas

#### 1. **Sarah - The Beginner Plant Parent** 🌱
- **Age**: 28, Marketing Professional
- **Experience**: New to plants, just bought her first houseplants
- **Goals**: Keep plants alive, learn basic care, identify mystery plants
- **Frustrations**: Doesn't know plant names, unsure about watering/light needs
- **Tech Comfort**: High - smartphone native, uses social media daily
- **Primary Platform**: Mobile app

#### 2. **Marcus - The Plant Enthusiast** 🌿
- **Age**: 35, Landscape Designer
- **Experience**: 10+ years growing plants, extensive collection
- **Goals**: Identify rare species, connect with community, share knowledge
- **Frustrations**: Limited plant ID app accuracy, isolated hobby
- **Tech Comfort**: Moderate - prefers desktop for research and forums
- **Primary Platform**: Web app + Mobile app

#### 3. **Dr. Chen - The Expert** 🔬
- **Age**: 52, Botany Professor
- **Experience**: 25+ years professional experience
- **Goals**: Help community, share educational content, accurate IDs
- **Frustrations**: Poor forum quality, lack of scientific rigor
- **Tech Comfort**: Moderate - academic, prefers web interface
- **Primary Platform**: Web app

#### 4. **Emma - The Content Creator** 📸
- **Age**: 24, Social Media Influencer
- **Experience**: Growing indoor jungle, plant aesthetic focus
- **Goals**: Quick IDs for content, beautiful plant photos, trending topics
- **Frustrations**: Slow ID process, generic care advice
- **Tech Comfort**: Very High - early adopter, mobile-first
- **Primary Platform**: Mobile app

---

## Mobile App User Stories

### Epic 1: Onboarding & Authentication

#### Story 1.1: First-Time Launch Experience
**As a** new user  
**I want to** see a compelling splash screen and introduction  
**So that** I understand what the app does and feel motivated to use it

**Acceptance Criteria:**
- Splash screen displays for 2-3 seconds with animated logo
- Shows "Discover Nature's Secrets" tagline
- Auto-detects system dark/light mode preference
- Smooth transition to home/landing page

**UI Notes:**
- Green/emerald gradient background (from design system)
- Animated leaf icon rotation
- Progress indicator during load

---

#### Story 1.2: Landing Page Introduction
**As a** new user  
**I want to** see key features before signing up  
**So that** I can decide if the app meets my needs

**Acceptance Criteria:**
- Display 4 feature cards: Identification, Care Tips, Community, Tracking
- Each card has icon, title, and brief description
- "Get Started" CTA button prominently displayed
- Theme toggle accessible in header
- Can dismiss and go straight to camera (guest mode consideration for future)

**UI Notes:**
- Feature cards use accent colors (green, blue, purple, amber)
- Scrollable on small screens
- Centered, max-width layout

---

#### Story 1.3: Sign Up with Email
**As a** new user  
**I want to** create an account with my email  
**So that** I can save my plant identifications and participate in the community

**Acceptance Criteria:**
- Email input with validation (format check)
- Password input with strength indicator
- Password confirmation field
- Display name input (3-20 characters)
- Terms of service checkbox
- "Sign Up" button disabled until all valid
- Error messages display inline
- Success redirects to camera/home

**UI Notes:**
- Clean, minimal form design
- Green CTA button
- Link to login if account exists
- Show/hide password toggle

---

#### Story 1.4: Sign Up with Social Providers
**As a** new user  
**I want to** sign up with Google or Apple  
**So that** I can quickly create an account without remembering another password

**Acceptance Criteria:**
- "Continue with Google" button
- "Continue with Apple" button (iOS only)
- Social auth handles profile photo and display name
- Still requires username if not provided
- One-tap sign up on subsequent visits
- Proper error handling for cancelled auth

**UI Notes:**
- Social buttons follow platform guidelines
- Icons and brand colors
- Stacked or side-by-side layout

---

#### Story 1.5: Login
**As a** returning user  
**I want to** log into my account  
**So that** I can access my saved data and continue using the app

**Acceptance Criteria:**
- Email input
- Password input
- "Remember me" toggle
- "Forgot password" link
- Login button
- Social login options
- Biometric login option (after first login)
- Error messages for invalid credentials

**UI Notes:**
- Link to sign up
- Same design consistency as sign up

---

#### Story 1.6: Password Reset
**As a** user who forgot their password  
**I want to** reset it via email  
**So that** I can regain access to my account

**Acceptance Criteria:**
- Enter email address
- Receive password reset email
- Click link in email opens app/web
- Enter new password (with confirmation)
- Password strength indicator
- Success message and auto-login
- Link expires after 24 hours

---

### Epic 2: Plant Identification

#### Story 2.1: Camera Capture
**As a** user  
**I want to** take a photo of a plant with my phone camera  
**So that** I can identify it instantly

**Acceptance Criteria:**
- Camera viewfinder fills screen
- Tap to focus
- Pinch to zoom
- Flash toggle
- Grid overlay (optional)
- Capture button (large, green, centered bottom)
- Switch front/back camera (not needed for plants but good UX)
- Proper camera permissions handling
- Preview captured photo before submitting

**UI Notes:**
- Clean camera interface
- Minimal UI during capture
- Focus indicator animation
- Haptic feedback on capture

---

#### Story 2.2: Gallery Selection
**As a** user  
**I want to** select an existing photo from my gallery  
**So that** I can identify a plant from a photo I took earlier

**Acceptance Criteria:**
- Gallery button visible on camera screen
- Opens native photo picker
- Can browse all photos/albums
- Crop/zoom functionality
- "Use Photo" confirmation
- Proper photo library permissions
- Handles large images (compression)

**UI Notes:**
- Gallery icon button
- Thumbnail preview of recent photos below camera
- Grid of 4-6 recent captures for quick re-identification

---

#### Story 2.3: Image Processing & Upload
**As a** user  
**I want to** see upload progress  
**So that** I know my image is being analyzed

**Acceptance Criteria:**
- Progress indicator appears immediately
- Shows "Analyzing plant..." message
- Progress bar or spinner animation
- Estimated time display (if >3 seconds)
- Cancel option
- Error handling for network issues
- Retry option on failure
- Image compresses before upload (optimize size)

**UI Notes:**
- Full-screen overlay with animation
- Leaf icon animation during analysis
- Encouraging messages ("Finding a match...")

---

#### Story 2.4: View Identification Results
**As a** user  
**I want to** see detailed information about the identified plant  
**So that** I can learn about it and care for it properly

**Acceptance Criteria:**
- Display plant photo (user's image)
- Common name (prominent, large text)
- Scientific name (italicized, smaller)
- Confidence score (e.g., "95% match")
- Detailed description paragraph
- Native region/habitat
- Plant category (succulent, fern, flowering, etc.)
- "Save to Collection" button
- "Share" button
- Timestamp of identification

**UI Notes:**
- Hero image at top
- Scrollable content
- Green accents for primary actions
- Card-based layout

---

#### Story 2.5: View Care Instructions
**As a** user  
**I want to** see specific care requirements  
**So that** I can keep my plant healthy

**Acceptance Criteria:**
- Watering instructions (frequency, amount, indicators)
- Sunlight requirements (direct/indirect, hours, direction)
- Temperature range (min/max, tolerance)
- Humidity preferences
- Soil type recommendations
- Fertilizer schedule
- Growth rate and mature size
- Common issues and troubleshooting
- Icons for each care category

**UI Notes:**
- Icon + text layout
- Color-coded difficulty level
- Expandable sections for details
- "Add Care Reminder" button (future feature)

---

#### Story 2.6: View Alternative Matches
**As a** user  
**I want to** see other possible plant matches  
**So that** I can choose the correct one if the top result is wrong

**Acceptance Criteria:**
- Display top 3-5 alternative matches
- Each shows small thumbnail, name, and confidence %
- Tap to view full details
- Can switch primary identification
- "Report incorrect ID" option

**UI Notes:**
- Horizontal scrollable list
- Or vertical list after main result
- Clear visual hierarchy

---

#### Story 2.7: Disease/Problem Detection
**As a** user  
**I want to** identify plant diseases or problems  
**So that** I can treat my plant before it dies

**Acceptance Criteria:**
- Optional "Check for Problems" button
- Analyzes same image for disease/pests
- Shows detected issues with confidence
- Provides treatment recommendations
- Links to products or solutions
- Severity indicator (low/medium/high)
- Prevention tips

**UI Notes:**
- Separate section in results
- Red/warning colors for problems
- Green "healthy" indicator if no issues

---

### Epic 3: Plant Collection & History

#### Story 3.1: View My Collection
**As a** user  
**I want to** see all plants I've identified  
**So that** I can build and manage my personal plant library

**Acceptance Criteria:**
- Grid or list view toggle
- Display plant thumbnail image
- Common name
- Date identified
- Pull to refresh
- Infinite scroll / pagination
- Sort options (recent, alphabetical, category)
- Filter options (indoor/outdoor, difficulty, etc.)
- Empty state with encouraging message

**UI Notes:**
- Photo-first design
- Plant cards match design system
- Quick visual scanning

---

#### Story 3.2: View Plant Details from History
**As a** user  
**I want to** tap on a saved plant  
**So that** I can review its information again

**Acceptance Criteria:**
- Opens same results view as initial identification
- All original data preserved
- Can view care instructions
- Can re-share
- Can add notes (future)
- Can delete from collection

---

#### Story 3.3: Delete from Collection
**As a** user  
**I want to** remove plants from my collection  
**So that** I can keep only relevant plants

**Acceptance Criteria:**
- Swipe to delete (iOS style)
- Long-press menu with delete option
- Confirmation dialog
- Undo option (toast/snackbar)
- Bulk delete option (select multiple)

---

#### Story 3.4: Share Plant Identification
**As a** user  
**I want to** share a plant identification with friends  
**So that** I can show them what I found or ask for advice

**Acceptance Criteria:**
- Native share sheet
- Generates shareable card/image with:
  - Plant photo
  - Plant name
  - App branding
  - Optional link to app
- Text sharing option
- Save image to gallery option
- Share to social media platforms

**UI Notes:**
- Beautiful share card design
- Matches app branding

---

### Epic 4: Community Forum (Mobile - Basic)

#### Story 4.1: Browse Forum Topics
**As a** user  
**I want to** browse community discussions  
**So that** I can learn from others and find answers

**Acceptance Criteria:**
- List view of forum topics
- Display: user avatar, username, title, preview, category, timestamp
- Show reply count and like count
- Category filter chips (Care, Problems, Show & Tell, etc.)
- Sort options (recent, popular, unanswered)
- Pull to refresh
- Infinite scroll
- Search functionality (basic)

**UI Notes:**
- Card-based layout
- Purple accent for forum
- Verified badge for experts
- Category color coding

---

#### Story 4.2: View Forum Topic/Thread
**As a** user  
**I want to** read a full forum discussion  
**So that** I can get detailed information

**Acceptance Criteria:**
- Original post at top with full content
- User info (avatar, name, badge)
- Post images (if any)
- Tags/labels
- Like button with count
- Reply count
- Chronological replies below
- Nested replies (1 level max on mobile)
- "Scroll to bottom" button for long threads

**UI Notes:**
- Clean reading experience
- Proper text formatting
- Image galleries

---

#### Story 4.3: Create New Forum Topic
**As a** logged-in user  
**I want to** create a new forum post  
**So that** I can ask questions or share information

**Acceptance Criteria:**
- Title input (required, max 100 chars)
- Category selection (required)
- Content text area (required, markdown support)
- Add up to 3 images
- Add tags (optional)
- Preview option
- Save as draft
- Post button
- Character/image limit indicators

**UI Notes:**
- Simplified mobile form
- Image upload with preview
- Auto-save draft

---

#### Story 4.4: Reply to Forum Topic
**As a** logged-in user  
**I want to** reply to a discussion  
**So that** I can contribute to the conversation

**Acceptance Criteria:**
- Reply text area at bottom
- Markdown toolbar (bold, italic, link)
- Add one image
- Tag/mention users with @
- Preview option
- Submit button
- Reply appears immediately (optimistic UI)

**UI Notes:**
- Fixed bottom input (like messaging apps)
- Expands when tapped
- Image attachment button

---

#### Story 4.5: Like/React to Posts
**As a** user  
**I want to** like helpful posts  
**So that** I can show appreciation and help others find good content

**Acceptance Criteria:**
- Heart/like button on posts and replies
- Tap to like/unlike
- Like count updates in real-time
- Visual feedback (animation, color change)
- Can see who liked (tap count)

---

#### Story 4.6: Basic Forum Search
**As a** user  
**I want to** search forum discussions  
**So that** I can find specific topics or information

**Acceptance Criteria:**
- Search bar in forum header
- Search by keywords in title and content
- Results sorted by relevance
- Highlight search terms in results
- Recent searches saved
- Filter by category

---

### Epic 5: User Profile & Settings

#### Story 5.1: View My Profile
**As a** user  
**I want to** see my profile information  
**So that** I can review my presence in the app

**Acceptance Criteria:**
- Profile photo
- Display name
- Username
- Email address
- Member since date
- Statistics:
  - Plants identified count
  - Forum posts count
  - Likes received
  - Collection size
- Bio/about section
- Location (optional)

**UI Notes:**
- Hero section with photo
- Stats in grid layout
- Scrollable profile

---

#### Story 5.2: Edit Profile
**As a** user  
**I want to** update my profile information  
**So that** I can keep it current and accurate

**Acceptance Criteria:**
- Upload/change profile photo (camera or gallery)
- Edit display name
- Edit bio (max 200 chars)
- Edit location
- Change password link
- Save button
- Discard changes confirmation
- Image cropping/resizing
- Loading states during save

---

#### Story 5.3: App Settings - Theme
**As a** user  
**I want to** switch between light and dark mode  
**So that** I can use the app comfortably in different lighting

**Acceptance Criteria:**
- Theme toggle switch
- Options: Light, Dark, System (auto)
- Immediate theme change (no restart)
- Smooth transition animation
- Persists across sessions
- Icon changes (sun/moon)

**UI Notes:**
- Prominent in settings
- Visual preview of themes

---

#### Story 5.4: App Settings - Notifications
**As a** user  
**I want to** manage notification preferences  
**So that** I only receive relevant alerts

**Acceptance Criteria:**
- Master notifications toggle
- Individual toggles for:
  - Forum replies to my posts
  - Likes on my content
  - New messages (future)
  - Plant care reminders (future)
  - App updates
- Push notification permissions handling
- Email notification preferences

---

#### Story 5.5: App Settings - Privacy
**As a** user  
**I want to** control my privacy settings  
**So that** I can manage what information is shared

**Acceptance Criteria:**
- Profile visibility (public/private)
- Show/hide email address
- Allow others to see my collection
- Data sharing preferences
- View privacy policy
- View terms of service

---

#### Story 5.6: App Settings - About & Support
**As a** user  
**I want to** access app information and help  
**So that** I can learn more or get support

**Acceptance Criteria:**
- App version number
- "What's New" / Changelog
- Tutorial / Help Center link
- Contact support
- Rate the app
- Share the app
- Licenses and attributions

---

#### Story 5.7: Logout
**As a** user  
**I want to** log out of my account  
**So that** I can secure my data or switch accounts

**Acceptance Criteria:**
- Logout button in settings
- Confirmation dialog
- Clears session data
- Returns to login screen
- Option to stay logged in on device

---

### Epic 6: General Mobile UX

#### Story 6.1: Bottom Navigation
**As a** user  
**I want to** quickly navigate between main sections  
**So that** I can efficiently use the app

**Acceptance Criteria:**
- 4 tabs: Home, Identify (Camera), Forum, Settings
- Active state clearly visible (green accent)
- Icon + label for each tab
- Smooth transitions
- Persists selected tab
- Badge count for notifications (future)

---

#### Story 6.2: Pull to Refresh
**As a** user  
**I want to** refresh content by pulling down  
**So that** I can see the latest data

**Acceptance Criteria:**
- Works on: Collection, Forum, Profile
- Visual indicator during pull
- Loading spinner during refresh
- Success feedback
- Error handling

---

#### Story 6.3: Offline Handling
**As a** user  
**I want to** see helpful messages when offline  
**So that** I understand why features aren't working

**Acceptance Criteria:**
- Detect offline state
- Show offline banner/message
- Disable network-dependent features
- Cache previously loaded content
- Auto-retry when back online
- Helpful error messages

---

#### Story 6.4: Loading States
**As a** user  
**I want to** see appropriate loading indicators  
**So that** I know the app is working

**Acceptance Criteria:**
- Skeleton screens for lists
- Spinners for actions
- Progress bars for uploads
- Consistent loading animations
- No janky transitions

---

#### Story 6.5: Error Handling
**As a** user  
**I want to** see clear error messages  
**So that** I understand what went wrong and how to fix it

**Acceptance Criteria:**
- User-friendly error messages (not technical)
- Suggested actions to resolve
- Retry buttons where applicable
- Contact support option for persistent errors
- Toast/snackbar for minor errors
- Full-screen for critical errors

---

---

## Web App User Stories

### Epic 7: Web Authentication & Onboarding

#### Story 7.1: Web Landing Page
**As a** visitor  
**I want to** see what the Plant ID Community offers  
**So that** I can decide if I want to join

**Acceptance Criteria:**
- Hero section with compelling headline
- Feature overview with screenshots/illustrations
- "Sign Up" and "Login" CTAs
- Responsive design (desktop, tablet)
- Theme toggle
- Navigation menu
- Footer with links

**UI Notes:**
- Modern, clean design
- Green/emerald branding
- Mobile and desktop optimized

---

#### Story 7.2: Web Sign Up
**As a** new user  
**I want to** create an account on the web  
**So that** I can access the community and blog

**Acceptance Criteria:**
- Same fields as mobile (email, password, display name)
- Social login options
- Client-side validation
- Server-side validation
- reCAPTCHA to prevent bots
- Email verification sent
- Auto-login after verification
- Responsive form design

---

#### Story 7.3: Web Login
**As a** returning user  
**I want to** log into the web platform  
**So that** I can participate in the community

**Acceptance Criteria:**
- Email and password fields
- "Remember me" checkbox
- Social login options
- Forgot password link
- Keyboard navigation support
- Session management
- Redirect to previous page after login

---

### Epic 8: Blog (Web Only)

#### Story 8.1: Browse Blog Posts
**As a** visitor or user  
**I want to** read blog articles about plants  
**So that** I can learn about plant care and trends

**Acceptance Criteria:**
- Grid or list layout
- Featured post at top
- Post card shows:
  - Featured image
  - Title
  - Excerpt
  - Author
  - Date
  - Read time
  - Category tags
- Pagination or infinite scroll
- Category filter
- Search functionality
- Responsive grid (1-3 columns)

**UI Notes:**
- Image-heavy, magazine style
- Wagtail CMS-powered
- SEO optimized

---

#### Story 8.2: Read Blog Post
**As a** reader  
**I want to** read a full blog article  
**So that** I can learn in-depth information

**Acceptance Criteria:**
- Full article content (Wagtail StreamField)
- Hero image
- Title and subtitle
- Author bio and photo
- Published date and update date
- Estimated read time
- Table of contents for long articles
- Rich text formatting:
  - Headings
  - Paragraphs
  - Images with captions
  - Blockquotes
  - Lists
  - Code blocks (if needed)
  - Embedded videos
- Social share buttons
- "Related Posts" section
- Comments section (future)
- Print-friendly layout

**UI Notes:**
- Clean, readable typography
- Optimal line length (60-80 chars)
- Generous spacing
- Responsive images

---

#### Story 8.3: Search Blog
**As a** reader  
**I want to** search blog articles  
**So that** I can find specific information

**Acceptance Criteria:**
- Search bar in header
- Full-text search
- Search suggestions/autocomplete
- Results page with relevance sorting
- Filter by category and date
- Highlight search terms in results
- "No results" helpful message

---

#### Story 8.4: Filter Blog by Category
**As a** reader  
**I want to** view posts by category  
**So that** I can explore specific topics

**Acceptance Criteria:**
- Category navigation menu
- Category archive pages
- Show post count per category
- Breadcrumb navigation
- Category description
- Responsive category grid

---

#### Story 8.5: Subscribe to Blog (Future)
**As a** reader  
**I want to** subscribe to new posts  
**So that** I don't miss content

**Acceptance Criteria:**
- Email subscription form
- RSS feed
- Email confirmation (double opt-in)
- Manage subscription preferences
- Unsubscribe link in emails

---

### Epic 9: Forum (Web - Full Features)

#### Story 9.1: Browse Forum - Desktop Experience
**As a** user on desktop  
**I want to** browse forum topics with more information  
**So that** I can efficiently find discussions

**Acceptance Criteria:**
- Table or card layout (user preference)
- Columns: Title, Author, Category, Replies, Views, Last Activity
- Sticky header
- Category sidebar
- Advanced filters:
  - By category
  - By date range
  - By answered/unanswered
  - By tags
- Sort options (newest, most replies, most views, trending)
- Pinned/stickied topics at top
- Search with advanced operators
- Quick preview on hover

**UI Notes:**
- Dense information layout
- Purple accent
- Keyboard shortcuts
- Multi-column responsive layout

---

#### Story 9.2: Create Forum Topic - Rich Editor
**As a** user on web  
**I want to** create detailed forum posts  
**So that** I can thoroughly explain my question or share information

**Acceptance Criteria:**
- Rich text editor (Markdown or WYSIWYG)
- Formatting toolbar:
  - Bold, italic, underline
  - Headers (H2-H4)
  - Lists (ordered, unordered)
  - Links
  - Blockquotes
  - Code blocks
- Upload multiple images (drag & drop)
- Image captions
- Add YouTube videos (embed)
- Tag suggestions
- Category selection (required)
- Draft auto-save
- Preview mode
- Attach plant from collection (link)
- Character count
- Spam detection

**UI Notes:**
- Split-screen preview option
- Responsive editor
- Keyboard shortcuts
- Image optimization

---

#### Story 9.3: Reply with Rich Content
**As a** user  
**I want to** write detailed replies  
**So that** I can provide helpful answers

**Acceptance Criteria:**
- Same rich text editor as topic creation
- Quote original post or specific replies
- @mention users (autocomplete)
- Mark reply as "solution" (topic author or moderator)
- Upload images
- Edit reply (within time limit or anytime)
- Delete reply (own or moderator)
- Reply notifications

---

#### Story 9.4: Forum Search - Advanced
**As a** user  
**I want to** use advanced search  
**So that** I can find specific discussions

**Acceptance Criteria:**
- Search operators:
  - Exact phrase "quotes"
  - Exclude -word
  - User:username
  - Category:name
  - Tag:name
  - Date ranges
- Search in titles only option
- Search in replies option
- Regex support (power users)
- Save searches
- Search history

---

#### Story 9.5: User Profiles - Forum Stats
**As a** user  
**I want to** view other users' profiles  
**So that** I can see their expertise and contributions

**Acceptance Criteria:**
- Public profile page
- Stats:
  - Total posts/replies
  - Likes received
  - Solutions provided
  - Member since
  - Last active
  - Badges/achievements
- Recent posts list
- Best answers
- Reputation score (future)
- Follow user (future)
- Send private message (future)

---

#### Story 9.6: Moderation Tools (Moderator/Admin)
**As a** moderator  
**I want to** manage forum content  
**So that** I can maintain quality and safety

**Acceptance Criteria:**
- Pin/unpin topics
- Lock/unlock topics
- Move topics to different categories
- Merge duplicate topics
- Mark replies as solution
- Edit any post (with history)
- Delete posts (soft delete)
- Ban users (with reason)
- View reported content
- Moderator notes

---

#### Story 9.7: Forum Notifications
**As a** user  
**I want to** receive notifications for forum activity  
**So that** I stay engaged with discussions

**Acceptance Criteria:**
- Notification types:
  - Reply to my topic
  - Reply to my comment
  - @mention
  - Topic I'm watching
  - Likes on my content
- Notification center dropdown
- Mark as read/unread
- Mark all as read
- Email digest options
- Real-time with WebSockets (nice to have)

---

### Epic 10: Plant ID (Web - Upload Only)

#### Story 10.1: Upload Plant Image (Web)
**As a** web user  
**I want to** upload a plant photo  
**So that** I can identify it

**Acceptance Criteria:**
- Drag & drop upload area
- Click to browse files
- Paste image from clipboard
- File type validation (jpg, png, webp)
- File size limit (10MB)
- Image preview before upload
- Crop/rotate tools
- Multiple images at once (batch ID)
- Progress bar during upload
- Cancel upload option

**UI Notes:**
- Large, obvious upload area
- Visual feedback for drag & drop
- Responsive design

---

#### Story 10.2: View Identification Results (Web)
**As a** web user  
**I want to** see identification results on desktop  
**So that** I can learn about my plant with a better view

**Acceptance Criteria:**
- Two-column layout (image | info)
- Larger image display
- Same information as mobile
- Print-friendly layout
- Save to collection button
- Download result as PDF
- Copy plant information
- Share link

**UI Notes:**
- Take advantage of screen space
- High-quality image display
- Readable text columns

---

### Epic 11: User Dashboard (Web)

#### Story 11.1: Personal Dashboard
**As a** logged-in user  
**I want to** see a personalized dashboard  
**So that** I can quickly access my activity

**Acceptance Criteria:**
- Recent identifications (grid)
- Forum activity feed
- My recent posts
- Notifications summary
- Quick stats widgets
- Shortcuts to common actions
- Personalized content recommendations
- Responsive dashboard layout

**UI Notes:**
- Card-based layout
- Drag-to-rearrange (future)
- Customizable widgets

---

### Epic 12: Web Settings & Preferences

#### Story 12.1: Account Settings (Web)
**As a** user  
**I want to** manage my account on web  
**So that** I can control my information

**Acceptance Criteria:**
- Same settings as mobile, plus:
- Connected accounts (social logins)
- Active sessions (view and revoke)
- Download my data (GDPR)
- Delete account option
- Security settings
- Two-factor authentication setup
- Email preferences (detailed)

---

#### Story 12.2: Privacy Dashboard
**As a** user  
**I want to** control my privacy  
**So that** I comply with my preferences

**Acceptance Criteria:**
- Privacy settings overview
- Data sharing controls
- Cookie preferences
- Block/mute users
- Export data request
- Clear history options

---

### Epic 13: General Web UX

#### Story 13.1: Responsive Navigation
**As a** user on any device  
**I want to** easily navigate the web app  
**So that** I can find what I need

**Acceptance Criteria:**
- Desktop: horizontal nav with dropdowns
- Tablet: horizontal nav with icons
- Mobile: hamburger menu
- Search bar in header
- User menu dropdown
- Notifications bell icon
- Theme toggle
- Breadcrumb navigation
- Footer with sitemap

---

#### Story 13.2: Accessibility (WCAG AA)
**As a** user with disabilities  
**I want to** use the app with assistive tech  
**So that** I can access all features

**Acceptance Criteria:**
- Keyboard navigation support
- Screen reader compatible
- ARIA labels on interactive elements
- Focus indicators
- Color contrast ratios meet WCAG AA
- Skip to content link
- Alt text for images
- Semantic HTML
- Form labels properly associated
- Error messages programmatically associated

---

#### Story 13.3: Performance
**As a** user  
**I want to** experience fast load times  
**So that** I don't waste time waiting

**Acceptance Criteria:**
- First Contentful Paint < 1.5s
- Largest Contentful Paint < 2.5s
- Time to Interactive < 3.5s
- Code splitting for routes
- Lazy loading images
- Optimized assets (minified, compressed)
- CDN for static assets
- Caching strategies
- Progressive web app (future)

---

---

## Shared Features (Mobile & Web)

### Epic 14: Plant Care Reminders (Future Phase)

#### Story 14.1: Set Care Reminders
**As a** user  
**I want to** set reminders for plant care tasks  
**So that** I don't forget to water or fertilize

**Acceptance Criteria:**
- Add reminder to plant in collection
- Reminder types: Water, Fertilize, Prune, Repot, Mist
- Custom reminder frequency
- Custom reminder time
- Notification settings per reminder
- Multiple reminders per plant
- Snooze option
- Mark as done
- Reminder history/log

---

#### Story 14.2: Care Log/Journal (Future Phase)
**As a** user  
**I want to** log care activities  
**So that** I can track my plant's health

**Acceptance Criteria:**
- Add log entry for plant
- Entry types: Watered, Fertilized, Repotted, Note, Photo
- Date and time stamp
- Optional notes
- Attach photos
- View log timeline
- Edit/delete entries
- Export log

---

### Epic 15: Social Features (Future Phase)

#### Story 15.1: Follow Users
**As a** user  
**I want to** follow other plant enthusiasts  
**So that** I can see their content

**Acceptance Criteria:**
- Follow/unfollow button on profiles
- Following/followers count
- View following list
- View followers list
- Activity feed from followed users
- Notification on new follow

---

#### Story 15.2: Private Messaging
**As a** user  
**I want to** send direct messages  
**So that** I can have private conversations

**Acceptance Criteria:**
- Message inbox
- Compose new message
- Search users to message
- Message thread view
- Real-time delivery (WebSocket)
- Read receipts
- Typing indicators
- Push notifications
- Block users from messaging

---

#### Story 15.3: Plant Wishlist
**As a** user  
**I want to** save plants I want to acquire  
**So that** I can remember them

**Acceptance Criteria:**
- Add to wishlist from identification
- Wishlist view (separate from collection)
- Mark as acquired (moves to collection)
- Priority ranking
- Notes per plant
- Share wishlist

---

---

## Admin User Stories

### Epic 16: Content Management

#### Story 16.1: Blog Post Creation (Wagtail Admin)
**As an** admin/editor  
**I want to** create blog posts in Wagtail  
**So that** I can publish educational content

**Acceptance Criteria:**
- Wagtail admin interface
- StreamField with rich blocks:
  - Paragraph
  - Heading
  - Image (with caption)
  - Video embed
  - Quote
  - Code block
  - Gallery
  - Callout box
  - Accordion
- SEO fields (meta title, description, OG image)
- Categories and tags
- Featured image
- Author selection
- Publish date scheduling
- Draft/review/published workflow
- Revision history
- Preview before publish

---

#### Story 16.2: Forum Moderation
**As a** moderator  
**I want to** moderate forum content  
**So that** I can maintain community standards

**Acceptance Criteria:**
- Moderation dashboard
- Reported content queue
- Ban/suspend users
- Edit any post
- Delete content
- View user history
- Send warnings
- Lock threads
- Pin important topics
- Merge duplicate threads
- Moderation logs
- Moderator notes

---

#### Story 16.3: User Management
**As an** admin  
**I want to** manage user accounts  
**So that** I can handle support issues

**Acceptance Criteria:**
- User list with search/filter
- View user details
- Reset passwords
- Verify email manually
- Change user roles
- Ban/suspend accounts
- View user activity
- Merge duplicate accounts
- Delete accounts (GDPR)
- Export user data

---

#### Story 16.4: Analytics Dashboard
**As an** admin  
**I want to** view app analytics  
**So that** I can understand usage and growth

**Acceptance Criteria:**
- User metrics (new, active, retention)
- Identification metrics (count, success rate)
- Forum metrics (posts, replies, active users)
- Blog metrics (views, top posts)
- Most identified plants
- Search terms analysis
- Geographic distribution
- Device/platform breakdown
- Custom date ranges
- Export reports

---

#### Story 16.5: Plant ID API Management
**As an** admin  
**I want to** monitor Plant.id API usage  
**So that** I can manage costs and quality

**Acceptance Criteria:**
- API call count
- Success/failure rates
- Average response time
- Cost tracking
- Rate limit monitoring
- Error logs
- Quality feedback tracking
- Alternative API testing

---

---

## Story Mapping & Priorities

### MVP (Phase 1-2) - Core Features

**Mobile:**
- ✅ Authentication (sign up, login, password reset)
- ✅ Camera capture and gallery selection
- ✅ Plant identification with results
- ✅ View care instructions
- ✅ Collection/history
- ✅ Basic settings (profile, theme, logout)

**Web:**
- ✅ Authentication
- ✅ Blog browsing and reading
- ✅ Basic forum browsing and posting
- ✅ Image upload for identification

### Phase 3 - Enhanced Features

**Mobile:**
- Forum participation (create, reply, like)
- Rich profile management
- Share functionality
- Disease detection
- Notifications

**Web:**
- Advanced forum features (search, moderation)
- User profiles and stats
- Full forum editor
- Personal dashboard

### Phase 4 - Advanced Features

**Both:**
- Care reminders and logs
- Social features (follow, messages)
- Wishlist
- Advanced search
- Gamification (badges, levels)

### Future Considerations

- AR plant identification
- Plant swap marketplace
- Expert consultations (paid)
- Plant care courses
- Mobile app widget
- Offline mode
- Multi-language support
- Plant disease ML model training feedback

---

## Success Metrics

### User Engagement
- Daily Active Users (DAU)
- Monthly Active Users (MAU)
- Session duration
- Identifications per user
- Forum posts per user
- Return rate after first identification

### Content Quality
- Identification accuracy rate
- User satisfaction score
- Forum helpful replies ratio
- Blog read completion rate

### Community Health
- Forum post/reply ratio
- Average response time
- Active contributors count
- Moderation action rate

### Business Metrics
- New user sign-ups
- User retention (30, 60, 90 day)
- Conversion rate (visitor to user)
- App store ratings
- Plant.id API cost per identification

---

**Document Status**: ✅ Complete v1.0  
**Last Updated**: October 21, 2025  
**Next Steps**: Use these stories to guide database schema design and API documentation  
**Note**: Stories marked with (Future Phase) are not part of MVP but documented for completeness
