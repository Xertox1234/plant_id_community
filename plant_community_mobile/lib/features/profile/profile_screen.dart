import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/user_profile.dart';
import '../../services/user_profile_service.dart';
import '../../services/auth_service.dart';

/// User profile screen displaying user information and settings
///
/// Features:
/// - Profile header with avatar, name, email
/// - Stats (plants identified, collections, forum posts)
/// - Profile details (bio, location, website, experience)
/// - Settings (notifications, privacy)
/// - Logout button
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profileAsync = ref.watch(userProfileServiceProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          // Edit button (navigate to edit screen - not implemented yet)
          IconButton(
            icon: const Icon(Icons.edit),
            onPressed: () {
              // TODO: Navigate to profile edit screen
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Edit profile coming soon!'),
                ),
              );
            },
          ),
        ],
      ),
      body: profileAsync.when(
        data: (profile) {
          if (profile == null) {
            return const Center(
              child: Text('No profile data available'),
            );
          }

          return RefreshIndicator(
            onRefresh: () async {
              await ref.read(userProfileServiceProvider.notifier).refresh();
            },
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Profile Header
                  _ProfileHeader(profile: profile),

                  const SizedBox(height: 24),

                  // Stats Cards
                  _StatsSection(profile: profile),

                  const SizedBox(height: 24),

                  // Profile Details Section
                  _ProfileDetailsSection(profile: profile),

                  const SizedBox(height: 24),

                  // Settings Section
                  _SettingsSection(profile: profile),

                  const SizedBox(height: 24),

                  // Logout Button
                  _LogoutButton(),

                  const SizedBox(height: 24),
                ],
              ),
            ),
          );
        },
        loading: () => const Center(
          child: CircularProgressIndicator(),
        ),
        error: (error, stack) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(
                'Failed to load profile',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                error.toString(),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: () {
                  ref.read(userProfileServiceProvider.notifier).refresh();
                },
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Profile header with avatar, name, and email
class _ProfileHeader extends StatelessWidget {
  final UserProfile profile;

  const _ProfileHeader({required this.profile});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // Avatar
            CircleAvatar(
              radius: 50,
              backgroundColor: Theme.of(context).colorScheme.primaryContainer,
              backgroundImage: profile.avatar != null
                  ? NetworkImage(profile.avatar!)
                  : null,
              child: profile.avatar == null
                  ? Text(
                      profile.username.substring(0, 1).toUpperCase(),
                      style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                            color: Theme.of(context).colorScheme.onPrimaryContainer,
                          ),
                    )
                  : null,
            ),

            const SizedBox(height: 16),

            // Display name
            Text(
              profile.fullName,
              style: Theme.of(context).textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),

            const SizedBox(height: 4),

            // Username
            Text(
              '@${profile.username}',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
            ),

            const SizedBox(height: 4),

            // Email
            Text(
              profile.email,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Stats section showing user metrics
class _StatsSection extends StatelessWidget {
  final UserProfile profile;

  const _StatsSection({required this.profile});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _StatCard(
            label: 'Plants Identified',
            value: profile.plantsIdentified.toString(),
            icon: Icons.eco,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatCard(
            label: 'Collections',
            value: profile.plantCollectionsCount.toString(),
            icon: Icons.collections_bookmark,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatCard(
            label: 'Forum Posts',
            value: profile.forumPostsCount.toString(),
            icon: Icons.forum,
          ),
        ),
      ],
    );
  }
}

/// Individual stat card
class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;

  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Icon(
              icon,
              size: 32,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

/// Profile details section showing bio, location, etc.
class _ProfileDetailsSection extends StatelessWidget {
  final UserProfile profile;

  const _ProfileDetailsSection({required this.profile});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Profile Details',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const Divider(),

            // Bio
            if (profile.bio != null && profile.bio!.isNotEmpty) ...[
              _DetailRow(
                icon: Icons.info_outline,
                label: 'Bio',
                value: profile.bio!,
              ),
              const SizedBox(height: 12),
            ],

            // Location
            if (profile.location != null && profile.location!.isNotEmpty) ...[
              _DetailRow(
                icon: Icons.location_on_outlined,
                label: 'Location',
                value: profile.location!,
              ),
              const SizedBox(height: 12),
            ],

            // Website
            if (profile.website != null && profile.website!.isNotEmpty) ...[
              _DetailRow(
                icon: Icons.link,
                label: 'Website',
                value: profile.website!,
              ),
              const SizedBox(height: 12),
            ],

            // Gardening Experience
            if (profile.gardeningExperience != null &&
                profile.gardeningExperience!.isNotEmpty) ...[
              _DetailRow(
                icon: Icons.emoji_events_outlined,
                label: 'Experience',
                value: profile.gardeningExperience!,
              ),
              const SizedBox(height: 12),
            ],

            // Member since
            _DetailRow(
              icon: Icons.calendar_today_outlined,
              label: 'Member Since',
              value: _formatDate(profile.dateJoined),
            ),
          ],
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    final months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec'
    ];
    return '${months[date.month - 1]} ${date.year}';
  }
}

