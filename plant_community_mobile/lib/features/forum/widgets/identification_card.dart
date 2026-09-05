import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';

/// The plant-ID SNAPSHOT a topic carries, rendered under the opening post
/// (audit M6; todo 341 wave 3). Mirrors the web `IdentificationCard`.
///
/// Two things this widget is deliberately careful about:
///
/// 1. It never claims the plant IS the top candidate — the backend stores
///    what the app suggested to the author (caller-supplied, unverified), so
///    the heading says so and every candidate carries its confidence.
/// 2. Once the topic is solved, the card points at the human answer
///    ([onJumpToAnswer]) so a reader who scrolls no further doesn't walk
///    away with the machine guess.
///
/// Nothing is fetched: the snapshot is complete as delivered.
class IdentificationCard extends StatelessWidget {
  const IdentificationCard({
    super.key,
    required this.identification,
    this.solvedPostId,
    this.onJumpToAnswer,
  });

  final ForumIdentification identification;

  /// The accepted answer's post id, when the topic is solved.
  final int? solvedPostId;

  /// Scrolls the accepted answer into view (the thread's own chase).
  final Future<void> Function()? onJumpToAnswer;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final image = identification.image;
    final provider = identification.provider;
    final jump = onJumpToAnswer;
    return Semantics(
      container: true,
      label: 'What the app suggested',
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.auto_awesome_outlined,
                    size: 18,
                    color: theme.colorScheme.secondary,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Text(
                    'What the app suggested',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // No-photo fallback is a real state, not an error: the FK
                  // is SET_NULL, and a run without a kept photo still has
                  // candidates.
                  if (image != null) ...[
                    _Photo(image: image),
                    const SizedBox(width: AppSpacing.md),
                  ],
                  Expanded(
                    child: identification.candidates.isEmpty
                        ? Text(
                            'No suggestions were recorded.',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          )
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              for (final candidate in identification.candidates)
                                _CandidateRow(candidate: candidate),
                            ],
                          ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Suggested by the Plant ID app'
                '${provider.isNotEmpty ? ' ($provider)' : ''} and attached '
                'by the author — not a confirmed identification. That’s '
                'what this thread is for.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (solvedPostId != null && jump != null)
                TextButton.icon(
                  onPressed: jump,
                  style: TextButton.styleFrom(
                    minimumSize: const Size(48, 48),
                    padding: EdgeInsets.zero,
                  ),
                  icon: const Icon(Icons.check_circle_outline, size: 18),
                  label: const Text('See the accepted answer'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Photo extends StatelessWidget {
  const _Photo({required this.image});
  final ForumImageBlock image;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      image: true,
      // Prefer the author's own alt text, fall back to the image's ROLE on
      // the page — never the upload filename.
      label: image.alt.isNotEmpty
          ? image.alt
          : 'Photo the author submitted for identification',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppSpacing.rSm),
        child: SizedBox(
          width: 96,
          height: 96,
          child: CachedNetworkImage(
            imageUrl: image.url,
            fit: BoxFit.cover,
            placeholder: (context, _) => ColoredBox(
              color: Theme.of(context).colorScheme.surfaceContainerHigh,
            ),
            errorWidget: (context, _, _) => Icon(
              Icons.broken_image_outlined,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ),
    );
  }
}

class _CandidateRow extends StatelessWidget {
  const _CandidateRow({required this.candidate});
  final ForumIdentificationCandidate candidate;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  candidate.name,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (candidate.scientificName.isNotEmpty)
                  Text(
                    candidate.scientificName,
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontStyle: FontStyle.italic,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Text(
            '${candidate.confidencePercent}%',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}
