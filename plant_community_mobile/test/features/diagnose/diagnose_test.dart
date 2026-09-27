import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:plant_community_mobile/features/diagnose/diagnose_api.dart';
import 'package:plant_community_mobile/features/diagnose/diagnose_screen.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// Records the upload and serves canned create + results payloads.
class _RecordingApiService extends ApiService {
  _RecordingApiService({required this.created, required this.results})
    : super(baseUrl: 'http://localhost:8000/api/v1');

  final Map<String, dynamic> created;
  final Map<String, dynamic> results;
  String? uploadPath;
  String? uploadField;
  Map<String, dynamic>? uploadData;
  String? getPath;

  @override
  Future<Response> uploadFile(
    String path, {
    required String filePath,
    String fieldName = 'image',
    Map<String, dynamic>? data,
    void Function(int sent, int total)? onSendProgress,
  }) async {
    uploadPath = path;
    uploadField = fieldName;
    uploadData = data;
    return Response(
      requestOptions: RequestOptions(path: path),
      data: created,
    );
  }

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    getPath = path;
    return Response(
      requestOptions: RequestOptions(path: path),
      data: results,
    );
  }
}

class _FakeDiagnoseApi implements DiagnoseApi {
  Completer<DiagnosisOutcome>? pending;
  Object? error;
  DiagnosisOutcome outcome = const DiagnosisOutcome(
    status: 'diagnosed',
    results: [],
  );
  final calls = <Map<String, Object?>>[];

  @override
  Future<DiagnosisOutcome> diagnose({
    required String imagePath,
    required String symptoms,
    String? plantCondition,
    String? location,
  }) async {
    calls.add({
      'imagePath': imagePath,
      'symptoms': symptoms,
      'plantCondition': plantCondition,
      'location': location,
    });
    if (pending != null) return pending!.future;
    if (error != null) throw error!;
    return outcome;
  }
}

class _FakePicker implements DiagnoseImagePicker {
  _FakePicker({this.error});
  static const path = '/tmp/does-not-exist.jpg';
  final Object? error;
  final sources = <ImageSource>[];

  @override
  Future<String?> pick(ImageSource source) async {
    sources.add(source);
    if (error != null) throw error!;
    return path;
  }
}

/// Records the arguments image_picker was called with; the user cancels.
class _RecordingImagePicker extends ImagePicker {
  ImageSource? source;
  double? maxWidth;
  double? maxHeight;
  int? imageQuality;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    this.source = source;
    this.maxWidth = maxWidth;
    this.maxHeight = maxHeight;
    this.imageQuality = imageQuality;
    return null;
  }
}

Widget _wrap(_FakeDiagnoseApi api, _FakePicker picker) => ProviderScope(
  overrides: [
    diagnoseApiProvider.overrideWithValue(api),
    diagnoseImagePickerProvider.overrideWithValue(picker),
  ],
  child: const MaterialApp(home: DiagnoseScreen()),
);

Future<void> _fill(
  WidgetTester tester, {
  String symptoms = 'Brown spots',
}) async {
  await tester.tap(find.text('Choose photo'));
  await tester.pump();
  await tester.enterText(find.widgetWithText(TextField, 'Symptoms'), symptoms);
  await tester.pump();
}

Future<void> _tapDiagnose(WidgetTester tester) async {
  await tester.ensureVisible(find.text('Diagnose'));
  await tester.pump();
  await tester.tap(find.text('Diagnose'));
}

FilledButton _submit(WidgetTester tester) => tester.widget<FilledButton>(
  find.byWidgetPredicate((w) => w is FilledButton),
);

