import 'package:flutter/material.dart';

/// The app's one ScaffoldMessenger, so services with no BuildContext (the
/// auth error SnackBar, the foreground push banner, todo 621) can reach it.
final rootScaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();
