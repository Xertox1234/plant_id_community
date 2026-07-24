/**
 * The forum reaction types, single-sourced for the web client.
 *
 * MUST stay in sync with the backend's `Reaction.REACTION_CHOICES`
 * (`backend/packages/wagtail_forum/wagtail_forum/models/reactions.py`), which is
 * also the enum exposed in the OpenAPI schema. There is no OpenAPI→TS codegen in
 * this app, so a backend drift-guard test
 * (`backend/apps/forum_host/tests/test_reaction_contract.py`) reads THIS literal
 * and fails CI if the two lists diverge (audit L16).
 */
export const REACTION_TYPES = ['like', 'love', 'helpful', 'thanks'] as const;
