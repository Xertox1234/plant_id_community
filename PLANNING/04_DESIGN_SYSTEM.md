# Design System & UI Guidelines

## Overview

This document outlines the design system for the Plant ID Community project, based on the Figma design from the [Plantidentificationapp repository](https://github.com/Xertox1234/Plantidentificationapp).

---

## Design Source

**Figma Design Repository**: https://github.com/Xertox1234/Plantidentificationapp

**Key Features:**
- ✅ Dark mode support
- ✅ Light mode support
- ✅ Mobile-first design
- ✅ Consistent component library
- ✅ Modern, clean aesthetic

---

## Theme System

### Dual Theme Support

Both web (React + Tailwind) and mobile (Flutter) will support:
- **Light Mode**: Default theme
- **Dark Mode**: User-selectable alternative
- **System Preference**: Auto-detect and follow OS theme

### Theme Implementation

#### Web (Tailwind CSS 4)
```javascript
// tailwind.config.js
export default {
  darkMode: 'class', // or 'media' for system preference
  theme: {
    extend: {
      colors: {
        // Light mode colors
        background: {
          DEFAULT: '#FFFFFF',
          secondary: '#F5F5F5',
        },
        // Dark mode colors (to be extracted from Figma)
        dark: {
          background: '#1A1A1A',
          surface: '#2D2D2D',
        },
        // Brand colors (to be extracted from Figma)
        primary: {
          DEFAULT: '#4CAF50', // Example green for plants
          light: '#81C784',
          dark: '#388E3C',
        },
        // Accent colors
        accent: {
          DEFAULT: '#FF6B6B', // Example
        },
      },
    },
  },
}
```

#### Flutter (Riverpod + Theme Provider)
```dart
// lib/core/theme/theme_data.dart
class AppTheme {
  // Light theme
  static ThemeData lightTheme = ThemeData(
    brightness: Brightness.light,
    primaryColor: Color(0xFF4CAF50), // Example
    scaffoldBackgroundColor: Color(0xFFFFFFFF),
    // ... more theme properties from Figma
  );

  // Dark theme
  static ThemeData darkTheme = ThemeData(
    brightness: Brightness.dark,
    primaryColor: Color(0xFF4CAF50),
    scaffoldBackgroundColor: Color(0xFF1A1A1A),
    // ... more theme properties from Figma
  );
}
```

---

## Design Tokens

✅ **Extracted from Figma Design Repository**

### Colors

#### Brand Colors - Green Palette
The primary brand color representing nature and plant life:
- **green-50**: `oklch(0.982 0.018 155.826)` - Lightest tint
- **green-100**: `oklch(0.962 0.044 156.743)`
- **green-200**: `oklch(0.925 0.084 155.995)`
- **green-400**: `oklch(0.792 0.209 151.711)`
- **green-500**: `oklch(0.723 0.219 149.579)` - Base green
- **green-600**: `oklch(0.627 0.194 149.214)` - Primary CTA color
- **green-700**: `oklch(0.527 0.154 150.069)` - Dark mode primary
- **green-800**: `oklch(0.448 0.119 151.328)`
- **green-900**: `oklch(0.393 0.095 152.535)`
- **green-950**: `oklch(0.266 0.065 152.934)` - Darkest shade

#### Brand Colors - Emerald Palette
Complementary emerald tones for gradients and accents:
- **emerald-100**: `oklch(0.95 0.052 163.051)`
- **emerald-400**: `oklch(0.765 0.177 163.223)`
- **emerald-600**: `oklch(0.596 0.145 163.225)` - Gradient partner
- **emerald-700**: `oklch(0.508 0.118 165.612)`
- **emerald-800**: `oklch(0.432 0.095 166.913)`
- **emerald-900**: `oklch(0.378 0.077 168.94)`
- **emerald-950**: `oklch(0.262 0.051 172.552)`

#### Accent Colors
Additional colors for features and categories:
- **blue-500**: `oklch(0.623 0.214 259.815)` - Care instructions
- **blue-600**: `oklch(0.546 0.245 262.881)`
- **purple-500**: `oklch(0.627 0.265 303.9)` - Community features
- **purple-600**: `oklch(0.558 0.288 302.321)`
- **amber-500**: `oklch(0.769 0.188 70.08)` - Tracking/history
- **amber-600**: `oklch(0.666 0.179 58.318)`

#### Light Theme Colors
- **Background**: `#ffffff` (pure white)
- **Foreground**: `oklch(0.145 0 0)` (near black)
- **Card**: `#ffffff`
- **Primary**: `#030213` (dark blue-black)
- **Primary Foreground**: `oklch(1 0 0)` (white)
- **Secondary**: `oklch(0.95 0.0058 264.53)` (light gray-blue)
- **Muted**: `#ececf0` (light gray)
- **Muted Foreground**: `#717182` (mid gray)
- **Border**: `rgba(0, 0, 0, 0.1)` (10% black)
- **Input Background**: `#f3f3f5`
- **Destructive**: `#d4183d` (red)
- **Destructive Foreground**: `#ffffff`

#### Dark Theme Colors
- **Background**: `oklch(0.145 0 0)` (dark)
- **Foreground**: `oklch(0.985 0 0)` (near white)
- **Card**: `oklch(0.145 0 0)`
- **Primary**: `oklch(0.985 0 0)` (white)
- **Primary Foreground**: `oklch(0.205 0 0)` (dark)
- **Secondary**: `oklch(0.269 0 0)` (dark gray)
- **Muted**: `oklch(0.269 0 0)`
- **Muted Foreground**: `oklch(0.708 0 0)` (light gray)
- **Border**: `oklch(0.269 0 0)`
- **Input**: `oklch(0.269 0 0)`
- **Destructive**: `oklch(0.396 0.141 25.723)` (red)
- **Destructive Foreground**: `oklch(0.637 0.237 25.331)`

#### Gradients
Used throughout the app for visual interest:
- **Splash Background**: 
  - Light: `from-green-50 to-emerald-100`
  - Dark: `from-green-950 to-emerald-950`
- **Icon/Button Gradient**: `from-green-500 to-emerald-600`
- **Text Gradient**:
  - Light: `from-green-700 to-emerald-700`
  - Dark: `from-green-400 to-emerald-400`
- **Hero Background**:
  - Light: `from-green-100 to-emerald-100`
  - Dark: `from-green-900/30 to-emerald-900/30`

### Typography

✅ **Extracted from Figma Design**

#### Font Family
- **Primary (Sans)**: `ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'`
- **Monospace**: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace`

#### Font Sizes
- **xs**: `0.75rem` (12px)
- **sm**: `0.875rem` (14px)
- **base**: `1rem` (16px) - Body text
- **lg**: `1.125rem` (18px)
- **xl**: `1.25rem` (20px)
- **2xl**: `1.5rem` (24px) - Main headings

#### Font Weights
- **normal**: `400` - Body text
- **medium**: `500` - Headings, buttons, labels

#### Line Heights
- **Tight**: `1.5` - Headings
- **Relaxed**: `1.625` - Body paragraphs

### Spacing

✅ **Extracted from Figma Design**

Standard spacing scale based on `0.25rem` (4px) unit:
- **xs**: `0.25rem` (4px)
- **sm**: `0.5rem` (8px)
- **md**: `1rem` (16px)
- **lg**: `1.5rem` (24px)
- **xl**: `2rem` (32px)
- **2xl**: `3rem` (48px)
- **3xl**: `4rem` (64px)

### Border Radius

✅ **Extracted from Figma Design**

Base radius: `0.625rem` (10px)
- **sm**: `0.225rem` (≈4px) - `calc(0.625rem - 4px)`
- **md**: `0.425rem` (≈7px) - `calc(0.625rem - 2px)`
- **lg**: `0.625rem` (10px) - Base radius
- **xl**: `1.25rem` (20px) - `calc(0.625rem + 4px)`
- **full**: `9999px` - Pills and circles

### Shadows/Elevation

From the design implementation:
- **Small**: Card shadows, subtle elevation
- **Medium**: Elevated components
- **Large**: Modal overlays
- **2xl**: Splash screen icon shadow

### Icons

- **Icon Library**: Lucide React (`lucide-react@0.487.0`)
- **Standard Size**: `h-5 w-5` (20px)
- **Large Icons**: `h-12 w-12` (48px) - Hero icons
- **Small Icons**: `h-4 w-4` (16px) - Inline icons

---

## Component Library

### Core Components (From Figma)

#### Buttons
- **Primary Button**: Main CTAs
- **Secondary Button**: Secondary actions
- **Text Button**: Tertiary actions
- **Icon Button**: Icon-only actions

**States**: Default, Hover, Pressed, Disabled, Loading

#### Cards
- **Plant Card**: Display plant identification results
- **Blog Card**: Blog post preview
- **Forum Topic Card**: Forum topic preview

#### Form Elements
- **Text Input**: Single-line text
- **Text Area**: Multi-line text
- **Select/Dropdown**: Options selection
- **Checkbox**: Multiple selection
- **Radio Button**: Single selection
- **Toggle/Switch**: Boolean values (e.g., theme toggle)

#### Navigation
- **Bottom Navigation** (Mobile): Primary navigation
- **Tab Bar**: Secondary navigation
- **App Bar**: Top navigation

#### Feedback
- **Loading Spinner**: Loading states
- **Progress Bar**: Upload/download progress
- **Snackbar/Toast**: Quick notifications
- **Alert Dialog**: Important messages
- **Empty State**: No content states

---

## Screen Designs (From Figma)

✅ **Implemented Screens in Design Repository**

### Mobile Screens

The Figma design includes the following complete screens:

1. **Splash Screen** ✅
   - Animated leaf icon with gradient
   - Brand name with gradient text
   - Tagline: "Discover Nature's Secrets"
   - Progress indicator
   - Auto-dismisses after loading

2. **Home/Landing Page** ✅
   - Hero section with camera icon
   - Welcome message
   - Four feature cards:
     * Instant Identification (green accent)
     * Care Instructions (blue accent)
     * Community Forum (purple accent)
     * Track Your Collection (amber accent)
   - "Get Started" CTA button

3. **Plant Identification Flow** ✅
   - **Camera Interface**:
     * Camera viewfinder
     * Capture button
     * Gallery access
     * Recent captures grid
   - **Processing State**:
     * Loading animation
     * "Analyzing plant..." message
   - **Results Screen**:
     * Plant image
     * Common name
     * Scientific name (italicized)
     * Detailed description
     * Care instructions with icons:
       - Watering (droplet icon)
       - Sunlight (sun icon)
       - Air circulation (wind icon)
       - Temperature (thermometer icon)
     * Timestamp of identification

4. **History/Collection** ✅
   - List of identified plants
   - Each card shows:
     * Plant thumbnail
     * Common name
     * Scientific name
     * Identification date
   - Tap to view full details

5. **Forum Interface** ✅
   - **Topics List**:
     * User avatar
     * Username with verification badge
     * Topic title
     * Preview text
     * Category label
     * Timestamp
     * Like and reply counts
     * Topic tags
   - **Topic Detail**:
     * Full post content
     * Replies thread
     * Reply input
   - Sample categories:
     * Plant Care
     * Beginner Guide
     * Show & Tell

6. **Settings Page** ✅
   - User profile section:
     * Avatar with edit button
     * Display name
     * Email
   - Theme toggle:
     * Light/dark mode switch
     * Icon changes (sun/moon)
   - Sections:
     * Account settings
     * Notifications
     * Preferences
     * About & Info
     * Logout

### Navigation Pattern ✅

**Bottom Navigation Bar** (4 tabs):
- **Home** (house icon)
- **Identify** (camera icon) - Primary feature
- **Forum** (message square icon)
- **Settings** (settings icon)

Active tab indicated with green accent color.

### Header Design ✅
- App logo (leaf icon) + "PlantID" text
- Theme toggle button (top right)
- Sticky header with backdrop blur
- Border bottom separator

### Web Screens (To Design/Implement)

Web will use similar design language but optimized for desktop:

1. **Home/Landing**
2. **Blog**
   - Blog Grid/List
   - Blog Detail
   - Create/Edit Blog (Admin)
3. **Forum**
   - Forum Categories
   - Topic List
   - Topic Detail
   - Create Topic
   - Reply Interface
4. **Plant ID** (Upload Only)
   - Simple upload interface
   - Results display
5. **User**
   - Profile
   - Dashboard

---

## Design Token Extraction Process

### ✅ Step 1: Figma Inspection - COMPLETE
Successfully accessed and extracted from the Figma design repository:
- ✅ All color values documented (green, emerald, accent colors)
- ✅ Typography system extracted (system fonts, sizes, weights, line heights)
- ✅ Spacing values extracted (0.25rem base unit)
- ✅ Border radius values extracted (0.625rem base)
- ✅ Gradient definitions documented

### ✅ Step 2: Export Assets - IN PROGRESS
Available in design repository:
- ✅ Lucide React icons (via npm package)
- ✅ Unsplash images (external links preserved)
- ⏳ Custom assets (if any) to be identified

### ✅ Step 3: Generate Tokens - COMPLETE
Created structured token files:
- ✅ `design-tokens.json` - Cross-platform design token definitions
- ✅ Color tokens for light/dark themes
- ✅ Typography tokens
- ✅ Spacing and radius tokens
- ✅ Gradient definitions

### Step 4: Implement in Code - PENDING

#### Tailwind CSS 4 (Web)
Based on `design_reference/src/styles/globals.css`:

```javascript
// tailwind.config.js
export default {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Import from design-tokens.json
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        // Brand colors
        green: {
          50: 'oklch(0.982 0.018 155.826)',
          100: 'oklch(0.962 0.044 156.743)',
          // ... all green shades
        },
        emerald: {
          // ... all emerald shades
        },
      },
      borderRadius: {
        lg: '0.625rem',
      },
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
}
```

#### Flutter (Mobile)
Create Dart constants:

```dart
// lib/core/theme/app_colors.dart
import 'package:flutter/material.dart';

