import { useId } from 'react';

interface BrandMarkProps {
  size?: number;
  className?: string;
}

/** Houseplant MD badged-leaf mark. The cross is clinic red #DE6B5A on green —
 *  NEVER red-on-white (protected Geneva emblem; spec §2.1). */
export default function BrandMark({ size = 34, className = '' }: BrandMarkProps) {
  const uid = useId();
  const tileId = `${uid}-tile`;
  const leafId = `${uid}-leaf`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className={className}
      role="img"
      aria-label="Houseplant MD"
    >
      <defs>
        <linearGradient id={tileId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#10362F" />
          <stop offset="1" stopColor="#0B2B26" />
        </linearGradient>
        <linearGradient id={leafId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#DAF1DE" />
          <stop offset="1" stopColor="#8EB69B" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#${tileId})`} />
      <g
        transform="translate(10 8) scale(1.85)"
        fill="none"
        stroke={`url(#${leafId})`}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
        <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
      </g>
      <circle cx="47" cy="47" r="11.5" fill="#DE6B5A" />
      <g fill="#DAF1DE">
        <rect x="44.8" y="40.8" width="4.4" height="12.4" rx="2.2" />
        <rect x="40.8" y="44.8" width="12.4" height="4.4" rx="2.2" />
      </g>
    </svg>
  );
}
