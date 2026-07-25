/// One page of a DRF `CursorPagination` list response
/// (`{next, previous, results}`). There is **no `count`** field — "has more"
/// is derived from `next != null`.
///
/// [next]/[previous] are absolute URLs; pass [next] straight back to the API
/// client to fetch the following page.
class CursorPage<T> {
  const CursorPage({required this.items, this.next, this.previous});

  final List<T> items;
  final String? next;
  final String? previous;

  bool get hasMore => next != null;

  /// Parse an envelope, mapping each `results` entry with [fromJson].
  factory CursorPage.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) fromJson,
  ) {
    final results = (json['results'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(fromJson)
        .toList(growable: false);
    return CursorPage<T>(
      items: results,
      next: json['next'] as String?,
      previous: json['previous'] as String?,
    );
  }
}
