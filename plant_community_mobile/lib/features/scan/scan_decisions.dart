import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/auth_service.dart';
import 'scan_job_api.dart';

/// Finished scans the user has not kept or dismissed yet (My Plants shows
/// them as cards). Empty while signed out.
final undecidedScansProvider = FutureProvider.autoDispose<List<ScanJob>>((
  ref,
) async {
  if (ref.watch(currentUserIdProvider) == null) return const [];
  return ref.watch(scanJobApiProvider).undecided();
});
