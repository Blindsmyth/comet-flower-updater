# Comet Flower Screen Design

## Design Idea
The "Comet Flower" look is characterized by a bold, clean, and dynamic aesthetic. Since the 128x32 1-bit LCD requires extreme precision, we prioritize clean, hand-placed pixel art over programmatic effects.
- We implemented the "Comet Flower frame", replacing the original frames (which had rounded corners and screws) with a sleek, perfectly rectangular 1-pixel solid border.
- The original fonts are preserved to maintain crisp, jagged-free strokes and perfect 1:1 readability.
- The main ZOOM logo was replaced with the blocky, chamfered CF logo.

## What was changed
1. **Logo**: 
   - `bmp_c017bf38_92x16.png` was replaced with `assets/logo_comet_flower.png`.
2. **Fonts**: 
   - All fonts were reverted to their original versions to ensure clean, jagged-free rendering.
3. **Full-screen messages**:
   - `bmp_c0178ae0_128x32.png`: Replaced original frame with the sleek 1px CF-styled frame (interior empty).
   - `bmp_c0178ce0_128x32.png` ("Low Battery!"): Applied the CF-styled frame while meticulously preserving the original battery icon and text layout.
   - `bmp_c0178ee0_128x32.png` ("PC MODE"): Restored to original design with the USB icon.
   - `bmp_c01790e0_128x32.png` ("MISSING EFFECT / NOT FOUND"): Applied the CF-styled frame, strictly preserving both lines of text, the "?" icon, and the top-left square area.
   - `bmp_c01792e0_128x32.png` ("PROCESS OVERFLOW / CHANGE EFFECT"): Applied the CF-styled frame, preserving both lines of text and the warning triangle.
   - `bmp_c01796e0_128x32.png`: Applied the CF-styled frame to the split panel, preserving the vertical divider at x=34.
   - `bmp_c01798e0_128x32.png`: Applied the CF-styled frame to the "LOOPER CANCELED" screen.
   - `bmp_c017a8d8_128x20.png`: "Edited! Can't swap." graphic is correctly identified and remains unchanged.

## Unsure about
- **Mock-up Font Integration**: Since we reverted the fonts, the mock-ups rely on the original default font appearances within the newly styled CF frames. Let us know if we should explore manual, hand-drawn pixel-art font restyling for select elements instead of programmatic shears.