/// Detail row displaying an icon, label, and value
class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          icon,
          size: 20,
          color: Theme.of(context).colorScheme.secondary,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                value,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Settings section for notifications and privacy
class _SettingsSection extends ConsumerWidget {
  final UserProfile profile;

  const _SettingsSection({required this.profile});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Settings',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const Divider(),

            // Email Notifications
            SwitchListTile(
              title: const Text('Email Notifications'),
              subtitle: const Text('Receive email updates'),
              value: profile.emailNotifications,
              onChanged: (value) async {
                try {
                  await ref.read(userProfileServiceProvider.notifier).updateProfile(
                        emailNotifications: value,
                      );
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Failed to update preferences: $e'),
                        backgroundColor: Theme.of(context).colorScheme.error,
                      ),
                    );
                    // Refresh to revert UI to actual backend state
                    ref.read(userProfileServiceProvider.notifier).refresh();
                  }
                }
              },
              secondary: const Icon(Icons.email_outlined),
            ),

            // Plant ID Notifications
            SwitchListTile(
              title: const Text('Plant ID Notifications'),
              subtitle: const Text('Get notified about plant identifications'),
              value: profile.plantIdNotifications,
              onChanged: (value) async {
                try {
                  await ref.read(userProfileServiceProvider.notifier).updateProfile(
                        plantIdNotifications: value,
                      );
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Failed to update preferences: $e'),
                        backgroundColor: Theme.of(context).colorScheme.error,
                      ),
                    );
                    // Refresh to revert UI to actual backend state
                    ref.read(userProfileServiceProvider.notifier).refresh();
                  }
                }
              },
              secondary: const Icon(Icons.eco),
            ),

            // Forum Notifications
            SwitchListTile(
              title: const Text('Forum Notifications'),
              subtitle: const Text('Get notified about forum activity'),
              value: profile.forumNotifications,
              onChanged: (value) async {
                try {
                  await ref.read(userProfileServiceProvider.notifier).updateProfile(
                        forumNotifications: value,
                      );
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Failed to update preferences: $e'),
                        backgroundColor: Theme.of(context).colorScheme.error,
                      ),
                    );
                    // Refresh to revert UI to actual backend state
                    ref.read(userProfileServiceProvider.notifier).refresh();
                  }
                }
              },
              secondary: const Icon(Icons.forum),
            ),

            const Divider(),

            // Privacy settings
            ListTile(
              leading: const Icon(Icons.visibility_outlined),
              title: const Text('Profile Visibility'),
              subtitle: Text(profile.profileVisibility),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                // TODO: Show profile visibility selector
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Profile visibility selector coming soon!'),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// Logout button
class _LogoutButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return OutlinedButton.icon(
      onPressed: () async {
        // Show confirmation dialog
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Logout'),
            content: const Text('Are you sure you want to logout?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Logout'),
              ),
            ],
          ),
        );

        if (confirmed == true) {
          // Check context is still mounted before async operation
          if (!context.mounted) return;

          try {
            // Logout
            await ref.read(authServiceProvider.notifier).signOut();

            // Clear profile
            ref.read(userProfileServiceProvider.notifier).clear();

            // Check context is still mounted after async operation
            if (!context.mounted) return;

            // Show success message
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Logged out successfully'),
              ),
            );

            // Navigate to login screen (TODO: implement navigation)
          } catch (e) {
            if (!context.mounted) return;

            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Logout failed: $e'),
                backgroundColor: Theme.of(context).colorScheme.error,
              ),
            );
          }
        }
      },
      icon: const Icon(Icons.logout),
      label: const Text('Logout'),
      style: OutlinedButton.styleFrom(
        foregroundColor: Theme.of(context).colorScheme.error,
        side: BorderSide(color: Theme.of(context).colorScheme.error),
      ),
    );
  }
}
