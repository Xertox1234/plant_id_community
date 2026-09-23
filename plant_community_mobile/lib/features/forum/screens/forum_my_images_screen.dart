import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../widgets/forum_my_images_grid.dart';

/// "My forum photos" (todo 374; web: the settings page's
/// `MyForumImagesSection`): every photo the viewer has shared to the forum,
/// each deletable behind a confirmation. Auth-only route — the backend 401s
/// an anonymous request.
class ForumMyImagesScreen extends StatelessWidget {
  const ForumMyImagesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('My forum photos')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Photos you added to forum posts. Deleting one removes it '
                'from every post that uses it.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              const Expanded(child: ForumMyImagesGrid(allowDelete: true)),
            ],
          ),
        ),
      ),
    );
  }
}
