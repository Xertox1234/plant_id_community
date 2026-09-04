/**
 * Dimension classes shared between a primitive and the skeleton block that
 * mirrors it, so a size change moves both (todo 333). A `.ts` module because a
 * `.tsx` component file may export only components
 * (react-refresh/only-export-components). Box and radius are separate so a
 * SkeletonBlock can take the box without stacking a second `rounded-*`
 * utility on the one its own `rounded` prop emits. Full class names, so
 * Tailwind's scanner sees them.
 */

export type TileSize = 'sm' | 'md';
export const TILE_BOX: Record<TileSize, string> = {
  sm: 'h-9 w-9',
  md: 'h-[46px] w-[46px]',
};
export const TILE_RADIUS: Record<TileSize, string> = {
  sm: 'rounded-[11px]',
  md: 'rounded-[14px]',
};

export type AvatarSize = 'sm' | 'md' | 'lg';
export const AVATAR_BOX: Record<AvatarSize, string> = {
  sm: 'h-[34px] w-[34px]',
  md: 'h-[38px] w-[38px]',
  lg: 'h-20 w-20',
};
export const AVATAR_RADIUS: Record<AvatarSize, string> = {
  sm: 'rounded-[11px]',
  md: 'rounded-[12px]',
  lg: 'rounded-md', // --radius-md is 16px; the token, not an arbitrary twin of it
};

/** PostCard's shell padding; PostCardSkeleton copies it. */
export const POST_CARD_PADDING = 'p-5 sm:p-6';
/** HeroCard's shell padding; the radius is Card's `radius="lg"`. */
export const HERO_CARD_PADDING = 'p-8 md:p-10';
