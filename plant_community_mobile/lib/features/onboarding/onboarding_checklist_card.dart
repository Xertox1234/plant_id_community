import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../shared/widgets/canopy_label.dart';
import '../../shared/widgets/canopy_surfaces.dart';
import 'onboarding_checklist_service.dart';

/// What each server step key reads as, and where doing it happens.
/// A key the app does not know (a newer server) is skipped.
const Map<String, ({String label, String route})> onboardingSteps = {
  'identify_plant': (
    label: 'Identify your first plant',
    route: AppRoutes.camera,
  ),
  'forum_post': (label: 'Say hello in the forum', route: AppRoutes.forum),
  'profile': (label: 'Add a photo or a short bio', route: AppRoutes.profile),
};

/// The onboarding checklist on the home screen (todo 412, owner decision
/// 2026-09-26). Shown to a signed-in user until every step is done or they
/// dismiss it; otherwise it takes no space at all.
class OnboardingChecklistCard extends ConsumerWidget {
  const OnboardingChecklistCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final checklist = ref.watch(onboardingChecklistServiceProvider).value;
    if (checklist == null || !checklist.visible) return const SizedBox.shrink();

    final steps = [
      for (final step in checklist.steps)
        if (onboardingSteps.containsKey(step.key)) step,
    ];
    if (steps.isEmpty) return const SizedBox.shrink();
    final done = steps.where((step) => step.done).length;
    final ext = context.canopy;

    return Padding(
      padding: EdgeInsets.only(bottom: ext.gapY * 2),
      child: CanopyCard(
        radius: AppSpacing.rLg,
        padding: EdgeInsets.all(ext.padCard),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(child: CanopyLabel('Getting started')),
                TextButton(
                  onPressed: () => ref
                      .read(onboardingChecklistServiceProvider.notifier)
                      .dismiss(),
                  child: const Text('Dismiss'),
                ),
              ],
            ),
            Text(
              '$done of ${steps.length} done',
              style: AppTypography.body.copyWith(color: ext.ink2),
            ),
            SizedBox(height: ext.gapY),
            for (final step in steps)
              _StepRow(
                label: onboardingSteps[step.key]!.label,
                done: step.done,
                onTap: step.done
                    ? null
                    : () async {
                        await context.push(onboardingSteps[step.key]!.route);
                        // Back from the step: the server may now call it done.
                        ref.invalidate(onboardingChecklistServiceProvider);
                      },
              ),
          ],
        ),
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({required this.label, required this.done, this.onTap});

  final String label;
  final bool done;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    // container: one node per row. CanopyCard's own Semantics would merge
    // the rows into the card otherwise, and a screen reader could not pick
    // a step.
    return Semantics(
      container: true,
      label: done ? 'Done: $label' : label,
      button: onTap != null,
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48),
          child: Row(
            children: [
              Icon(
                done ? LucideIcons.circleCheck : LucideIcons.circle,
                size: 22,
                color: done ? cs.primary : cs.onSurfaceVariant,
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: done ? cs.onSurfaceVariant : cs.onSurface,
                    decoration: done ? TextDecoration.lineThrough : null,
                  ),
                ),
              ),
              if (!done)
                Icon(
                  LucideIcons.chevronRight,
                  size: 18,
                  color: cs.onSurfaceVariant,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
