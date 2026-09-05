import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import PageMeta from '../components/PageMeta';

export default function NotFoundPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <PageMeta title="Page not found — Houseplant MD" />
      <Card
        radius="lg"
        className="flex flex-col items-center gap-6 p-10 text-center md:flex-row md:text-left"
      >
        <img
          src="/illustrations/lost-leaf.webp"
          alt=""
          className="h-44 w-44 flex-none rounded-lg border border-line-2 object-cover"
        />
        <div className="flex flex-col items-center gap-3 md:items-start">
          <span className="font-mono text-micro tracking-[0.18em] text-secondary uppercase">
            404
          </span>
          <h1 className="gt-h1 text-balance">This leaf is not in our records.</h1>
          <p className="text-ink-2">
            The page you&apos;re looking for was moved, renamed, or never sprouted. Try the search
            in the top bar, or head somewhere green:
          </p>
          <div className="mt-2 flex flex-wrap justify-center gap-2.5">
            <Link to="/" className="canopy-cta rounded-pill px-5 py-2.5 text-body-sm font-semibold">
              Back to home
            </Link>
            <Link
              to="/forum"
              className="rounded-pill border border-line-2 px-5 py-2.5 text-body-sm font-semibold text-ink transition-colors hover:bg-surface-2"
            >
              Browse the forum
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
}
