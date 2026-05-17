# Wagtail CMS — binding rules

Compact checklist auto-injected before edits. Long-form:
`backend/docs/patterns/domain/wagtail.md`, `.../domain/blog.md`.

- **Wagtail admin is at `/cms/`, not `/admin/`.**
- **Signal handlers use `isinstance(instance, BlogPostPage)`**, never `hasattr` —
  multi-table inheritance makes `hasattr` match unintended page types.
- **StreamField blocks need matching frontend handling** — every new block type
  added to a model must get a case in the React `StreamFieldRenderer`.
- **Prefetch related pages** (`related_posts`, etc.) in the API queryset to avoid
  N+1 and empty results.
- Cache-invalidation signals must cover `page_published` AND `page_unpublished`.
- Verify the Wagtail API v2 serializes new fields before wiring the frontend.
