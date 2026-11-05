import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http_parser/http_parser.dart';

import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import 'capture_session.dart';
import 'capture_steps.dart';

/// Where a background scan job is in its life.
enum ScanJobStatus {
  pending,
  processing,
  done,
  degraded,
  failed,
  cancelled;

  /// Still running: it holds the user's one scan slot.
  bool get isActive =>
      this == ScanJobStatus.pending || this == ScanJobStatus.processing;

  /// Ended with a result to show (a degraded one names the plant only).
  bool get hasResult =>
      this == ScanJobStatus.done || this == ScanJobStatus.degraded;
}

/// The health verdict of a diagnose scan. [state] is `found`, `healthy` or
/// `unavailable` (the health check could not run).
class ScanDiagnosis {
  const ScanDiagnosis({
    required this.state,
    this.name,
    this.probability,
    this.description,
  });

  final String state;
  final String? name;
  final double? probability;
  final String? description;

  factory ScanDiagnosis.fromJson(Map<String, dynamic> json) => ScanDiagnosis(
    state: json['state'] as String,
    name: json['name'] as String?,
    probability: (json['probability'] as num?)?.toDouble(),
    description: json['description'] as String?,
  );
}

/// The summary of a finished scan. Null on [ScanJob.result] for a job that
/// failed or was cancelled.
class ScanJobResult {
  const ScanJobResult({
    required this.plantName,
    required this.scientificName,
    required this.confidence,
    required this.description,
    required this.diagnosis,
  });

  final String plantName;
  final String scientificName;
  final double? confidence;
  final String description;

  /// Null for an identify scan.
  final ScanDiagnosis? diagnosis;

  factory ScanJobResult.fromJson(Map<String, dynamic> json) {
    final diagnosis = json['diagnosis'];
    return ScanJobResult(
      plantName: json['plant_name'] as String? ?? '',
      scientificName: json['scientific_name'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble(),
      description: json['description'] as String? ?? '',
      diagnosis: diagnosis is Map<String, dynamic>
          ? ScanDiagnosis.fromJson(diagnosis)
          : null,
    );
  }
}

/// One background scan job, as the server reports it.
class ScanJob {
  const ScanJob({
    required this.id,
    required this.mode,
    required this.status,
    required this.chargedAs,
    required this.result,
    required this.photos,
    required this.coverPhoto,
    required this.createdAt,
  });

  final String id;
  final ScanMode mode;
  final ScanJobStatus status;

  /// `diagnose` or `identify` once the scan is done or degraded; empty
  /// otherwise (a failed or cancelled scan costs nothing).
  final String chargedAs;
  final ScanJobResult? result;

  /// Authenticated photo URL per role (never a public storage URL).
  final Map<CaptureRole, String> photos;
  final String? coverPhoto;
  final DateTime createdAt;

