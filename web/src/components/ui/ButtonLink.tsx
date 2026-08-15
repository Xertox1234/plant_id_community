/**
 * ButtonLink Component
 *
 * A react-router <Link> wearing the Button visual recipe. Use it wherever a
 * navigation action should look like a button — never nest <Button> inside a
 * <Link>: <a><button> is invalid HTML and gives keyboard users a double tab
 * stop whose Enter doesn't navigate.
 *
 * Deliberately no `loading`/`disabled` — links can't be disabled; if the
 * action must be gated, it's a Button with an onClick navigation.
 *
 * @example
 * <ButtonLink to="/forum/new-thread" variant="primary">Start a thread</ButtonLink>
 */

import { ReactNode } from 'react';
import { Link, LinkProps } from 'react-router-dom';
import { buttonClassNames, type ButtonSize, type ButtonVariant } from './buttonStyles';

interface ButtonLinkProps extends Omit<LinkProps, 'className'> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
}

export default function ButtonLink({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  ...props
}: ButtonLinkProps) {
  return (
    <Link className={buttonClassNames(variant, size, className)} {...props}>
      {children}
    </Link>
  );
}
