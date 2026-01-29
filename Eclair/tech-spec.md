# Eclair - Technical Specification

## 1. Tech Stack Overview

| Category | Technology |
|----------|------------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite |
| Styling | Tailwind CSS 3.4 |
| UI Components | shadcn/ui (minimal usage) |
| Animation | Framer Motion |
| Icons | Lucide React (if needed) |

## 2. Tailwind Configuration Guide

### Color Extensions

```javascript
colors: {
  'eclair': {
    'bg': '#9BA8B4',
    'text': '#E5D085',
    'text-muted': '#C4B56E',
    'border': '#B8A86A',
  }
}
```

### Font Extensions

```javascript
fontFamily: {
  'sans': ['Inter', 'Helvetica Neue', 'Arial', 'sans-serif'],
}
```

## 3. Component Inventory

### Custom Components (to build)

| Component | Props | Description |
|-----------|-------|-------------|
| `StaggeredLogo` | `text: string, className?: string` | Creates the pyramid text effect |
| `VerticalText` | `text: string, position: 'left' \| 'right'` | Rotated vertical text |
| `AnimatedHeadline` | `text: string, className?: string` | Word-by-word stagger animation |
| `InfoBlock` | `label: string, value: string, subValue?: string` | Label-value pair for footer |
| `NavLink` | `href: string, children: ReactNode` | Animated navigation link |

### Shadcn/UI Components

None required - this is a purely custom typography-focused design.

## 4. Animation Implementation Plan

| Interaction Name | Tech Choice | Implementation Logic |
|------------------|-------------|---------------------|
| Page Load - Logo Stagger | Framer Motion | `staggerChildren: 0.1` on container, each line fades in from `y: -20` with `opacity: 0` → `y: 0, opacity: 1` |
| Page Load - Headline | Framer Motion | Split text by words, `staggerChildren: 0.08`, each word from `y: 30, opacity: 0` |
| Page Load - Footer | Framer Motion | Simple fade in with `delay: 1.2` |
| Page Load - Vertical Text | Framer Motion | Slide in from edge with `x: 50` → `x: 0` |
| Nav Link Hover | Tailwind + CSS | `hover:opacity-60 hover:translate-x-2 transition-all duration-300` |
| Logo Hover | Tailwind | `hover:scale-[1.02] transition-transform duration-400` |

### Animation Timing Constants

```typescript
const ANIMATION_CONFIG = {
  easing: {
    default: [0.4, 0, 0.2, 1],
    easeOut: [0, 0, 0.2, 1],
    easeIn: [0.4, 0, 1, 1],
  },
  duration: {
    fast: 0.3,
    normal: 0.5,
    slow: 0.8,
  },
  stagger: {
    logo: 0.08,
    headline: 0.06,
  },
  delay: {
    subtitle: 0.6,
    headline: 0.8,
    footer: 1.2,
    vertical: 1.0,
  }
};
```

## 5. Project File Structure

```
app/
├── src/
│   ├── components/
│   │   ├── StaggeredLogo.tsx
│   │   ├── VerticalText.tsx
│   │   ├── AnimatedHeadline.tsx
│   │   ├── InfoBlock.tsx
│   │   └── NavLink.tsx
│   ├── sections/
│   │   └── HeroSection.tsx
│   ├── lib/
│   │   └── animations.ts
│   ├── App.tsx
│   ├── App.css
│   └── main.tsx
├── tailwind.config.js
└── index.html
```

## 6. Package Installation List

```bash
# Animation library
npm install framer-motion

# Font (Inter)
npm install @fontsource/inter
```

## 7. Responsive Breakpoints

| Breakpoint | Width | Adjustments |
|------------|-------|-------------|
| Mobile | < 640px | Headline: 40px, Stack footer vertically, Hide vertical text |
| Tablet | 640-1024px | Headline: 60px, 2-column footer |
| Desktop | > 1024px | Headline: 80-96px, Full 3-column footer |

## 8. Accessibility Considerations

- Respect `prefers-reduced-motion` media query
- Ensure sufficient color contrast (gold on blue-gray)
- Semantic HTML structure
- Keyboard navigable links
