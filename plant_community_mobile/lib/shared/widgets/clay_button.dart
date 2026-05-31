import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';

enum ClayButtonVariant { primary, secondary, outline }

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
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool fullWidth;
  final ClayButtonSize size;
  final ClayButtonVariant variant;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;
    final isDisabled = onPressed == null;

    final Color bg;
    final Color fg;
    final List<BoxShadow> shadow;

    switch (variant) {
      case ClayButtonVariant.primary:
        bg = isDisabled ? cs.surfaceContainerHighest : ext.clay;
        fg = isDisabled ? cs.onSurface.withValues(alpha: 0.38) : ext.onClay;
        shadow = isDisabled ? const [] : ext.shadow1;
      case ClayButtonVariant.secondary:
        bg = isDisabled ? cs.surfaceContainerHighest : cs.primary;
        fg = isDisabled ? cs.onSurface.withValues(alpha: 0.38) : cs.onPrimary;
        shadow = isDisabled ? const [] : ext.shadow1;
      case ClayButtonVariant.outline:
        bg = Colors.transparent;
        fg = isDisabled ? cs.onSurface.withValues(alpha: 0.38) : cs.primary;
        shadow = const [];
    }

    final (double vPad, double hPad, double fontSize) = switch (size) {
      ClayButtonSize.small => (AppSpacing.sm, AppSpacing.md, 14.0),
      ClayButtonSize.medium => (AppSpacing.md, AppSpacing.lg, 16.0),
      ClayButtonSize.large => (AppSpacing.lg, AppSpacing.xl, 16.0),
    };

    final border = variant == ClayButtonVariant.outline
        ? Border.all(
            color: isDisabled
                ? cs.onSurface.withValues(alpha: 0.12)
                : cs.primary,
          )
        : null;

    final button = Container(
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSpacing.rPill),
        border: border,
        boxShadow: shadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: isDisabled ? null : onPressed,
          borderRadius: BorderRadius.circular(AppSpacing.rPill),
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: hPad, vertical: vPad),
            child: Row(
              mainAxisSize: fullWidth ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    color: fg,
                    fontSize: fontSize,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (icon != null) ...[
                  const SizedBox(width: AppSpacing.sm),
                  Icon(icon, color: fg, size: fontSize + 2),
                ],
              ],
            ),
          ),
        ),
      ),
    );

    if (fullWidth) {
      return SizedBox(width: double.infinity, child: button);
    }
    return button;
  }
}
