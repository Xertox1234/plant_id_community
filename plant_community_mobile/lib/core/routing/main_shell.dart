import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'app_router.dart';

/// A top-level destination in [MainShell]'s navigation bar.
///
/// The `route` values here are load-bearing beyond documentation:
/// `scripts/check_flutter_route_reachability.py` rule D counts a
/// `StatefulShellBranch` root as reachable only when this file mentions the
/// matching `AppRoutes` constant. Declare a branch without a destination and
/// the checker reports it as an orphan, which is the intended behaviour.
class ShellDestination {
  const ShellDestination({
    required this.route,
    required this.icon,
    required this.selectedIcon,
    required this.label,
  });

  final String route;
  final IconData icon;
  final IconData selectedIcon;
  final String label;
}

/// Primary navigation shell: four tabs plus a raised Identify action.
///
/// Before this existed the app had no primary navigation at all — from a cold
/// launch a user could reach Settings and the camera, and `/profile` (and so
/// sign-in, which only `profile_screen.dart` links to) was reachable from
/// nothing. See todo 384.
///
/// Identify is a centre action rather than a fifth tab: it is the app's core
/// verb, and `/camera` lives on the ROOT navigator, not in a branch, so the
/// nav bar disappears during capture and backing out returns to whichever tab
/// the user came from.
///
/// **This must stay a [StatelessWidget], not a `ConsumerWidget`.**
/// `test/routing/app_router_test.dart` pumps `MaterialApp.router` with no
/// `ProviderScope` in the widget tree in most of its ~40 tests; that works only
/// because nothing in the shell reads a provider. `StatefulShellRoute` hands us
/// [navigationShell] as a constructor argument, so no read is needed. Adding
/// one (a Forum unread badge, say) means wrapping it in a `Consumer` and
/// wrapping those tests in a scope — do that deliberately, not by accident.
class MainShell extends StatelessWidget {
  const MainShell({super.key, required this.navigationShell});

  /// Supplied by `StatefulShellRoute.indexedStack`; also the branch switcher.
  final StatefulNavigationShell navigationShell;

  /// Order matters: this is index-aligned with the branch order in
  /// `app_router.dart`, because [StatefulNavigationShell.goBranch] addresses
  /// branches positionally.
  static const List<ShellDestination> destinations = <ShellDestination>[
    ShellDestination(
      route: AppRoutes.home,
      icon: Icons.home_outlined,
      selectedIcon: Icons.home,
      label: 'Home',
    ),
    ShellDestination(
      route: AppRoutes.collection,
      icon: Icons.eco_outlined,
      selectedIcon: Icons.eco,
      label: 'My Plants',
    ),
    ShellDestination(
      route: AppRoutes.forum,
      icon: Icons.forum_outlined,
      selectedIcon: Icons.forum,
      label: 'Forum',
    ),
    ShellDestination(
      route: AppRoutes.profile,
      icon: Icons.person_outline,
      selectedIcon: Icons.person,
      label: 'Profile',
    ),
  ];

  void _onDestinationSelected(int index) {
    // Tapping the tab you are already on pops that branch back to its root,
    // which is the platform convention on both iOS and Android.
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    // No AppBar here on purpose: all 23 screens build their own Scaffold and
    // AppBar, so a shell-level one would double every header.
    return Scaffold(
      body: navigationShell,
      floatingActionButton: FloatingActionButton(
        // An explicit tag is REQUIRED, not cosmetic. `indexedStack` keeps every
        // branch alive at once and the shell sits inside the root navigator's
        // page, so this FAB shares a Hero subtree with every screen in every
        // branch. Several of those have FABs of their own
        // (forum_topics_screen.dart:54, forum_thread_screen.dart:128), and two
        // default-tagged FABs in one subtree throw "multiple heroes share the
        // same tag". Caught by test/routing/app_router_test.dart.
        heroTag: 'shellIdentifyFab',
        tooltip: 'Identify a plant',
        onPressed: () => context.push(AppRoutes.camera),
        child: const Icon(Icons.camera_alt),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: _onDestinationSelected,
        destinations: <Widget>[
          for (final ShellDestination d in destinations)
            NavigationDestination(
              icon: Icon(d.icon),
              selectedIcon: Icon(d.selectedIcon),
              label: d.label,
              tooltip: d.label,
            ),
        ],
      ),
    );
  }
}
