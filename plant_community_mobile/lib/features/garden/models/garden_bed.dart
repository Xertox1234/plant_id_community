/// Garden Bed Model
///
/// Represents a physical garden bed or growing area.
/// Maps to backend GardenBed model from apps/garden_calendar/models.py
class GardenBed {
  /// Unique identifier (UUID from backend)
  final String id;

  /// Owner's user ID
  final String ownerId;

  /// Name of this garden bed
  final String name;

  /// Detailed description
  final String? description;

  /// Type of garden bed
  final BedType bedType;

  /// Dimensions in inches
  final int? lengthInches;
  final int? widthInches;
  final int? depthInches;

  /// Layout data for plant positions (x, y coordinates)
  /// Stored as JSON Map<String, dynamic>
  final Map<String, dynamic>? layoutData;

  /// Location and climate
  final String? locationName;
  final SunExposure? sunExposure;
  final String? hardinessZone;

  /// Soil information
  final String? soilType;
  final double? soilPh;

  /// Status
  final bool isActive;

  /// Timestamps
  final DateTime createdAt;
  final DateTime updatedAt;

  /// Notes
  final String? notes;

  const GardenBed({
    required this.id,
    required this.ownerId,
    required this.name,
    this.description,
    required this.bedType,
    this.lengthInches,
    this.widthInches,
    this.depthInches,
    this.layoutData,
    this.locationName,
    this.sunExposure,
    this.hardinessZone,
    this.soilType,
    this.soilPh,
    this.isActive = true,
    required this.createdAt,
    required this.updatedAt,
    this.notes,
  });

  /// Create from JSON
  factory GardenBed.fromJson(Map<String, dynamic> json) {
    return GardenBed(
      id: json['uuid'] as String,
      ownerId: json['owner'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      bedType: BedType.fromString(json['bed_type'] as String),
      lengthInches: json['length_inches'] as int?,
      widthInches: json['width_inches'] as int?,
      depthInches: json['depth_inches'] as int?,
      layoutData: json['layout_data'] as Map<String, dynamic>?,
      locationName: json['location_name'] as String?,
      sunExposure: json['sun_exposure'] != null
          ? SunExposure.fromString(json['sun_exposure'] as String)
          : null,
      hardinessZone: json['hardiness_zone'] as String?,
      soilType: json['soil_type'] as String?,
      soilPh: json['soil_ph'] != null ? (json['soil_ph'] as num).toDouble() : null,
      isActive: json['is_active'] as bool? ?? true,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      notes: json['notes'] as String?,
    );
  }

  /// Convert to JSON for API
  Map<String, dynamic> toJson() {
    return {
      'uuid': id,
      'owner': ownerId,
      'name': name,
      'description': description,
      'bed_type': bedType.value,
      'length_inches': lengthInches,
      'width_inches': widthInches,
      'depth_inches': depthInches,
      'layout_data': layoutData,
      'location_name': locationName,
      'sun_exposure': sunExposure?.value,
      'hardiness_zone': hardinessZone,
      'soil_type': soilType,
      'soil_ph': soilPh,
      'is_active': isActive,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'notes': notes,
    };
  }

  /// Copy with new values
  GardenBed copyWith({
    String? id,
    String? ownerId,
    String? name,
    String? description,
    BedType? bedType,
    int? lengthInches,
    int? widthInches,
    int? depthInches,
    Map<String, dynamic>? layoutData,
    String? locationName,
    SunExposure? sunExposure,
    String? hardinessZone,
    String? soilType,
    double? soilPh,
    bool? isActive,
    DateTime? createdAt,
    DateTime? updatedAt,
    String? notes,
  }) {
    return GardenBed(
      id: id ?? this.id,
      ownerId: ownerId ?? this.ownerId,
      name: name ?? this.name,
      description: description ?? this.description,
      bedType: bedType ?? this.bedType,
      lengthInches: lengthInches ?? this.lengthInches,
      widthInches: widthInches ?? this.widthInches,
      depthInches: depthInches ?? this.depthInches,
      layoutData: layoutData ?? this.layoutData,
      locationName: locationName ?? this.locationName,
      sunExposure: sunExposure ?? this.sunExposure,
      hardinessZone: hardinessZone ?? this.hardinessZone,
      soilType: soilType ?? this.soilType,
      soilPh: soilPh ?? this.soilPh,
      isActive: isActive ?? this.isActive,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      notes: notes ?? this.notes,
    );
  }

  /// Calculate area in square inches
  int? get areaSquareInches {
    if (lengthInches != null && widthInches != null) {
      return lengthInches! * widthInches!;
    }
    return null;
  }

  /// Calculate volume in cubic inches
  int? get volumeCubicInches {
    if (lengthInches != null && widthInches != null && depthInches != null) {
      return lengthInches! * widthInches! * depthInches!;
    }
    return null;
  }
}

/// Bed Type Enum
enum BedType {
  raised('raised', 'Raised Bed'),
  inGround('in_ground', 'In-Ground Bed'),
  container('container', 'Container Garden'),
  greenhouse('greenhouse', 'Greenhouse'),
  indoor('indoor', 'Indoor Growing'),
  hydroponic('hydroponic', 'Hydroponic System'),
  other('other', 'Other');

  const BedType(this.value, this.label);
  final String value;
  final String label;

  static BedType fromString(String value) {
    return BedType.values.firstWhere(
      (e) => e.value == value,
      orElse: () => BedType.other,
    );
  }
}

/// Sun Exposure Enum
enum SunExposure {
  fullSun('full_sun', 'Full Sun (6+ hours)'),
  partialSun('partial_sun', 'Partial Sun (4-6 hours)'),
  partialShade('partial_shade', 'Partial Shade (2-4 hours)'),
  fullShade('full_shade', 'Full Shade (<2 hours)');

  const SunExposure(this.value, this.label);
  final String value;
  final String label;

  static SunExposure fromString(String value) {
    return SunExposure.values.firstWhere(
      (e) => e.value == value,
      orElse: () => SunExposure.partialSun,
    );
  }
}
