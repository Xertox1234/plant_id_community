/// The product's user-facing identity.
///
/// Before this existed the app showed THREE competing names: "Plant Community"
/// (the `MaterialApp` title and Settings' about row), "PlantID" (home and
/// splash) and "Houseplant MD" (the auth screens) — none of which agreed with
/// the web. The canonical name is **Houseplant MD** (design spec §2.1); the
/// repo/package name `plant_community_mobile` is unchanged and internal.
///
/// "Canopy" names the design language, never the product — do not surface it.
abstract final class AppBrand {
  /// The product name, everywhere a user can read it.
  static const String name = 'Houseplant MD';

  /// Sub-title for the brand block on splash and auth screens (spec §2.1).
  static const String tagline = 'The plant clinic';
}
