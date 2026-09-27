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
/// [push] is for a route outside the tab shell (the camera); a tab's root is
/// switched to with `go`, never pushed on top of another branch. A key the
/// app does not know (a newer server) is skipped.
const Map<String, ({String label, String route, bool push})> onboardingSteps = {
  'identify_plant': (
    label: 'Identify your first plant',
    route: AppRoutes.camera,
    push: true,
  ),
  'forum_post': (
    label: 'Say hello in the forum',
    route: AppRoutes.forum,
    push: false,
  ),
  'save_topic': (
    label: 'Save a topic to read later',
    route: AppRoutes.forum,
    push: false,
  ),
};

/// The onboarding checklist on the home screen (todo 412, owner decisions
/// 2026-09-26). Shown to a signed-in user until every step is done or they
/// dismiss it; otherwise it takes no space at all.
///
/// Home stays mounted in the tab shell, and a step can be done anywhere
/// (the camera replaces itself with the results screen; the forum is another
/// tab), so the card refreshes whenever the router lands on Home and when
/// the app resumes, rather than waiting on a pushed route's result.
class OnboardingChecklistCard extends ConsumerStatefulWidget {
  const OnboardingChecklistCard({super.key});

  @override
  ConsumerState<OnboardingChecklistCard> createState() =>
      _OnboardingChecklistCardState();
}

class _OnboardingChecklistCardState
    extends ConsumerState<OnboardingChecklistCard> {
  GoRouter? _router;
  late final AppLifecycleListener _lifecycle;

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onResume: _refresh);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final router = GoRouter.maybeOf(context);
    if (!identical(router, _router)) {
      _router?.routerDelegate.removeListener(_onRouteChanged);
      _router = router;
      _router?.routerDelegate.addListener(_onRouteChanged);
    }
  }

  @override
  void dispose() {
    _router?.routerDelegate.removeListener(_onRouteChanged);
    _lifecycle.dispose();
    super.dispose();
  }

  void _onRouteChanged() {
    final path = _router?.routerDelegate.currentConfiguration.uri.path;
    if (path == AppRoutes.home) _refresh();
  }

  void _refresh() {
    if (!mounted) return;
    final current = ref.read(onboardingChecklistServiceProvider).value;
    // Complete or dismissed never comes back: no need to ask again.
    if (current != null && !current.visible) return;
    ref.invalidate(onboardingChecklistServiceProvider);
  }

  @override
  Widget build(BuildContext context) {
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
                    : () {
                        final spec = onboardingSteps[step.key]!;
                        if (spec.push) {
                          context.push(spec.route);
                        } else {
                          context.go(spec.route);
                        }
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
