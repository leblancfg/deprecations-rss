# Social Card Generation

This directory contains the social card implementation for the AI Deprecations Feeds website.

## Files

- `social-card.html` - HTML template for the social card that matches the site design
- `social-card.png` - Generated social card image (1200x630px)

## Generating the Social Card Image

To generate the social card image from the HTML template:

1. Install playwright:
   ```bash
   pip install playwright
   playwright install
   ```

2. Run the generation script:
   ```bash
   python ../generate_social_card.py
   ```

## Design

The social card maintains visual consistency with the main site design:

- **Colors**: Dark background (#1a1a1a) with orange gradient accents
- **Typography**: JetBrains Mono monospace font
- **Elements**: 
  - Bell icon (🔔) matching the favicon
  - Site title with gradient text effect
  - Tagline in muted text
  - Provider badges showing supported AI providers
  - Site URL in brand orange color
  - Subtle dotted pattern backgrounds

## Usage

The social card is automatically included in the HTML via Open Graph and Twitter Card meta tags:

```html
<!-- Open Graph -->
<meta property="og:image" content="https://deprecations.info/social-card.png">

<!-- Twitter -->
<meta property="twitter:image" content="https://deprecations.info/social-card.png">
```

## Dimensions

- **Size**: 1200x630 pixels (standard social media image size)
- **Aspect Ratio**: 1.91:1
- **Format**: PNG with transparency support