import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ClayVariant = 'primary' | 'secondary' | 'outline';
type ClaySize = 'sm' | 'md' | 'lg';

export interface ClayButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon?: ReactNode;
  fullWidth?: boolean;
  size?: ClaySize;
  variant?: ClayVariant;
  loading?: boolean;
}

const VARIANT: Record<ClayVariant, string> = {
  primary: 'bg-clay text-on-clay shadow-2',
  secondary: 'bg-primary text-on-primary shadow-2',
  outline: 'bg-transparent border border-primary text-primary',
};
const SIZE: Record<ClaySize, string> = {
  sm: 'px-4 py-2 text-sm',
  md: 'px-6 py-3 text-base',
  lg: 'px-8 py-4 text-base',
};

export default function ClayButton({
  label,
  icon,
  fullWidth = false,
  size = 'lg',
  variant = 'primary',
  loading = false,
  disabled,
  type = 'button',
  className = '',
  ...rest
}: ClayButtonProps) {
  const isDisabled = disabled || loading;
  const classes = [
    'inline-flex items-center justify-center gap-2 rounded-pill font-semibold tracking-[0.25px]',
    'min-h-[44px] transition-colors',
    fullWidth && 'w-full',
    isDisabled ? 'bg-surface-3 text-ink-3/40 cursor-not-allowed' : VARIANT[variant],
    SIZE[size],
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      {...rest}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={classes}
    >
      {loading ? (
        <>
          <span
            aria-hidden="true"
            className="h-5 w-5 animate-spin rounded-full border-2 border-current/40 border-t-current"
          />
          <span className="sr-only">{label}</span>
        </>
      ) : (
        <>
          {icon && <span aria-hidden="true">{icon}</span>}
          <span>{label}</span>
        </>
      )}
    </button>
  );
}