  factory ScanJob.fromJson(Map<String, dynamic> json) {
    final result = json['result'];
    final photos = json['photos'];
    return ScanJob(
      id: json['id'] as String,
      mode: ScanMode.values.byName(json['mode'] as String),
      // An unknown status from a newer server reads as failed, not a crash.
      status: ScanJobStatus.values.firstWhere(
        (s) => s.name == json['status'],
        orElse: () => ScanJobStatus.failed,
      ),
      chargedAs: json['charged_as'] as String? ?? '',
      result: result is Map<String, dynamic>
          ? ScanJobResult.fromJson(result)
          : null,
      photos: {
        if (photos is Map<String, dynamic>)
          for (final e in photos.entries)
            for (final role in CaptureRole.values)
              if (role.name == e.key) role: e.value as String,
      },
      coverPhoto: json['cover_photo'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// Today's scan allowance for the signed-in user.
class ScanAllowance {
  const ScanAllowance({
    required this.isPremium,
    required this.diagnoseRemaining,
    required this.diagnoseLimit,
    required this.identifyRemaining,
    required this.identifyLimit,
    required this.resetsAt,
    required this.plantIdAvailable,
    required this.slowAfterSeconds,
    required this.premiumDiagnoseLimit,
  });

  final bool isPremium;
  final int diagnoseRemaining, diagnoseLimit, identifyRemaining, identifyLimit;
  final DateTime resetsAt;

  /// False when Plant.id has no room for a diagnosis right now.
  final bool plantIdAvailable;
  final int slowAfterSeconds;
  final int premiumDiagnoseLimit;

  factory ScanAllowance.fromJson(Map<String, dynamic> json) {
    final diagnose = json['diagnose'] as Map<String, dynamic>;
    final identify = json['identify'] as Map<String, dynamic>;
    return ScanAllowance(
      isPremium: json['is_premium'] as bool,
      diagnoseRemaining: (diagnose['remaining'] as num).toInt(),
      diagnoseLimit: (diagnose['limit'] as num).toInt(),
      identifyRemaining: (identify['remaining'] as num).toInt(),
      identifyLimit: (identify['limit'] as num).toInt(),
      resetsAt: DateTime.parse(json['resets_at'] as String),
      plantIdAvailable: json['plant_id_available'] as bool,
      slowAfterSeconds: (json['slow_after_seconds'] as num).toInt(),
      premiumDiagnoseLimit: (json['premium_diagnose_limit'] as num).toInt(),
    );
  }

  int remainingFor(ScanMode m) => switch (m) {
    ScanMode.diagnose => diagnoseRemaining,
    ScanMode.identify => identifyRemaining,
  };
}

/// The server declined to start a scan: `allowance_exhausted` (429, with
/// [kind]), `plant_id_busy` (503) or `scan_in_progress` (409, with [jobId]).
class ScanRefused implements Exception {
  const ScanRefused({required this.code, this.kind, this.jobId});

  /// The [ScanRefused] for [e], or null when [e] is some other failure.
  static ScanRefused? tryFrom(ApiException e) {
    const codes = {'allowance_exhausted', 'plant_id_busy', 'scan_in_progress'};
    final code = e.code;
    if (code == null || !codes.contains(code)) return null;
    final kind = e.body?['kind'];
    final jobId = e.body?['job_id'];
    return ScanRefused(
      code: code,
      kind: kind is String ? kind : null,
      jobId: jobId is String ? jobId : null,
    );
  }

  final String code;
  final String? kind;
  final String? jobId;

  @override
  String toString() => 'ScanRefused($code)';
}

/// Client of the background scan-job endpoints.
class ScanJobApi {
  ScanJobApi(this._api);

  final ApiService _api;

  static const _base = '/plant-identification/scans/';

  Future<ScanAllowance> allowance() async {
    final response = await _api.get(
      '${_base}allowance/',
      queryParameters: {
        'utc_offset_minutes': DateTime.now().timeZoneOffset.inMinutes,
      },
    );
    return ScanAllowance.fromJson(_object(response));
  }

  /// Uploads every shot under its role name and starts the job. Throws
  /// [ScanRefused] when the server declines; other failures stay
  /// [ApiException]. [onProgress] reports the upload as 0..1.
  Future<ScanJob> create(
    CaptureResult r, {
    void Function(double)? onProgress,
  }) async {
    final form = FormData();
    form.fields
      ..add(MapEntry('mode', r.mode.name))
      ..add(
        MapEntry(
          'utc_offset_minutes',
          DateTime.now().timeZoneOffset.inMinutes.toString(),
        ),
      );
    for (final e in r.shots.entries) {
      form.files.add(
        MapEntry(
          e.key.name,
          // The server accepts only image/* part types; Dio would send
          // application/octet-stream by default.
          await MultipartFile.fromFile(
            e.value,
            filename: '${e.key.name}.jpg',
            contentType: MediaType('image', 'jpeg'),
          ),
        ),
      );
    }
    try {
      final response = await _api.post(
        _base,
        data: form,
        receiveTimeout: slowAnalysisReceiveTimeout,
        onSendProgress: onProgress == null
            ? null
            : (sent, total) {
                if (total > 0) onProgress(sent / total);
              },
      );
      return ScanJob.fromJson(_object(response));
    } on ApiException catch (e) {
      final refused = ScanRefused.tryFrom(e);
      if (refused != null) throw refused;
      rethrow;
    }
  }

  Future<ScanJob> get(String id) async =>
      ScanJob.fromJson(_object(await _api.get('$_base$id/')));

  Future<ScanJob> cancel(String id) async =>
      ScanJob.fromJson(_object(await _api.post('$_base$id/cancel/')));

  /// URL of one stored photo. It needs the bearer token to load.
  String photoUrl(String id, CaptureRole role) =>
      '${_api.baseUrl}$_base$id/photos/${role.name}/';

  Map<String, dynamic> _object(Response response) {
    final data = response.data;
    if (data is! Map<String, dynamic>) {
      throw ApiException('The server sent an unexpected response.');
    }
    return data;
  }
}

final scanJobApiProvider = Provider<ScanJobApi>(
  (ref) => ScanJobApi(ref.watch(apiServiceProvider)),
);

/// Today's allowance, or null when signed out or it cannot be loaded.
final scanAllowanceProvider = FutureProvider.autoDispose<ScanAllowance?>((
  ref,
) async {
  if (ref.watch(currentUserIdProvider) == null) return null;
  try {
    return await ref.watch(scanJobApiProvider).allowance();
  } catch (e) {
    debugPrint('[SCAN_JOB] Allowance read failed: $e');
    return null;
  }
});
