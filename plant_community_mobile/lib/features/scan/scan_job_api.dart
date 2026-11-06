import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http_parser/http_parser.dart';
import 'package:intl/intl.dart';

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

/// What the user has decided about a finished scan. An unknown or missing
/// value from the server reads as [kept], so an old server never shows a
/// countdown.
enum ScanDecision {
  undecided,
  kept,
  dismissed,
  expired,
  removed;

  static ScanDecision parse(Object? raw) => ScanDecision.values.firstWhere(
    (d) => d.name == raw,
    orElse: () => ScanDecision.kept,
  );
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
    this.decision = ScanDecision.kept,
    this.decideBy,
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

  /// Whether the user still has to keep or dismiss this scan.
  final ScanDecision decision;

  /// When an undecided scan expires; null once decided.
  final DateTime? decideBy;

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
      decision: ScanDecision.parse(json['decision']),
      decideBy: json['decide_by'] is String
          ? DateTime.parse(json['decide_by'] as String)
          : null,
    );
  }
}

/// The signed-in user's scan allowance: a scan counts for 24 hours after it
/// was made (a rolling window, not a calendar day).
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

  /// When the next diagnosis comes back (UTC).
  final DateTime resetsAt;

  /// [resetsAt] as a local clock time, e.g. "3:42 PM".
  String get resetsAtLabel => DateFormat.jm().format(resetsAt.toLocal());

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
    String? retryOf,
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
    if (retryOf != null) form.fields.add(MapEntry('retry_of', retryOf));
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
        options: Options(headers: {'X-Scan-Decisions': '1'}),
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

  Future<ScanJob> keep(String id) async =>
      ScanJob.fromJson(_object(await _api.post('$_base$id/keep/')));

  Future<void> dismiss(String id) async {
    await _api.post('$_base$id/dismiss/');
  }

  Future<void> remove(String id) async {
    await _api.post('$_base$id/remove/');
  }

  /// Finished scans still waiting for keep or dismiss.
  Future<List<ScanJob>> undecided() async {
    final response = await _api.get(
      _base,
      queryParameters: {'decision': 'undecided'},
    );
    final data = response.data;
    if (data is! List) {
      throw ApiException('The server sent an unexpected response.');
    }
    return [for (final j in data) ScanJob.fromJson(j as Map<String, dynamic>)];
  }

  static final _photoUrlId = RegExp(
    r'/scans/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/photos/',
  );

  /// The job uuid in one of our photo URLs, or null for anything else (a
  /// Firebase Storage URL, null, empty).
  static String? jobIdFromPhotoUrl(String? url) {
    if (url == null || url.isEmpty) return null;
    final path = Uri.tryParse(url)?.path;
    if (path == null) return null;
    return _photoUrlId.firstMatch(path)?.group(1);
  }

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
