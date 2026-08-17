import { Sparkles, MessagesSquare, BookOpen } from 'lucide-react';
import { Link } from 'react-router-dom';
import HeroCard from '../components/ui/HeroCard';
import ButtonLink from '../components/ui/ButtonLink';
import Card from '../components/ui/Card';
import Tile from '../components/ui/Tile';

interface FeatureCardProps {
  title: string;
  description: string;
  href: string;
  tone: 'sage' | 'bloom' | 'orchid';
  Icon: typeof Sparkles;
}

/**
 * HomePage Component
 *
 * Landing page: hero + three feature cards, on the Canopy primitives
 * (Canopy PR 4). Same copy/links for every visitor — no personalized
 * activity feed (deferred, todo 308).
 */
export default function HomePage() {
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
    <Card className="p-card">
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
