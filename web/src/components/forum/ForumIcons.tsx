/**
 * Field Notes icon set — tiny stroke glyphs that replace the emoji chrome
 * (📌 🔒 💬 👁️ 🔗 ✏️ 🗑️ 🚩 🔔 🔕) across the forum surfaces.
 *
 * Every icon is decorative: adjacent text carries the meaning, so each renders
 * with aria-hidden. Size via the `size` prop (px) or className; color follows
 * `currentColor`.
 */

import type { SVGProps } from 'react';

interface IconProps extends SVGProps<SVGSVGElement> {
  size?: number;
}

function base({ size = 14, className = '', ...props }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 16 16',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.5,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    className: `inline-block shrink-0 ${className}`,
    ...props,
  };
}

export function IconReply(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M13.5 10.5V4a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 4v5A1.5 1.5 0 0 0 4 10.5h1v3l3.4-3h3.6a1.5 1.5 0 0 0 1.5-1.5Z" />
    </svg>
  );
}

export function IconEye(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M1.5 8C3.2 4.9 5.5 3.4 8 3.4S12.8 4.9 14.5 8c-1.7 3.1-4 4.6-6.5 4.6S3.2 11.1 1.5 8Z" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  );
}

export function IconPin(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M9.5 1.5 14.5 6.5 13 8l-.5-.5-3 3L9 13 6.5 10.5 3 14l-1-1 3.5-3.5L3 7l2.5-.5 3-3L8 3l1.5-1.5Z" />
    </svg>
  );
}

export function IconLock(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3.5" y="7" width="9" height="6.5" rx="1" />
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
    </svg>
  );
}

export function IconLeaf(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M13.5 2.5c-6 0-10.5 4-11 11 7-.5 11-5 11-11Z" />
      <path d="M2.5 13.5C5.5 10 9 6.5 13 3" />
    </svg>
  );
}

export function IconLink(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6.5 9.5 9.5 6.5" />
      <path d="M7.5 4.5 9 3a2.47 2.47 0 0 1 3.5 0L13 3.5A2.47 2.47 0 0 1 13 7l-1.5 1.5" />
      <path d="M8.5 11.5 7 13a2.47 2.47 0 0 1-3.5 0L3 12.5A2.47 2.47 0 0 1 3 9l1.5-1.5" />
    </svg>
  );
}

export function IconPencil(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="m11.5 2 2.5 2.5L6 12.5l-3.5 1 1-3.5L11.5 2Z" />
    </svg>
  );
}

export function IconTrash(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M2.5 4.5h11" />
      <path d="M6 4.5V3h4v1.5" />
      <path d="m4 4.5.7 9h6.6l.7-9" />
    </svg>
  );
}

export function IconFlag(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3.5 14V2.5" />
      <path d="M3.5 3h8L10 5.75l1.5 2.75h-8" />
    </svg>
  );
}

export function IconCheck(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="m3 8.5 3.2 3L13 4.5" />
    </svg>
  );
}

export function IconBell(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M8 2a4 4 0 0 1 4 4c0 2.9.9 3.8 1.5 4.3H2.5C3.1 9.8 4 8.9 4 6a4 4 0 0 1 4-4Z" />
      <path d="M6.5 12.5a1.5 1.5 0 0 0 3 0" />
    </svg>
  );
}

export function IconBellOff(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M5.2 3.2A4 4 0 0 1 12 6c0 2.9.9 3.8 1.5 4.3H6" />
      <path d="M4 6c0 2.9-.9 3.8-1.5 4.3H4" />
      <path d="M6.5 12.5a1.5 1.5 0 0 0 3 0" />
      <path d="m2.5 2.5 11 11" />
    </svg>
  );
}
