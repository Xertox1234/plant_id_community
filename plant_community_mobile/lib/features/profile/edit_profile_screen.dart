import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/routing/app_router.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../models/user_profile.dart';
import '../../services/api_service.dart';
import '../../services/user_profile_service.dart';
import '../../shared/widgets/canopy_surfaces.dart';

/// Mirrors the backend `bio` column (`max_length=500` on `users.User`).
const int profileBioMaxLength = 500;

/// Mirrors the backend avatar cap (`MAX_AVATAR_SIZE` in
/// `apps/core/validators.py`).
const int avatarMaxUploadBytes = 2 * 1024 * 1024;

/// Picks the avatar photo. An interface so widget tests inject a fake
/// without platform channels, like `ForumImagePicker` and
/// `DiagnoseImagePicker`.
abstract class ProfileAvatarPicker {
  /// The picked file's path, or null if the user cancelled. Throws
  /// [ApiException] (413) when the photo is over [avatarMaxUploadBytes],
  /// before the bytes go over the wire.
  Future<String?> pick();
}

class DeviceProfileAvatarPicker implements ProfileAvatarPicker {
  const DeviceProfileAvatarPicker({ImagePicker? picker}) : _picker = picker;

  final ImagePicker? _picker;

  /// The backend keeps the original and serves a 150 px thumbnail, so an
  /// avatar never needs a phone camera's full resolution. Bounding the pick
  /// keeps a current phone photo under the 2 MB cap and inside the 4096 px
  /// limit. Unlike the forum picker nothing here needs the bytes exact (an
  /// animated GIF avatar flattening to one frame is fine).
  static const double maxEdgePx = 1024;
  static const int imageQuality = 85;

  @override
  Future<String?> pick() async {
    final file = await (_picker ?? ImagePicker()).pickImage(
      source: ImageSource.gallery,
      maxWidth: maxEdgePx,
      maxHeight: maxEdgePx,
      imageQuality: imageQuality,
    );
    if (file == null) return null;
    if (await file.length() > avatarMaxUploadBytes) {
      throw ApiException(
        'That photo is over 2 MB. Pick a smaller one.',
        statusCode: 413,
      );
    }
    return file.path;
  }
}

/// Edit the signed-in user's bio and avatar (todo 455).
///
/// Opened from the Profile tab's pencil and from the onboarding checklist's
/// "profile" step. The route is auth-protected in the router. The avatar
/// uploads as soon as it is picked; the bio saves with the Save button.
class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({
    super.key,
    this.avatarPicker = const DeviceProfileAvatarPicker(),
  });

  /// Wrapped behind an interface so tests can inject a fake.
  final ProfileAvatarPicker avatarPicker;

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _bioController = TextEditingController();
  bool _bioLoaded = false;
  bool _saving = false;
  bool _uploading = false;

  @override
  void dispose() {
    _bioController.dispose();
    super.dispose();
  }

  void _showError(Object error) {
    if (!mounted) return;
    final message = error is UserProfileException
        ? error.message
        : error is ApiException
        ? error.message
        : '$error';
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Theme.of(context).colorScheme.error,
      ),
    );
  }

  Future<void> _changePhoto() async {
    final String? path;
    try {
      path = await widget.avatarPicker.pick();
    } catch (e) {
      _showError(e);
      return;
    }
    if (path == null || !mounted) return;
    setState(() => _uploading = true);
    try {
      await ref.read(userProfileServiceProvider.notifier).uploadAvatar(path);
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Photo updated')));
    } catch (e) {
      _showError(e);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref
          .read(userProfileServiceProvider.notifier)
          .updateProfile(bio: _bioController.text.trim());
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Profile saved')));
      if (context.canPop()) {
        context.pop();
      } else {
        context.go(AppRoutes.profile);
      }
    } catch (e) {
      _showError(e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(userProfileServiceProvider);
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final busy = _saving || _uploading;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit profile'),
        actions: [
          TextButton(
            onPressed: busy || profileAsync.value == null ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Save'),
          ),
        ],
      ),
      body: switch (profileAsync) {
        AsyncData(:final value) when value != null => _form(value, ext, busy),
        AsyncError(:final error) => Center(
          child: Padding(
            padding: EdgeInsets.all(ext.padScreen),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Could not load your profile',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  error is UserProfileException ? error.message : '$error',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () =>
                      ref.read(userProfileServiceProvider.notifier).refresh(),
                  icon: const Icon(LucideIcons.refreshCw),
                  label: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
        _ => const Center(child: CircularProgressIndicator()),
      },
    );
  }

  Widget _form(UserProfile profile, GreenThumbExtension ext, bool busy) {
    if (!_bioLoaded) {
      _bioController.text = profile.bio ?? '';
      _bioLoaded = true;
    }
    final cs = Theme.of(context).colorScheme;
    final avatarUrl = profile.avatar;

    return SingleChildScrollView(
      padding: EdgeInsets.all(ext.padScreen),
      child: CanopyCard(
        padding: EdgeInsets.all(ext.padCard),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Semantics(
                label: avatarUrl == null
                    ? 'No profile photo'
                    : 'Your profile photo',
                image: true,
                child: CircleAvatar(
                  radius: 48,
                  backgroundColor: cs.primaryContainer,
                  backgroundImage: avatarUrl != null
                      ? NetworkImage(avatarUrl)
                      : null,
                  onBackgroundImageError: avatarUrl != null
                      ? (error, _) {
                          if (kDebugMode) {
                            debugPrint('[EDIT_PROFILE] Avatar failed: $error');
                          }
                        }
                      : null,
                  child: _uploading
                      ? const CircularProgressIndicator()
                      : avatarUrl == null
                      ? Icon(LucideIcons.user, size: 40, color: cs.primary)
                      : null,
                ),
              ),
            ),
            SizedBox(height: ext.gapY),
            Center(
              child: TextButton.icon(
                onPressed: busy ? null : _changePhoto,
                icon: const Icon(LucideIcons.camera),
                label: Text(avatarUrl == null ? 'Add photo' : 'Change photo'),
              ),
            ),
            SizedBox(height: ext.gapY * 2),
            TextField(
              controller: _bioController,
              enabled: !_saving,
              maxLength: profileBioMaxLength,
              minLines: 3,
              maxLines: 6,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Bio',
                hintText: 'What do you grow? What are you learning?',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
