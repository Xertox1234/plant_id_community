

### 2026-10-30 - Review round 2: non-blocking findings

- **Fixed (medium, introduced by the round-1 fix; four reviewers):** if the member's profile fetch failed, every category toggle silently did nothing for the visit. A failed load now lets toggles work locally for the visit and skips the save, because the stored set is unknown. Test `still toggles for this visit when the stored set failed to load, without saving`, mutation-checked.
- **Fixed (low):** a save queued by the previous account could run after an identity switch and PUT that account's set as the new one. Each identity change bumps a counter, and a stale queued save is dropped. Test `drops a save the previous account queued once the identity changes`, mutation-checked.
- **Declined:** collapsed ids are not intersected with real category pks. Bounded at 200 and self-only; an unknown id is inert.
