# Phase 4 — Frontend Design System

## Design direction

The platform uses a calm, premium commerce aesthetic: clean typography,
translucent surfaces, restrained gradient light, and responsive layouts. The
system avoids decorative controls that compete with product or security tasks.
It is implemented once in `static/css/app.css` and shared by all server-rendered
templates.

## Tokens

| Token family | Light mode | Dark mode | Purpose |
| --- | --- | --- | --- |
| Canvas | cool off-white `#f5f7ff` | ink `#10121f` | page background and gradient field |
| Surface | translucent white | blue-charcoal glass | cards, notices, and form containers |
| Brand | indigo `#635bff` | lavender `#a69eff` | primary actions and links |
| Accent | teal `#008e86` | mint `#5eead4` | supporting emphasis and eyebrow labels |
| Text | near-black `#16182b` | near-white `#f7f8ff` | readable primary content |
| Focus | dark indigo | pale lavender | three-pixel keyboard focus ring |

Spacing, radii, shadows, typography, and all color values are CSS custom
properties. Components consume those tokens rather than choosing one-off
values, so a future storefront inherits the same visual language.

## Typography and components

- **Typography:** a fast system sans-serif stack, fluid heading sizes via
  `clamp()`, high-contrast body text, and a reserved monospace face for secrets
  and identifiers.
- **Navigation:** a floating glass-style header with a compact theme control,
  mobile-safe labels, and a keyboard skip link.
- **Cards:** `sc-card` provides the glass surface, border, radius, and one
  consistent soft shadow.
- **Actions:** `sc-button` is the primary action; `sc-button-quiet` supports
  secondary navigation without visual competition.
- **Forms:** `sc-form` supplies semantic labels, consistent inputs, errors,
  checkboxes, and focus states without JavaScript widgets.
- **Status and data:** `status-message`, `profile-fact`, and `sc-code` cover
  messages, account summaries, and sensitive one-time setup values.

## Theme behaviour and accessibility

The theme starts from the operating-system preference, persists a user choice
in local storage when permitted, and changes the root `data-theme` attribute.
An inline pre-paint initializer prevents a visible light/dark flash; the small
external script keeps the button label and `aria-pressed` state accurate.

The system includes semantic HTML, visible focus rings, a skip link, no
color-only meaning, responsive layout down to 320px, and a
`prefers-reduced-motion` mode that disables non-essential animation.

## Motion

Motion is intentionally limited to a short entrance transition and a subtle
primary-button lift. There are no looping effects, auto-playing content, or
motion-dependent interactions. Users who request reduced motion receive an
effectively static interface.

## Tailwind handoff

`static/src/tailwind.css` and `package.json` define the matching Tailwind v4
tokens and build commands. The current development environment has no Node.js,
so the usable custom-property CSS is committed directly and no unverified
Tailwind build artifact is generated here.

On a Node-enabled development or CI machine:

```bash
npm install
npm run css:build
```

The built `static/css/tailwind.css` can then be added to the base template when
the customer storefront begins using Tailwind utility classes. This preserves a
small, fully working Phase 4 interface now while keeping the requested Tailwind
toolchain ready for the page-building phases.