void main() {
  group('HttpDiagnoseApi', () {
    test('uploads image_1 with the symptoms, then reads the results', () async {
      final api = _RecordingApiService(
        created: {'request_id': 'abc-123', 'status': 'diagnosed'},
        results: {
          'request_id': 'abc-123',
          'status': 'diagnosed',
          'results': [
            {
              'id': 1,
              'suggested_disease_name': 'Root rot',
              'confidence_percentage': 82.4,
              'diagnosis_source': 'api_plant_health',
              'recommended_treatments': 'Repot into fresh mix.',
            },
            {
              'id': 2,
              'diagnosis_source': 'system_message',
              'notes': 'Ask the community.',
            },
          ],
        },
      );

      final outcome = await HttpDiagnoseApi(api).diagnose(
        imagePath: '/x.jpg',
        symptoms: 'Mushy stems',
        plantCondition: 'poor',
        location: '',
      );

      expect(api.uploadPath, '/plant-identification/disease-requests/');
      expect(api.uploadField, 'image_1');
      // Empty optionals are left out: `plant_condition` is a choices field
      // and an empty or unknown value is a 400.
      expect(api.uploadData, {
        'symptoms_description': 'Mushy stems',
        'plant_condition': 'poor',
      });
      expect(
        api.getPath,
        '/plant-identification/disease-requests/abc-123/results/',
      );
      expect(outcome.results.first.name, 'Root rot');
      expect(outcome.results.first.confidencePercentage, 82);
      expect(outcome.results.last.isSystemMessage, isTrue);
    });

    test('no condition picked: plant_condition is not sent at all', () async {
      final api = _RecordingApiService(
        created: {'request_id': 'r1'},
        results: {'status': 'diagnosed', 'results': []},
      );
      await HttpDiagnoseApi(api).diagnose(
        imagePath: '/x.jpg',
        symptoms: 's',
        plantCondition: '',
        location: 'North window',
      );
      expect(api.uploadData, {
        'symptoms_description': 's',
        'location': 'North window',
      });
    });

    test('a create response with no request_id is an error, not a GET of '
        '"null"', () async {
      final api = _RecordingApiService(created: {}, results: {});
      await expectLater(
        HttpDiagnoseApi(api).diagnose(imagePath: '/x.jpg', symptoms: 's'),
        throwsA(isA<ApiException>()),
      );
      expect(api.getPath, isNull);
    });
  });

  test('the device picker bounds the photo inside the backend limits (PR '
      '#857 review)', () async {
    final picker = _RecordingImagePicker();
    final path = await DeviceDiagnoseImagePicker(
      picker: picker,
    ).pick(ImageSource.gallery);

    expect(path, isNull);
    expect(picker.source, ImageSource.gallery);
    expect(picker.maxWidth, lessThanOrEqualTo(4096));
    expect(picker.maxHeight, lessThanOrEqualTo(4096));
    expect(picker.imageQuality, isNotNull);
  });

  group('DiagnoseScreen', () {
    testWidgets('Diagnose stays disabled until there is a photo AND symptoms', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(_FakeDiagnoseApi(), _FakePicker()));
      expect(_submit(tester).onPressed, isNull);

      await tester.enterText(
        find.widgetWithText(TextField, 'Symptoms'),
        'Brown spots',
      );
      await tester.pump();
      expect(_submit(tester).onPressed, isNull, reason: 'no photo yet');

      await tester.tap(find.text('Choose photo'));
      await tester.pump();
      expect(_submit(tester).onPressed, isNotNull);

      await tester.enterText(find.widgetWithText(TextField, 'Symptoms'), '  ');
      await tester.pump();
      expect(_submit(tester).onPressed, isNull, reason: 'blank symptoms');
    });

    testWidgets('Take photo opens the camera', (tester) async {
      final picker = _FakePicker();
      await tester.pumpWidget(_wrap(_FakeDiagnoseApi(), picker));
      await tester.tap(find.text('Take photo'));
      await tester.pump();
      expect(picker.sources, [ImageSource.camera]);
    });

    testWidgets('shows a loading state, then the results', (tester) async {
      final api = _FakeDiagnoseApi()..pending = Completer();
      await tester.pumpWidget(_wrap(api, _FakePicker()));
      await _fill(tester);

      await _tapDiagnose(tester);
      await tester.pump();
      expect(find.text('Diagnosing…'), findsOneWidget);
      expect(_submit(tester).onPressed, isNull, reason: 'no double submit');

      api.pending!.complete(
        const DiagnosisOutcome(
          status: 'diagnosed',
          results: [
            DiagnosisResult(
              id: 1,
              name: 'Root rot',
              confidencePercentage: 82,
              severity: 'moderate',
              treatments: 'Repot into fresh mix.',
            ),
            DiagnosisResult(
              id: 2,
              isSystemMessage: true,
              notes: 'Ask the community.',
            ),
          ],
        ),
      );
      await tester.pump();

      expect(find.text('Diagnosing…'), findsNothing);
      expect(find.text('Root rot'), findsOneWidget);
      expect(find.text('82%'), findsOneWidget);
      expect(find.textContaining('Repot into fresh mix.'), findsOneWidget);
      expect(find.text('Ask the community.'), findsOneWidget);
      expect(api.calls.single['symptoms'], 'Brown spots');
    });

    testWidgets('a failed request says so', (tester) async {
      final api = _FakeDiagnoseApi()
        ..outcome = const DiagnosisOutcome(status: 'failed', results: []);
      await tester.pumpWidget(_wrap(api, _FakePicker()));
      await _fill(tester);
      await _tapDiagnose(tester);
      await tester.pump();
      expect(
        find.text('Diagnosis unavailable — please try again.'),
        findsOneWidget,
      );
    });

    testWidgets('a rate limit gets its own message, never the raw error', (
      tester,
    ) async {
      final api = _FakeDiagnoseApi()
        ..error = ApiException('Request was throttled.', statusCode: 429);
      await tester.pumpWidget(_wrap(api, _FakePicker()));
      await _fill(tester);
      await _tapDiagnose(tester);
      await tester.pump();
      expect(
        find.text('Too many diagnoses in a row — try again in a minute.'),
        findsOneWidget,
      );
      expect(find.textContaining('throttled'), findsNothing);
    });

    testWidgets('an oversized photo is refused before upload', (tester) async {
      final api = _FakeDiagnoseApi();
      await tester.pumpWidget(
        _wrap(
          api,
          _FakePicker(
            error: ApiException(
              'That photo is over 10 MB. Pick a smaller one.',
              statusCode: 413,
            ),
          ),
        ),
      );
      await tester.tap(find.text('Choose photo'));
      await tester.pump();
      expect(
        find.text('That photo is over 10 MB. Pick a smaller one.'),
        findsOneWidget,
      );
      expect(_submit(tester).onPressed, isNull);
      expect(api.calls, isEmpty);
    });

    testWidgets('no results asks for a clearer photo', (tester) async {
      await tester.pumpWidget(_wrap(_FakeDiagnoseApi(), _FakePicker()));
      await _fill(tester);
      await _tapDiagnose(tester);
      await tester.pump();
      expect(find.textContaining('No diagnosis was produced'), findsOneWidget);
    });
  });

  test('diagnoseErrorMessage never leaks a non-API exception', () {
    expect(
      diagnoseErrorMessage(StateError('boom')),
      'Diagnosis unavailable — please try again.',
    );
    expect(
      diagnoseErrorMessage(
        ApiException('Please describe the symptoms.', statusCode: 400),
      ),
      'Please describe the symptoms.',
    );
  });
}
