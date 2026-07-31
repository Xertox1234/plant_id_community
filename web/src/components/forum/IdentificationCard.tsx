import { Sparkles } from 'lucide-react';
import type { ThreadIdentification } from '@/types';

interface IdentificationCardProps {
  identification: ThreadIdentification;
  /**
   * The accepted answer's post id, when the topic is solved. The card then
   * links to it, so the snapshot never reads as the last word on the question.
   */
  solvedPostId?: number | null;
}

/**
 * The plant-ID snapshot a topic carries, rendered above the opening post
 * (audit M6).
 *
 * Two things this component is deliberately careful about:
 *
 * 1. **It never claims the plant IS the top candidate.** The backend stores
 *    what the app suggested to the author — caller-supplied, unverified — so
 *    the heading says so, and every candidate is shown with its confidence
 *    rather than one being presented as the answer.
 * 2. **Once the topic is solved, the card points at the human answer.** A
 *    reader who scrolls no further should not walk away with the machine guess.
 */
export default function IdentificationCard({
  identification,
  solvedPostId,
}: IdentificationCardProps) {
  const { image, provider, candidates } = identification;

  return (
    <section
      aria-labelledby="identification-heading"
      className="mb-6 overflow-hidden rounded-lg border border-line bg-surface-2 shadow-md"
    >
      <div className="flex items-center gap-2 border-b border-line px-6 py-3">
        <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
        <h2 id="identification-heading" className="text-sm font-semibold text-ink">
          What the app suggested
        </h2>
      </div>

      <div className="flex flex-col gap-6 p-6 sm:flex-row">
        {/* No-photo fallback is a real state, not an error: the FK is SET_NULL,
            and an identification run without a kept photo still has candidates. */}
        {image && (
          <img
            src={image.url}
            // Prefer the author's own description, fall back to the image's
            // ROLE on the page. Before M7 (todo 281) `image.alt` was derived
            // from the Wagtail title — i.e. the upload filename — so this was
            // hardcoded to avoid reading out "IMG_4021.jpg". It now carries
            // author-supplied text, which beats a generic role sentence; the
            // fallback still covers an image uploaded without alt (including
            // every pre-M7 row, which serves "").
            alt={image.alt || 'Photo the author submitted for identification'}
            width={image.width}
            height={image.height}
            className="w-full max-w-56 self-start rounded-lg object-cover"
          />
        )}

        <div className="min-w-0 flex-1">
          <ol className="space-y-2">
            {candidates.map((candidate, index) => (
              <li
                key={`${candidate.scientific_name || candidate.name}-${index}`}
                className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-line pb-2 last:border-b-0 last:pb-0"
              >
                <span className="min-w-0">
                  <span className="font-medium text-ink">{candidate.name}</span>
                  {candidate.scientific_name && (
                    <em className="ml-2 text-sm text-ink-2">{candidate.scientific_name}</em>
                  )}
                </span>
                {/* Confidence is 0–1 from the backend. Rendered as a percentage
                    because that is how the identify screen shows it. */}
                <span className="shrink-0 text-sm tabular-nums text-ink-2">
                  {Math.round(candidate.confidence * 100)}%
                </span>
              </li>
            ))}
          </ol>

          <p className="mt-4 text-xs text-ink-3">
            Suggested by the Plant ID app
            {provider ? ` (${provider})` : ''} and attached by the author — not a confirmed
            identification. That&rsquo;s what this thread is for.
          </p>

          {solvedPostId != null && (
            <a
              href={`#post-${solvedPostId}`}
              className="mt-3 inline-block text-sm font-medium text-primary underline"
            >
              See the accepted answer
            </a>
          )}
        </div>
      </div>
    </section>
  );
}
