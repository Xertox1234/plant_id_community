import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/green_thumb_extension.dart';

/// The Canopy button — the Flutter counterpart of the web's `Button` /
/// `ButtonLink` recipes (`web/src/components/ui/buttonStyles.ts`).
///
/// Variants map one-to-one with the web's:
///
/// | variant     | web recipe                                            |
/// |-------------|-------------------------------------------------------|
/// | [primary]   | `canopy-cta shadow-1` — the mint→sage gradient CTA     |
/// | [secondary] | `bg-surface-2 text-ink border border-line`             |
/// | [outline]   | `border border-line-2 text-ink`                        |
/// | [ghost]     | `text-ink-2`, surface-2 fill on interaction            |
///
/// The gradient primary is why this exists rather than a themed `FilledButton`:
/// Flutter's `ButtonStyle` has no gradient slot. `FilledButton` is themed to
/// the flat primary colour and remains fine for secondary actions.
enum ClayButtonVariant { primary, secondary, outline, ghost }

/// Sizes follow the web's `sm` / `md` / `lg`: `px-3 py-1.5 text-sm`,
/// `px-4 py-2 text-base`, `px-6 py-3 text-lg`.
enum ClayButtonSize { small, medium, large }

class ClayButton extends StatelessWidget {
  const ClayButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.fullWidth = false,
    this.size = ClayButtonSize.large,
    this.variant = ClayButtonVariant.primary,
    this.loading = false,
    this.loadingLabel,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool fullWidth;
  final ClayButtonSize size;
  final ClayButtonVariant variant;

  /// Disables the button and shows a spinner.
  final bool loading;

  /// Shown in place of [label] while [loading] (e.g. "Posting…"). A visible
  /// label swap is the most reliable "busy" signal for a screen reader; the
  /// button is also flagged busy either way.
  final String? loadingLabel;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = context.canopy;
    final isDisabled = onPressed == null || loading;

    final (double hPad, double vPad, TextStyle textStyle) = switch (size) {
      ClayButtonSize.small => (12.0, 6.0, AppTypography.buttonSm),
      ClayButtonSize.medium => (16.0, 8.0, AppTypography.button),
      ClayButtonSize.large => (24.0, 12.0, AppTypography.buttonLg),
    };

    // The web uses `disabled:opacity-50` on the whole control. Flutter has no
    // equivalent in BoxDecoration, so the wrapper below applies the opacity —
    // which keeps the gradient, border and text fading together as one piece
    // rather than each guessing its own disabled colour.
    Gradient? gradient;
    Color? fill;
    Color foreground;
    Border? border;
    List<BoxShadow> shadow = const [];

    switch (variant) {
      case ClayButtonVariant.primary:
        gradient = ext.ctaGradient;
        foreground = cs.onPrimary;
        shadow = ext.shadow1;
      case ClayButtonVariant.secondary:
        fill = ext.surface2;
        foreground = cs.onSurface;
        border = Border.all(color: ext.line);
      case ClayButtonVariant.outline:
        fill = Colors.transparent;
        foreground = cs.onSurface;
        border = Border.all(color: ext.line2);
      case ClayButtonVariant.ghost:
        fill = Colors.transparent;
        foreground = ext.ink2;
    }

    final radius = BorderRadius.circular(AppSpacing.rPill);
    final shownLabel = loading ? (loadingLabel ?? label) : label;

    Widget button = DecoratedBox(
      decoration: BoxDecoration(
        // The fill is UNCHANGED when disabled — the `Opacity` wrapper below
        // fades the whole control, exactly as the web's `disabled:opacity-50`
        // does. Swapping the gradient for a flat `surface3` made the disabled
        // primary invisible in light mode: surface3 is near-white there, and
        // near-white at 50% on a mint ground has almost no contrast.
        gradient: gradient,
        color: fill,
        borderRadius: radius,
        border: border,
        // The shadow is the exception: a lifted shadow on a dead control reads
        // as interactive.
        boxShadow: isDisabled ? const [] : shadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: isDisabled ? null : onPressed,
          borderRadius: radius,
          // The app-wide focus accent — the web rings every button in secondary.
          focusColor: cs.secondary.withValues(alpha: 0.24),
          splashColor: cs.secondary.withValues(alpha: 0.16),
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: hPad, vertical: vPad),
            child: Row(
              mainAxisSize: fullWidth ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (loading) ...[
                  SizedBox(
                    width: textStyle.fontSize,
                    height: textStyle.fontSize,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation(foreground),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                ],
                Flexible(
                  child: Text(
                    shownLabel,
                    style: textStyle.copyWith(color: foreground),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (icon != null && !loading) ...[
                  const SizedBox(width: AppSpacing.sm),
                  Icon(icon, color: foreground, size: textStyle.fontSize! + 2),
                ],
              ],
            ),
          ),
        ),
      ),
    );

    if (isDisabled) {
      button = Opacity(opacity: 0.5, child: button);
    }
    if (fullWidth) {
      button = SizedBox(width: double.infinity, child: button);
    }
    return Semantics(button: true, enabled: !isDisabled, child: button);
  }
}
