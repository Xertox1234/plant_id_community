import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

void main() {
  group('FirestoreService', () {
    // These cover the Plant (de)serialization contract FirestoreService relies
    // on. The real service CRUD/stream behavior is exercised against a
    // FakeFirebaseFirestore in the 'FirestoreService against fake Firestore'
    // group below.

    test('Plant model toJson/fromJson roundtrip', () {
      // Create test plant
      final plant = Plant(
        id: 'test-123',
        name: 'Test Plant',
        scientificName: 'Testus plantus',
        description: 'A test plant for unit testing',
        care: ['Water daily', 'Full sun', 'Fertilize monthly'],
        imageUrl: 'https://example.com/plant.jpg',
        timestamp: DateTime.parse('2025-11-15T10:00:00Z'),
      );

      // Convert to JSON
      final json = plant.toJson();

      // Verify JSON structure
      expect(json['id'], equals('test-123'));
      expect(json['name'], equals('Test Plant'));
      expect(json['scientificName'], equals('Testus plantus'));
      expect(json['description'], equals('A test plant for unit testing'));
      expect(json['care'], isA<List<String>>());
      expect(json['care'].length, equals(3));
      expect(json['imageUrl'], equals('https://example.com/plant.jpg'));
      expect(json['timestamp'], equals('2025-11-15T10:00:00.000Z'));

      // Convert back to Plant
      final plantFromJson = Plant.fromJson(json);

      // Verify roundtrip
      expect(plantFromJson.id, equals(plant.id));
      expect(plantFromJson.name, equals(plant.name));
      expect(plantFromJson.scientificName, equals(plant.scientificName));
      expect(plantFromJson.description, equals(plant.description));
      expect(plantFromJson.care, equals(plant.care));
      expect(plantFromJson.imageUrl, equals(plant.imageUrl));
      expect(plantFromJson.timestamp, equals(plant.timestamp));
    });

    test('Plant model handles null imageUrl', () {
      final plant = Plant(
        id: 'test-456',
        name: 'No Image Plant',
        scientificName: 'Noimage plantus',
        description: 'Plant without image',
        care: ['Water weekly'],
        imageUrl: null, // No image
        timestamp: DateTime.now(),
      );

      final json = plant.toJson();
      expect(json['imageUrl'], isNull);

      final plantFromJson = Plant.fromJson(json);
      expect(plantFromJson.imageUrl, isNull);
    });

    test('Plant model handles empty care array', () {
      final plant = Plant(
        id: 'test-789',
        name: 'Low Care Plant',
        scientificName: 'Lowcare plantus',
        description: 'Requires no special care',
        care: [], // Empty care instructions
        timestamp: DateTime.now(),
      );

      final json = plant.toJson();
      expect(json['care'], isA<List<String>>());
      expect(json['care'].length, equals(0));

      final plantFromJson = Plant.fromJson(json);
      expect(plantFromJson.care, isEmpty);
    });

    test('FirestoreException has correct message', () {
      final exception = FirestoreException('Test error message');
      expect(exception.message, equals('Test error message'));
      expect(
        exception.toString(),
        equals('FirestoreException: Test error message'),
      );
    });

  });

  group('Plant copyWith', () {
    final originalPlant = Plant(
      id: 'original-id',
      name: 'Original Name',
      scientificName: 'Original scientific',
      description: 'Original description',
      care: ['Original care'],
      imageUrl: 'https://example.com/original.jpg',
      timestamp: DateTime.parse('2025-01-01T00:00:00Z'),
    );

    test('copyWith returns identical plant when no arguments', () {
      final copiedPlant = originalPlant.copyWith();

      expect(copiedPlant.id, equals(originalPlant.id));
      expect(copiedPlant.name, equals(originalPlant.name));
      expect(copiedPlant.scientificName, equals(originalPlant.scientificName));
      expect(copiedPlant.description, equals(originalPlant.description));
      expect(copiedPlant.care, equals(originalPlant.care));
      expect(copiedPlant.imageUrl, equals(originalPlant.imageUrl));
      expect(copiedPlant.timestamp, equals(originalPlant.timestamp));
    });

    test('copyWith updates only specified fields', () {
      final newTimestamp = DateTime.parse('2025-11-15T10:00:00Z');

      final copiedPlant = originalPlant.copyWith(
        name: 'Updated Name',
        timestamp: newTimestamp,
      );

      expect(copiedPlant.id, equals(originalPlant.id)); // Unchanged
      expect(copiedPlant.name, equals('Updated Name')); // Changed
      expect(
        copiedPlant.scientificName,
        equals(originalPlant.scientificName),
      ); // Unchanged
      expect(
        copiedPlant.description,
        equals(originalPlant.description),
      ); // Unchanged
      expect(copiedPlant.care, equals(originalPlant.care)); // Unchanged
      expect(copiedPlant.imageUrl, equals(originalPlant.imageUrl)); // Unchanged
      expect(copiedPlant.timestamp, equals(newTimestamp)); // Changed
    });

    test('copyWith preserves imageUrl when not specified', () {
      // When imageUrl is not provided, it should preserve original value
      final copiedPlant = originalPlant.copyWith(name: 'New Name');

      expect(copiedPlant.imageUrl, equals(originalPlant.imageUrl));
    });

    test('copyWith can update care instructions', () {
      final newCare = [
        'Water twice daily',
        'Partial shade',
        'Fertilize weekly',
      ];

      final copiedPlant = originalPlant.copyWith(care: newCare);

      expect(copiedPlant.care, equals(newCare));
      expect(copiedPlant.care.length, equals(3));
    });
  });

  group('Firestore Data Validation', () {
    test('Plant requires all mandatory fields', () {
      // This would throw at runtime if required fields are missing
      expect(
        () => Plant(
          id: 'test-id',
          name: 'Test',
          scientificName: 'Testus',
          description: 'Test desc',
          care: [],
          timestamp: DateTime.now(),
        ),
        returnsNormally,
      );
    });

    test('Plant fromJson handles ISO 8601 timestamp formats', () {
      final testCases = [
        '2025-11-15T10:00:00.000Z', // With milliseconds and Z
        '2025-11-15T10:00:00Z', // Without milliseconds
        '2025-11-15T10:00:00.000+00:00', // With timezone offset
      ];

      for (final timestampString in testCases) {
        final json = {
          'id': 'test',
          'name': 'Test',
          'scientificName': 'Test',
          'description': 'Test',
          'care': <String>[],
          'timestamp': timestampString,
        };

        final plant = Plant.fromJson(json);
        expect(plant.timestamp, isA<DateTime>());
      }
    });

    test('Plant fromJson throws on invalid timestamp', () {
      final json = {
        'id': 'test',
        'name': 'Test',
        'scientificName': 'Test',
        'description': 'Test',
        'care': <String>[],
        'timestamp': 'not-a-valid-date',
      };

      expect(() => Plant.fromJson(json), throwsFormatException);
    });

    test('Plant fromJson throws on missing required fields', () {
      final json = {
        'id': 'test',
        'name': 'Test',
        // Missing scientificName, description, care, timestamp
      };

      expect(() => Plant.fromJson(json), throwsA(isA<TypeError>()));
    });

    test('Plant fromJson handles care as List<dynamic>', () {
      final json = {
        'id': 'test',
        'name': 'Test',
        'scientificName': 'Test',
        'description': 'Test',
        'care': <dynamic>['Water daily', 'Full sun'], // List<dynamic>
        'timestamp': '2025-11-15T10:00:00Z',
      };

      final plant = Plant.fromJson(json);
      expect(plant.care, isA<List<String>>());
      expect(plant.care.length, equals(2));
    });
  });

  // Exercises the REAL FirestoreService against an in-memory FakeFirebaseFirestore
  // injected through firebaseFirestoreProvider — so the actual query, parsing,
  // ordering and error-skipping logic runs, not a hand-rolled reimplementation.
  group('FirestoreService against fake Firestore', () {
    late FakeFirebaseFirestore fake;
    late ProviderContainer container;
    late FirestoreService service;

    const uid = 'user-1';

    Plant plantAt(String id, DateTime ts, {String name = 'Plant'}) => Plant(
      id: id,
      name: name,
      scientificName: '$name scientificus',
      description: 'desc',
      care: const ['Water weekly'],
      timestamp: ts,
    );

    setUp(() {
      fake = FakeFirebaseFirestore();
      container = ProviderContainer(
        overrides: [firebaseFirestoreProvider.overrideWithValue(fake)],
      );
      service = container.read(firestoreServiceProvider.notifier);
    });

    tearDown(() => container.dispose());

    test('savePlant persists and getPlantsStream reads it back', () async {
      await service.savePlant(
        uid,
        plantAt('p1', DateTime.parse('2026-01-01T00:00:00Z'), name: 'Rose'),
      );

      final snapshot = await service.getPlantsStream(uid).first;

      expect(snapshot.plants, hasLength(1));
      expect(snapshot.plants.first.id, 'p1');
      expect(snapshot.plants.first.name, 'Rose');
    });

    test('getPlantsStream orders plants by timestamp, newest first', () async {
      await service.savePlant(
        uid,
        plantAt('old', DateTime.parse('2026-01-01T00:00:00Z')),
      );
      await service.savePlant(
        uid,
        plantAt('new', DateTime.parse('2026-03-01T00:00:00Z')),
      );
      await service.savePlant(
        uid,
        plantAt('mid', DateTime.parse('2026-02-01T00:00:00Z')),
      );

      final snapshot = await service.getPlantsStream(uid).first;

      expect(snapshot.plants.map((p) => p.id).toList(), ['new', 'mid', 'old']);
    });

    test('getPlantsStream skips malformed documents', () async {
      // A document that cannot be parsed (missing required fields), written
      // straight to the backend to simulate a corrupt/foreign record.
      await fake
          .collection('users')
          .doc(uid)
          .collection('identified_plants')
          .doc('broken')
          .set({
            'id': 'broken',
            'timestamp': DateTime.parse('2026-03-01T00:00:00Z')
                .toIso8601String(),
          });
      await service.savePlant(
        uid,
        plantAt('good', DateTime.parse('2026-02-01T00:00:00Z')),
      );

      final snapshot = await service.getPlantsStream(uid).first;

      expect(snapshot.plants.map((p) => p.id).toList(), ['good']);
    });

    test('deletePlant removes a plant', () async {
      await service.savePlant(
        uid,
        plantAt('p1', DateTime.parse('2026-01-01T00:00:00Z')),
      );

      await service.deletePlant(uid, 'p1');

      final snapshot = await service.getPlantsStream(uid).first;
      expect(snapshot.plants, isEmpty);
    });

    test('getPlant returns the plant, or null when missing', () async {
      await service.savePlant(
        uid,
        plantAt('p1', DateTime.parse('2026-01-01T00:00:00Z'), name: 'Fern'),
      );

      final found = await service.getPlant(uid, 'p1');
      expect(found, isNotNull);
      expect(found!.name, 'Fern');

      final missing = await service.getPlant(uid, 'nope');
      expect(missing, isNull);
    });

    test('clearAllPlants removes every plant for the user', () async {
      await service.savePlant(
        uid,
        plantAt('p1', DateTime.parse('2026-01-01T00:00:00Z')),
      );
      await service.savePlant(
        uid,
        plantAt('p2', DateTime.parse('2026-02-01T00:00:00Z')),
      );

      await service.clearAllPlants(uid);

      final snapshot = await service.getPlantsStream(uid).first;
      expect(snapshot.plants, isEmpty);
    });

    test('plants are scoped per user', () async {
      await service.savePlant(
        'user-a',
        plantAt('a1', DateTime.parse('2026-01-01T00:00:00Z')),
      );
      await service.savePlant(
        'user-b',
        plantAt('b1', DateTime.parse('2026-01-01T00:00:00Z')),
      );

      final aSnap = await service.getPlantsStream('user-a').first;
      final bSnap = await service.getPlantsStream('user-b').first;

      expect(aSnap.plants.map((p) => p.id), ['a1']);
      expect(bSnap.plants.map((p) => p.id), ['b1']);
    });

    test('savePlant rejects an empty userId', () async {
      await expectLater(
        () => service.savePlant(
          '',
          plantAt('p1', DateTime.parse('2026-01-01T00:00:00Z')),
        ),
        throwsA(isA<FirestoreException>()),
      );
    });
  });
}
