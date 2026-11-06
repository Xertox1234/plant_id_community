import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

const _jobId = '3f1c2a4e-1111-4222-8333-444455556666';

Map<String, dynamic> _jobJson({
  String mode = 'diagnose',
  String status = 'done',
  String chargedAs = 'diagnose',
  Map<String, dynamic>? result,
  Map<String, String>? photos,
  String? coverPhoto,
  Object? decision = 'undecided',
  String? decideBy = '2026-11-03T09:30:20Z',
}) => {
  'decision': ?decision,
  'decide_by': decideBy,
  'id': _jobId,
  'mode': mode,
  'status': status,
  'charged_as': chargedAs,
  'created_at': '2026-11-02T09:30:00Z',
  'finished_at': '2026-11-02T09:30:20Z',
  'result': result,
  'photos':
      photos ??
      {
        'problem':
            'https://api.test/api/v1/plant-identification/scans/$_jobId/photos/problem/',
        'whole':
            'https://api.test/api/v1/plant-identification/scans/$_jobId/photos/whole/',
      },
  'cover_photo':
      coverPhoto ??
      'https://api.test/api/v1/plant-identification/scans/$_jobId/photos/whole/',
};

Map<String, dynamic> _resultJson(Map<String, dynamic>? diagnosis) => {
  'plant_name': 'Monstera',
  'scientific_name': 'Monstera deliciosa',
  'confidence': 0.91,
  'description': 'A climbing aroid.',
  'suggestions': [
    {
      'plant_name': 'Monstera',
      'scientific_name': 'Monstera deliciosa',
      'probability': 0.91,
    },
  ],
  'diagnosis': diagnosis,
};

class _Call {
  _Call(
    this.method,
    this.path,
    this.data,
    this.query,
    this.onSendProgress,
    this.receiveTimeout,
    this.options,
  );
  final Options? options;
  final String method;
  final String path;
  final dynamic data;
  final Map<String, dynamic>? query;
  final void Function(int, int)? onSendProgress;
  final Duration? receiveTimeout;
}

class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'https://api.test/api/v1');

  final calls = <_Call>[];
  Object? error;
  Object? body = <String, dynamic>{};

  @override
  void setAuthToken(String? token) {}

  Future<Response> _answer(
    String method,
    String path,
    dynamic data,
    Map<String, dynamic>? query, [
    void Function(int, int)? progress,
    Duration? timeout,
    Options? options,
  ]) async {
    calls.add(_Call(method, path, data, query, progress, timeout, options));
    if (error != null) throw error!;
    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: body,
    );
  }

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => _answer('GET', path, null, queryParameters, null, null, options);

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    void Function(int sent, int total)? onSendProgress,
    Duration? receiveTimeout,
  }) => _answer(
    'POST',
    path,
    data,
    queryParameters,
    onSendProgress,
    receiveTimeout,
    options,
  );
}

