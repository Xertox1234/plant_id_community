import { useNavigate, Link } from 'react-router-dom';
import GrainOverlay from '../components/ui/GrainOverlay';
import Eyebrow from '../components/ui/Eyebrow';
import ClayButton from '../components/ui/ClayButton';

interface FeatureCardProps {
  title: string;
  description: string;
  href: string;
  accentClass?: string;
}

/**
 * HomePage Component
 *
 * Landing page with hero section and feature cards.
 * Header and navigation now handled by RootLayout.
 */
export default function HomePage() {
  const navigate = useNavigate();

  return (
    <GrainOverlay>
      {/* Hero Section */}
      <section className="bg-surface py-24 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <Eyebrow className="mb-3">Plant Identification Community</Eyebrow>
          <h1 className="gt-display text-ink mb-6">
            Discover the World of <span className="text-primary">Plants</span>
          </h1>
          <p className="text-xl text-ink-2 mb-8 max-w-3xl mx-auto">
            Join our community of plant enthusiasts. Identify plants with AI, share your garden, and
            learn from experts and fellow plant lovers.
          </p>

          <div className="flex gap-4 justify-center flex-wrap">
            <ClayButton label="Get Started" size="lg" onClick={() => navigate('/identify')} />
            <Link
              to="/forum"
              className="px-8 py-3 bg-surface-2 text-primary rounded-pill font-medium border border-primary hover:bg-primary/10 transition-colors inline-flex items-center"
            >
              Join Community
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-4 bg-surface">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="gt-h1 text-ink mb-4">Everything you need to explore plants</h2>
            <p className="text-xl text-ink-2">
              From AI-powered identification to community knowledge sharing
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard
              title="AI Plant Identification"
              description="Upload photos of plants and get instant identification using advanced AI technology."
              href="/identify"
              accentClass="text-primary"
            />
            <FeatureCard
              title="Discussion Forum"
              description="Ask questions, share tips, and participate in discussions about plant care."
              href="/forum"
              accentClass="text-berry"
            />
            <FeatureCard
              title="Plant Blog"
              description="Read expert articles, care guides, and plant stories from our community."
              href="/blog"
              accentClass="text-sky"
            />
          </div>
        </div>
      </section>
    </GrainOverlay>
  );
}

function FeatureCard({ title, description, href, accentClass = 'text-primary' }: FeatureCardProps) {
  return (
    <div className="bg-surface-2 rounded-lg p-card shadow-1 border border-line hover:shadow-2 transition-shadow">
      <h3 className="text-xl font-semibold text-ink mb-3">{title}</h3>
      <p className="text-ink-3 mb-6 leading-relaxed">{description}</p>
      <Link
        to={href}
        className={`inline-flex items-center font-medium ${accentClass} hover:underline`}
      >
        Learn more →
      </Link>
    </div>
  );
}
