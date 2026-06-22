# Security — binding rules

Compact checklist auto-injected before edits. Long-form: `backend/docs/patterns/security/`.

- **ViewSet `get_permissions()` MUST call `super().get_permissions()`** for custom
  `@action` endpoints. Overriding without `super()` silently drops action-level
  `permission_classes` — a real auth hole. See `architecture/viewsets.md`.
- **Never f-string table/column names into raw SQL** (migrations included). Use
  `psycopg2.sql.Identifier()` plus an explicit whitelist of allowed names.
- **Escape SQL `LIKE` wildcards** (`%`, `_`, `\`) in user-supplied search terms
  before passing to `__icontains`/`__contains` queries.
- **File uploads: all 4 validation layers** — extension, MIME type, size, and a
  PIL/Pillow decode check. Never trust the client-sent content type alone.
- **No secrets in code, logs, or commits.** API keys and `SECRET_KEY` come from
  `.env`. `SECRET_KEY` must be ≥50 chars and must not contain `django-insecure`.
- **Sanitize all rendered HTML** with DOMPurify (web) before injecting; never
  `dangerouslySetInnerHTML` with unsanitized content.
- **Auth-sensitive code is never delegated** to the cheap worker — review by hand.
- Redact PII (emails, tokens) from logs; GDPR redaction applies to Firebase auth.
- **Never create user accounts in migrations or any other deploy-time path.**
  Blog migration 0004 auto-created superuser `plant_care_admin` with a hardcoded
  password on every `migrate` until 2026-06-10. Dev/demo/E2E seed commands must
  refuse to run in production (`if not settings.DEBUG: raise CommandError(...)`),
  and byline-only accounts get `set_unusable_password()` — never a literal password.
- **Try a bump before suppressing a vuln.** pip-audit's empty "Fix Versions"
  column does NOT mean unfixable — the advisory's affected range may exclude a
  newer release (bleach `GHSA-g75f-g53v-794x` showed no fix at 6.3.0 but was gone
  at 6.4.0). Add an `--ignore-vuln` line (in `.github/workflows/security-scan.yml`)
  only when no bump clears it, with a dated one-line justification. Run
  `npm audit fix` WITHOUT `--force` (`--force` pulls breaking majors).
