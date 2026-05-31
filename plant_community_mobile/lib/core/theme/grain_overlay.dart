import 'package:flutter/material.dart';
import 'green_thumb_extension.dart';

class GrainOverlay extends StatelessWidget {
  const GrainOverlay({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<GreenThumbExtension>();
    if (ext == null || !ext.showGrain) return child;

    return Stack(
      children: [
        child,
        Positioned.fill(
          child: IgnorePointer(
            child: Image.asset(
              'assets/images/grain.png',
              fit: BoxFit.cover,
              color: Colors.black.withValues(alpha: 0.35),
              colorBlendMode: BlendMode.multiply,
            ),
          ),
        ),
      ],
    );
  }
}
