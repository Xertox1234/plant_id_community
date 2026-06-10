import type { SeverityAssessment } from '../types/diagnosis';

const SEVERITY_COLORS: Record<SeverityAssessment, string> = {
  mild: 'bg-leaf/10 text-ink ring-leaf/20',
  moderate: 'bg-warn/10 text-ink ring-warn/20',
  severe: 'bg-tertiary/10 text-ink ring-tertiary/20',
  critical: 'bg-error/10 text-ink ring-error/20',
};

const SEVERITY_FALLBACK = 'bg-surface-2 text-ink-2 ring-line/20';

/**
 * Tailwind badge classes for a diagnosis severity. Single-sourced (todo 222 / L8)
 * — `DiagnosisCard` and `DiagnosisDetailPage` carried drifted copies (one typed
 * `string`, one `SeverityAssessment`). Typed precisely here; the fallback guards
 * an unexpected runtime value.
 */
export function getSeverityColor(severity: SeverityAssessment): string {
  return SEVERITY_COLORS[severity] || SEVERITY_FALLBACK;
}
