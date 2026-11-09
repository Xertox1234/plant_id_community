import 'package:flutter/material.dart';

/// The app router's root Navigator, so the auth listener in `MyApp` (which
/// sits above it) can open the consent sheet over whatever screen is up.
final rootNavigatorKey = GlobalKey<NavigatorState>();
