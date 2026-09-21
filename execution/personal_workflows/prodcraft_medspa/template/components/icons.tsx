// components/icons.tsx
// Inline SVG icon set for services, keyed by business.schema.json's `icon`
// enum. Stroke-based, currentColor, no external requests.

import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  width: 28,
  height: 28,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export function SyringeIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M18 2l4 4M14.5 5.5l4 4M4 20l3-1 9-9-3-3-9 9-1 3z" />
      <path d="M13 6l2 2M11 8l2 2" />
    </svg>
  );
}

export function SparkleIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" />
      <path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7L19 16z" />
    </svg>
  );
}

export function LaserIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="3" y="10" width="7" height="4" rx="1" />
      <path d="M10 12h11M17 8l4 4-4 4" />
    </svg>
  );
}

export function DropletIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z" />
    </svg>
  );
}

export function LeafIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M20 4c0 9-6 15-15 15C5 10 11 4 20 4z" />
      <path d="M5 19c3-3 6-6 9-11" />
    </svg>
  );
}

export function SunIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
    </svg>
  );
}

export function BodyIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="5" r="2.5" />
      <path d="M8 21l1.5-8L7 10l2-3.5h6L17 10l-2.5 3L16 21" />
    </svg>
  );
}

export function NeedleIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M20 4l-3 3M4 20l9-9M13 11l2 2M15 9l2 2M17 7l2 2" />
    </svg>
  );
}

export function ScaleIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3v18M7 7l-4 6a3.5 3.5 0 0 0 8 0l-4-6zM17 7l-4 6a3.5 3.5 0 0 0 8 0l-4-6zM4 21h16M7 3h10" />
    </svg>
  );
}

export function FlaskIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M9 2h6M10 2v6l-5.5 9.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-3.5L14 8V2" />
      <path d="M7.5 15h9" />
    </svg>
  );
}

export const SERVICE_ICONS: Record<string, (props: IconProps) => JSX.Element> = {
  syringe: SyringeIcon,
  sparkle: SparkleIcon,
  laser: LaserIcon,
  droplet: DropletIcon,
  leaf: LeafIcon,
  sun: SunIcon,
  body: BodyIcon,
  needle: NeedleIcon,
  scale: ScaleIcon,
  flask: FlaskIcon,
};
