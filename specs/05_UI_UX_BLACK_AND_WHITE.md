# 05 — Monochrome UI/UX Design Specification (Black & White)

## 1. Visual Identity & Philosophy
A strict **editorial monochrome palette** (`#000000` and `#FFFFFF`) engineered to eliminate visual clutter when a user is tired or overstimulated. Hierarchy is achieved through **typography weight, negative space, and crisp `1px` borders**—never gradients, drop shadows, or multi-color badges.

## 2. Design Tokens (CSS Variables)
```css
:root {
  /* Core Surfaces */
  --bg-primary: #FFFFFF;
  --bg-inverse: #000000;
  --bg-subtle: #F7F7F7;

  /* Text */
  --text-primary: #000000;
  --text-secondary: #525252;
  --text-inverse: #FFFFFF;

  /* Borders & Dividers */
  --border-hairline: 1px solid #E5E5E5;
  --border-strong: 1.5px solid #000000;

  /* Interactive States */
  --pill-bg: #FFFFFF;
  --pill-border: 1px solid #000000;
  --pill-hover-bg: #000000;
  --pill-hover-text: #FFFFFF;

  /* Radii & Spacing */
  --radius-card: 12px;
  --radius-pill: 9999px;
  --radius-input: 8px;
  --space-unit: 8px;
}

/* Optional High-Contrast Dark Mode Inversion */
[data-theme="dark"] {
  --bg-primary: #000000;
  --bg-inverse: #FFFFFF;
  --bg-subtle: #121212;
  --text-primary: #FFFFFF;
  --text-secondary: #A3A3A3;
  --text-inverse: #000000;
  --border-hairline: 1px solid #262626;
  --border-strong: 1.5px solid #FFFFFF;
}
```

## 3. Typography Scale
- **Font Family:** `'Inter', -apple-system, BlinkMacSystemFont, sans-serif` + `'JetBrains Mono', monospace` for prices, ETAs, and mood tags.
- **Screen Header:** `18px` / `600 SemiBold` / `-0.02em` tracking.
- **Chat Message Body:** `15px` / `400 Regular` / `1.45` line-height.
- **Combo Card Title:** `16px` / `700 Bold` / `#000000`.
- **Mood-Match Rationale:** `13px` / `400 Regular` / `#525252`.
- **Metadata (`22 MINS • ₹219`):** `12px` / `600 SemiBold` / `JetBrains Mono` / uppercase.

## 4. Mobile Screen Wireframe (390px Viewport)
```
+--------------------------------------------------+
| <-  MOODBITE AI                  [VEG ONLY] [o]  |  <- 1.5px bottom border
+--------------------------------------------------+
|                                                  |
|  MOODBITE                                        |
|  +--------------------------------------------+  |
|  | Hey! Rough day, chill evening, or just     |  |  <- White card, 1px #000 border
|  | need fast food so you don't have to think? |  |
|  +--------------------------------------------+  |
|                                                  |
|              +--------------------------------+  |
|              | super tired and mood is off,   |  |  <- Solid #000 bubble, #FFF text
|              | want something fast to cheer up|  |
|              +--------------------------------+  |
|                                                  |
|  MOODBITE                                        |
|  Say no more—zero-mess comfort coming right up:  |
|                                                  |
|  +--------------------------------------------+  |
|  | [COMFORT CLASSIC]           22 MINS • ₹219 |  |  <- Inverted #000 tag badge
|  | Homestyle Rajma Chawal + Chilled Coke      |  |
|  | Punjabi Angithi • ★ 4.4                    |  |
|  | Warm, zero-effort bowl with a cold fizzy   |  |
|  | kick to lift your mood fast.               |  |
|  |                                            |  |
|  | [ + ADD COMBO TO CART ]                    |  |  <- Full-width #000 button
|  +--------------------------------------------+  |
|                                                  |
|  +--------------------------------------------+  |
|  | [ZERO-MESS ROLL]            20 MINS • ₹239 |  |
|  | Paneer Tikka Roll + Masala Lemonade        |  |
|  | ...                                        |  |
|  +--------------------------------------------+  |
|                                                  |
|  REFINE LIST:                                    |
|  ( Under ₹250 )  ( Spicier )  ( Swap Drink )     |  <- 1px #000 outline pills
+--------------------------------------------------+
|  Type how you're feeling...              [ -> ]  |  <- 1.5px #000 input bar
+--------------------------------------------------+
```

## 5. Component Interaction Rules
- **User Chat Bubbles:** Right-aligned, `#000000` background, `#FFFFFF` text, `12px` radius (`2px` bottom-right corner).
- **Agent Chat Bubbles:** Left-aligned, `#FFFFFF` background, `#000000` text, `1px solid #000000` border.
- **Recommendation Cards:** Pure white surface with `1.5px solid #000000` border. Top-left mood tag rendered as an inverted solid `#000000` rectangle with `10px` uppercase monospace `#FFFFFF` text.
- **Primary CTA (`+ ADD COMBO TO CART`):** Solid `#000000` fill, `#FFFFFF` bold text; on click transitions to `✓ ADDED TO CART (₹219)` with white background and `1.5px solid #000000` border.
- **Loading State:** Minimal 3-dot monochrome pulse (`#000000`) with rotating micro-copy (*"Reading the vibe..."*, *"Checking fast kitchens near you..."*).
