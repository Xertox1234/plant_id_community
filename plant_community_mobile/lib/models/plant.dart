/// Plant identification result
class Plant {
  /// Unique identifier
  final String id;

  /// Common name
  final String name;

  /// Scientific name
  final String scientificName;

  /// Description
  final String description;

  /// Care instructions
  final List<String> care;

  /// Image URL (user's uploaded image)
  final String? imageUrl;

  /// Timestamp of identification
  final DateTime timestamp;

  const Plant({
    required this.id,
    required this.name,
    required this.scientificName,
    required this.description,
    required this.care,
    this.imageUrl,
    required this.timestamp,
  });

  /// Copy with new values
  Plant copyWith({
    String? id,
    String? name,
    String? scientificName,
    String? description,
    List<String>? care,
    String? imageUrl,
    DateTime? timestamp,
  }) {
    return Plant(
      id: id ?? this.id,
      name: name ?? this.name,
      scientificName: scientificName ?? this.scientificName,
      description: description ?? this.description,
      care: care ?? this.care,
      imageUrl: imageUrl ?? this.imageUrl,
      timestamp: timestamp ?? this.timestamp,
    );
  }
}
