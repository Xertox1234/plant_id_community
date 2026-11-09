import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

class _RecordingFirestore extends Fake implements FirebaseFirestore {
  final List<String> calls = [];

  @override
  Future<void> terminate() async => calls.add('terminate');

  @override
  Future<void> clearPersistence() async => calls.add('clearPersistence');
}

void main() {
  test('terminates the instance before clearing its persistence', () async {
    final firestore = _RecordingFirestore();

    await clearFirestoreOfflineCache(firestore);

    // clearPersistence is refused on a started instance.
    expect(firestore.calls, ['terminate', 'clearPersistence']);
  });
}
