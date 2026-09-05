/**
 * Report reasons shared by the post-report picker (PostCard) and the
 * direct-message report form (ConversationPage, todo 339). Mirrors
 * wagtail_forum Report.REASON_CHOICES — one list, so the two pickers can never
 * drift. A `.ts` module because a `.tsx` component file may export only
 * components (react-refresh/only-export-components).
 */
export const REPORT_REASONS = [
  { value: 'spam', label: 'Spam' },
  { value: 'abuse', label: 'Abuse' },
  { value: 'off_topic', label: 'Off topic' },
  { value: 'other', label: 'Other' },
] as const;

export type ReportReason = (typeof REPORT_REASONS)[number]['value'];
