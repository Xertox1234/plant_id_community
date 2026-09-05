import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';

/// A topic's poll (audit M8; todo 341 wave 3): the question, the ballot,
/// and — once the viewer has voted or the poll has closed — a result bar
/// per option. Mirrors the web `PollCard`.
///
/// Single-choice polls (`maxChoices == 1`) vote with one tap per option.
/// Multi-choice polls collect a ballot of checkboxes, CAPPED client-side at
/// `maxChoices` (an unticked box goes inert once the ballot is full, so the
/// Vote button can never send a ballot the server would refuse whole), and
/// submit it with one Vote button.
///
/// Every number here comes from the server. Results stay hidden until the
/// viewer votes (or the poll closes) so the running tally cannot anchor
/// their choice; the total is shown throughout. "Optimistic" here means the
/// CONTROLS: `poll.pendingOptionIds` (set by `TopicDetail.votePoll` the
/// moment a ballot is sent) disables them at once — the counts wait for the
/// server, which can refuse.
///
/// Dumb widget: [onVote] is awaited but its errors are the caller's to show
/// (the thread screen maps them through `forumErrorMessage`).
class PollCard extends StatefulWidget {
  const PollCard({
    super.key,
    required this.poll,
    required this.canVote,
    this.onVote,
  });

  final ForumPoll poll;

  /// Signed-out viewers see the question and totals but get no ballot.
  final bool canVote;

  /// Cast a ballot (1..maxChoices option ids). `null` renders no controls.
  final Future<void> Function(List<int> optionIds)? onVote;

  @override
  State<PollCard> createState() => _PollCardState();
}

class _PollCardState extends State<PollCard> {
  /// Multi-choice draft: the option ids ticked but not yet submitted.
  final List<int> _selected = [];

  ForumPoll get _poll => widget.poll;

  bool get _showResults => _poll.hasVoted || _poll.isClosed;

  bool get _votingDisabled =>
      !widget.canVote ||
      widget.onVote == null ||
      _poll.hasVoted ||
      _poll.isClosed ||
      _poll.isVoting;

  void _toggleSelected(int optionId) {
    setState(() {
      if (_selected.contains(optionId)) {
        _selected.remove(optionId);
      } else if (_selected.length < _poll.maxChoices) {
        _selected.add(optionId);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final poll = _poll;
    final totalNoun = poll.isMultiChoice
        ? (poll.totalVotes == 1 ? 'voter' : 'voters')
        : (poll.totalVotes == 1 ? 'vote' : 'votes');
    final footer = [
      '${poll.totalVotes} $totalNoun',
      if (!widget.canVote && !poll.isClosed) 'sign in to vote',
      if (widget.canVote && poll.hasVoted) 'your vote is final',
    ].join(' · ');

    return Semantics(
      container: true,
      label: 'Poll: ${poll.question}',
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.poll_outlined,
                    size: 20,
                    color: theme.colorScheme.secondary,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      poll.question,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  if (poll.isClosed) ...[
                    const SizedBox(width: AppSpacing.sm),
                    const _ClosedChip(),
                  ],
                ],
              ),
              if (poll.isMultiChoice && !_showResults)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: Text(
                    'Pick up to ${poll.maxChoices}.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              const SizedBox(height: AppSpacing.sm),
              for (final option in poll.options) ...[
                if (_showResults)
                  _ResultRow(
                    option: option,
                    percent: poll.percentFor(option),
                    isMine: poll.myVoteOptionIds.contains(option.id),
                  )
                else if (poll.isMultiChoice)
                  _ballotCheckbox(option)
                else
                  _ballotButton(option),
                const SizedBox(height: AppSpacing.xs),
              ],
              if (poll.isMultiChoice && !_showResults)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: FilledButton(
                    onPressed: _votingDisabled || _selected.isEmpty
                        ? null
                        : () => widget.onVote?.call(List.of(_selected)),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(48, 48),
                    ),
                    child: poll.isVoting
                        ? const _ButtonSpinner()
                        : const Text('Vote'),
                  ),
                ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                footer,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _ballotButton(ForumPollOption option) {
    final pending = _poll.pendingOptionIds.contains(option.id);
    return OutlinedButton(
      onPressed: _votingDisabled
          ? null
          : () => widget.onVote?.call([option.id]),
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(double.infinity, 48),
        alignment: Alignment.centerLeft,
      ),
      child: Row(
        children: [
          Expanded(child: Text(option.text)),
          if (pending) const _ButtonSpinner(),
        ],
      ),
    );
  }

  Widget _ballotCheckbox(ForumPollOption option) {
    final isSelected = _selected.contains(option.id);
    // The cap is enforced HERE, not only server-side: an unticked box goes
    // inert once the ballot is full.
    final capped = !isSelected && _selected.length >= _poll.maxChoices;
    return CheckboxListTile(
      value: isSelected,
      onChanged: _votingDisabled || capped
          ? null
          : (_) => _toggleSelected(option.id),
      title: Text(option.text),
      controlAffinity: ListTileControlAffinity.leading,
      contentPadding: EdgeInsets.zero,
      dense: true,
    );
  }
}

class _ResultRow extends StatelessWidget {
  const _ResultRow({
    required this.option,
    required this.percent,
    required this.isMine,
  });

  final ForumPollOption option;
  final int percent;
  final bool isMine;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final votes = option.voteCount == 1 ? 'vote' : 'votes';
    return Semantics(
      label:
          '${option.text}: ${option.voteCount} $votes, $percent%'
          '${isMine ? ', your vote' : ''}',
      // The label already carries every number; without this a screen
      // reader would announce each row twice (the bar is decorative).
      excludeSemantics: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  option.text,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              if (isMine) ...[
                Icon(Icons.check, size: 14, color: theme.colorScheme.primary),
                const SizedBox(width: 2),
                Text(
                  'your vote',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.primary,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
              ],
              Text(
                '${option.voteCount} ($percent%)',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          ClipRRect(
            borderRadius: BorderRadius.circular(AppSpacing.rPill),
            child: LinearProgressIndicator(
              value: percent / 100,
              minHeight: 8,
              backgroundColor: theme.colorScheme.surfaceContainerHighest,
            ),
          ),
        ],
      ),
    );
  }
}

class _ClosedChip extends StatelessWidget {
  const _ClosedChip();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Text(
        'Closed',
        style: theme.textTheme.labelSmall?.copyWith(
          fontWeight: FontWeight.w700,
          color: theme.colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

class _ButtonSpinner extends StatelessWidget {
  const _ButtonSpinner();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 16,
      width: 16,
      child: CircularProgressIndicator(strokeWidth: 2),
    );
  }
}