void main() {
  late Directory tmp;
  late _FakeApiService api;
  late ScanJobApi client;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('scan_job_api');
    api = _FakeApiService();
    client = ScanJobApi(api);
  });

  tearDown(() => tmp.deleteSync(recursive: true));

  String shot(String name) {
    final f = File('${tmp.path}/$name.jpg')..writeAsBytesSync([1, 2, 3]);
    return f.path;
  }

  test('create sends every shot under its role name and the offset', () async {
    api.body = _jobJson(status: 'pending', chargedAs: '', result: null);
    final progress = <double>[];

    final job = await client.create(
      CaptureResult(
        mode: ScanMode.diagnose,
        shots: {
          CaptureRole.problem: shot('p'),
          CaptureRole.leaf: shot('l'),
          CaptureRole.whole: shot('w'),
        },
      ),
      onProgress: progress.add,
    );

    final call = api.calls.single;
    expect(call.method, 'POST');
    expect(call.path, '/plant-identification/scans/');
    expect(call.receiveTimeout, slowAnalysisReceiveTimeout);
    final form = call.data as FormData;
    final fields = {for (final f in form.fields) f.key: f.value};
    expect(fields['mode'], 'diagnose');
    expect(
      fields['utc_offset_minutes'],
      DateTime.now().timeZoneOffset.inMinutes.toString(),
    );
    expect(form.files.map((f) => f.key).toSet(), {'problem', 'leaf', 'whole'});
    for (final f in form.files) {
      // The server rejects application/octet-stream parts.
      expect(f.value.contentType.toString(), 'image/jpeg');
      expect(f.value.filename, '${f.key}.jpg');
    }
    call.onSendProgress!(50, 200);
    expect(progress, [0.25]);
    expect(job.status, ScanJobStatus.pending);
    expect(job.status.isActive, isTrue);
    expect(call.options!.headers!['X-Scan-Decisions'], '1');
    expect(fields.containsKey('retry_of'), isFalse);
  });

  test('create sends retry_of when given', () async {
    api.body = _jobJson(status: 'pending', chargedAs: '', result: null);
    await client.create(
      CaptureResult(
        mode: ScanMode.diagnose,
        shots: {CaptureRole.problem: shot('p')},
      ),
      retryOf: _jobId,
    );
    final form = api.calls.single.data as FormData;
    final fields = {for (final f in form.fields) f.key: f.value};
    expect(fields['retry_of'], _jobId);
    expect(api.calls.single.options!.headers!['X-Scan-Decisions'], '1');
  });

  test('fromJson maps decision and decide_by', () {
    final job = ScanJob.fromJson(_jobJson());
    expect(job.decision, ScanDecision.undecided);
    expect(job.decideBy, DateTime.utc(2026, 11, 3, 9, 30, 20));
    for (final d in ScanDecision.values) {
      expect(ScanJob.fromJson(_jobJson(decision: d.name)).decision, d);
    }
  });

  test('a missing, unknown or null decision becomes kept', () {
    for (final j in [
      _jobJson(decision: null, decideBy: null),
      _jobJson(decision: 'mystery'),
      _jobJson(decision: 7),
    ]) {
      final job = ScanJob.fromJson(j);
      expect(job.decision, ScanDecision.kept);
    }
    expect(
      ScanJob.fromJson(_jobJson(decision: null, decideBy: null)).decideBy,
      isNull,
    );
  });

  test('keep, dismiss, remove and undecided hit the right endpoints', () async {
    api.body = _jobJson(decision: 'kept', decideBy: null);
    final kept = await client.keep(_jobId);
    expect(kept.decision, ScanDecision.kept);
    expect(api.calls.last.method, 'POST');
    expect(api.calls.last.path, '/plant-identification/scans/$_jobId/keep/');

    api.body = null;
    await client.dismiss(_jobId);
    expect(api.calls.last.method, 'POST');
    expect(api.calls.last.path, '/plant-identification/scans/$_jobId/dismiss/');
    await client.remove(_jobId);
    expect(api.calls.last.method, 'POST');
    expect(api.calls.last.path, '/plant-identification/scans/$_jobId/remove/');

    api.body = [_jobJson(), _jobJson(decision: 'undecided')];
    final list = await client.undecided();
    expect(api.calls.last.method, 'GET');
    expect(api.calls.last.path, '/plant-identification/scans/');
    expect(api.calls.last.query, {'decision': 'undecided'});
    expect(list, hasLength(2));
    expect(list.first.decision, ScanDecision.undecided);
  });

  test('jobIdFromPhotoUrl reads the uuid or returns null', () {
    expect(
      ScanJobApi.jobIdFromPhotoUrl(
        'https://api.test/api/v1/plant-identification/scans/$_jobId/photos/whole/',
      ),
      _jobId,
    );
    expect(
      ScanJobApi.jobIdFromPhotoUrl(
        'https://firebasestorage.googleapis.com/v0/b/x/o/scans%2Fa.jpg?alt=media',
      ),
      isNull,
    );
    expect(ScanJobApi.jobIdFromPhotoUrl(null), isNull);
    expect(ScanJobApi.jobIdFromPhotoUrl(''), isNull);
  });

  test('fromJson parses a degraded job with diagnosis unavailable', () {
    final job = ScanJob.fromJson(
      _jobJson(
        status: 'degraded',
        chargedAs: 'identify',
        result: _resultJson({
          'state': 'unavailable',
          'name': null,
          'probability': null,
          'description': null,
        }),
      ),
    );

    expect(job.id, _jobId);
    expect(job.mode, ScanMode.diagnose);
    expect(job.status, ScanJobStatus.degraded);
    expect(job.status.hasResult, isTrue);
    expect(job.status.isActive, isFalse);
    expect(job.chargedAs, 'identify');
    expect(job.result!.plantName, 'Monstera');
    expect(job.result!.scientificName, 'Monstera deliciosa');
    expect(job.result!.confidence, 0.91);
    expect(job.result!.diagnosis!.state, 'unavailable');
    expect(job.result!.diagnosis!.name, isNull);
    expect(job.photos.keys, {CaptureRole.problem, CaptureRole.whole});
    expect(job.coverPhoto, endsWith('/photos/whole/'));
    expect(job.createdAt, DateTime.utc(2026, 11, 2, 9, 30));
  });

  test(
    'fromJson parses a failed job with a null result and found diagnosis',
    () {
      final failed = ScanJob.fromJson(
        _jobJson(
          status: 'failed',
          chargedAs: '',
          result: null,
          coverPhoto: null,
        ),
      );
      expect(failed.result, isNull);
      expect(failed.status.hasResult, isFalse);

      final found = ScanJob.fromJson(
        _jobJson(
          mode: 'identify',
          result: _resultJson({
            'state': 'found',
            'name': 'Root rot',
            'probability': 0.7,
            'description': 'Overwatering.',
          }),
        ),
      );
      expect(found.mode, ScanMode.identify);
      expect(found.result!.diagnosis!.name, 'Root rot');
      expect(found.result!.diagnosis!.probability, 0.7);
    },
  );

  test(
    'allowance parses the backend shape and remainingFor picks the mode',
    () async {
      api.body = {
        'is_premium': false,
        'diagnose': {'limit': 1, 'used': 1, 'remaining': 0},
        'identify': {'limit': 5, 'used': 2, 'remaining': 3},
        'resets_at': '2026-11-03T00:00:00Z',
        'plant_id_available': true,
        'slow_after_seconds': 45,
        'premium_diagnose_limit': 3,
      };

      final a = await client.allowance();

      expect(api.calls.single.path, '/plant-identification/scans/allowance/');
      expect(api.calls.single.query!['utc_offset_minutes'], isA<int>());
      expect(a.isPremium, isFalse);
      expect(a.diagnoseLimit, 1);
      expect(a.remainingFor(ScanMode.diagnose), 0);
      expect(a.remainingFor(ScanMode.identify), 3);
      expect(a.identifyLimit, 5);
      expect(a.resetsAt, DateTime.utc(2026, 11, 3));
      expect(a.plantIdAvailable, isTrue);
      expect(a.slowAfterSeconds, 45);
      expect(a.premiumDiagnoseLimit, 3);
    },
  );

  test('get and cancel hit the job URL and photoUrl names the role', () async {
    api.body = _jobJson();
    await client.get(_jobId);
    await client.cancel(_jobId);
    expect(api.calls[0].method, 'GET');
    expect(api.calls[0].path, '/plant-identification/scans/$_jobId/');
    expect(api.calls[1].method, 'POST');
    expect(api.calls[1].path, '/plant-identification/scans/$_jobId/cancel/');
    expect(
      client.photoUrl(_jobId, CaptureRole.leaf),
      'https://api.test/api/v1/plant-identification/scans/$_jobId/photos/leaf/',
    );
  });

  test('429 allowance_exhausted becomes ScanRefused(kind: diagnose)', () async {
    api.error = ApiException(
      'Too many requests. Please wait a moment and try again.',
      statusCode: 429,
      code: 'allowance_exhausted',
      body: {
        'code': 'allowance_exhausted',
        'kind': 'diagnose',
        'limit': 1,
        'resets_at': '2026-11-03T00:00:00Z',
      },
    );

    await expectLater(
      client.create(
        CaptureResult(
          mode: ScanMode.diagnose,
          shots: {CaptureRole.problem: shot('p')},
        ),
      ),
      throwsA(
        isA<ScanRefused>()
            .having((e) => e.code, 'code', 'allowance_exhausted')
            .having((e) => e.kind, 'kind', 'diagnose')
            .having((e) => e.jobId, 'jobId', isNull),
      ),
    );
  });

  test('409 scan_in_progress carries jobId', () async {
    api.error = ApiException(
      'Another scan is still running.',
      statusCode: 409,
      code: 'scan_in_progress',
      body: {'code': 'scan_in_progress', 'job_id': _jobId},
    );

    await expectLater(
      client.create(
        CaptureResult(
          mode: ScanMode.diagnose,
          shots: {CaptureRole.problem: shot('p')},
        ),
      ),
      throwsA(
        isA<ScanRefused>()
            .having((e) => e.code, 'code', 'scan_in_progress')
            .having((e) => e.jobId, 'jobId', _jobId),
      ),
    );
  });

  test('503 plant_id_busy is refused; other errors pass through', () async {
    api.error = ApiException('busy', statusCode: 503, code: 'plant_id_busy');
    final shots = {CaptureRole.problem: shot('p')};
    await expectLater(
      client.create(CaptureResult(mode: ScanMode.diagnose, shots: shots)),
      throwsA(
        isA<ScanRefused>().having((e) => e.code, 'code', 'plant_id_busy'),
      ),
    );

    final other = ApiException('bad', statusCode: 400, code: 'invalid');
    api.error = other;
    await expectLater(
      client.create(CaptureResult(mode: ScanMode.diagnose, shots: shots)),
      throwsA(same(other)),
    );
  });

  test(
    'handleDioException keeps the envelope code and body on 429 and 503',
    () {
      DioException err(int status, Map<String, dynamic> data) => DioException(
        requestOptions: RequestOptions(path: '/x'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/x'),
          statusCode: status,
          data: data,
        ),
      );

      final e429 =
          api.handleDioException(
                err(429, {'code': 'allowance_exhausted', 'kind': 'identify'}),
              )
              as ApiException;
      expect(e429.code, 'allowance_exhausted');
      expect(e429.body!['kind'], 'identify');
      expect(e429.statusCode, 429);

      final e503 =
          api.handleDioException(err(503, {'code': 'plant_id_busy'}))
              as ApiException;
      expect(e503.code, 'plant_id_busy');

      final e409 =
          api.handleDioException(
                err(409, {'code': 'scan_in_progress', 'job_id': _jobId}),
              )
              as ApiException;
      expect(e409.body!['job_id'], _jobId);
    },
  );
}
