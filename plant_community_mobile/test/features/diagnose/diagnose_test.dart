import 'dart:async';
import 'dart:convert';
import 'dart:io';

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
  String? uploadFilename;
  Duration? uploadReceiveTimeout;
  String? getPath;

  @override
  Future<Response> uploadFile(
    String path, {
    required String filePath,
    String fieldName = 'image',
    String? filename,
    Map<String, dynamic>? data,
    void Function(int sent, int total)? onSendProgress,
    Duration? receiveTimeout,
  }) async {
    uploadPath = path;
    uploadField = fieldName;
    uploadData = data;
    uploadFilename = filename;
    uploadReceiveTimeout = receiveTimeout;
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

  /// Served in order, one per pick, before falling back to [path].
  final paths = <String>[];

  @override
  Future<String?> pick(ImageSource source) async {
    sources.add(source);
    if (error != null) throw error!;
    return paths.isNotEmpty ? paths.removeAt(0) : path;
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

  group('todo 461', () {
    const fullResult = DiagnosisOutcome(
      status: 'diagnosed',
      results: [
        DiagnosisResult(
          id: 1,
          name: 'Root rot',
          confidencePercentage: 82,
          severity: 'moderate',
          symptoms: 'Mushy, dark roots',
          immediateActions: 'Stop watering',
          treatments: 'Repot into fresh mix.',
        ),
      ],
    );

    test('the results fixture maps every field the card shows', () async {
      final api = _RecordingApiService(
        created: {'request_id': 'abc-123'},
        results: {
          'status': 'diagnosed',
          'results': [
            {
              'id': 7,
              'suggested_disease_name': 'Root rot',
              'confidence_percentage': 82.4,
              'severity_assessment': 'moderate',
              'symptoms_identified': 'Mushy, dark roots',
              'immediate_actions': 'Stop watering',
              'recommended_treatments': 'Repot into fresh mix.',
            },
          ],
        },
      );

      final outcome = await HttpDiagnoseApi(
        api,
      ).diagnose(imagePath: '/x.jpg', symptoms: 's');

      final r = outcome.results.single;
      expect(r.severity, 'moderate');
      expect(r.symptoms, 'Mushy, dark roots');
      expect(r.immediateActions, 'Stop watering');
      expect(r.treatments, 'Repot into fresh mix.');
    });

    testWidgets('the card shows severity, symptoms and immediate actions', (
      tester,
    ) async {
      final api = _FakeDiagnoseApi()..outcome = fullResult;
      await tester.pumpWidget(_wrap(api, _FakePicker()));
      await _fill(tester);
      await _tapDiagnose(tester);
      await tester.pump();

      expect(find.textContaining('moderate'), findsOneWidget);
      expect(find.textContaining('Mushy, dark roots'), findsOneWidget);
      expect(find.textContaining('Stop watering'), findsOneWidget);
    });

    testWidgets('a new photo clears the previous result', (tester) async {
      final api = _FakeDiagnoseApi()..outcome = fullResult;
      final picker = _FakePicker()..paths.addAll(['/tmp/a.jpg', '/tmp/b.jpg']);
      await tester.pumpWidget(_wrap(api, picker));
      await _fill(tester);
      await _tapDiagnose(tester);
      await tester.pump();
      expect(find.text('Root rot'), findsOneWidget);

      await tester.ensureVisible(find.text('Retake'));
      await tester.tap(find.text('Retake'));
      await tester.pump();

      expect(find.text('Root rot'), findsNothing);
    });

    testWidgets('edited symptoms clear the previous result, a cursor move '
        'does not', (tester) async {
      final api = _FakeDiagnoseApi()..outcome = fullResult;
      await tester.pumpWidget(_wrap(api, _FakePicker()));
      await _fill(tester);
      await _tapDiagnose(tester);
      await tester.pump();
      expect(find.text('Root rot'), findsOneWidget);

      final field = find.widgetWithText(TextField, 'Symptoms');
      tester.widget<TextField>(field).controller!.selection =
          const TextSelection.collapsed(offset: 2);
      await tester.pump();
      expect(find.text('Root rot'), findsOneWidget);

      await tester.enterText(field, 'Brown spots on new leaves');
      await tester.pump();
      expect(find.text('Root rot'), findsNothing);
    });

    testWidgets('the chosen condition and the trimmed location reach '
        'diagnose()', (tester) async {
      final api = _FakeDiagnoseApi();
      await tester.pumpWidget(_wrap(api, _FakePicker()));
      await _fill(tester, symptoms: '  Brown spots  ');

      await tester.ensureVisible(find.text('Plant condition (optional)'));
      await tester.tap(find.text('Plant condition (optional)'));
      await tester.pumpAndSettle();
      await tester.tap(find.text(plantConditionChoices['poor']!).last);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Location (optional)'),
        '  North window  ',
      );
      await tester.pump();
      await _tapDiagnose(tester);
      await tester.pump();

      expect(api.calls.single, {
        'imagePath': _FakePicker.path,
        'symptoms': 'Brown spots',
        'plantCondition': 'poor',
        'location': 'North window',
      });
    });

    testWidgets('a pending or processing outcome says it is still running, '
        'not an empty result', (tester) async {
      final api = _FakeDiagnoseApi()
        ..outcome = const DiagnosisOutcome(status: 'processing', results: []);
      await tester.pumpWidget(_wrap(api, _FakePicker()));
      await _fill(tester);
      await _tapDiagnose(tester);
      await tester.pump();

      expect(find.textContaining('still being prepared'), findsOneWidget);
      expect(find.textContaining('No diagnosis was produced'), findsNothing);
      expect(
        const DiagnosisOutcome(status: 'pending', results: []).inProgress,
        isTrue,
      );
    });

    testWidgets('the preview decodes at its laid-out width, not the photo\'s', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(_FakeDiagnoseApi(), _FakePicker()));
      await tester.tap(find.text('Choose photo'));
      await tester.pump();

      final image = tester.widget<Image>(
        find.descendant(
          of: find.bySemanticsLabel('Selected plant photo'),
          matching: find.byType(Image),
        ),
      );
      final box = tester.getSize(find.byType(AspectRatio).first);
      final dpr = tester.view.devicePixelRatio;
      expect(image.image, isA<ResizeImage>());
      expect((image.image as ResizeImage).width, (box.width * dpr).ceil());
      expect(previewCacheWidth(double.infinity, 3), isNull);
    });

    test('an Android HEIC pick uploads with a .jpg name; other names pass '
        'through', () {
      expect(
        diagnoseUploadName('/cache/scaled_IMG_0042.HEIC'),
        'scaled_IMG_0042.jpg',
      );
      expect(diagnoseUploadName('/cache/leaf.heif'), 'leaf.jpg');
      expect(diagnoseUploadName('/cache/leaf.jpg'), 'leaf.jpg');
      expect(diagnoseUploadName('/cache/leaf.png'), 'leaf.png');
    });

    test('the diagnose upload asks for a receive timeout above the '
        "server's 60 s plant.health call", () async {
      final api = _RecordingApiService(
        created: {'request_id': 'r1'},
        results: {'status': 'diagnosed', 'results': []},
      );
      await HttpDiagnoseApi(
        api,
      ).diagnose(imagePath: '/cache/IMG_1.heic', symptoms: 's');

      expect(api.uploadReceiveTimeout, slowAnalysisReceiveTimeout);
      expect(slowAnalysisReceiveTimeout, greaterThan(Duration(seconds: 60)));
      expect(api.uploadFilename, 'IMG_1.jpg');
    });

    group('over real HTTP', () {
      late HttpServer server;
      late List<(String, String, Map<String, String?>)> seen;
      HttpOverrides? saved;
      Duration createDelay = Duration.zero;

      setUp(() async {
        saved = HttpOverrides.current;
        HttpOverrides.global = null;
        seen = [];
        createDelay = Duration.zero;
        server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
        server.listen((request) async {
          final body = utf8.decode(
            await request.fold<List<int>>(<int>[], (a, c) => a..addAll(c)),
            allowMalformed: true,
          );
          final contentType = request.headers.contentType;
          seen.add((
            request.method,
            request.uri.path,
            {'contentType': contentType?.mimeType, 'body': body},
          ));
          final isCreate = request.method == 'POST';
          if (isCreate) await Future<void>.delayed(createDelay);
          request.response
            ..statusCode = isCreate ? HttpStatus.created : HttpStatus.ok
            ..headers.contentType = ContentType.json
            ..write(
              jsonEncode(
                isCreate
                    ? {'request_id': 'r-1', 'status': 'diagnosed'}
                    : {
                        'status': 'diagnosed',
                        'results': [
                          {'id': 1, 'suggested_disease_name': 'Root rot'},
                        ],
                      },
              ),
            );
          await request.response.close();
        });
      });

      tearDown(() async {
        await server.close(force: true);
        HttpOverrides.global = saved;
      });

      test('the real multipart upload carries image_1 under a .jpg name and '
          'the form fields', () async {
        final dir = await Directory.systemTemp.createTemp('diagnose');
        addTearDown(() => dir.delete(recursive: true));
        final photo = File('${dir.path}/scaled_IMG_7.heic')
          ..writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0, 1, 2, 3]);
        final api = ApiService(
          baseUrl: 'http://${server.address.host}:${server.port}/api/v1',
        );

        final outcome = await HttpDiagnoseApi(api).diagnose(
          imagePath: photo.path,
          symptoms: 'Mushy stems',
          plantCondition: 'poor',
          location: 'Bathroom',
        );

        expect(outcome.results.single.name, 'Root rot');
        final create = seen.first;
        expect(create.$1, 'POST');
        expect(create.$2, '/api/v1/plant-identification/disease-requests/');
        expect(create.$3['contentType'], 'multipart/form-data');
        final body = create.$3['body']!;
        expect(body, contains('name="image_1"; filename="scaled_IMG_7.jpg"'));
        expect(body, isNot(contains('.heic')));
        expect(body, contains('name="symptoms_description"'));
        expect(body, contains('Mushy stems'));
        expect(body, contains('name="plant_condition"'));
        expect(body, contains('name="location"'));
        expect(
          seen.last.$2,
          '/api/v1/plant-identification/disease-requests/r-1/results/',
        );
      });

      test("uploadFile's receiveTimeout overrides the client default for "
          'that request', () async {
        final dir = await Directory.systemTemp.createTemp('diagnose');
        addTearDown(() => dir.delete(recursive: true));
        final photo = File('${dir.path}/p.jpg')..writeAsBytesSync([1, 2, 3]);
        final api = ApiService(
          baseUrl: 'http://${server.address.host}:${server.port}',
        );
        createDelay = const Duration(milliseconds: 400);

        await expectLater(
          api.uploadFile(
            '/up/',
            filePath: photo.path,
            receiveTimeout: const Duration(milliseconds: 50),
          ),
          throwsA(
            isA<ApiException>().having(
              (e) => e.message,
              'message',
              contains('timeout'),
            ),
          ),
        );

        final ok = await api.uploadFile(
          '/up/',
          filePath: photo.path,
          receiveTimeout: const Duration(seconds: 5),
        );
        expect(ok.statusCode, HttpStatus.created);
      });
    });
  });
}
