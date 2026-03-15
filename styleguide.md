UI Style Guide: Neo-Brutalism
Design Philosophy
Neo-Brutalism (or Neobrutalism) rebels against the soft, highly polished, and overly clean corporate styles of modern web design. It embraces raw aesthetics, high legibility, stark contrasts, and unapologetic boldness. It is not about being "ugly," but rather about being radically authentic, structural, and striking.

1. Color Palette
Neo-Brutalism abandons subtle gradients and muted pastels in favor of high-contrast, web-safe, and jarring primary colors.

Primary Backgrounds: Often harsh whites, pale creams, or stark blacks to make foreground elements pop.

Off-White: #FAFAFA or #FFF9EE

Pitch Black: #000000

Accent Colors: Highly saturated, almost "default" looking colors. They can intentionally clash to create visual tension.

Acid Green: #CCFF00

Harsh Red: #FF4911

Electric Blue: #1100FF

Bright Yellow: #FFE600

Hot Pink: #FF00FF

Rule of Thumb: Never use gradients. Stick strictly to flat, solid fills.

2. Typography
Typography in Neo-Brutalism is structural, highly legible, and aggressive. It often mixes standard web-safe fonts with heavy, grotesque sans-serifs or coding-style fonts.

Headings (H1, H2, H3): * Font Families: Grotesque and bold (e.g., Space Grotesk, Archivo Black, Syne, Neue Haas Grotesk).

Weight: 800 (Extra Bold) or 900 (Black).

Casing: ALL CAPS or massive sentence case for impact.

Tracking: Tight letter-spacing for headlines to create a blocky feel.

Body Text:

Font Families: Brutally standard or monospaced (e.g., Inter, Public Sans, Roboto Mono, Courier New).

Weight: 400 (Regular) or 500 (Medium).

Size: Generally larger than standard (e.g., 18px or 20px base size) to ensure maximum readability.

Color: 100% Black (#000000) on light backgrounds, or 100% White (#FFFFFF) on dark backgrounds. No soft grays for text.

3. Borders & Shapes
Everything is contained, boxed, and heavily outlined. The skeleton of the layout is deliberately exposed.

Stroke / Border Width: Elements (cards, buttons, inputs, images) must have a thick, solid border.

Standard width: 2px to 4px.

Color: strictly #000000.

Border Radius: * Option A (Classic Brutal): 0px (completely sharp, square corners).

Option B (Friendly Brutal): Completely pill-shaped or heavy rounding (e.g., 8px or 50px), but still maintaining the harsh black outline.

4. Shadows (The Defining Feature)
Neo-Brutalist shadows are solid, unblurred blocks. They look like the element is physically stamped onto the page.

Blur Radius: 0px (Absolutely no blur or feathering).

Spread: 0px or 1px.

Offset: High offset on the X and Y axis to create a 3D isometric block effect.

Example: box-shadow: 4px 4px 0px #000000;

Heavy Example: box-shadow: 8px 8px 0px #000000;

Color: Usually solid black (#000000), but can sometimes be a clashing primary color.

5. Components & Interactions
Buttons
Buttons should look like physical, clickable blocks.

Default State: Thick black border, solid bright background color, heavy solid drop shadow (e.g., 6px offset).

Hover State: Background color flips to a clashing color. The cursor should change to pointer (or a custom retro cursor).

Active/Click State: The button "presses down" into the page. The shadow disappears or reduces, and the button translates X and Y to fill the space where the shadow was.

CSS Logic: transform: translate(6px, 6px); box-shadow: 0px 0px 0px #000;

Cards
Cards function as isolated containers.

They must have heavy borders, high-contrast backgrounds, and distinct solid shadows.

Content inside the cards should also be compartmentalized with internal borders separating the header, image, and text.

Inputs & Forms
Input fields mirror buttons but with a white or pale background.

Focus State: The border doesn't glow; it gets thicker (e.g., jumps from 2px to 4px), or the background turns pale yellow to indicate focus.

6. Imagery & Iconography
Photography: Raw, unedited, high-contrast, or cutout images with the background removed. Often paired with stark black outlines.

Illustrations: Flat vectors, bold lines, limited color palettes (matching the UI), pop-art style, or deliberately naive/retro MS Paint aesthetics.

Icons: Thick line weights (2px - 3px). No filled icons with gradients. SVG icons should perfectly match the stroke width of the surrounding borders. (e.g., Phosphor Icons or Lucide Icons set to a heavy weight).

7. Layout & Spacing
Grid: Visible grids are welcome. You can literally draw 1px or 2px black lines to separate sections of the website instead of using whitespace.

Spacing: Margins and padding should be generous but rigid. Avoid overlapping elements unless it is deliberate to create a "collage" effect, in which case the top element must have a thick solid shadow to separate it from the bottom element.