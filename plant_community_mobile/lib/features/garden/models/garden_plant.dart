/// Garden Plant Model
///
/// Represents an individual plant instance in a garden bed.
/// Maps to backend Plant model from apps/garden_calendar/models.py
class GardenPlant {
  /// Unique identifier (UUID from backend)
  final String id;

  /// Garden bed this plant is in
  final String gardenBedId;

  /// Link to identified plant species (optional)
  final String? plantSpeciesId;

  /// Plant identification
  final String commonName;
  final String? scientificName;
  final String? variety;

  /// Planting information
  final DateTime plantedDate;
  final String? source;

  /// Position in bed (for visual layout on canvas)
  final int? positionX;
  final int? positionY;

  /// Health and growth
  final HealthStatus healthStatus;
  final GrowthStage? growthStage;

  /// Status
  final bool isActive;
  final DateTime? removedDate;
  final String? removalReason;

  /// Notes
  final String? notes;

  /// Tags for organization
  final List<String> tags;

  /// Timestamps
  final DateTime createdAt;
  final DateTime updatedAt;

  const GardenPlant({
    required this.id,
    required this.gardenBedId,
    this.plantSpeciesId,
    required this.commonName,
    this.scientificName,
    this.variety,
    required this.plantedDate,
    this.source,
    this.positionX,
    this.positionY,
    required this.healthStatus,
    this.growthStage,
    this.isActive = true,
    this.removedDate,
    this.removalReason,
    this.notes,
    this.tags = const [],
    required this.createdAt,
    required this.updatedAt,
  });

  /// Create from JSON
  factory GardenPlant.fromJson(Map<String, dynamic> json) {
    return GardenPlant(
      id: json['uuid'] as String,
      gardenBedId: json['garden_bed'] as String,
      plantSpeciesId: json['plant_species'] as String?,
      commonName: json['common_name'] as String,
      scientificName: json['scientific_name'] as String?,
      variety: json['variety'] as String?,
      plantedDate: DateTime.parse(json['planted_date'] as String),
      source: json['source'] as String?,
      positionX: json['position_x'] as int?,
      positionY: json['position_y'] as int?,
      healthStatus: HealthStatus.fromString(json['health_status'] as String),
      growthStage: json['growth_stage'] != null
          ? GrowthStage.fromString(json['growth_stage'] as String)
          : null,
      isActive: json['is_active'] as bool? ?? true,
      removedDate: json['removed_date'] != null
          ? DateTime.parse(json['removed_date'] as String)
          : null,
      removalReason: json['removal_reason'] as String?,
      notes: json['notes'] as String?,
      tags: (json['tags'] as List<dynamic>?)?.cast<String>() ?? [],
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  /// Convert to JSON for API
  Map<String, dynamic> toJson() {
    return {
      'uuid': id,
      'garden_bed': gardenBedId,
      'plant_species': plantSpeciesId,
      'common_name': commonName,
      'scientific_name': scientificName,
      'variety': variety,
      'planted_date': plantedDate.toIso8601String().split('T')[0],
      'source': source,
      'position_x': positionX,
      'position_y': positionY,
      'health_status': healthStatus.value,
      'growth_stage': growthStage?.value,
      'is_active': isActive,
      'removed_date': removedDate?.toIso8601String().split('T')[0],
      'removal_reason': removalReason,
      'notes': notes,
      'tags': tags,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  /// Copy with new values
  GardenPlant copyWith({
    String? id,
    String? gardenBedId,
    String? plantSpeciesId,
    String? commonName,
    String? scientificName,
    String? variety,
    DateTime? plantedDate,
    String? source,
    int? positionX,
    int? positionY,
    HealthStatus? healthStatus,
    GrowthStage? growthStage,
    bool? isActive,
    DateTime? removedDate,
    String? removalReason,
    String? notes,
    List<String>? tags,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return GardenPlant(
      id: id ?? this.id,
      gardenBedId: gardenBedId ?? this.gardenBedId,
      plantSpeciesId: plantSpeciesId ?? this.plantSpeciesId,
      commonName: commonName ?? this.commonName,
      scientificName: scientificName ?? this.scientificName,
      variety: variety ?? this.variety,
      plantedDate: plantedDate ?? this.plantedDate,
      source: source ?? this.source,
      positionX: positionX ?? this.positionX,
      positionY: positionY ?? this.positionY,
      healthStatus: healthStatus ?? this.healthStatus,
      growthStage: growthStage ?? this.growthStage,
      isActive: isActive ?? this.isActive,
      removedDate: removedDate ?? this.removedDate,
      removalReason: removalReason ?? this.removalReason,
      notes: notes ?? this.notes,
      tags: tags ?? this.tags,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// Calculate days since planted
  int get daysSincePlanted {
    return DateTime.now().difference(plantedDate).inDays;
  }

  /// Is plant unhealthy?
  bool get isUnhealthy {
    return healthStatus == HealthStatus.poor ||
        healthStatus == HealthStatus.critical ||
        healthStatus == HealthStatus.diseased ||
        healthStatus == HealthStatus.pest_damaged;
  }
}

/// Health Status Enum
enum HealthStatus {
  excellent('excellent', 'Excellent'),
  good('good', 'Good'),
  fair('fair', 'Fair'),
  poor('poor', 'Poor'),
  critical('critical', 'Critical'),
  diseased('diseased', 'Diseased'),
  pest_damaged('pest_damaged', 'Pest Damaged'),
  recovering('recovering', 'Recovering');

  const HealthStatus(this.value, this.label);
  final String value;
  final String label;

  static HealthStatus fromString(String value) {
    return HealthStatus.values.firstWhere(
      (e) => e.value == value,
      orElse: () => HealthStatus.good,
    );
  }
}

/// Growth Stage Enum
enum GrowthStage {
  seed('seed', 'Seed'),
  germination('germination', 'Germination'),
  seedling('seedling', 'Seedling'),
  vegetative('vegetative', 'Vegetative Growth'),
  budding('budding', 'Budding'),
  flowering('flowering', 'Flowering'),
  fruiting('fruiting', 'Fruiting/Producing'),
  harvest('harvest', 'Harvest Ready'),
  dormant('dormant', 'Dormant'),
  declining('declining', 'Declining');

  const GrowthStage(this.value, this.label);
  final String value;
  final String label;

  static GrowthStage fromString(String value) {
    return GrowthStage.values.firstWhere(
      (e) => e.value == value,
      orElse: () => GrowthStage.seedling,
    );
  }
}
