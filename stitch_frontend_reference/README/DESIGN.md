# Design System: The Obsidian Intelligence Console

## 1. Overview & Creative North Star
**Creative North Star: "The Kinetic Monolith"**

This design system rejects the "SaaS-dashboard-in-a-box" aesthetic. Instead, it draws from the high-stakes precision of McKinsey’s data visualizations and the immersive depth of high-end financial terminals. It is built to feel like a high-performance instrument—heavy, silent, and incredibly responsive.

The "Kinetic Monolith" approach breaks the traditional grid through **intentional asymmetry** and **tonal depth**. Rather than using lines to separate data, we use the "negative space of shadows" and layered translucency. The interface should feel as though it is carved out of dark volcanic glass, where information doesn't sit *on* the screen, but resides *within* its layers.

---

## 2. Colors & Surface Logic

### The Palette
We utilize a deep-scale charcoal and monochromatic foundation to allow the high-frequency accents to communicate status instantaneously.

*   **Background (Core):** `#131313` (Surface-Dim)
*   **Surface-Container-Lowest:** `#0E0E0E` (Used for deep "wells" or background workspace)
*   **Surface-Container-High:** `#2A2A2A` (Used for elevated, interactive cards)
*   **Primary (Electric Blue):** `#B8C3FF` (Knowledge Graphs / AI Insights)
*   **Secondary (Neon Green):** `#D7FFC5` (Active States / System Health)
*   **Tertiary (Amber):** `#FBBC00` (Data Friction / Risk Warnings)

### The "No-Line" Rule
**Strict Mandate:** Designers are prohibited from using 1px solid borders for sectioning. 
Structure is defined by the **Surface Hierarchy**:
*   A section is defined by moving from `surface-container-low` to `surface-container-highest`.
*   Vertical spacing (using the `8` or `10` spacing tokens) must be used to imply separation rather than a stroke.

### Surface Hierarchy & Nesting
Think of the UI as physical sheets of smoked glass. 
1.  **Base:** `surface` (#131313)
2.  **App Bar / Navigation:** `surface-container-low` (#1C1B1B)
3.  **Workspace / Panels:** `surface-container-high` (#2A2A2A)
4.  **Floating Modals:** `surface-bright` (#3A3939) with a 20px backdrop blur.

### Signature Textures: Glassmorphism 2.0
For AI-driven insights or knowledge graph overlays, use semi-transparent surfaces. 
*   **Token:** `primary-container` at 15% opacity.
*   **Effect:** `backdrop-filter: blur(12px);`
*   **Result:** A "frosted sapphire" look that suggests intelligence and depth without obstructing the data beneath.

---

## 3. Typography: Precision vs. Performance

The typographic system is a dialogue between **Manrope** (The Authority) and **Space Grotesk** (The Technical).

*   **Display & Headlines (Manrope):** Use `headline-lg` for macro-insights. Set with tight letter-spacing (-0.02em) to evoke an editorial, high-end report feel.
*   **Navigation & Labels (Inter):** Use `title-sm` for sidebar and primary navigation. Inter provides the "clean" McKinsey-style utility required for long-form reading.
*   **Data & Technical Readouts (Space Grotesk):** Use `label-md` for all numerical data, timestamps, and coordinates. This monospace-inspired sans-serif ensures that digits align perfectly in tables and graphs, communicating mathematical precision.

**Hierarchy Note:** Use `on-surface-variant` (#C4C5D9) for secondary labels to create a "recessed" text effect, ensuring only the most critical data points pop in `on-surface` (#E5E2E1).

---

## 4. Elevation & Depth

### The Layering Principle
Do not use `z-index` values randomly. Elevation is achieved by "stacking" tones:
*   Place a `surface-container-lowest` card inside a `surface-container-low` section to create a "sunken" data well.
*   Place a `surface-container-highest` card on a `surface` background to create a "raised" command module.

### Ambient Shadows
Shadows must never be black. Use a tinted shadow:
*   **Color:** `#000000` at 40% opacity for depth.
*   **Blur:** 24px - 48px.
*   **Spread:** -4px (to keep the shadow "tucked" and professional).

### The "Ghost Border" Fallback
If contrast testing requires a boundary, use a **Ghost Border**:
*   **Stroke:** 1px.
*   **Color:** `outline-variant` (#434656) at **20% opacity**.
*   **Effect:** It should only be visible when the eye looks specifically for it; it should not contribute to the visual noise of the layout.

---

## 5. Components

### Primary Buttons (The Insight Action)
*   **Style:** `primary` (#B8C3FF) background with `on-primary` (#002388) text.
*   **Shape:** `md` (0.375rem) roundedness. 
*   **State:** On hover, apply a subtle `primary-fixed-dim` outer glow (4px blur).

### Data Chips (Status Indicators)
*   **Active State:** `secondary-container` (#2FF801) at 10% fill with `on-secondary-container` (#0F6D00) text.
*   **Shape:** `full` (pill shape).
*   **Constraint:** No borders. Use the fill color to define the chip.

### Input Fields (The Data Entry)
*   **Base:** `surface-container-lowest` (#0E0E0E).
*   **Active/Focus:** A "Ghost Border" of `primary` at 40% opacity and a subtle `surface-tint` inner glow.
*   **Label:** Always `label-sm` (Space Grotesk) to maintain the "analyst terminal" feel.

### Knowledge Graph Nodes (Custom Component)
*   **Core:** 8px circles using `primary`.
*   **Connection Lines:** `outline-variant` (#434656) at 30% opacity.
*   **Interaction:** On hover, the node should expand to 12px with a `secondary` glow, signifying the reactive nature of the system.

---

## 6. Do's and Don'ts

### Do:
*   **Do** use vertical white space (Spacing `12` or `16`) to group related analytical modules.
*   **Do** use `tertiary` (Amber) sparingly. It is a "friction" color—only use it for data outliers or high-risk variables.
*   **Do** lean into asymmetry. A sidebar that doesn't reach the bottom of the screen or a data-viz that overlaps its container edge adds to the custom "editorial" feel.

### Don't:
*   **Don't** use 100% white text. Use `on-surface` (#E5E2E1) to reduce eye strain in high-density dark mode environments.
*   **Don't** use standard "drop shadows" on cards. Rely on tonal shifting between `surface-container` levels.
*   **Don't** use dividers in tables. Use alternating row backgrounds (Surface-Dim vs. Surface-Container-Low) or simply use 1.5x line height to create visual separation.
*   **Don't** use standard icons for status. Use the system's "Reactive" colors (Neon Green/Amber) in small, geometric dots for a more sophisticated feel.