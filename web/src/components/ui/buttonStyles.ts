/**
 * Shared button class recipes — consumed by Button (a real <button>) and
 * ButtonLink (a react-router <Link> wearing the same look).
 *
 * Lives in its own module because react-refresh/only-export-components only
 * exempts literal const exports from component files — exporting these maps
 * or the helper from Button.tsx would break Fast Refresh.
 */

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

const baseStyles =
  'inline-flex items-center justify-center font-semibold transition-colors motion-safe:transition-all rounded-pill focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-50 disabled:cursor-not-allowed';

const variants: Record<ButtonVariant, string> = {
  primary: 'canopy-cta shadow-1 motion-safe:hover:-translate-y-px hover:shadow-2',
  secondary: 'bg-surface-2 text-ink border border-line hover:bg-surface-3',
  outline: 'border border-line-2 text-ink hover:bg-surface-2',
  ghost: 'text-ink-2 hover:bg-surface-2 hover:text-ink',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

export function buttonClassNames(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  className = ''
): string {
  return `${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`;
}
