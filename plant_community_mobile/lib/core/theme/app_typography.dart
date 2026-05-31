import 'package:flutter/material.dart';

class AppTypography {
  AppTypography._();

  static const String _display = 'BricolageGrotesque';
  static const String _body = 'Geist';
  static const String _mono = 'GeistMono';

  static const TextStyle display = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 32.0,
    height: 1.02,
    letterSpacing: 32.0 * -0.02,
  );

  static const TextStyle h1 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 28.0,
    height: 1.1,
    letterSpacing: 28.0 * -0.02,
  );

  static const TextStyle h2 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 22.0,
    height: 1.15,
    letterSpacing: 22.0 * -0.02,
  );

  static const TextStyle h3 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 18.0,
    height: 1.2,
    letterSpacing: 18.0 * -0.02,
  );

  static const TextStyle eyebrow = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 11.0,
    letterSpacing: 11.0 * 0.06,
    height: 1.4,
  );

  static const TextStyle body = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 16.0,
    height: 1.625,
  );

  static const TextStyle bodySm = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 14.0,
    height: 1.625,
  );

  static const TextStyle bodyXs = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 12.0,
    height: 1.5,
  );

  static const TextStyle label = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w500,
    fontSize: 14.0,
    height: 1.4,
  );

  static const TextStyle button = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 16.0,
    height: 1.4,
    letterSpacing: 0.25,
  );

  static const TextStyle buttonSm = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 14.0,
    height: 1.4,
    letterSpacing: 0.25,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 12.0,
    height: 1.4,
  );

  static const TextStyle mono = TextStyle(
    fontFamily: _mono,
    fontWeight: FontWeight.w400,
    fontSize: 14.0,
    fontFeatures: [FontFeature.tabularFigures()],
  );
}
