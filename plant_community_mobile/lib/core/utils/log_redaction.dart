/// Utilities for GDPR-compliant logging — never write raw PII to logs.
library;

/// Redacts an email address for logging.
///
/// Shows the first two characters of the local part plus the domain, e.g.
/// `john.doe@example.com` -> `jo***@example.com`. Returns `***` when there is
/// no usable email. Mirrors the backend `redact_email` helper.
String redactEmail(String? email) {
  if (email == null || !email.contains('@')) {
    return '***';
  }
  final parts = email.split('@');
  final local = parts.first;
  final domain = parts.sublist(1).join('@');
  if (local.length <= 2) {
    return '${'*' * local.length}@$domain';
  }
  return '${local.substring(0, 2)}***@$domain';
}
