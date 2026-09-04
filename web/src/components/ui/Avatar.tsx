import { AVATAR_BOX, AVATAR_RADIUS, type AvatarSize } from './dimensions';

interface AvatarProps {
  src: string;
  alt: string;
  size?: AvatarSize;
  /** Green presence dot (e.g. "expert online"). */
  presence?: boolean;
  className?: string;
}

export default function Avatar({
  src,
  alt,
  size = 'md',
  presence = false,
  className = '',
}: AvatarProps) {
  return (
    <span className={`relative inline-block flex-none ${className}`}>
      <img
        src={src}
        alt={alt}
        className={`border border-line-2 object-cover ${AVATAR_BOX[size]} ${AVATAR_RADIUS[size]}`}
      />
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
