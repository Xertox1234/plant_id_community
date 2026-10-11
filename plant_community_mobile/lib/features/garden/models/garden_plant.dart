/// A plant in the user's garden: `garden_calendar.Plant`, as the LIST
/// payload of `GET /calendar/api/plants/` serializes it
/// (`PlantListSerializer` in `backend/apps/garden_calendar/api/serializers.py`).
///
/// Houseplant core only (todo 386 owner decision): no bed picker, no layout
/// position, no weather. A plant without a bed is the normal case, so
/// [gardenBed] is nullable — the API returns `null` for it (todo 457 item 8).
class GardenPlant {
  const GardenPlant({
    required this.id,
    required this.commonName,
    this.gardenBed,
    this.gardenBedName,
    this.variety = '',
    this.healthStatus = 'healthy',
    this.healthStatusDisplay = 'Healthy',
    this.plantedDate,
    this.isActive = true,
  });

  /// The plant's UUID (its primary key on the server).
  final String id;

  /// The bed's UUID, or null for a plant with no bed.
  final String? gardenBed;

  /// The bed's name, or null for a plant with no bed.
  final String? gardenBedName;

  final String commonName;
  final String variety;

  /// `HEALTH_STATUS_CHOICES` key (`thriving`, `healthy`, ...). Kept as the
  /// raw key: the server owns the vocabulary and sends the label with it.
  final String healthStatus;
  final String healthStatusDisplay;

  final DateTime? plantedDate;
  final bool isActive;

  factory GardenPlant.fromJson(Map<String, dynamic> json) {
    final planted = json['planted_date'];
    return GardenPlant(
      id: json['uuid'] as String,
      gardenBed: json['garden_bed'] as String?,
      gardenBedName: json['garden_bed_name'] as String?,
      commonName: json['common_name'] as String? ?? '',
      variety: json['variety'] as String? ?? '',
      healthStatus: json['health_status'] as String? ?? 'healthy',
      healthStatusDisplay:
          json['health_status_display'] as String? ??
          json['health_status'] as String? ??
          '',
      plantedDate: planted is String ? DateTime.tryParse(planted) : null,
      isActive: json['is_active'] as bool? ?? true,
    );
  }

  /// The name shown in lists: "Monstera (Thai Constellation)".
  String get displayName =>
      variety.isEmpty ? commonName : '$commonName ($variety)';
}
