interface AvatarProps {
  src: string;
  alt: string;
  size?: 'sm' | 'md';
  /** Green presence dot (e.g. "expert online"). */
  presence?: boolean;
  className?: string;
}

const SIZES: Record<'sm' | 'md', string> = {
  sm: 'h-[34px] w-[34px] rounded-[11px]',
  md: 'h-[38px] w-[38px] rounded-[12px]',
};

export default function Avatar({
  src,
  alt,
  size = 'md',
  presence = false,
  className = '',
}: AvatarProps) {
  return (
    <span className={`relative inline-block flex-none ${className}`}>
      <img src={src} alt={alt} className={`border border-line-2 object-cover ${SIZES[size]}`} />
      {presence && (
        <span
          data-presence
          aria-hidden="true"
          className="absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-pill border-2 border-surface bg-secondary"
        />
      )}
    </span>
  );
}
