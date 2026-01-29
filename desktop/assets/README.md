# Assets Folder

## Icon Requirements

The desktop app needs a tray icon. Place your icon files here:

- `icon.png` - App icon (256x256px recommended)
- `IconTemplate.png` - Template icon for macOS (16x16px, black/transparent)

### Creating a Template Icon (macOS)

For best macOS integration, create a 16x16px icon:
- Use only black and transparent pixels
- Name it `IconTemplate.png` (capital I, capital T)
- macOS will automatically adapt it to light/dark mode

### Quick Placeholder

If you don't have an icon yet, you can create a simple one:

```bash
# Using ImageMagick (if installed)
convert -size 16x16 xc:transparent -fill black -draw "circle 8,8 8,2" IconTemplate.png

# Or just use a emoji/text
convert -size 16x16 -background transparent -fill black -font Arial -pointsize 12 -gravity center label:"F" IconTemplate.png
```

Or simply download any small PNG icon from the web and rename it to `icon.png`.

### Windows/Linux

For Windows and Linux, use `icon.png` (any standard PNG icon works).
