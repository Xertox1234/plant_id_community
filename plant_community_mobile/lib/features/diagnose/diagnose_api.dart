import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../services/api_service.dart';

/// Plant disease diagnosis (todo 444), the same API the web's `/diagnose`
/// calls (`web/src/services/diseaseService.ts`):
///
/// * `POST /plant-identification/disease-requests/` (multipart, signed in)
///   creates the request and diagnoses it synchronously;
/// * `GET  /plant-identification/disease-requests/<uuid>/results/` reads it.
abstract class DiagnoseApi {
  Future<DiagnosisOutcome> diagnose({
    required String imagePath,
    required String symptoms,
    String? plantCondition,
    String? location,
  });
}

/// `PlantDiseaseRequest.plant_condition` choices
/// (`backend/apps/plant_identification/models.py`). The field only accepts
/// these keys; anything else is a 400.
const Map<String, String> plantConditionChoices = {
  'excellent': 'Excellent - minor symptoms',
  'good': 'Good - some concerning symptoms',
  'fair': 'Fair - moderate damage visible',
  'poor': 'Poor - significant damage',
  'critical': 'Critical - plant may die',
};

class HttpDiagnoseApi implements DiagnoseApi {
  HttpDiagnoseApi(this._api);

  final ApiService _api;

  static const _base = '/plant-identification/disease-requests';

  @override
  Future<DiagnosisOutcome> diagnose({
    required String imagePath,
    required String symptoms,
    String? plantCondition,
    String? location,
  }) async {
    final created = await _api.uploadFile(
      '$_base/',
      filePath: imagePath,
      fieldName: 'image_1',
      data: {
        'symptoms_description': symptoms,
        if (plantCondition != null && plantCondition.isNotEmpty)
          'plant_condition': plantCondition,
        if (location != null && location.isNotEmpty) 'location': location,
      },
    );
    final requestId = (created.data as Map<String, dynamic>)['request_id'];
    if (requestId is! String || requestId.isEmpty) {
      throw ApiException('Diagnosis unavailable — please try again.');
    }
    final results = await _api.get('$_base/$requestId/results/');
    return DiagnosisOutcome.fromJson(results.data as Map<String, dynamic>);
  }
}

final diagnoseApiProvider = Provider<DiagnoseApi>(
  (ref) => HttpDiagnoseApi(ref.watch(apiServiceProvider)),
);

/// The results payload: `{request_id, status, results: [...]}`.
class DiagnosisOutcome {
  const DiagnosisOutcome({required this.status, required this.results});

  /// `pending | processing | diagnosed | needs_help | failed`.
  final String status;
  final List<DiagnosisResult> results;

  bool get failed => status == 'failed';

  factory DiagnosisOutcome.fromJson(Map<String, dynamic> json) {
    return DiagnosisOutcome(
      status: _str(json['status']),
      results: (json['results'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(DiagnosisResult.fromJson)
          .toList(growable: false),
    );
  }
}

/// One `PlantDiseaseResultSerializer` row.
class DiagnosisResult {
  const DiagnosisResult({
    required this.id,
    this.name = '',
    this.confidencePercentage,
    this.isSystemMessage = false,
    this.severity = '',
    this.symptoms = '',
    this.immediateActions = '',
    this.treatments = '',
    this.notes = '',
  });

  final int id;
  final String name;
  final int? confidencePercentage;

  /// `diagnosis_source == system_message`: the honest "service unavailable,
  /// ask the community" fallback, shown as a notice, not a disease card.
  final bool isSystemMessage;
  final String severity;
  final String symptoms;
  final String immediateActions;
  final String treatments;
  final String notes;

  factory DiagnosisResult.fromJson(Map<String, dynamic> json) {
    final suggested = _str(json['suggested_disease_name']);
    final pct = json['confidence_percentage'];
    return DiagnosisResult(
      id: json['id'] is int ? json['id'] as int : 0,
      name: suggested.isNotEmpty ? suggested : _str(json['display_name']),
      confidencePercentage: pct is num ? pct.round() : null,
      isSystemMessage: json['diagnosis_source'] == 'system_message',
      severity: _str(json['severity_assessment']),
      symptoms: _str(json['symptoms_identified']),
      immediateActions: _str(json['immediate_actions']),
      treatments: _str(json['recommended_treatments']),
      notes: _str(json['notes']),
    );
  }
}

String _str(Object? value) => value is String ? value : '';

/// Picks the diagnosis photo. An interface so widget tests inject a fake
/// without platform channels, like `ForumImagePicker`.
abstract class DiagnoseImagePicker {
  /// The picked file's path, or null if the user cancelled. Throws
  /// [ApiException] (413) when the photo is over [maxUploadBytes], before
  /// the bytes go over the wire.
  Future<String?> pick(ImageSource source);
}

/// Mirrors the backend cap (`MAX_IMAGE_SIZE` in `apps/core/validators.py`).
const int diagnoseMaxUploadBytes = 10 * 1024 * 1024;

/// Longest edge of a diagnosis photo. The backend refuses an ORIGINAL over
/// 4096 px or 10 MB (`validate_plant_identification_image`) before it
/// resizes to 1200 px, and image_picker hands back a current iPhone's 24 MP
/// photo as a quality-1.0 JPEG. Bounding the pick keeps it inside both
/// limits. Unlike the forum picker, nothing here needs the bytes exact: the
/// backend re-encodes every diagnosis image to JPEG (PR #857 review).
const double diagnoseMaxEdgePx = 2048;
const int diagnoseImageQuality = 85;

class DeviceDiagnoseImagePicker implements DiagnoseImagePicker {
  const DeviceDiagnoseImagePicker({ImagePicker? picker}) : _picker = picker;

  final ImagePicker? _picker;

  @override
  Future<String?> pick(ImageSource source) async {
    final file = await (_picker ?? ImagePicker()).pickImage(
      source: source,
      maxWidth: diagnoseMaxEdgePx,
      maxHeight: diagnoseMaxEdgePx,
      imageQuality: diagnoseImageQuality,
    );
    if (file == null) return null;
    if (await file.length() > diagnoseMaxUploadBytes) {
      throw ApiException(
        'That photo is over 10 MB. Pick a smaller one.',
        statusCode: 413,
      );
    }
    return file.path;
  }
}

final diagnoseImagePickerProvider = Provider<DiagnoseImagePicker>(
  (ref) => const DeviceDiagnoseImagePicker(),
);
