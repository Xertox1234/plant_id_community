import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

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
    required this.label,
  });

  final String route;

  /// One glyph for both states. Lucide is an all-outlined set with no filled
  /// variants, so selection is carried by colour and the indicator pill —
  /// exactly how the web's sidebar marks its active item. The previous
  /// outlined/filled pair was a Material idiom the web never had.
  final IconData icon;

  final String label;
}

/// Primary navigation shell: four tabs plus a floating Identify action.
///
/// Before this existed the app had no primary navigation at all — from a cold
/// launch a user could reach Settings and the camera, and `/profile` (and so
/// sign-in, which only `profile_screen.dart` links to) was reachable from
/// nothing. See todo 384.
///
/// Identify is a floating action rather than a fifth tab: it is the app's core
/// verb, and `/camera` lives on the ROOT navigator, not in a branch, so the
/// nav bar disappears during capture and backing out returns to whichever tab
/// the user came from.
///
/// **One floating button per screen** (owner decision 2026-10-18, option 2 in
/// `plant_community_mobile/docs/patterns/flutter-ui-design.md` Part 1b). The
/// camera sits bottom-right and is shown only where the screen has no primary
/// action of its own; see [ownsPrimaryAction]. Before this, a centred shell
/// FAB covered the last row of every list and collided with the screens' own
/// FABs ("New topic" was clipped to "New to").
///
/// **This must stay a [StatelessWidget], not a `ConsumerWidget`.**
/// `test/routing/app_router_test.dart` pumps `MaterialApp.router` with no
/// `ProviderScope` in the widget tree in most of its ~40 tests; that works only
/// because nothing in the shell reads a provider. `StatefulShellRoute` hands us
/// [navigationShell] as a constructor argument, so no read is needed. Adding
/// one (a Forum unread badge, say) means wrapping it in a `Consumer` and
/// wrapping those tests in a scope — do that deliberately, not by accident.
class MainShell extends StatelessWidget {
  const MainShell({
    super.key,
    required this.navigationShell,
    required this.location,
  });

  /// Supplied by `StatefulShellRoute.indexedStack`; also the branch switcher.
  final StatefulNavigationShell navigationShell;

  /// The current path, from the shell builder's `state.uri.path`. A plain
  /// argument rather than a provider read: see the class doc on why this
  /// stays a [StatelessWidget].
  final String location;

  /// Key for the shell's Identify FAB, so tests can tell it from a screen's.
  static const identifyFabKey = ValueKey<String>('shellIdentifyFab');

  /// Height of a standard FAB plus its 16px float margin: how far a list's
  /// end must sit above the bottom for its last row to clear the FAB.
  static const fabClearance = 56.0 + 16.0;

  /// Screens that own the bottom-right corner, where the Identify FAB is
  /// hidden. Either they have a FAB of their own, or a composer whose send
  /// button and input sit at the bottom (owner call 2026-10-21). When a
  /// screen's own FAB is conditionally absent (signed out, locked thread) the
  /// camera stays hidden too; it is one tab away.
  static final List<RegExp> _ownPrimaryActionRoutes = <RegExp>[
    RegExp('^${AppRoutes.garden}\$'), // garden_screen.dart: "Add plant"
    RegExp(r'^/forum/boards/[^/]+$'), // forum_topics_screen.dart: "New topic"
    RegExp(r'^/forum/topics/[^/]+$'), // forum_thread_screen.dart: "Reply"
    RegExp(r'^/forum/compose$'),
    RegExp('^${AppRoutes.forumMessages}/[^/]+\$'), // a DM conversation
    // A group conversation, and the new-group form at /forum/groups/new.
    RegExp('^${AppRoutes.forumGroups}/[^/]+\$'),
  ];

  /// Bottom padding a scroll view under this shell adds INSIDE its own
  /// padding, so content scrolls beneath the Identify FAB yet its last row
  /// ends clear of it. Zero where the FAB is hidden, or outside the shell.
  static EdgeInsets fabClearanceOf(BuildContext context) => EdgeInsets.only(
    bottom:
        context
            .dependOnInheritedWidgetOfExactType<_FabClearance>()
            ?.clearance ??
        0,
  );

  /// Whether the screen at [path] owns the corner the Identify FAB sits in.
  static bool ownsPrimaryAction(String path) =>
      _ownPrimaryActionRoutes.any((RegExp r) => r.hasMatch(path));

  /// Order matters: this is index-aligned with the branch order in
  /// `app_router.dart`, because [StatefulNavigationShell.goBranch] addresses
  /// branches positionally.
  static const List<ShellDestination> destinations = <ShellDestination>[
    ShellDestination(
      route: AppRoutes.home,
      icon: LucideIcons.house,
      label: 'Home',
    ),
    ShellDestination(
      route: AppRoutes.collection,
      icon: LucideIcons.leaf,
      label: 'My Plants',
    ),
    ShellDestination(
      route: AppRoutes.forum,
      icon: LucideIcons.messagesSquare,
      label: 'Forum',
    ),
    ShellDestination(
      route: AppRoutes.profile,
      icon: LucideIcons.user,
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
    final showIdentify = !ownsPrimaryAction(location);
    // No AppBar here on purpose: all 23 screens build their own Scaffold and
    // AppBar, so a shell-level one would double every header.
    return Scaffold(
      // Always wrapped, so toggling the FAB never changes navigationShell's
      // parent chain. NOT a MediaQuery padding: screens wrap their scroll
      // views in SafeArea, which would consume it OUTSIDE the scroll view and
      // clip every list 72px above the bar (seen on the simulator). Screens
      // add [fabClearanceOf] inside their own scroll padding instead.
      body: _FabClearance(
        clearance: showIdentify ? fabClearance : 0,
        child: navigationShell,
      ),
      floatingActionButton: showIdentify
          ? FloatingActionButton(
              key: identifyFabKey,
              // An explicit tag is REQUIRED, not cosmetic. `indexedStack`
              // keeps every branch alive at once and the shell sits inside the
              // root navigator's page, so this FAB shares a Hero subtree with
              // every screen in every branch -- including a garden or forum
              // FAB kept alive in a branch the user has left. Two
              // default-tagged FABs in one subtree throw "multiple heroes
              // share the same tag". No test fails without it any more (checked
              // 2026-10-21), because the shell FAB is now hidden where a screen
              // has its own; keep it for the kept-alive branch case.
              heroTag: 'shellIdentifyFab',
              tooltip: 'Identify a plant',
              onPressed: () => context.push(AppRoutes.camera),
              child: const Icon(LucideIcons.camera),
            )
          : null,
      // endFloat: the corner a screen's own FAB uses, so the two can never
      // both show (see [ownsPrimaryAction]). The old centre placement also
      // straddled the boundary between destinations 1 and 2 of four.
      // Asserted by 'the Identify FAB never covers a tab selection indicator'
      // in test/routing/navigation_shell_test.dart.
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: _onDestinationSelected,
        destinations: <Widget>[
          for (final ShellDestination d in destinations)
            NavigationDestination(
              icon: Icon(d.icon),
              label: d.label,
              tooltip: d.label,
            ),
        ],
      ),
    );
  }
}

class _FabClearance extends InheritedWidget {
  const _FabClearance({required this.clearance, required super.child});

  final double clearance;

  @override
  bool updateShouldNotify(_FabClearance oldWidget) =>
      clearance != oldWidget.clearance;
}
