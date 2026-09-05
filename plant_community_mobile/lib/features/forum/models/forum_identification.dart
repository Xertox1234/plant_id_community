import 'forum_body_block.dart';

/// One candidate the Plant ID app suggested — `{name, scientific_name,
/// confidence}`, confidence 0–1 (`IDENTIFICATION_CANDIDATE_SCHEMA`).
class ForumIdentificationCandidate {
  const ForumIdentificationCandidate({
    required this.name,
    required this.scientificName,
    required this.confidence,
  });

  final String name;

  /// `''` when the provider gave none.
  final String scientificName;

  /// 0–1 from the backend; rendered as a percentage like the identify screen.
  final double confidence;

  int get confidencePercent => (confidence * 100).round();

  factory ForumIdentificationCandidate.fromJson(Map<String, dynamic> json) {
    final raw = json['confidence'];
    return ForumIdentificationCandidate(
      name: json['name'] as String? ?? '',
      scientificName: json['scientific_name'] as String? ?? '',
      confidence: raw is num ? raw.toDouble().clamp(0.0, 1.0) : 0.0,
    );
  }
}

/// The plant-ID SNAPSHOT a topic carries (audit M6; todo 341 wave 3) —
/// detail payload only. Author-supplied, not a verified determination: the
/// backend records what the app suggested to the person who posted, so the
/// card labels it as such and never presents it as an authoritative ID.
///
/// Nothing here is ever re-fetched or re-run: `identification_result_id` is
/// deliberately not serialized by the backend, so there is nothing to look
/// up. [image] is `null` when the photo was never attached or has since
/// been deleted (the FK is SET_NULL) — a real state, not an error.
class ForumIdentification {
  const ForumIdentification({
    this.image,
    required this.provider,
    required this.candidates,
    this.createdAt,
  });

  final ForumImageBlock? image;

  /// `''` when unknown.
  final String provider;
  final List<ForumIdentificationCandidate> candidates;
  final DateTime? createdAt;

  factory ForumIdentification.fromJson(Map<String, dynamic> json) {
    final image = json['image'];
    return ForumIdentification(
      image: image is Map<String, dynamic>
          ? ForumImageBlock.fromUploadResponse(image)
          : null,
      provider: json['provider'] as String? ?? '',
      candidates: (json['candidates'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumIdentificationCandidate.fromJson)
          .toList(growable: false),
      createdAt: _parseDate(json['created_at']),
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
