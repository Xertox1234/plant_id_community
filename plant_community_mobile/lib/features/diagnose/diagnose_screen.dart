import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/constants/app_spacing.dart';
import '../../services/api_service.dart';
import 'diagnose_api.dart';

/// Diagnose a sick plant (todo 444): a photo, the symptoms, and optionally
/// the plant's condition and location; then the diagnosis. Signed-in only
/// (the router guards `/diagnose`; the API is `IsAuthenticated`).
class DiagnoseScreen extends ConsumerStatefulWidget {
  const DiagnoseScreen({super.key});

  @override
  ConsumerState<DiagnoseScreen> createState() => _DiagnoseScreenState();
}

class _DiagnoseScreenState extends ConsumerState<DiagnoseScreen> {
  final _symptoms = TextEditingController();
  final _location = TextEditingController();
  String? _imagePath;
  String? _condition;
  bool _loading = false;
  String? _error;
  DiagnosisOutcome? _outcome;

  @override
  void initState() {
    super.initState();
    // Rebuild so the submit button tracks the symptoms field.
    _symptoms.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _symptoms.dispose();
    _location.dispose();
    super.dispose();
  }

  bool get _canSubmit =>
      _imagePath != null && _symptoms.text.trim().isNotEmpty && !_loading;

  Future<void> _pick(ImageSource source) async {
    try {
      final path = await ref.read(diagnoseImagePickerProvider).pick(source);
      if (path == null || !mounted) return;
      setState(() {
        _imagePath = path;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(
        () => _error = e is ApiException && e.statusCode == 413
            ? e.message
            : "Couldn't open the photo. Try another one.",
      );
    }
  }

  Future<void> _submit() async {
    if (!_canSubmit) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _error = null;
      _outcome = null;
    });
    try {
      final outcome = await ref
          .read(diagnoseApiProvider)
          .diagnose(
            imagePath: _imagePath!,
            symptoms: _symptoms.text.trim(),
            plantCondition: _condition,
            location: _location.text.trim(),
          );
      if (!mounted) return;
      setState(() {
        if (outcome.failed) {
          _error = 'Diagnosis unavailable — please try again.';
        } else {
          _outcome = outcome;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = diagnoseErrorMessage(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final outcome = _outcome;
    return Scaffold(
      appBar: AppBar(title: const Text('Diagnose a sick plant')),
      body: SafeArea(
        // Not a ListView: a short form should build every field, so focus
        // traversal and screen readers reach the ones below the photo.
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Add a photo of the affected leaves and describe the symptoms.',
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: AppSpacing.md),
              _PhotoPicker(
                imagePath: _imagePath,
                enabled: !_loading,
                onPick: _pick,
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _symptoms,
                enabled: !_loading,
                minLines: 3,
                maxLines: 6,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Symptoms',
                  hintText:
                      'e.g. Yellow leaves with black spots, spreading from the '
                      'bottom up',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              DropdownButtonFormField<String>(
                initialValue: _condition,
                decoration: const InputDecoration(
                  labelText: 'Plant condition (optional)',
                  border: OutlineInputBorder(),
                ),
                items: [
                  for (final e in plantConditionChoices.entries)
                    DropdownMenuItem(value: e.key, child: Text(e.value)),
                ],
                onChanged: _loading
                    ? null
                    : (value) => setState(() => _condition = value),
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _location,
                enabled: !_loading,
                maxLength: 200,
                decoration: const InputDecoration(
                  labelText: 'Location (optional)',
                  hintText: 'e.g. North window, bathroom',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              FilledButton.icon(
                onPressed: _canSubmit ? _submit : null,
                icon: _loading
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(LucideIcons.stethoscope),
                label: Text(_loading ? 'Diagnosing…' : 'Diagnose'),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.md),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.error,
                    ),
                  ),
                ),
              ],
              if (outcome != null) ...[
                const SizedBox(height: AppSpacing.lg),
                _Results(outcome: outcome),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// User-facing copy for a failed diagnosis. Never a raw exception string.
String diagnoseErrorMessage(Object error) {
  if (error is ApiException) {
    switch (error.statusCode) {
      case 429:
        return 'Too many diagnoses in a row — try again in a minute.';
      case 401:
        return 'Your session expired. Sign in again to diagnose.';
      case 400:
      case 413:
        // The serializer's own message ("Please describe the symptoms…",
        // an image-validation reason) is specific and human.
        if (error.message.isNotEmpty) return error.message;
    }
  }
  return 'Diagnosis unavailable — please try again.';
}

class _PhotoPicker extends StatelessWidget {
  const _PhotoPicker({
    required this.imagePath,
    required this.enabled,
    required this.onPick,
  });

  final String? imagePath;
  final bool enabled;
  final void Function(ImageSource source) onPick;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final path = imagePath;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (path != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: AspectRatio(
              aspectRatio: 4 / 3,
              child: Semantics(
                image: true,
                label: 'Selected plant photo',
                child: Image.file(
                  File(path),
                  fit: BoxFit.cover,
                  errorBuilder: (context, _, _) =>
                      ColoredBox(color: theme.colorScheme.surfaceContainerHigh),
                ),
              ),
            ),
          ),
        if (path != null) const SizedBox(height: AppSpacing.sm),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: enabled ? () => onPick(ImageSource.camera) : null,
                icon: const Icon(LucideIcons.camera),
                label: Text(path == null ? 'Take photo' : 'Retake'),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: enabled ? () => onPick(ImageSource.gallery) : null,
                icon: const Icon(LucideIcons.image),
                label: const Text('Choose photo'),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({required this.outcome});

  final DiagnosisOutcome outcome;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (outcome.results.isEmpty) {
      return Semantics(
        liveRegion: true,
        child: const Text(
          'No diagnosis was produced. Please try a clearer photo and a fuller '
          'symptom description.',
        ),
      );
    }
    return Semantics(
      liveRegion: true,
      container: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final r in outcome.results)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: r.isSystemMessage
                  ? Container(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.surfaceContainerHigh,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(r.notes),
                    )
                  : _ResultCard(result: r),
            ),
        ],
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result});

  final DiagnosisResult result;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final pct = result.confidencePercentage;
    Widget line(String label, String text) => Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xs),
      child: Text.rich(
        TextSpan(
          children: [
            TextSpan(
              text: '$label: ',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            TextSpan(text: text),
          ],
        ),
        style: theme.textTheme.bodyMedium,
      ),
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    result.name.isNotEmpty ? result.name : 'Unknown condition',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                if (pct != null)
                  Semantics(
                    label: '$pct percent confidence',
                    child: ExcludeSemantics(
                      child: Text('$pct%', style: theme.textTheme.labelLarge),
                    ),
                  ),
              ],
            ),
            if (result.severity.isNotEmpty) line('Severity', result.severity),
            if (result.symptoms.isNotEmpty) line('Symptoms', result.symptoms),
            if (result.immediateActions.isNotEmpty)
              line('Immediate actions', result.immediateActions),
            if (result.treatments.isNotEmpty)
              line('Recommended treatments', result.treatments),
          ],
        ),
      ),
    );
  }
}