class AppColors {
  // Brand Colors - Green
  static const Color green50 = Color(0xFFFAFDFA);
  static const Color green500 = Color(0xFF4CAF50);
  static const Color green600 = Color(0xFF43A047);
  static const Color green700 = Color(0xFF388E3C);
  // ... all color definitions
  
  // Light Theme
  static const Color lightBackground = Color(0xFFFFFFFF);
  static const Color lightForeground = Color(0xFF030213);
  
  // Dark Theme  
  static const Color darkBackground = Color(0xFF1A1A1A);
  static const Color darkForeground = Color(0xFFFAFAFA);
}

// lib/core/theme/app_theme.dart
class AppTheme {
  static ThemeData lightTheme = ThemeData(
    brightness: Brightness.light,
    colorScheme: ColorScheme.light(
      primary: AppColors.green600,
      secondary: AppColors.emerald600,
      // ... map all colors
    ),
  );
  
  static ThemeData darkTheme = ThemeData(
    brightness: Brightness.dark,
    colorScheme: ColorScheme.dark(
      primary: AppColors.green500,
      // ... map all colors
    ),
  );
}
```

---

## Implementation Guidelines

### Consistency Rules

1. **Always use design tokens** - Never hard-code colors, spacing, etc.
2. **Follow Figma designs closely** - Match pixel-perfect where reasonable
3. **Maintain theme consistency** - Ensure both themes are equally polished
4. **Responsive design** - Adapt to different screen sizes gracefully

### Accessibility

- **Color Contrast**: Ensure WCAG AA compliance minimum
- **Touch Targets**: Minimum 44x44px for mobile
- **Font Sizes**: Minimum 16px for body text
- **Focus States**: Clear visual focus indicators
- **Screen Reader Support**: Proper semantic HTML and Flutter semantics

### Animation & Transitions

- **Consistent Duration**: Use standard durations (150ms, 300ms, 500ms)
- **Smooth Easing**: Use ease-out for entrances, ease-in for exits
- **Purposeful Motion**: Animations should have a purpose, not just decoration
- **Respect Reduced Motion**: Honor user preference for reduced motion

---

## Next Steps

1. **Access Figma Design**: Review the complete design system
2. **Extract Design Tokens**: Document all colors, typography, spacing
3. **Create Component Catalog**: Document all components with variations
4. **Build Shared Tokens**: Create JSON files for cross-platform use
5. **Implement Themes**: Build theme systems for both web and mobile
6. **Create Style Guide**: Living documentation of design patterns

---

## Resources

- **Figma Design**: https://github.com/Xertox1234/Plantidentificationapp
- **Tailwind CSS 4 Docs**: https://tailwindcss.com/
- **Flutter Material Design**: https://docs.flutter.dev/ui/design/material
- **Figma Design Tokens Plugin**: https://www.figma.com/community/plugin/888356646278934516
- **Tailwind Shades Generator**: https://tailwind.simeongriggs.dev/

---

**Document Status**: ✅ Complete v1.0 - Design Tokens Extracted
**Last Updated**: October 21, 2025
**Design Source**: https://github.com/Xertox1234/Plantidentificationapp
**Figma Original**: https://www.figma.com/design/c4gvEaqEnNcDslZ1XcQBF2/Plant-Identification-App
**Next Steps**: Implement design tokens in web (Tailwind) and mobile (Flutter) during Phase 2 development
