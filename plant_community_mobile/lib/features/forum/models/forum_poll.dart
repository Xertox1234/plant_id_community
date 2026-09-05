/// One choice in a topic's poll, with its server-aggregated count. Mirrors
/// the backend `POLL_OPTION_SCHEMA` (`wagtail_forum/api/serializers.py`).
class ForumPollOption {
  const ForumPollOption({
    required this.id,
    required this.text,
    required this.order,
    required this.voteCount,
  });

  final int id;
  final String text;
  final int order;

  /// Aggregated server-side from vote rows on every read. There is no
  /// stored counter and no writable path to this number — render it, never
  /// derive or submit it.
  final int voteCount;

  factory ForumPollOption.fromJson(Map<String, dynamic> json) {
    return ForumPollOption(
      id: json['id'] as int,
      text: json['text'] as String? ?? '',
      order: json['order'] as int? ?? 0,
      voteCount: json['vote_count'] as int? ?? 0,
    );
  }
}

/// A topic's poll with server-computed results and the viewer's own vote
/// (todo 341 wave 3). Mirrors the backend `POLL_SCHEMA` — the ONE read shape
/// `TopicDetailSerializer.get_poll` and `PollVoteView` both return
/// (`Poll.serialize`).
///
/// A vote is one final submission per viewer: single-choice ([maxChoices]
/// == 1) is one option, multi-choice is 1..[maxChoices] options sent
/// together. A second submission is refused (409), never replaced.
class ForumPoll {
  const ForumPoll({
    required this.id,
    required this.question,
    this.closesAt,
    required this.isClosed,
    required this.maxChoices,
    required this.options,
    required this.totalVotes,
    required this.myVoteOptionIds,
    this.pendingOptionIds = const [],
  });

  final int id;
  final String question;

  /// `null` when the poll never closes.
  final DateTime? closesAt;
  final bool isClosed;

  /// 1 = single-choice; N = a voter may pick up to N options in one ballot.
  final int maxChoices;
  final List<ForumPollOption> options;

  /// People who answered (distinct voters), not vote rows — in a
  /// multi-choice poll the per-option counts can sum past this.
  final int totalVotes;

  /// THIS viewer's own choice(s); empty when they have not voted (and always
  /// empty for anonymous). Never anyone else's — only the aggregate is
  /// public.
  final List<int> myVoteOptionIds;

  /// CLIENT-ONLY: the ballot currently in flight, empty when idle. Never
  /// parsed from JSON. Set by `TopicDetail.votePoll` the moment a ballot is
  /// submitted (so the card disables its controls at once), cleared on
  /// failure (revert) and replaced wholesale by the server's poll on
  /// success. Counts are never touched locally — they are shared state
  /// every reader sees and the server can legitimately refuse a vote.
  final List<int> pendingOptionIds;

  bool get hasVoted => myVoteOptionIds.isNotEmpty;
  bool get isMultiChoice => maxChoices > 1;
  bool get isVoting => pendingOptionIds.isNotEmpty;

  /// Whole-number percent of [totalVotes] for [option], or 0 when nobody
  /// has voted. In a multi-choice poll this is "share of voters who picked
  /// this", so the percentages can sum past 100.
  int percentFor(ForumPollOption option) {
    if (totalVotes <= 0) return 0;
    return ((option.voteCount / totalVotes) * 100).round();
  }

  ForumPoll copyWith({List<int>? pendingOptionIds}) {
    return ForumPoll(
      id: id,
      question: question,
      closesAt: closesAt,
      isClosed: isClosed,
      maxChoices: maxChoices,
      options: options,
      totalVotes: totalVotes,
      myVoteOptionIds: myVoteOptionIds,
      pendingOptionIds: pendingOptionIds ?? this.pendingOptionIds,
    );
  }

  factory ForumPoll.fromJson(Map<String, dynamic> json) {
    return ForumPoll(
      id: json['id'] as int,
      question: json['question'] as String? ?? '',
      closesAt: _parseDate(json['closes_at']),
      isClosed: json['is_closed'] as bool? ?? false,
      // The server default is 1; a missing value must never read as "no
      // limit" — that would let the card send a ballot the server refuses.
      maxChoices: json['max_choices'] as int? ?? 1,
      options: (json['options'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ForumPollOption.fromJson)
          .toList(growable: false),
      totalVotes: json['total_votes'] as int? ?? 0,
      myVoteOptionIds:
          (json['my_vote_option_ids'] as List<dynamic>? ?? const [])
              .whereType<int>()
              .toList(growable: false),
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value)?.toLocal();
  }
  return null;
}
