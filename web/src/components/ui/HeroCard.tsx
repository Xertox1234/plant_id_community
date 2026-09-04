import type { ReactNode } from 'react';
import Card from './Card';
import { HERO_CARD_PADDING } from './dimensions';

interface HeroCardProps {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  art?: ReactNode;
}

export default function HeroCard({ eyebrow, title, description, actions, art }: HeroCardProps) {
  return (
    <Card radius="lg" className={HERO_CARD_PADDING}>
      <div className={`grid items-center gap-8 ${art ? 'md:grid-cols-[1.25fr_0.75fr]' : ''}`}>
        <div className="flex flex-col items-start gap-3.5">
          {eyebrow && (
            <span className="font-mono text-[11px] tracking-[0.18em] text-secondary uppercase">
              {eyebrow}
            </span>
          )}
          <h2 className="gt-h1 text-balance md:text-[38px]">{title}</h2>
          {description && <p className="max-w-[44ch] text-[14.5px] text-ink-2">{description}</p>}
          {actions && <div className="mt-2 flex flex-wrap gap-2.5">{actions}</div>}
        </div>
        {art && <div className="justify-self-start md:justify-self-end">{art}</div>}
      </div>
    </Card>
  );
}
