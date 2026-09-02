import { Sparkles, MessagesSquare, BookOpen, type LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import HeroCard from '../components/ui/HeroCard';
import ButtonLink from '../components/ui/ButtonLink';
import Card from '../components/ui/Card';
import Tile, { type TileTone } from '../components/ui/Tile';
import HomeActivity from '../components/home/HomeActivity';
import { useAuth } from '../contexts/AuthContext';

interface FeatureCardProps {
  title: string;
  description: string;
  href: string;
  tone: Exclude<TileTone, 'pollen'>;
  Icon: LucideIcon;
}

/**
 * HomePage Component
 *
 * Landing page: hero + three feature cards, on the Canopy primitives
 * (Canopy PR 4), plus a personalized activity feed for logged-in visitors
 * (todo 315). The hero and feature cards are identical for everyone; only
 * `HomeActivity` is gated, and it mounts nothing — and fetches nothing —
 * for an anonymous visitor, so logged-out Home is byte-identical to PR 4's.
 */
export default function HomePage() {
  const { user, isAuthenticated, isLoading } = useAuth();

  return (
    <div className="flex flex-col gap-8 py-8">
      {/* HeroCard's title renders as an h2 by design — the page still needs
          its own h1 for the document outline. */}
      <h1 className="sr-only">Home</h1>
      <HeroCard
        eyebrow="Plant Identification Community"
        title={
          <>
            Discover the World of <span className="text-primary">Plants</span>
          </>
        }
        description="Join our community of plant enthusiasts. Identify plants with AI, share your garden, and learn from experts and fellow plant lovers."
        actions={
          <>
            <ButtonLink to="/identify" variant="primary">
              Get Started
            </ButtonLink>
            <ButtonLink to="/forum" variant="ghost">
              Join Community
            </ButtonLink>
          </>
        }
      />

      {/* Logged-in only. Deliberately below the hero and above the feature
          cards: a returning member gets their own activity first, while the
          evergreen "what this site is" row stays reachable for both audiences.
          The parent is `gap-8` (not `space-y-8`), so inserting a child here
          cannot shift a sibling's margin — see docs/rules/react.md.

          `!isLoading` matters, not just `isAuthenticated`: AuthProvider seeds
          `user` from sessionStorage BEFORE verifying with the backend, so a
          visitor whose session has since expired would otherwise mount this,
          fire both requests, and flash the previous session's stats before
          verification unmounts it.

          `key={user?.id}` matters because `isAuthenticated` is `!!user` — it
          stays `true` across an identity change, so React would reuse the
          instance and HomeActivity's mount-once effect would never refetch.
          `revalidateIdentity()` swaps the user on tab focus precisely to catch
          a cookie-jar switch (todo 297, live prod incident 2026-08-13); without
          this key the header would update to account B while "Your season"
          still showed account A's numbers. */}
      {!isLoading && isAuthenticated && <HomeActivity key={user?.id} />}

      <div className="grid gap-5 md:grid-cols-3">
        <FeatureCard
          title="AI Plant Identification"
          description="Upload photos of plants and get instant identification using advanced AI technology."
          href="/identify"
          tone="sage"
          Icon={Sparkles}
        />
        <FeatureCard
          title="Discussion Forum"
          description="Ask questions, share tips, and participate in discussions about plant care."
          href="/forum"
          tone="bloom"
          Icon={MessagesSquare}
        />
        <FeatureCard
          title="Plant Blog"
          description="Read expert articles, care guides, and plant stories from our community."
          href="/blog"
          tone="orchid"
          Icon={BookOpen}
        />
      </div>
    </div>
  );
}

function FeatureCard({ title, description, href, tone, Icon }: FeatureCardProps) {
  return (
    <Card interactive className="p-card">
      <Link to={href} className="flex items-start gap-4">
        <Tile tone={tone} aria-hidden="true">
          <Icon className="h-5 w-5" />
        </Tile>
        <div className="min-w-0 flex-1">
          <h3 className="gt-h3 text-ink">{title}</h3>
          <p className="mt-1 text-sm leading-relaxed text-ink-2">{description}</p>
          <span className="mt-2 inline-block text-sm font-medium text-primary">Learn more →</span>
        </div>
      </Link>
    </Card>
  );
}
