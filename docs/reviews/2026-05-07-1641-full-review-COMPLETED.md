# Full Code Review — 2026-05-07 16:41 UTC

**Review ID:** `2026-05-07-1641`  
**Started:** 2026-05-07T16:41:01Z  
**Completed:** 2026-05-07T20:31:04Z

**Scope:** backend/apps, web/src, plant_community_mobile/lib, firebase  
**Files reviewed:** 206  
**Reviewers invoked:** 10  
**Total findings:** 1043 (24 critical, 313 high, 427 medium, 239 low, 40 info)

> ⚠️ **7 invocation(s) failed** — see "Failed Invocations" at the bottom. To resume, re-invoke the orchestrator (it will detect the partial state).

## Finding Status

- [x] #8 forum-post-serializer-rich-content-n1 → todo 064 (completed 2026-05-08)
- [x] #9 forum-post-serializer-rich-content-n1 → todo 064 (completed 2026-05-08)
- [x] #10 forum-post-serializer-rich-content-n1 → todo 064 (completed 2026-05-08)
- [x] #1 forum-category-thread-count-n1 (already fixed — annotated_thread_count in CategoryViewSet, 2026-05-09)
- [x] #2 forum-category-post-count-n1 (already fixed — annotated_post_count in CategoryViewSet, 2026-05-09)
- [x] #3 flagged-content-flag-count-n1 (already fixed — annotation in ModerationQueueViewSet, 2026-05-09)
- [x] #4 setup-forums-hardcoded-password (already fixed — requires existing superuser, 2026-05-09)
- [x] #5 forum-integration-topics-count-n1 (already fixed — uses Machina direct_topics_count, 2026-05-09)
- [x] #6 forum-integration-posts-count-n1 (already fixed — uses Machina direct_posts_count, 2026-05-09)
- [x] #7 forum-integration-last-activity-n1 (already fixed — uses Machina last_post_on, 2026-05-09)
- [x] #11 garden-calendar-taste-rating-fielderror (already fixed — aggregation uses quality_rating, 2026-05-09)
- [x] #13 simple-views-validationerror-not-imported (already fixed — import present, 2026-05-09)
- [x] #14 plant-id-user-vote-n1 (already fixed — user_vote_annotation Subquery in viewset, 2026-05-09)
- [x] #16 firebase-email-verified-not-checked (already fixed — email_verified checked at line 154, 2026-05-09)
- [x] #17 oauth-missing-state-parameter (already fixed — state generated and stored in session, 2026-05-09)
- [x] #18 oauth-callback-state-not-validated (already fixed — state validated via compare_digest, 2026-05-09)
- [x] #19 demodata-wrong-fields (already fixed — create_demo_data no longer calls DemoData.objects.create with those fields, 2026-05-09)
- [x] #20 users-views-timezone-not-imported (already fixed — import present at line 13, 2026-05-09)
- [x] #21 users-views-longest-streak-attr-error (already fixed — uses `or 0` pattern, 2026-05-09)
- [x] #22 onboarding-analytics-wrong-field (already fixed — uses log_event() with action_type, 2026-05-09)
- [x] #38 blog-viewsets-wagtail-query-import (already fixed — try/except fallback present, 2026-05-09)
- [x] #43 blog-popular-action-n1 (already fixed — popular is in list-optimized branch, 2026-05-09)
- [x] #25 blog-admin-views-search-escaping-line-81 → todo 069 (completed 2026-05-09)
- [x] #26 blog-admin-views-search-escaping-line-267 → todo 069 (completed 2026-05-09)
- [x] #27 blog-admin-views-search-escaping-line-282 → todo 069 (completed 2026-05-09)
- [x] #28 blog-admin-views-search-escaping-line-290 → todo 069 (completed 2026-05-09)
- [x] #29 blog-api-serializers-category-post-count-n1 → todo 070 (completed 2026-05-09)
- [x] #30 blog-api-serializers-category-url-n1 → todo 070 (completed 2026-05-09)
- [x] #31 blog-api-serializers-series-post-count-n1 → todo 070 (completed 2026-05-09)
- [x] #32 blog-api-serializers-author-post-count-n1 → todo 070 (completed 2026-05-09)
- [x] #33 blog-api-serializers-author-recent-posts-n1 → todo 070 (completed 2026-05-09)
- [x] #34 blog-api-serializers-author-page-url-n1 → todo 070 (completed 2026-05-09)
- [x] #35 blog-api-serializers-index-featured-posts-n1 → todo 070 (completed 2026-05-09)
- [x] #36 blog-api-serializers-index-recent-posts-n1 → todo 070 (completed 2026-05-09)
- [x] #37 blog-api-serializers-category-page-posts-n1 → todo 070 (completed 2026-05-09)
- [x] #39 blog-viewsets-featured-else-branch-n1 → todo 071 (completed 2026-05-09)
- [x] #41 blog-viewsets-recent-else-branch-n1 → todo 071 (completed 2026-05-09)
- [x] #47 blog-viewsets-related-no-prefetch → todo 071 (completed 2026-05-09)
- [x] #48 blog-viewsets-related-no-get-queryset → todo 071 (completed 2026-05-09)
- [x] #40 blog-viewsets-recent-limit-no-validation → todo 072 (completed 2026-05-09)
- [x] #42 blog-viewsets-popular-days-no-validation → todo 072 (completed 2026-05-09)
- [x] #46 blog-viewsets-search-suggestions-escaping → todo 072 (completed 2026-05-09)
- [x] #49 blog-viewsets-listing-view-int-cast → todo 072 (completed 2026-05-09)
- [x] #44 blog-viewsets-by-category-loop-n1 → todo 073 (completed 2026-05-09)
- [x] #45 blog-viewsets-by-category-per-query → todo 073 (completed 2026-05-09)

---

## 🔴 Critical (24)

### `backend/apps/forum/serializers/category_serializer.py`

**#1** Line 61: get_thread_count is a SerializerMethodField that calls obj.get_thread_count() which executes a COUNT query per category, causing N+1 on the category list endpoint.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Replace with conditional annotation Count('threads', filter=Q(threads__is_active=True)) on the queryset in CategoryViewSet.get_queryset().

**#2** Line 69: get_post_count is a SerializerMethodField that calls obj.get_post_count() which runs a Sum aggregate query per category, causing N+1 on the category list endpoint.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate post_count via Sum('threads__post_count', filter=Q(threads__is_active=True)) in the viewset queryset.

### `backend/apps/forum/serializers/flagged_content_serializer.py`

**#3** Line 119: get_flag_count is a SerializerMethodField that runs a COUNT query against FlaggedContent for every flag returned, causing N+1 on the moderation queue list endpoint.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate flag_count on the queryset in ModerationQueueViewSet.get_queryset() using a subquery / window function instead of per-row queries.

### `backend/apps/forum_integration/management/commands/setup_forums.py`

**#4** Line 372: Management command creates a superuser with a hardcoded weak password ('admin123'); a leaked or accidentally-run command in production yields full admin access.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/security/secret-management.md
- **Suggested fix:** Require an existing admin user (or prompt for a password); never hardcode credentials in code.

### `backend/apps/forum_integration/serializers.py`

**#5** Line 37: ForumCategorySerializer.get_topics_count runs a COUNT query per Forum object in list views (N+1 over forum categories).

- **Reviewer:** performance-reviewer
- **Rule:** N+1 in SerializerMethodField — backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Annotate Forum queryset with Count('topics', filter=Q(topics__approved=True)) in ForumCategoryListView.get_queryset and read the annotation.

**#6** Line 41: ForumCategorySerializer.get_posts_count executes another COUNT (Post.objects.filter(topic__forum=obj…)) per forum, compounding N+1 with get_topics_count.

- **Reviewer:** performance-reviewer
- **Rule:** N+1 in SerializerMethodField — backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Use Count('topics__posts', filter=Q(topics__posts__approved=True)) annotation on the queryset rather than a Python-level count per object.

**#7** Line 45: ForumCategorySerializer.get_last_activity issues an ORDER BY/LIMIT 1 query for every Forum row in the list response.

- **Reviewer:** performance-reviewer
- **Rule:** N+1 in SerializerMethodField
- **Suggested fix:** Annotate the queryset with Max('topics__last_post_on', filter=Q(topics__approved=True)) or Subquery referencing latest Post.created.

**#8** Line 137: PostSerializer.get_rich_content accesses obj.rich_content (reverse OneToOne) and triggers a per-row query when serializing a list of posts.

- **Reviewer:** performance-reviewer
- **Rule:** N+1 — reverse OneToOne access without select_related
- **Suggested fix:** Add select_related('rich_content') in every queryset that feeds PostSerializer (PostListView, TopicDetailView, forum_search, PostImageListView paths).

**#9** Line 147: PostSerializer.get_content_format does another obj.rich_content lookup per object (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** N+1 — reverse OneToOne access without select_related
- **Suggested fix:** Cache the rich_content access (or pre-select via select_related('rich_content')) and pull all three method fields from the same prefetched object.

**#10** Line 154: PostSerializer.get_ai_assisted accesses obj.rich_content yet again — third reverse OneToOne hit per row in list responses.

- **Reviewer:** performance-reviewer
- **Rule:** N+1 — repeated reverse OneToOne access
- **Suggested fix:** select_related('rich_content') once in the view queryset; or compute all three fields from a single try/except block stored on self.context.

### `backend/apps/garden_calendar/api/views.py`

**#11** Line 1462: Aggregating Avg('taste_rating') but Harvest model has no taste_rating field (only quality_rating) — runtime FieldError when statistics action is hit.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Remove avg_taste aggregation or add taste_rating field to the Harvest model.

### `backend/apps/plant_identification/api/diagnosis_serializers.py`

**#12** Line 251: Authorization check uses non-existent attribute `value.request.is_public` instead of an actual visibility flag, so the second part of the OR is always False and the IDOR guard depends solely on user ownership; if the related model lacks `is_public`, this is fine but the dead-attribute path is fragile and `getattr` masks bugs.

- **Reviewer:** django-drf-reviewer
- **Rule:** permission/IDOR
- **Suggested fix:** Verify PlantDiseaseRequest exposes a real `is_public` field; if not, drop the getattr branch entirely and just check ownership.

### `backend/apps/plant_identification/api/simple_views.py`

**#13** Line 127: ValidationError is referenced in except clause but never imported, causing NameError at runtime when validate_image_file raises ValidationError.

- **Reviewer:** api-design-reviewer
- **Rule:** missing import
- **Suggested fix:** Add `from django.core.exceptions import ValidationError` (or the relevant module) at the top of the file.

### `backend/apps/plant_identification/serializers.py`

**#14** Line 223: PlantIdentificationResultSerializer.get_user_vote() does a per-result PlantIdentificationVote.objects.get() — classic N+1 multiplied across lists (PlantIdentificationResultViewSet, PlantIdentificationRequestWithResultsSerializer.identification_results), each result triggers an extra query.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** In viewset get_queryset(), annotate user_vote via Subquery(PlantIdentificationVote.objects.filter(user=request.user, result=OuterRef('pk')).values['vote_type'](:1)) and read from annotation.

### `backend/apps/plant_identification/views.py`

**#15** Line 875: PlantDiseaseResultViewSet.vote action allows any authenticated user to spam upvotes/downvotes without persistent vote tracking, enabling unlimited vote inflation per user.

- **Reviewer:** django-drf-reviewer
- **Rule:** missing rate limit / duplicate vote prevention
- **Suggested fix:** Add a PlantDiseaseVote model (mirroring PlantIdentificationVote) and reject duplicate votes per user/result.

### `backend/apps/users/firebase_auth_views.py`

**#16** Line 139: Firebase token is verified but `email_verified` claim is never checked; an attacker can sign up with Firebase using any unverified email and be logged in as the matching Django user (account takeover for existing accounts like <admin@example.com>).

- **Reviewer:** security-reviewer
- **Rule:** OWASP ASVS 2.7.5 / Firebase docs: only trust email when email_verified=true
- **Suggested fix:** Reject the token unless `decoded_token.get('email_verified') is True` (or the provider is one with verified emails like Google) before calling get_or_create_user_from_firebase.

### `backend/apps/users/oauth_views.py`

**#17** Line 64: OAuth authorization URL is built without a CSRF `state` parameter, and the callback never validates one — enables OAuth CSRF / account-binding attacks (RFC 6749 §10.12).

- **Reviewer:** security-reviewer
- **Rule:** RFC 6749 §10.12 — REQUIRED state parameter
- **Suggested fix:** Generate a cryptographically random state, store in the user session, include `state=<value>` in the authorize URL, and verify it matches in oauth_callback before exchanging the code.

**#18** Line 118: oauth_callback exchanges the code and logs the user in without validating an OAuth `state` parameter, allowing an attacker's authorization code to log a victim into the attacker's account or vice versa.

- **Reviewer:** security-reviewer
- **Rule:** RFC 6749 §10.12
- **Suggested fix:** Read state from query params, compare with the value stored in session/signed cookie at oauth_login, and abort on mismatch before any token exchange or login call.

### `backend/apps/users/services.py`

**#19** Line 657: DemoData.objects.create() passes 'user', 'demo_type=comprehensive', and 'created_data' kwargs, but the DemoData model has no 'user' field, no 'created_data' field, and 'comprehensive' is not in DEMO_TYPES — this will raise TypeError/ValidationError every time create_demo_data runs.

- **Reviewer:** django-drf-reviewer
- **Rule:** model-field-mismatch
- **Suggested fix:** Either add user/created_data fields to DemoData or store demo creation results on a different model (e.g., OnboardingProgress.demo_data_shown).

### `backend/apps/users/views.py`

**#20** Line 1089: care_reminder_action calls timezone.now() but django.utils.timezone is not imported at module scope — every 'complete'/'skip' action will raise NameError at runtime.

- **Reviewer:** django-drf-reviewer
- **Rule:** missing-import
- **Suggested fix:** Add `from django.utils import timezone` at the top of views.py.

**#21** Line 1199: completion_stats['max_streak'].longest_streak — Max('longest_streak') aggregation returns an int, not a model instance; .longest_streak access will raise AttributeError on every dashboard_stats response when there is at least one reminder.

- **Reviewer:** django-drf-reviewer
- **Rule:** aggregation-misuse
- **Suggested fix:** Replace with `completion_stats['max_streak'] or 0`.

**#22** Line 1330: OnboardingAnalytics.objects.create(event_type=...) but the model field is 'action_type' (not 'event_type'); also the required onboarding_progress FK is not provided — every track_onboarding_event call will fail.

- **Reviewer:** django-drf-reviewer
- **Rule:** model-field-mismatch
- **Suggested fix:** Use OnboardingAnalytics.log_event() classmethod, or pass action_type=event_type and resolve onboarding_progress.

### `firebase/firestore.rules`

**#23** Line 59: sync_queue create rule allows any authenticated user to create entries with an arbitrary user_id; a malicious client can inject sync work attributed to other users.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Firestore rules: writes must validate request.resource.data.user_id == request.auth.uid
- **Suggested fix:** Change to `allow create: if isAuthenticated() && request.resource.data.user_id == request.auth.uid;`

### `plant_community_mobile/lib/services/firebase_storage_service.dart`

**#24** Line 75: uploadTask.snapshotEvents.listen() creates a StreamSubscription that is never cancelled, leaking the subscription on every upload when onProgress is supplied (and across hot restarts).

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Memory Leaks (BLOCKER) — every StreamSubscription must be cancelled
- **Suggested fix:** Capture the StreamSubscription in a local variable and cancel it in a try/finally around `await uploadTask` (or attach via uploadTask.whenComplete to cancel).

---

## 🟠 High (313)

### `backend/apps/blog/admin_views.py`

**#25** Line 81: icontains search on user-provided query without calling escape_search_query() — % and _ wildcards are not escaped, allowing wildcard injection.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation.md
- **Suggested fix:** Wrap search_query in apps.core.utils.query_sanitization.escape_search_query() before using in icontains filters.

**#26** Line 267: icontains search on user-supplied query param without escape_search_query() escaping of % and _.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation.md
- **Suggested fix:** Escape the query via escape_search_query() before passing to icontains filters.

**#27** Line 282: icontains search on query for comments without wildcard escaping.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation.md
- **Suggested fix:** Use escape_search_query() on the query argument.

**#28** Line 290: icontains search on category name/description without wildcard escaping.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation.md
- **Suggested fix:** Use escape_search_query() on the query argument.

### `backend/apps/blog/api/serializers.py`

**#29** Line 44: SerializerMethodField get_post_count runs obj.blogpostpage_set.live().public().count() per category — N+1 query when categories serialized as nested list.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Annotate categories queryset with Count('blogpostpage', filter=Q(blogpostpage__live=True)) and read annotation in serializer.

**#30** Line 49: get_url runs BlogCategoryPage.objects.filter(category=obj).live().first() per category — N+1 query when categories are serialized in lists.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Prefetch related BlogCategoryPage on the categories queryset, or build a category->page map once per request.

**#31** Line 74: BlogSeriesSerializer.get_post_count runs obj.blogpostpage_set.live().public().count() per series — N+1 query.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use Count() annotation on the series queryset.

**#32** Line 118: BlogAuthorPageSerializer.get_post_count runs BlogPostPage.objects.live().public().filter(author=obj.author).count() per author — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Annotate author queryset with Count('author__blogpostpage', filter=Q(...)).

**#33** Line 126: get_recent_posts runs full BlogPostPage queryset per author — N+1 in author list views.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Prefetch author's recent posts via Prefetch() in viewset.

**#34** Line 292: _get_author_page_url runs BlogAuthorPage.objects.filter(author=author).live().first() per post — N+1 in retrieve views with category-prefetched related posts.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Cache author->author_page mapping per request or annotate author with author_page.

**#35** Line 411: BlogIndexPageSerializer.get_featured_posts queries BlogPostPage without select_related/prefetch_related; serialized via BlogPostPageListSerializer that needs author, categories, tags, featured_image — generates N+1 per call.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author') and prefetch_related('categories','tags','featured_image') and annotate_comment_count.

**#36** Line 431: get_recent_posts queries BlogPostPage without select_related/prefetch_related — N+1 when serialized via list serializer.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related/prefetch_related on this queryset.

**#37** Line 454: BlogCategoryPageSerializer.get_posts queries BlogPostPage without select_related/prefetch_related — N+1 when serialized.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author') and prefetch_related('categories','tags','featured_image').

### `backend/apps/blog/api/viewsets.py`

**#38** Line 32: Query is imported from wagtail.search.models but it lives at wagtail.contrib.search_promotions.models in Wagtail 7.x; Query becomes None silently and listing_view search analytics are dead code.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Import from wagtail.contrib.search_promotions.models with try/except fallback.

**#39** Line 281: featured() action uses get_queryset() but action='featured' falls through to the 'else' branch which only does select_related; serializer requires categories/tags/comments/featured_image prefetches — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Either treat action in ('list','featured','recent','popular') the same as list, or attach the same prefetches/annotations in the else branch.

**#40** Line 291: recent action accepts user-supplied limit with no upper bound and no validation, enabling DoS via huge slice and 500 errors on non-numeric input.

- **Reviewer:** api-design-reviewer
- **Rule:** validate query params; cap limit (see POPULAR_POSTS_MAX_LIMIT pattern)
- **Suggested fix:** Wrap int() in try/except ValueError -> 400, and clamp to a documented MAX limit constant.

**#41** Line 292: recent() action falls through to the bare else branch in get_queryset and lacks categories/tags/featured_image prefetches and _comment_count annotation needed by BlogPostPageListSerializer — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Apply list-style prefetches/annotation for action == 'recent'.

**#42** Line 322: popular action calls bare int(request.GET.get('limit', ...)) and int(request.GET.get('days', ...)); non-numeric values raise ValueError producing HTTP 500 instead of HTTP 400.

- **Reviewer:** api-design-reviewer
- **Rule:** Error responses: 400 for validation errors
- **Suggested fix:** Catch ValueError and return Response({'error': 'invalid limit/days'}, status=400).

**#43** Line 370: popular() relies on get_queryset() but action='popular' falls through to the else branch with only select_related — list serializer triggers N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Treat 'popular' like 'list' in get_queryset() for prefetches/annotation.

**#44** Line 393: by_category loops over featured categories and runs a fresh queryset+serializer per category - N+1.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Batch via Prefetch with category-grouped posts in a single query.

**#45** Line 394: by_category executes self.get_queryset().filter[categories=category](:5) inside a Python loop over featured categories — generates N queries per category.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Single-query approach using Prefetch with to_attr per category, or use a window function/group-by.

**#46** Line 422: search_suggestions: unescaped icontains for title and Tag.name searches.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/security/input-validation.md
- **Suggested fix:** Apply wildcard escaping to query string before filter.

**#47** Line 442: related() action queryset has no select_related/prefetch_related and no _comment_count annotation — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author','series'), prefetch_related('categories','tags','featured_image'), and Count() annotation.

**#48** Line 442: related action does not call self.get_queryset(); missing select_related/prefetch_related causes N+1.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Build off self.get_queryset() or add select_related('author','series') + prefetch_related.

**#49** Line 473: listing_view casts offset/limit from query string with bare int(...), so malformed values crash with 500 instead of returning 400.

- **Reviewer:** api-design-reviewer
- **Rule:** Error responses: 400 for validation errors
- **Suggested fix:** Validate and coerce with proper error handling, returning a 400 with the standard {'error': ...} shape.

### `backend/apps/blog/api_views.py`

**#50** Line 148: scientific_name__icontains uses unescaped user input - % and_ LIKE wildcards not escaped.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/security/input-validation.md
- **Suggested fix:** query.replace('%', r'\%').replace('_', r'\_') before icontains.

**#51** Line 163: common_names__icontains uses unescaped user input.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/security/input-validation.md
- **Suggested fix:** Escape % and _ in query before icontains.

### `backend/apps/blog/management/commands/migrate_care_guides_to_blog.py`

**#52** Line 69: Management command creates a user with hardcoded password 'temp_password_change_immediately' and is_superuser=True — operationally dangerous.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/secret-management.md
- **Suggested fix:** Require admin user to exist; raise CommandError if not. Never auto-create privileged users with default passwords.

### `backend/apps/blog/middleware.py`

**#53** Line 138: Deduplication cache.set() runs even when transaction.on_commit() callback later fails — failure path leaves dedup set with no view recorded; subsequent legitimate views will be silently dropped for the TTL window.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/caching.md
- **Suggested fix:** Move cache.set() inside the on_commit callback after successful create, or before but invalidate on failure.

### `backend/apps/blog/models.py`

**#54** Line 747: BlogPostPage.get_context related_posts queryset has no select_related/prefetch_related; rendered via Wagtail templates triggers N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author') and prefetch_related('categories','tags').

### `backend/apps/blog/serializers.py`

**#55** Line 38: BlogCategorySerializer.get_post_count runs obj.blogpostpage_set.live().public().count() per category — N+1 in lists.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Annotate the categories queryset with Count('blogpostpage', filter=...).

**#56** Line 56: BlogSeriesSerializer.get_post_count runs obj.blogpostpage_set.live().public().count() per series — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Annotate with Count() in the viewset queryset.

**#57** Line 105: BlogAuthorSerializer.get_post_count runs BlogPostPage.objects.live().public().filter(author=obj.author).count() per author — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Annotate the author queryset with Count() in the viewset.

**#58** Line 176: BlogPostPageSerializer.get_comment_count runs obj.comments.filter(is_approved=True).count() per post — N+1 in list views.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Annotate queryset with _comment_count=Count('comments', filter=Q(comments__is_approved=True)).

**#59** Line 219: BlogPostListSerializer.get_comment_count runs obj.comments.filter(is_approved=True).count() per post — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use annotated _comment_count from queryset.

### `backend/apps/blog/services/ai_rate_limiter.py`

**#60** Line 61: Rate limit increment is non-atomic: read-then-set race condition allows multiple concurrent requests to bypass the limit.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/rate-limiting.md
- **Suggested fix:** Use cache.incr() (atomic) with cache.add() to initialize, or rely on django-ratelimit which handles atomicity.

**#61** Line 73: cache.set() with TTL on every increment creates a sliding window — limit can never reset if user calls steadily; should use add()+incr() with a fixed window.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/rate-limiting.md
- **Suggested fix:** Use cache.add(key, 0, TTL) on first call, then cache.incr(key) — TTL only set once per window.

**#62** Line 188: Returns plain HttpResponse with 429 from a DRF/Django app — does not match Ratelimited exception handler pattern; may bypass DRF error formatting and audit logging.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/rate-limiting.md (Issue #133)
- **Suggested fix:** Raise a Ratelimited exception (or use django-ratelimit decorator) and rely on the project's custom exception handler that returns RFC-compliant 429.

### `backend/apps/blog/services/plant_data_lookup_service.py`

**#63** Line 106: icontains query on common_names with raw user input — % and_ not escaped.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation.md
- **Suggested fix:** Escape query via escape_search_query() before passing to icontains.

**#64** Line 129: Loads PlantSpecies.objects.all() and iterates in Python for fuzzy match — full table scan with O(N) memory and per-row Python work.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Use PostgreSQL trigram similarity (GIN + pg_trgm) or restrict to a candidate set via initial filter.

**#65** Line 171: N+1: iterating user_requests then issuing .filter(is_accepted=True) per-request triggers a query per loop iteration despite prefetch_related on 'identification_results'.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Use Prefetch('identification_results', queryset=PlantIdentificationResult.objects.filter(is_accepted=True)) to apply the filter inside the prefetch.

### `backend/apps/blog/signals.py`

**#66** Line 105: post_delete receiver registered without sender=BlogPostPage; fires for every model delete in the project, then isinstance() filters — wasteful.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use @receiver(post_delete, sender=BlogPostPage) to scope the signal.

### `backend/apps/blog/tests/test_blog_viewsets_caching.py`

**#67** Line 212: Performance test docstring says cached response should be <50ms but assertion uses assertLess(elapsed_ms, 500), 10x looser than the stated target.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: strict assertions for performance
- **Suggested fix:** Tighten threshold to the documented target or use query-count assertions.

**#68** Line 228: Same issue: docstring says <30ms but assertLess uses 500ms.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: strict assertions for performance
- **Suggested fix:** Tighten the threshold or replace with a deterministic query-count check.

**#69** Line 253: test_cache_invalidates_on_post_update asserts original_title != self.blog_post.title after mutating self.blog_post.title in memory; this passes regardless of caching behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: assertion must verify the claim
- **Suggested fix:** Compare response2.data['title'] to original_title and assert the new title is returned after invalidation.

### `backend/apps/blog/views.py`

**#70** Line 64: BlogPostPageViewSet.get_queryset misses_comment_count Count() annotation — BlogPostListSerializer fires N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add .annotate(_comment_count=Count('comments', filter=Q(comments__is_approved=True))).

**#71** Line 81: tags__name__icontains receives raw query param without LIKE wildcard escaping.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/security/input-validation.md
- **Suggested fix:** Escape % and _ before icontains filter.

**#72** Line 195: BlogCategoryViewSet.posts queryset only has select_related('author'); BlogPostListSerializer accesses categories, tags, featured_image, comments — N+1 per post.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add prefetch_related('categories','tags','featured_image') and Count() annotation.

**#73** Line 225: BlogSeriesViewSet.posts queryset misses prefetch_related for categories/tags/featured_image and _comment_count annotation — N+1 in serializer.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add prefetch_related and Count() annotation.

**#74** Line 252: BlogAuthorViewSet.posts only prefetches categories; BlogPostListSerializer reads tags + comment_count — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Also prefetch tags + add Count('comments', filter=Q(...)) annotation.

**#75** Line 382: blog_stats recent_posts queryset has no select_related/prefetch_related — N+1 when serialized via BlogPostListSerializer.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author') and prefetch_related('categories','tags','featured_image').

**#76** Line 404: blog_search queryset only prefetches categories; BlogPostListSerializer reads tags and comment_count — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add prefetch_related('tags') and Count() annotation; also use icontains escaping per project pattern.

**#77** Line 405: blog_search uses unescaped icontains across title/introduction/content_blocks/tags.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/security/input-validation.md
- **Suggested fix:** Sanitize query: replace % and _ before Q().

**#78** Line 412: Category search uses unescaped icontains on name/description.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/security/input-validation.md
- **Suggested fix:** Escape % and _ wildcards before icontains.

### `backend/apps/blog/wagtail_hooks.py`

**#79** Line 55: Wagtail homepage panel issues 5+ COUNT queries plus aggregate Sum and order_by view_count on every admin homepage load — should be cached.

- **Reviewer:** performance-reviewer
- **Rule:** architecture/caching.md
- **Suggested fix:** Cache panel content with cache.get_or_set(key, build, timeout=300).

**#80** Line 200: page_listing_buttons hook calls page.comments.filter(is_approved=True).count() per row in the admin page listing — N+1 query per page rendered.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Annotate listing queryset (via construct_explorer_page_queryset hook) with comment_count, or cache.

### `backend/apps/core/middleware.py`

**#81** Line 114: Logs raw user_id and ip_address without log_safe_ip.

- **Reviewer:** django-drf-reviewer
- **Rule:** PII-safe logging
- **Suggested fix:** Use log_safe_ip(ip_address).

**#82** Line 167: Security alert log includes raw user_id and ip_address without redaction.

- **Reviewer:** django-drf-reviewer
- **Rule:** PII-safe logging
- **Suggested fix:** Use log_safe_ip(ip_address).

**#83** Line 277: SecurityMetricsMiddleware._track_security_metric stores a 'unique_ips' set as a cache value and rewrites it on every request.

- **Reviewer:** performance-reviewer
- **Rule:** performance/caching.md
- **Suggested fix:** Use a Redis HyperLogLog (PFADD) or a Set with EXPIRE for unique IP counting.

### `backend/apps/core/security.py`

**#84** Line 284: Logs partial email and full domain — leaks PII; log_safe_email exists.

- **Reviewer:** django-drf-reviewer
- **Rule:** PII-safe logging
- **Suggested fix:** Replace with log_safe_email(user.email).

**#85** Line 290: Raw username logged in plain text — bypasses log_safe_username helper.

- **Reviewer:** django-drf-reviewer
- **Rule:** PII-safe logging
- **Suggested fix:** Use log_safe_username(username).

**#86** Line 295: Raw username logged in error path.

- **Reviewer:** django-drf-reviewer
- **Rule:** PII-safe logging
- **Suggested fix:** Use log_safe_username(username).

**#87** Line 331: Raw username in logger.info bypasses pii-safe logging helper.

- **Reviewer:** django-drf-reviewer
- **Rule:** PII-safe logging
- **Suggested fix:** Use log_safe_username(username).

**#88** Line 379: track_failed_login logs raw IP and username without log_safe_* helpers.

- **Reviewer:** django-drf-reviewer
- **Rule:** PII-safe logging
- **Suggested fix:** Use log_safe_ip(ip_address) and log_safe_username(username).

**#89** Line 587: json.dumps(details) in security alerts may serialize raw usernames/IPs from track_failed_login and track_validation_failure into logs.

- **Reviewer:** django-drf-reviewer
- **Rule:** GDPR/PII-safe logging
- **Suggested fix:** Hash username/IP via log_safe_username/log_safe_ip before passing to alert details.

**#90** Line 687: SecurityMiddleware.track_api_request runs on every /api/ request and performs cache.get + cache.set with a Python list rewrite per call.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Replace list-of-timestamps pattern with a Redis INCR + EXPIRE counter.

### `backend/apps/core/services/email_service.py`

**#91** Line 100: User.objects.get(email=recipient_email) can raise MultipleObjectsReturned; not handled.

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF service robustness
- **Suggested fix:** Use .filter(email=...).first() or handle MultipleObjectsReturned.

**#92** Line 100: send_email does User.objects.get(email=...) per call; from send_bulk_email this becomes one query per recipient (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Pre-fetch users via User.objects.in_bulk(field_name='email') and pass User instances.

### `backend/apps/core/services/notification_service.py`

**#93** Line 152: User.objects.get(email=recipient) can raise MultipleObjectsReturned; only DoesNotExist handled.

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF service robustness
- **Suggested fix:** Use .filter(email=...).first() or catch MultipleObjectsReturned.

### `backend/apps/core/validators.py`

**#94** Line 81: MIME-type validation silently falls back to extension-only when python-magic is unavailable, breaking the 4-layer file upload validation.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/file-upload.md — 4-layer validation
- **Suggested fix:** Make python-magic a hard dependency or raise ValidationError when unavailable in production.

### `backend/apps/forum/auditlog.py`

**#95** Line 1: Forum app is missing apps/forum/auditlog.py — required for GDPR compliance to register UserProfile, Post, Thread, Attachment, FlaggedContent, ModerationAction, Reaction with django-auditlog (other apps such as users/, plant_identification/, garden_calendar/ have one).

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/secret-management.md / GDPR convention
- **Suggested fix:** Create apps/forum/auditlog.py registering user-impacting models with auditlog.register().

### `backend/apps/forum/serializers/category_serializer.py`

**#96** Line 67: SerializerMethodField get_thread_count calls obj.get_thread_count() which runs self.threads.filter(is_active=True).count() — executes one COUNT query per category in list views (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md — N+1 in SerializerMethodField
- **Suggested fix:** Annotate thread_count with Count('threads', filter=Q(threads__is_active=True)) in CategoryViewSet.get_queryset() and read obj.thread_count in the serializer.

**#97** Line 75: SerializerMethodField get_post_count calls obj.get_post_count() which runs Sum aggregate per category — second N+1 query per row in category lists.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md — aggregate per object
- **Suggested fix:** Annotate post_count with Sum('threads__post_count', filter=Q(threads__is_active=True)) in CategoryViewSet.get_queryset().

**#98** Line 95: get_children calls obj.children.filter(is_active=True).order_by(...) which defeats the viewset's prefetch_related('children') — runs a fresh query per parent category; CategoryTreeSerializer recurses, compounding the cost.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md — filtered access defeats prefetch
- **Suggested fix:** Use Prefetch('children', queryset=Category.objects.filter(is_active=True).order_by('display_order', 'name')) in CategoryViewSet.get_queryset().

### `backend/apps/forum/serializers/flagged_content_serializer.py`

**#99** Line 119: SerializerMethodField get_flag_count executes FlaggedContent.objects.filter(...).count() per row — N+1 across the moderation queue list endpoint.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md — N+1 in SerializerMethodField
- **Suggested fix:** Annotate flag_count via Subquery/Count grouped on post_id and thread_id in ModerationQueueViewSet.get_queryset(), then read from annotation.

### `backend/apps/forum/signals.py`

**#100** Line 223: post_save signal handler synchronously runs TrustLevelService.update_user_trust_level (which does count queries and a profile save) on every post creation, blocking the request thread.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/architecture/services.md
- **Suggested fix:** Move trust-level recalculation to a Celery task triggered from the signal.

### `backend/apps/forum/tests/base.py`

**#101** Line 182: assertQueryCountLessThan helper uses assertLessEqual; this normalises a non-strict assertion across the suite and contradicts the strict equality requirement for performance tests.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Rename to assertQueryCountEqual using assertEqual, or remove and force tests to assert exact counts.

### `backend/apps/forum/tests/test_cache_integration.py`

**#102** Line 163: Test mutates post.content (no such field on Post; the model uses content_raw); the save still triggers signals so the assertion passes accidentally and the 'updated content' aspect is untested.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Use post.content_raw = 'Updated content'.

**#103** Line 254: Cache invalidation assertion is gated by hasattr(mock_service, 'invalidate_category'), which is always True for a MagicMock, so the test silently passes regardless of behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Remove the hasattr guard and assert mock_service.invalidate_category.assert_called_with(...) unconditionally.

### `backend/apps/forum/tests/test_post_performance.py`

**#104** Line 321: Detail-view query assertion uses assertLessEqual(query_count, 3) instead of strict assertEqual, defeating regression detection per the strict-assertion pattern.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Replace with self.assertEqual(query_count, N) and document why N is the expected count.

### `backend/apps/forum/viewsets/moderation_queue_viewset.py`

**#105** Line 107: ordering query param is passed directly into queryset.order_by() without whitelist validation, allowing arbitrary fields (and ORM relation traversal) to be requested by API clients.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Use DRF OrderingFilter with explicit ordering_fields whitelist or validate against an allowed-fields set.

**#106** Line 187: Generic exception handler returns f'Failed to execute moderation action: {str(e)}' to the client, exposing internal error messages.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Log internally; return a generic error message to the client.

### `backend/apps/forum/viewsets/post_viewset.py`

**#107** Line 754: Generic 'except Exception as e' returns str(e) directly to the client, leaking internal error/stack details from a failed image upload.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Log the full exception server-side; return a generic 'Image upload failed' message to the client.

### `backend/apps/forum/viewsets/thread_viewset.py`

**#108** Line 140: ThreadViewSet.get_permissions() does not call super() for the @action 'flag_thread' (line 522), so the action-level permission_classes=[IsAuthenticatedOrReadOnly] is silently ignored and the default branch [IsAuthenticatedOrReadOnly()] is used.

- **Reviewer:** django-drf-reviewer
- **Rule:** Issue #131 / patterns/architecture/viewsets.md
- **Suggested fix:** Add 'if self.action == "flag_thread": return super().get_permissions()' or include in an action whitelist that delegates to super().

### `backend/apps/forum_integration/api_views.py`

**#109** Line 229: icontains search on Topic.subject does not escape % and _ wildcards from user input, allowing wildcard injection / inefficient LIKE patterns.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/security/input-validation.md
- **Suggested fix:** Run query through escape_search_query() before passing to icontains.

**#110** Line 235: icontains search on Post.content does not escape % and _ wildcards in the user-supplied query.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/security/input-validation.md
- **Suggested fix:** Escape % and _ before applying icontains.

**#111** Line 250: forum_stats executes 3 unbounded COUNT/DISTINCT queries (total_topics, total_posts, active_users) on every request and lacks any Redis caching despite being a frequently-polled stats endpoint.

- **Reviewer:** performance-reviewer
- **Rule:** Frequently-accessed aggregate without Redis cache — caching.md
- **Suggested fix:** Wrap counts in cache.get_or_set('forum_stats:v1', …, timeout=300) and invalidate on post creation.

**#112** Line 376: Uses rest_framework.permissions.PermissionDenied which does not exist (PermissionDenied lives in rest_framework.exceptions); raise will fail with AttributeError at runtime.

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF API surface
- **Suggested fix:** Import from rest_framework.exceptions: `from rest_framework.exceptions import PermissionDenied`.

**#113** Line 408: Same invalid reference: permissions.PermissionDenied is not a real attribute on rest_framework.permissions; will raise AttributeError when delete is attempted by a non-owner.

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF API surface
- **Suggested fix:** Use rest_framework.exceptions.PermissionDenied.

**#114** Line 422: TopicMarkViewedView increments views_count via unauthenticated POST (AllowAny) with no rate-limit, enabling trivial view-count inflation/abuse.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/architecture/rate-limiting.md
- **Suggested fix:** Require authentication or apply per-IP/user django-ratelimit on this endpoint.

**#115** Line 668: Image upload only checks user-supplied content_type and size; no PIL magic-number/MIME verification or extension whitelist (missing 4-layer file upload validation).

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/security/file-upload.md
- **Suggested fix:** Validate extension, MIME type, size, and PIL.Image.verify() / image.format on the uploaded file.

**#116** Line 1056: user_trust_level executes 4+ COUNT queries (posts_count, topics_count, plus permission checks) on every call without caching, making the endpoint expensive for authenticated polls.

- **Reviewer:** performance-reviewer
- **Rule:** Hot endpoint missing Redis cache layer — backend/docs/patterns/architecture/caching.md
- **Suggested fix:** Cache the trust-level payload in Redis keyed on user_id with TTL of 5–15 min and invalidate on new post/topic creation.

**#117** Line 1215: UserTopicsListView iterates every Forum and calls perm_handler.can_read_forum in a Python loop (N permission lookups per request).

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Use machina's get_readable_forums() / queryset-aware permission helper instead of per-forum Python iteration.

**#118** Line 1215: UserTopicsListView.get_queryset iterates every FORUM_POST forum and calls perm_handler.can_read_forum per forum, which often issues additional permission queries — O(F) overhead on every list call with no caching.

- **Reviewer:** performance-reviewer
- **Rule:** Per-request permission scan — should be cached/batched
- **Suggested fix:** Use Machina's PermissionHandler.forum_list_filter (or batched permission lookup) and cache the resulting accessible_forums per user under a short-TTL Redis key.

**#119** Line 1260: UserWatchedTopicsListView duplicates the per-Forum can_read_forum loop, again producing N permission queries per request.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Resolve accessible forums via a single permission queryset, not a Python loop.

**#120** Line 1260: UserWatchedTopicsListView repeats the same per-forum permission iteration as UserTopicsListView; same O(F) overhead per request.

- **Reviewer:** performance-reviewer
- **Rule:** Per-request permission scan — should be cached/batched
- **Suggested fix:** Refactor accessible-forum lookup into a helper that caches per (user_id) and reuse in both views.

### `backend/apps/forum_integration/management/commands/setup_forums.py`

**#121** Line 90: Calling .delete() on Wagtail page subclass querysets bypasses the page tree and can leave the MPTT tree in an inconsistent state; Wagtail pages must be deleted via Page.delete() / through the tree.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/domain/wagtail.md
- **Suggested fix:** Iterate page instances and call .delete() on each so Wagtail tree maintenance runs, or delete via the parent's children.

### `backend/apps/forum_integration/models.py`

**#122** Line 207: machina_forum_id is a plain IntegerField with no FK constraint or on_delete behaviour, so deleting a Machina Forum leaves dangling references; ForumPageMapping already provides the proper FK, so this duplicates state and risks drift.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Use a ForeignKey to forum.Forum (or rely solely on ForumPageMapping) so referential integrity is enforced.

### `backend/apps/forum_integration/serializers.py`

**#123** Line 39: SerializerMethodField get_topics_count issues a COUNT query per Forum row when serializing categories list (N+1).

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Replace with a Count() annotation on the queryset in ForumCategoryListView.get_queryset().

**#124** Line 43: SerializerMethodField get_posts_count issues a COUNT query per Forum row (N+1 across the categories list).

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Use a Count('topics__posts', filter=Q(topics__posts__approved=True)) annotation.

**#125** Line 47: SerializerMethodField get_last_activity runs an ORDER BY query per Forum row (N+1).

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Annotate Max('topics__posts__created', filter=Q(approved=True)) on the queryset.

**#126** Line 113: TopicSerializer.get_last_poster spawns User serializer through obj.last_post.poster; without select_related('last_post__poster') this is N+1 across topic lists.

- **Reviewer:** performance-reviewer
- **Rule:** Foreign-key chain access without select_related
- **Suggested fix:** Ensure all topic querysets use select_related('last_post', 'last_post__poster') (UserTopicsListView and ForumTopicsListView already do; SimpleTopicSerializer-driven endpoints should too).

**#127** Line 187: _expand_rich_content runs a PlantSpeciesPage query inside a SerializerMethodField, producing per-post DB hits when serializing a post list.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Lift plant_page lookups into a per-request prefetch/cache or do a single bulk lookup at the view layer.

**#128** Line 461: TopicWithFirstPostSerializer.get_last_poster accesses obj.last_post.poster — TopicsFeedView prefetches first_post but only select_relates last_post, last_post__poster (covered) yet PostWithImagesSerializer for first_post will still trigger rich_content N+1 (see lines 137/147/154).

- **Reviewer:** performance-reviewer
- **Rule:** Composite N+1 in feed serializer
- **Suggested fix:** Add select_related on first_post__rich_content (and last_post__rich_content if rendered) in TopicsFeedView.get_queryset.

### `backend/apps/forum_integration/tests/test_plant_mention_serialization.py`

**#129** Line 63: Tests call private serializer method `_normalize_rich_content` (leading underscore) directly — this couples tests to implementation details, defeating the purpose of testing public behaviour and making refactors painful.

- **Reviewer:** test-quality-reviewer
- **Rule:** test naming & structure (test behaviour, not implementation)
- **Suggested fix:** Drive normalization through the public serializer interface: instantiate CreateTopicSerializer(data=...) and assert .is_valid() / .validated_data.

### `backend/apps/forum_integration/views.py`

**#130** Line 194: Template view performs icontains search without escaping % and _ wildcards from user input.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/security/input-validation.md
- **Suggested fix:** Use escape_search_query() helper before calling filter.

**#131** Line 200: Post.content icontains search lacks wildcard escaping for user-supplied query.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/security/input-validation.md
- **Suggested fix:** Escape % and _ before passing to filter().

### `backend/apps/forum_integration/wagtail_hooks.py`

**#132** Line 105: add_forum_stats_panel runs four COUNT queries on every Wagtail admin homepage render with no caching.

- **Reviewer:** performance-reviewer
- **Rule:** Repeated aggregate query in admin hook — should cache
- **Suggested fix:** Cache the four counts in Redis (30–60s TTL) and reuse here and in add_forum_summary_items.

**#133** Line 167: add_forum_summary_items runs the same forum/topic/pending counts as add_forum_stats_panel — duplicate aggregate queries on every admin page load.

- **Reviewer:** performance-reviewer
- **Rule:** Duplicate aggregate query — share cached result
- **Suggested fix:** Extract a single get_forum_admin_stats() helper that computes once per request (or via Redis) and consumes the result in both hooks.

**#134** Line 204: Mutating features.default_features.append('ai') without first registering 'ai' via features.register_editor_plugin / register_converter_rule will register an unknown feature and silently fail or break Draftail init.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/domain/wagtail.md
- **Suggested fix:** Register the AI feature plugin first (features.register_editor_plugin(...)) before appending its name to default_features, or remove this hook if AI isn't wired up.

**#135** Line 226: construct_main_menu strips 'settings' and 'help' menu items for any non-superuser, which removes Wagtail Settings access for legitimate staff/editors and is unrelated to forum scope.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Scope this filter to a specific forum-only group, or remove it; do not mutate the global admin menu for all non-superusers from the forum app.

### `backend/apps/garden/serializers.py`

**#136** Line 86: PestImage validation only checks size, extension, and MIME content_type — missing PIL magic-number verification (4-layer file upload rule). Attackers can spoof Content-Type and extension to upload non-image payloads.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — file upload requires 4-layer validation (extension, MIME, size, PIL magic-number)
- **Suggested fix:** After other checks, open the file with PIL.Image.open(value) and call verify() inside try/except.

**#137** Line 118: JournalImage validation lacks PIL magic-number check; same 4-layer validation gap as PestImage.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — file upload 4-layer validation
- **Suggested fix:** Add PIL.Image.open(value).verify() after MIME check.

**#138** Line 290: GardenPlantSerializer.validate_image lacks PIL magic-number check; user-uploaded plant images bypass the 4th validation layer.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — file upload 4-layer validation
- **Suggested fix:** Add PIL.Image.open(value).verify() after MIME check.

**#139** Line 408: plant_count is a SerializerMethodField that calls obj.plants.count() — BLOCKER N+1 in list view (one COUNT query per Garden). Garden list endpoint will scale O(n) extra queries.

- **Reviewer:** django-drf-reviewer
- **Rule:** Performance — SerializerMethodField that queries DB is N+1; use conditional annotations
- **Suggested fix:** Annotate the queryset with Count('plants') in get_queryset and read obj.plant_count.

**#140** Line 408: GardenSerializer.get_plant_count uses obj.plants.count() in SerializerMethodField, executing one COUNT query per Garden in list/detail views (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - SerializerMethodField with related_set access
- **Suggested fix:** Annotate Count('plants') in GardenViewSet.get_queryset() and read from annotation.

**#141** Line 525: GardenListSerializer.get_plant_count repeats the same N+1 in the list endpoint; counts() runs once per garden in the page.

- **Reviewer:** django-drf-reviewer
- **Rule:** Performance — N+1 from SerializerMethodField
- **Suggested fix:** Add .annotate(plant_count=Count('plants')) in GardenViewSet.get_queryset.

**#142** Line 525: GardenListSerializer.get_plant_count uses obj.plants.count() per garden in list view, causing one COUNT query per row (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add Count('plants') annotation in GardenViewSet.get_queryset() and read from annotation.

### `backend/apps/garden/services/companion_planting_service.py`

**#143** Line 102: validate_garden_layout iterates O(N^2) plant pairs; each call to check_compatibility invokes get_plant_care_data twice, each performing a fresh PlantCareLibrary.objects.get() — quadratic DB queries per garden validation.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - batch lookups
- **Suggested fix:** Preload PlantCareLibrary.objects.filter(scientific_name__iexact__in=names) into a dict once, then pass care data into check_compatibility instead of re-querying per pair.

**#144** Line 257: get_companion_suggestions does PlantCareLibrary.objects.get(...) inside a per-name for-loop — N queries for N companions.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - .filter(__in=...) over loops
- **Suggested fix:** Single .filter(scientific_name__iexact__in=companion_names) and build a dict for lookups.

**#145** Line 306: get_plants_to_avoid does PlantCareLibrary.objects.get(...) inside a per-name loop — N queries for N enemy plants.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use a single .filter(scientific_name__iexact__in=enemy_names).

### `backend/apps/garden/services/firebase_notification_service.py`

**#146** Line 240: send_batch_reminders calls send_reminder_notification in a loop, which performs an individual fcm.send() round-trip and a separate reminder.save(update_fields=...) DB write per reminder — true N+1 of network and DB writes; FCM supports send_each_for_multicast/send_all and bulk update.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/architecture/caching.md - batch external IO
- **Suggested fix:** Build messages list and use fcm.send_each() / send_all(), then CareReminder.objects.filter(id__in=sent_ids).update(notification_sent=True).

**#147** Line 275: datetime.now() used as window boundary against tz-aware CareReminder.scheduled_date — produces wrong query window and Django will warn about naive/aware mismatch.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use django.utils.timezone.now().

### `backend/apps/garden/services/firebase_sync_service.py`

**#148** Line 177: sync_user_reminders loops calling sync_reminder() (one Firestore document write per reminder) instead of using sync_reminder_batch which batches up to 500 writes — N round-trips for bulk sync.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/architecture/caching.md - batch external IO
- **Suggested fix:** Delegate to cls.sync_reminder_batch(list(reminders)) for bulk syncs.

### `backend/apps/garden/services/smart_reminder_service.py`

**#149** Line 112: datetime.now().date() under USE_TZ=True produces server-local date; combined with scheduled_date__date filter this drops or includes wrong reminders near midnight UTC.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.localdate() or timezone.now().date().

**#150** Line 123: auto_skip_reminders calls check_reminder_with_weather() per reminder; each call invokes WeatherService.get_care_recommendations() which fans out to multiple OpenWeatherMap API calls. With many reminders sharing a garden/location, this multiplies external API cost (and latency).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/architecture/caching.md - batch by location
- **Suggested fix:** Group reminders by garden.location key and call get_care_recommendations once per unique location; cache results in-memory for the run.

**#151** Line 186: datetime.now() + timedelta used for end_date on a tz-aware scheduled_date filter — naive vs aware comparison.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.now().

**#152** Line 197: get_upcoming_reminders_with_weather calls check_reminder_with_weather() per reminder, repeating WeatherService API/cache lookups for every reminder even when many share the same garden location.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/architecture/caching.md
- **Suggested fix:** Memoize/cache per unique (lat,lng) key for the duration of the request before iterating reminders.

### `backend/apps/garden/viewsets.py`

**#153** Line 78: GardenViewSet.get_queryset prefetches Garden.plants but does not prefetch plant.reminders / pest_issues / journal_entries; GardenSerializer renders these nested via GardenPlantSerializer on retrieve — guaranteed N+1 per plant on detail responses.

- **Reviewer:** django-drf-reviewer
- **Rule:** Performance — prefetch_related must cover reverse FK accessed by serializer
- **Suggested fix:** In the Prefetch('plants', ...) queryset chain prefetch_related('reminders','pest_issues__images','journal_entries__images').

**#154** Line 78: GardenViewSet.get_queryset() applies the same heavy prefetch (plants, tasks, journal_entries) for both list and retrieve; for list view (GardenListSerializer) the prefetched tasks/journal_entries/plants are unused, wasting queries and memory.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - conditional prefetch by action
- **Suggested fix:** Branch on self.action: minimal prefetch for list (just Count annotation); full prefetch (including plants__reminders, plants__pest_issues__images, plants__journal_entries__images) for retrieve.

**#155** Line 78: GardenViewSet.get_queryset() omits select_related('user') even though GardenListSerializer/GardenSerializer expose user via StringRelatedField, triggering one query per row to render user.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - select_related for FK accessed by serializer
- **Suggested fix:** Add .select_related('user') to the queryset.

**#156** Line 97: ratelimit decorator on create() is not paired with a custom exception handler that maps Ratelimited (PermissionDenied subclass) to HTTP 429 with Retry-After — clients receive 403 instead of 429, violating the project rate-limit pattern.

- **Reviewer:** django-drf-reviewer
- **Rule:** Issue #133 — django-ratelimit returns 403 unless Ratelimited is mapped to 429 first
- **Suggested fix:** Ensure project DRF EXCEPTION_HANDLER checks isinstance(exc, Ratelimited) before DRF processing, or use block=False and check was_limited.

**#157** Line 116: featured() action returns GardenSerializer (which nests plants -> reminders/pest_issues/journal_entries and tasks/journal_entries) but only prefetches plants and plants.plant_species, causing N+1 cascade on every request.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add prefetch_related for tasks, journal_entries, plants__reminders, plants__pest_issues__images, plants__journal_entries__images.

**#158** Line 169: GardenPlantViewSet.get_queryset() prefetches 'pest_issues__images' and 'journal_entries__images' for every action including list; on a list endpoint with many plants this loads thousands of nested image records eagerly.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - conditional prefetch by action
- **Suggested fix:** Branch on self.action and only apply heavy nested prefetches for retrieve; for list, use a slim serializer or limit nested data.

**#159** Line 196: CareReminderViewSet.get_queryset() does not select_related('user') but CareReminderSerializer renders user via StringRelatedField, causing N+1 on user per reminder in list/upcoming.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add 'user' to select_related: select_related('user', 'garden_plant__garden').

**#160** Line 217: datetime.now() returns a naive datetime but USE_TZ=True; comparing to scheduled_date (DateTimeField, tz-aware) raises a warning and produces incorrect filter results across DST transitions.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene under USE_TZ=True
- **Suggested fix:** Use django.utils.timezone.now() instead of datetime.now().

**#161** Line 232: complete action is not idempotent: calling it twice on a recurring reminder creates two duplicate 'next' CareReminder rows because the action does not check reminder.completed before scheduling the next instance.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — idempotent state transitions
- **Suggested fix:** Guard with `if reminder.completed: return ...` before mutating, or wrap in transaction.atomic with select_for_update.

**#162** Line 242: completed_at = datetime.now() stores a naive datetime in a tz-aware DateTimeField under USE_TZ=True.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.now() from django.utils.timezone.

**#163** Line 263: skip action has the same non-idempotent recurring-clone bug as complete; repeated POSTs spawn duplicate CareReminder rows.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — idempotent state transitions
- **Suggested fix:** Check reminder.skipped early-return; wrap mutation in transaction.atomic + select_for_update.

**#164** Line 309: TaskViewSet.get_queryset() omits select_related('user') though TaskSerializer renders user via StringRelatedField, causing N+1 on user in list view.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add 'user' to select_related: select_related('user', 'garden').

**#165** Line 326: task.completed_at = datetime.now() — naive datetime assigned to tz-aware DateTimeField.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.now().

**#166** Line 346: PestIssueViewSet.get_queryset() omits select_related('user') though PestIssueSerializer exposes user via StringRelatedField, causing N+1 on user in list view.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add 'user' to select_related.

**#167** Line 359: PestIssue.upload_image accepts file uploads with no rate limiting; constants.py defines RATE_LIMIT_IMAGE_UPLOAD but it is never applied here.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — rate limit upload endpoints
- **Suggested fix:** Decorate with @method_decorator(ratelimit(key='user', rate=RATE_LIMIT_IMAGE_UPLOAD, method='POST')).

**#168** Line 408: JournalEntryViewSet.get_queryset() omits select_related('user') though JournalEntrySerializer exposes user via StringRelatedField, causing N+1 on user in list view.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add 'user' to select_related.

**#169** Line 422: JournalEntry.upload_image lacks rate limiting; same gap as PestIssue.upload_image — RATE_LIMIT_IMAGE_UPLOAD constant is unused.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — rate limit upload endpoints
- **Suggested fix:** Apply ratelimit decorator with RATE_LIMIT_IMAGE_UPLOAD.

### `backend/apps/garden_calendar/api/serializers.py`

**#170** Line 42: attendee_count maps to CommunityEvent.attendee_count property which calls self.attendees.count() per object, causing N queries despite prefetch_related('attendees') (count is not satisfied by prefetch).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - prefetch does NOT satisfy .count(); use Count() annotation
- **Suggested fix:** Add .annotate(attendee_count=Count('attendees')) in get_queryset() and remove the model-property fallback.

**#171** Line 43: spots_remaining property reads attendee_count which triggers a per-object COUNT query in list view (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Compute spots_remaining in Python from the annotated attendee_count and max_attendees.

**#172** Line 66: SerializerMethodField get_user_rsvp_status calls obj.attendees.get(user=...) per event in list view, executing one query per event (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - SerializerMethodField with related_set access is a BLOCKER
- **Suggested fix:** Annotate user_rsvp_status in CommunityEventViewSet.get_queryset() using a Subquery or prefetched filter, then read from annotation.

**#173** Line 522: GardenBedListSerializer.plant_count maps to GardenBed.plant_count property (.plants.filter(is_active=True).count()) which fires a query per bed in list view (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add .annotate(plant_count=Count('plants', filter=Q(plants__is_active=True))) in GardenBedViewSet.get_queryset() and serve the annotated value (the existing TODO already notes this).

**#174** Line 524: utilization_rate property reads plant_count, which executes another COUNT per bed; combined with plant_count this is 2N+ queries on list view.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Compute utilization_rate from the annotated plant_count + dimensions in Python.

### `backend/apps/garden_calendar/api/views.py`

**#175** Line 50: CommunityEventViewSet has no lookup_field='uuid' despite serializing 'uuid' as the public identifier; URL routing will use pk and clients will pass DB ids (or 404) instead of UUIDs.

- **Reviewer:** api-design-reviewer
- **Rule:** UUID Endpoints checklist
- **Suggested fix:** Add lookup_field = 'uuid' (and document on the @extend_schema_view) so the URL becomes /api/v1/events/<uuid:uuid>/.

**#176** Line 50: CommunityEventViewSet, SeasonalTemplateViewSet, WeatherAlertViewSet, CareLogViewSet, HarvestViewSet, PlantImageViewSet, and GrowingZoneViewSet have no @extend_schema/@extend_schema_view annotations or 429 documentation, leaving rate-limited endpoints undocumented in Swagger.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema checklist
- **Suggested fix:** Add @extend_schema_view tags + 429 OpenApiResponse to viewsets that wrap @ratelimit (event create, RSVP, image upload, care task complete/skip).

**#177** Line 92: icontains filter on user-controlled string without escaping % and _wildcards (CommunityEventViewSet.get_queryset privacy filter on city).

- **Reviewer:** django-drf-reviewer
- **Rule:** Permissions & Security — escape_search_query()
- **Suggested fix:** Apply query.replace('%', r'\%').replace('_', r'\_') (or use the project escape_search_query helper).

**#178** Line 131: ratelimit(block=True) raises Ratelimited (PermissionDenied) which DRF converts to HTTP 403, not 429 with Retry-After — applies to every @method_decorator(ratelimit) call in this file.

- **Reviewer:** api-design-reviewer
- **Rule:** Issue #133 / rate-limiting pattern
- **Suggested fix:** Ensure the project-wide DRF exception handler maps Ratelimited -> 429 with Retry-After (see backend/docs/patterns/architecture/rate-limiting.md).

**#179** Line 144: perform_update uses self.permission_denied to enforce ownership instead of the permission class, returning 403 inside the create/update flow but bypassing has_object_permission; ownership rule should live in IsGardenOwner-equivalent permission for events for consistency and OpenAPI docs.

- **Reviewer:** api-design-reviewer
- **Rule:** viewsets pattern
- **Suggested fix:** Implement a CommunityEventOwnerPermission with has_object_permission and remove inline organizer check.

**#180** Line 153: @action sits above @method_decorator(ratelimit) — the ratelimit decorator wraps the bound method but @action's routing already captured the original; depending on order DRF will route to the unwrapped method and rate limiting silently fails (this pattern is repeated for upload_image at lines 879-881, complete at 1210-1211, and skip at 1271-1272).

- **Reviewer:** api-design-reviewer
- **Rule:** rate-limiting pattern
- **Suggested fix:** Place @action as the OUTERMOST decorator (top-most) and @method_decorator(ratelimit) below it so the action wraps the rate-limited callable.

**#181** Line 155: CommunityEventViewSet.rsvp uses pk=None and is registered as detail=True without lookup_field='uuid'; CommunityEvent likely uses UUID, so the default URL pattern uses <int:pk> instead of <uuid:uuid>.

- **Reviewer:** api-design-reviewer
- **Rule:** UUID Endpoints checklist + diagnosis pattern
- **Suggested fix:** Set lookup_field = 'uuid' on CommunityEventViewSet and rename action signature to (self, request, uuid=None).

**#182** Line 163: RSVP returns serializer.errors (DRF default shape: {field: [errors]}) which violates the consistent error envelope used elsewhere in this view ({'error': '...'}).

- **Reviewer:** api-design-reviewer
- **Rule:** Error Responses checklist
- **Suggested fix:** Wrap as {'error': 'Validation failed', 'detail': serializer.errors} or rely on raise_exception=True with a global exception handler.

**#183** Line 366: WeatherAlertViewSet.get_queryset filters with city__icontains=user.location without wildcard escaping.

- **Reviewer:** django-drf-reviewer
- **Rule:** Permissions & Security — escape_search_query()
- **Suggested fix:** Escape % and _ before icontains.

**#184** Line 405: active_alerts action runs three queryset evaluations: serializer iteration, .count(), and another filter+count — could be combined with conditional aggregation in one query.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use .aggregate(total=Count('id'), high=Count('id', filter=Q(severity__in=['high','critical']))) and pass list to serializer once.

**#185** Line 568: TODO acknowledges plant_count annotation is missing; current code accepts known N+1 in list view despite documented fix.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Re-enable .annotate(plant_count=Count('plants', filter=Q(plants__is_active=True))) and remove the TODO.

**#186** Line 657: GardenBed.analytics action loops over plants in Python to build health_status_breakdown instead of using a single Count() aggregation in the database.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - aggregations must use Count()/Sum()/Avg(), not Python loops
- **Suggested fix:** Replace the loop with garden_bed.plants.filter(is_active=True).values('health_status').annotate(count=Count('uuid')).

**#187** Line 1454: HarvestViewSet.statistics runs four separate filter+aggregate queries (one per unit) plus separate avg_quality and avg_taste queries instead of a single conditional aggregation.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - combine aggregates
- **Suggested fix:** Use a single .aggregate() call with Sum(..., filter=Q(unit='lbs')) etc. and combine quality/taste into one aggregate call.

**#188** Line 1462: Harvest.objects.aggregate(avg=Avg('taste_rating')) — the Harvest model defines no 'taste_rating' field (only quality_rating), so this aggregation raises FieldError at runtime.

- **Reviewer:** django-drf-reviewer
- **Rule:** Models & Queries
- **Suggested fix:** Remove taste_rating logic or add the field to the model.

**#189** Line 1511: PlantImageViewSet orders by '-created_at', but PlantImage has no created_at field (only uploaded_at and taken_date). Will raise FieldError when listing images.

- **Reviewer:** django-drf-reviewer
- **Rule:** Models & Queries
- **Suggested fix:** Use '-uploaded_at' or '-taken_date'.

### `backend/apps/garden_calendar/services/care_schedule_service.py`

**#190** Line 95: CareTask.objects.create() omits required non-null fields 'created_by' (FK CASCADE, no null) and 'title' (CharField, no blank). All five auto-generation create() calls in this method (lines 95, 112, 126, 143, 158) will raise IntegrityError at runtime.

- **Reviewer:** django-drf-reviewer
- **Rule:** Models & Queries
- **Suggested fix:** Accept a created_by user param and supply both created_by and a sensible default title (e.g., from get_task_type_display).

**#191** Line 95: generate_initial_tasks_for_plant performs up to 5 individual CareTask.objects.create() INSERTs per plant; should batch via bulk_create for performance.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Build CareTask instances in a list and call CareTask.objects.bulk_create(tasks).

**#192** Line 332: generate_seasonal_tasks creates one CareTask per (template, plant) pair via individual .create() — for many users this becomes O(templates * plants) INSERTs.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Accumulate tasks in a list and use bulk_create(); also use prefetch on plants once outside the inner loop.

**#193** Line 339: generate_seasonal_tasks() also calls CareTask.objects.create() without the required created_by and title fields, causing IntegrityError.

- **Reviewer:** django-drf-reviewer
- **Rule:** Models & Queries
- **Suggested fix:** Pass created_by=user and title=template.name (or task_type display).

### `backend/apps/garden_calendar/services/garden_analytics_service.py`

**#194** Line 94: get_bed_utilization_stats iterates beds and reads bed.utilization_rate / bed.plant_count properties, each issuing a COUNT(*) query — N+1 on number of garden beds.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate plant_count with Count('plants', filter=Q(plants__is_active=True)) on the queryset, then derive utilization in Python.

### `backend/apps/garden_calendar/signals.py`

**#195** Line 31: icontains filter on user-supplied event.city without wildcard escaping — also runs in a signal handler so any user-controlled value flows in.

- **Reviewer:** django-drf-reviewer
- **Rule:** Permissions & Security — escape_search_query()
- **Suggested fix:** Escape % and _ before icontains.

**#196** Line 40: post_save signal sends up to 100 emails synchronously inside the request/transaction; blocks event creation and risks DB connection holding while SMTP runs.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/domain/celery.md - long-running side-effects must run in Celery tasks
- **Suggested fix:** Dispatch notifications to a Celery task (e.g., send_event_notifications.delay(event_id)).

**#197** Line 104: WeatherAlert signal: location__icontains=instance.city without wildcard escaping.

- **Reviewer:** django-drf-reviewer
- **Rule:** Permissions & Security — escape_search_query()
- **Suggested fix:** Escape % and _ before icontains.

**#198** Line 113: Weather alert post_save sends up to 200 push notifications synchronously inside the signal — same blocking issue as event notifications.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Move to Celery task; signal should only enqueue.

### `backend/apps/garden_calendar/tests/test_performance.py`

**#199** Line 66: Performance test asserts assertNumQueries(12) for an N+1 pattern that the docstring itself identifies as needing optimization to 2 queries — locking in a known-bad query count instead of failing the regression.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md (strict assertion section)
- **Suggested fix:** Annotate plant_count in the queryset, then tighten assertion to assertNumQueries(2) so future regressions fail.

**#200** Line 82: Detail endpoint test asserts assertNumQueries(5) but docstring acknowledges the target should be 3 — strict counts must reflect the intended optimization, not the current bug.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Fix the N+1 in the property usage or annotate; then assert the optimized count.

**#201** Line 277: Test asserts assertNumQueries(8) while explicitly noting it 'could be optimized to 2 with annotation' — the test cements a known-suboptimal query pattern as the contract.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Replace property-based per-bed COUNT with a single annotation and tighten assertion.

**#202** Line 300: Comprehensive dashboard test asserts 17 queries — sum of multiple unoptimized analytics calls. Comment chain shows 10 of those are the same N+1 captured at line 277, compounding the regression-blindness.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Optimize the underlying analytics methods, then update each assertion to the new strict count.

### `backend/apps/plant_identification/api/diagnosis_serializers.py`

**#203** Line 191: DiagnosisCardDetailSerializer.get_active_reminders_count fires a filtered count() query per card — N+1 when serializing lists.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization
- **Suggested fix:** Replace with a Count() annotation with a filter argument or precompute on the queryset.

**#204** Line 191: DiagnosisCardDetailSerializer.get_active_reminders_count() runs a COUNT() per object. Although used on retrieve only, the existing prefetch_related('reminders') still won't help with .count() — will trigger a fresh query.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate active_reminders_count via Count('reminders', filter=Q(reminders__is_active=True, reminders__sent=False, reminders__cancelled=False)) in DiagnosisCardViewSet.get_queryset() for retrieve action.

### `backend/apps/plant_identification/api/endpoints.py`

**#205** Line 130: PlantCategoryAPIViewSet does not set versioning_class = None — DRF DEFAULT_VERSIONING_CLASS is NamespaceVersioning globally, which breaks Wagtail API v2 routing as noted on PlantSpeciesAPIViewSet line 30.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Add `versioning_class = None` at top of class to match PlantSpeciesAPIViewSet.

**#206** Line 166: PlantCareGuideAPIViewSet missing versioning_class = None override; will fail under global NamespaceVersioning that Wagtail API doesn't honor.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Add `versioning_class = None` to disable DRF versioning for Wagtail API.

**#207** Line 237: PlantSpeciesPageViewSet missing versioning_class = None — same DRF NamespaceVersioning breakage as siblings.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Add `versioning_class = None`.

**#208** Line 256: PlantSpeciesPageViewSet.get_queryset() does prefetch_related('gallery_images') but the detail serializer calls get_rendition() per image — Wagtail won't auto-prefetch renditions; this still incurs O(N) rendition queries on detail loads.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Replace with prefetch_related(Prefetch('gallery_images', queryset=Image.objects.prefetch_renditions('fill-400x300','fill-200x150'))).

**#209** Line 331: PlantCategoryIndexPageViewSet missing versioning_class = None.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Add `versioning_class = None`.

### `backend/apps/plant_identification/api/serializers.py`

**#210** Line 99: PlantCategorySerializer.get_plant_count calls obj.plant_species.count() per category without prefetching — produces N+1 SELECT COUNT queries when serializing list endpoints.

- **Reviewer:** wagtail-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate the queryset with Count('plant_species') in PlantCategoryAPIViewSet.get_queryset and read the annotated value here.

**#211** Line 101: PlantCategorySerializer.get_plant_count() calls obj.plant_species.count() per row on /api/v2/plant_categories/ — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** PlantCategoryAPIViewSet.get_queryset() should annotate plant_count=Count('plant_species') instead of using prefetch_related (count cannot be served from prefetch).

**#212** Line 124: PlantCareGuideSerializer.get_tags() iterates obj.tags.all() per row — taggit M2M query per object on care guide lists.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** PlantCareGuideAPIViewSet.get_queryset() must prefetch_related('tagged_items__tag') (or use prefetch_related('tags')).

**#213** Line 177: PlantSpeciesPageSerializer.get_related_plants() runs an additional filter+distinct query per detail object, plus calls get_rendition() per related plant — significant per-detail latency and missing cache.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md, patterns/architecture/caching.md
- **Suggested fix:** Cache related plants per species_page (Redis, 1h TTL) and select_related('plant_species') with prefetch_related('categories') on the inner queryset.

**#214** Line 177: get_related_plants issues a separate query per parent page, then accesses plant.plant_species.scientific_name/common_names without select_related, causing N+1 on every detail fetch.

- **Reviewer:** wagtail-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add .select_related('plant_species') to the related_plants queryset and prefetch on the viewset detail action.

**#215** Line 184: obj.plant_species.family will AttributeError when plant_species is None — same nullable FK issue, breaks any page where the species link is unset.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Early-return [] if not obj.plant_species, or use getattr with default.

**#216** Line 195: Direct attribute access plant.plant_species.scientific_name will raise AttributeError because PlantSpeciesPage.plant_species is null=True/blank=True (models.py:2211).

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Guard with `if plant.plant_species else None` and conditionally include scientific_name/common_name.

### `backend/apps/plant_identification/api/simple_views.py`

**#217** Line 69: @ratelimit decorator returns 403 by default (Ratelimited inherits PermissionDenied) instead of 429 with Retry-After header — violates project Issue #133 pattern.

- **Reviewer:** api-design-reviewer
- **Rule:** rate-limiting.md / Issue #133
- **Suggested fix:** Ensure custom exception handler checks isinstance(exc, Ratelimited) so this endpoint returns 429 with Retry-After header.

**#218** Line 78: @transaction.atomic wraps a view that performs long-running external API calls (Plant.id + PlantNet), holding a DB transaction open across network I/O.

- **Reviewer:** api-design-reviewer
- **Rule:** architecture concern
- **Suggested fix:** Move atomic to the inner DB-write portion of the service, not around the entire view including external calls.

**#219** Line 78: `@transaction.atomic` decorator wraps an endpoint that performs blocking external API calls (Plant.id + PlantNet) inside the DB transaction, holding row locks for tens of seconds and risking pool exhaustion.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/concurrency
- **Suggested fix:** Remove @transaction.atomic — no DB writes happen here, or move it to wrap only the persistence section.

**#220** Line 116: Error response shape uses {'success': false, 'error': '...'} which conflicts with project-standard {'error': '...'} or {'error', 'detail'}.

- **Reviewer:** api-design-reviewer
- **Rule:** Error Responses checklist: consistent shape
- **Suggested fix:** Return {'error': 'message'} (and optional 'detail') consistently across all error paths.

**#221** Line 127: `except ValidationError` is used but `ValidationError` is never imported in this module, so a malformed image will raise NameError instead of returning 400.

- **Reviewer:** django-drf-reviewer
- **Rule:** import error
- **Suggested fix:** Add `from rest_framework.exceptions import ValidationError` (or `from django.core.exceptions import ValidationError`) at top of file.

**#222** Line 154: Service errors are returned with HTTP 200 OK plus {'success': False, 'error': ...}, hiding failures from clients and breaking standard HTTP semantics.

- **Reviewer:** api-design-reviewer
- **Rule:** Error Responses checklist: 4xx/5xx for failures
- **Suggested fix:** Return HTTP 502/503 (upstream/service unavailable) or 400, not 200.

### `backend/apps/plant_identification/permissions.py`

**#223** Line 41: IsAuthenticatedOrReadOnlyWithRateLimit unconditionally returns True for anonymous POST traffic — the rate-limit-only protection contradicts the class name and silently disables auth even in production.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/authentication
- **Suggested fix:** For anonymous users, return False unless request.method in SAFE_METHODS (matching IsAuthenticatedForIdentification).

**#224** Line 41: IsAuthenticatedOrReadOnlyWithRateLimit always returns True regardless of method, despite its name and docstring claiming read-only access for anonymous users; this misleads callers into believing writes are restricted when they are not.

- **Reviewer:** security-reviewer
- **Rule:** backend/docs/patterns/architecture/viewsets.md (least-privilege permissions)
- **Suggested fix:** Either gate non-SAFE_METHODS on request.user.is_authenticated, or rename the class and docstring to accurately reflect that it permits all methods and relies entirely on the @ratelimit decorator.

### `backend/apps/plant_identification/serializers.py`

**#225** Line 91: PlantIdentificationRequestSerializer.get_results_count does `obj.identification_results.count()` per row — N+1 query in list responses.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization
- **Suggested fix:** Use Count() annotation in the viewset queryset and read from the annotated field.

**#226** Line 91: PlantIdentificationRequestSerializer.get_results_count() runs a COUNT(*) query per object via obj.identification_results.count() — N+1 on list endpoints (UserPlantViewSet, PlantIdentificationRequestViewSet list).

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md (N+1 via SerializerMethodField)
- **Suggested fix:** Annotate queryset with Count('identification_results') in get_queryset() and read from obj.results_count_annotated.

**#227** Line 143: PlantDiseaseRequestSerializer.get_results_count triggers per-row count query — N+1.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization
- **Suggested fix:** Annotate Count('diagnosis_results') on the queryset.

**#228** Line 145: PlantDiseaseRequestSerializer.get_results_count() executes obj.diagnosis_results.count() per object — N+1 on disease request list endpoints.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use Count('diagnosis_results') annotation in PlantDiseaseRequestViewSet.get_queryset().

**#229** Line 196: PlantIdentificationResultSerializer.get_user_vote runs a DB query per result via SerializerMethodField — classic N+1 across list responses.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization (BLOCKER N+1)
- **Suggested fix:** Annotate the queryset in the viewset with a Subquery/Exists for the current user vote and pull from the annotation.

**#230** Line 295: PlantIdentificationRequestWithResultsSerializer nests identification_results without prefetch_related — list endpoint issues a query per request to load child results.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md (prefetch on nested serializers)
- **Suggested fix:** PlantIdentificationRequestViewSet.get_queryset() must prefetch_related('identification_results', 'identification_results__identified_species').

**#231** Line 332: PlantIdentificationRequestWithResultsSerializer.get_results_count() runs a per-row count query — N+1 across list responses.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate Count('identification_results') instead of per-object count() call.

**#232** Line 384: Duplicate PlantDiseaseRequestSerializer.get_results_count() at line 384 also runs per-row count() — same N+1 pattern.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Remove the duplicate class declaration and replace with annotated count.

**#233** Line 470: PlantDiseaseDatabaseSerializer.get_affected_plant_count() runs obj.affected_plants.count() per row — N+1 on the disease database list endpoint.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate Count('affected_plants') in PlantDiseaseDatabaseViewSet.get_queryset().

**#234** Line 476: SavedDiagnosisSerializer embeds PlantDiseaseResultSerializer for diagnosis_result without select_related on the source viewset — each saved diagnosis triggers a query for the FK plus its request and diagnosed_by relations.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md (select_related on FKs accessed by nested serializers)
- **Suggested fix:** SavedDiagnosisViewSet.get_queryset() must select_related('diagnosis_result', 'diagnosis_result__request', 'diagnosis_result__diagnosed_by').

**#235** Line 512: TreatmentAttemptSerializer.diagnosis_info nests PlantDiseaseResultSerializer; viewset does no select_related — N+1 across list responses.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** TreatmentAttemptViewSet.get_queryset() should select_related('diagnosis_result', 'diagnosis_result__request', 'user') and prefetch any nested needs.

**#236** Line 573: PlantDiseaseRequestWithResultsSerializer.get_results_count() and nested diagnosis_results without prefetch — both N+1 on the disease request list endpoint.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** PlantDiseaseRequestViewSet.get_queryset() must prefetch_related('diagnosis_results', 'plant_species') and annotate Count('diagnosis_results').

### `backend/apps/plant_identification/services/ai_care_service.py`

**#237** Line 34: AIPlantCareService.generate_care_instructions() has no Redis cache. Pattern target for AI generation is 80-95% hit rate; identical (plant_name, common_names, location, experience) calls re-hit OpenAI/AI provider on every regenerate.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/architecture/caching.md (AI cache 80-95%)
- **Suggested fix:** Wrap generate_care_instructions in cache.get_or_set() keyed on hashed (plant_name, common_names, experience_level) with 24h+ TTL; honor force_regenerate flag to bypass.

### `backend/apps/plant_identification/services/ai_image_service.py`

**#238** Line 39: AIBotanicalImageService instantiates the OpenAI client eagerly in **init** instead of lazy-init — violates the lazy-init pattern (e.g. _ensure_openai_initialized) required so tests can run without credentials.

- **Reviewer:** wagtail-reviewer
- **Rule:** wagtail checklist: AI Integration — Lazy-init pattern required
- **Suggested fix:** Defer openai.OpenAI() to a _get_client() helper invoked only when generate_plant_image is called.

### `backend/apps/plant_identification/services/identification_service.py`

**#239** Line 645: _get_local_species_matches builds icontains queries on `common_names`, `scientific_name`, `genus` from raw user-controlled `query` without escape_search_query().

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation
- **Suggested fix:** Call escape_search_query(query) before constructing the Q() filter.

### `backend/apps/plant_identification/services/plant_health_service.py`

**#240** Line 376: search_local_database uses `disease_name__icontains=disease_name` without escape_search_query() — `%` and `_` from user input act as SQL wildcards.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation
- **Suggested fix:** Wrap the input with apps.core.utils.query_sanitization.escape_search_query() before filtering.

### `backend/apps/plant_identification/services/plant_id_service.py`

**#241** Line 159: Cache key violates required format `app:feature:scope:identifier` — only contains 3 colon-separated segments and no app prefix beyond `plant_id`. Should namespace under `plant_identification:`.

- **Reviewer:** django-drf-reviewer
- **Rule:** caching pattern
- **Suggested fix:** Use `plant_identification:plant_id:v3:{hash}:{include_diseases}`.

### `backend/apps/plant_identification/services/plantnet_service.py`

**#242** Line 237: Cache key `plantnet:v2:{project}:{hash}:...` lacks the app prefix mandated by the caching pattern (`app:feature:scope:identifier`).

- **Reviewer:** django-drf-reviewer
- **Rule:** caching pattern
- **Suggested fix:** Prefix with `plant_identification:` to scope keys to the app.

### `backend/apps/plant_identification/tasks.py`

**#243** Line 17: autoretry_for=(Exception,) retries on every exception including permanent/programming errors (ValueError, TypeError, DoesNotExist subclasses), wasting workers and masking bugs.

- **Reviewer:** celery-async-reviewer
- **Rule:** checklist: autoretry_for must list specific exceptions — not bare Exception
- **Suggested fix:** List only transient exceptions (e.g., requests.RequestException, TimeoutError, ConnectionError, RateLimitExceeded) and let permanent errors fail fast.

**#244** Line 23: Task is not idempotent — repeated runs with the same request_uuid will re-invoke the external Plant.id/PlantNet API, double-billing and duplicating results, with no guard checking req.status before processing.

- **Reviewer:** celery-async-reviewer
- **Rule:** checklist: Tasks that modify state must be idempotent
- **Suggested fix:** At task entry, short-circuit if req.status in ('completed','failed') or use a 'processing' status guard / DB lock to prevent concurrent re-execution.

### `backend/apps/plant_identification/test_executor_caching.py`

**#245** Line 414: Performance assertion uses assertLess(elapsed, 0.18) which is a brittle wall-clock test that will be flaky under CI load and provides no clear regression signal — strict-equality / event-ordering checks are preferred for parallelism verification.

- **Reviewer:** test-quality-reviewer
- **Rule:** performance/query-optimization.md — strict assertions over thresholds
- **Suggested fix:** Verify parallelism via mock call ordering / threading.Event timestamps rather than total elapsed time, and skip in CI with @pytest.mark.slow if timing must remain.

### `backend/apps/plant_identification/test_services.py`

**#246** Line 667: TestServiceCaching mocks django.core.cache.cache.get/set, which violates the rule against mocking infrastructure layers and produces a brittle test that does not exercise actual caching behaviour.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality-reviewer: do not mock infrastructure (cache/db) — use real Redis/Postgres or override_settings
- **Suggested fix:** Use Django's real cache (LocMem or Redis) and assert behaviour by calling _make_request twice while checking the cache backend, instead of mocking cache.get/set.

### `backend/apps/plant_identification/views.py`

**#247** Line 124: PlantIdentificationRequestViewSet has no select_related/prefetch_related on its queryset — list endpoints touch FK user repeatedly.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization
- **Suggested fix:** Add .select_related('user') and .prefetch_related('identification_results') in get_queryset.

**#248** Line 133: PlantIdentificationRequestViewSet.get_queryset() lacks select_related/prefetch_related — list serializer accesses results count + (when WithResults serializer is used elsewhere) nested results → N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** select_related('user') + prefetch_related(Prefetch('identification_results', queryset=PlantIdentificationResult.objects.select_related('identified_species', 'identified_by'))); annotate results_count.

**#249** Line 138: PlantIdentificationRequestViewSet.create wraps the rate-limit decorator but django-ratelimit raises Ratelimited (PermissionDenied -> 403); without a custom exception handler converting to 429 the API returns the wrong HTTP status.

- **Reviewer:** django-drf-reviewer
- **Rule:** Issue #133
- **Suggested fix:** Ensure a global exception handler maps Ratelimited to HTTP 429 with Retry-After (see backend/docs/patterns/architecture/rate-limiting.md).

**#250** Line 286: PlantIdentificationResultViewSet.get_queryset() lacks select_related — serializer accesses request, identified_species, identified_by per row plus get_user_vote() — N+1 chain on result list.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** select_related('request', 'identified_species', 'identified_by') in get_queryset().

**#251** Line 723: PlantDiseaseRequestViewSet.get_queryset does not select_related/prefetch_related, but list serializer pulls plant_species_data and diagnosis_results — heavy N+1.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization
- **Suggested fix:** Add .select_related('plant_species', 'plant_identification_request').prefetch_related('diagnosis_results').

**#252** Line 731: PlantDiseaseRequestViewSet.get_queryset() returns the disease requests without select_related/prefetch_related; list serializer is PlantDiseaseRequestWithResultsSerializer which nests diagnosis_results — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** select_related('user', 'plant_species', 'plant_identification_request') + prefetch_related('diagnosis_results') + annotate results_count.

**#253** Line 744: PlantDiseaseRequestViewSet.create rate-limited with `regenerate` (5/m) tier, far stricter than the documented `plant_identification` (100/h) bucket — likely misconfiguration causing legitimate failures.

- **Reviewer:** django-drf-reviewer
- **Rule:** rate limiting policy
- **Suggested fix:** Use constants.RATE_LIMITS['authenticated']['plant_identification'] or a dedicated bucket.

**#254** Line 749: perform_create runs disease diagnosis synchronously inside an HTTP request, blocking the worker for tens of seconds on external Plant.health API; comment says 'TODO: Enqueue Celery task'.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/services
- **Suggested fix:** Enqueue a Celery task and return 202 with status polling, mirroring run_identification.delay().

**#255** Line 1066: SavedDiagnosisViewSet.get_queryset uses no select_related — serializer pulls diagnosis_data including request relation, causing N+1.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization
- **Suggested fix:** Add .select_related('diagnosis_result', 'diagnosis_result__request', 'diagnosis_result__diagnosed_by').

**#256** Line 1188: search_local_plants runs scientific_name__icontains and common_names__icontains over a TextField/CharField; the model has no GIN/trigram or db_index on these columns (PlantSpecies.Meta declares only ordering). On large catalogs this triggers full table scans.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md (GIN index for icontains)
- **Suggested fix:** Add GinIndex with TrigramExtension on scientific_name, common_names, family — or at minimum migrate to PostgreSQL pg_trgm + gin_trgm_ops index.

**#257** Line 1244: search_local_diseases uses disease_name__icontains without GIN/trigram index on PlantDiseaseDatabase.disease_name — full scan as data grows.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add a trigram GIN index on PlantDiseaseDatabase.disease_name.

**#258** Line 1493: regenerate_care_instructions looks up PlantIdentificationResult by integer id (`id=result_id`), exposing internal sequential IDs in URLs and bypassing the model's UUID; ownership check happens after the lookup but the URL leak persists.

- **Reviewer:** django-drf-reviewer
- **Rule:** domain/diagnosis (UUID lookups in DRF)
- **Suggested fix:** Switch URL pattern and lookup to UUID.

### `backend/apps/search/services/search_service.py`

**#259** Line 163: Topic search annotates SearchVector('subject') + SearchVector('first_post__content') at query time instead of using the persisted Topic.search_vector field that signals already populate, doubling FTS computation cost per request and joining to Post for every query.

- **Reviewer:** performance-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md (use SearchVectorField)
- **Suggested fix:** Filter on the persisted search_vector column (e.g. .filter(search_vector=search_query).annotate(rank=SearchRank('search_vector', search_query))).

**#260** Line 169: topic.first_post access uses select_related('poster','forum') but not 'first_post', causing one extra query per topic (N+1) when accessing first_post.content.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add 'first_post' to select_related.

**#261** Line 174: topic.first_post.content is accessed in the loop while select_related only includes 'poster' and 'forum'; this triggers an N+1 query on Post for every topic in the result set.

- **Reviewer:** performance-reviewer
- **Rule:** List views must use select_related for all accessed FKs
- **Suggested fix:** Add 'first_post' to select_related (e.g. select_related('poster', 'forum', 'first_post')).

**#262** Line 189: topics_qs.count() called after annotate(...).filter(search=...) re-executes the expensive FTS aggregate just to count; same pattern in plants/blog/diseases.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Materialize the limited list once and count separately, or use a base id-only count query.

**#263** Line 189: topics_qs.count() is called after iterating the same annotated queryset; PostgreSQL re-executes the full FTS query without the LIMIT, doubling DB work for every search request (same pattern repeats for plants L239, blog L293, diseases L340).

- **Reviewer:** performance-reviewer
- **Rule:** Avoid redundant .count() on annotated FTS querysets
- **Suggested fix:** Cache the queryset id list once or compute count via a stripped queryset; consider single SQL with window function COUNT(*) OVER().

**#264** Line 199: filters['plant_family'] passed directly into icontains without wildcard escaping enables wildcard injection.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Run filter values through escape_search_query() before icontains.

**#265** Line 208: Plants search re-builds SearchVector('scientific_name')+('common_names')+('family') twice per query (annotate search and SearchRank) ignoring the persisted PlantSpecies.search_vector populated by signals.

- **Reviewer:** performance-reviewer
- **Rule:** Use SearchVectorField instead of runtime SearchVector
- **Suggested fix:** Replace runtime SearchVector with .filter(search_vector=search_query).annotate(rank=SearchRank('search_vector', search_query)).

**#266** Line 260: Blog search annotates SearchVector at query time on title/introduction/meta_description although signals maintain a persisted search_vector field; runtime FTS over many BlogPostPage rows is expensive and not index-backed.

- **Reviewer:** performance-reviewer
- **Rule:** Use persisted search_vector + GIN index
- **Suggested fix:** Filter and rank against the existing search_vector field rather than rebuilding SearchVector each request.

**#267** Line 287: post.categories.all() inside per-result loop produces N+1 queries for blog category access.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add .prefetch_related('categories') to blog_qs.

**#268** Line 287: post.categories.all() is iterated inside the result-building loop without prefetch_related, producing one query per blog post (N+1) on the M2M categories relation.

- **Reviewer:** performance-reviewer
- **Rule:** List views must use prefetch_related for accessed M2M
- **Suggested fix:** Add .prefetch_related('categories') to blog_qs before slicing.

**#269** Line 306: filters['affected_plants'] passes raw user input into icontains without escaping % or _ wildcards.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Escape user-supplied filter value before icontains.

**#270** Line 309: Diseases search recomputes SearchVector for disease_name/description/symptoms at query time rather than using the persisted vector populated by the post_save signal.

- **Reviewer:** performance-reviewer
- **Rule:** Use persisted search_vector + GIN index
- **Suggested fix:** Replace runtime SearchVector annotate with persisted search_vector filter and SearchRank.

**#271** Line 408: icontains filter on query_text uses raw user input without escaping % and_ wildcards, allowing wildcard injection.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Apply escape_search_query() to partial_query before passing to icontains.

**#272** Line 421: icontains lookups on scientific_name and common_names use raw user input without wildcard escaping.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Escape % and _in partial_query via escape_search_query() helper.

### `backend/apps/search/signals.py`

**#273** Line 31: post_save handler issues raw SearchVector update on every Topic save without checking connection.vendor; will fail on SQLite test DBs and runs on every save (perf).

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Guard with `if connection.vendor != 'postgresql': return`; consider scheduling via Celery.

**#274** Line 45: Post post_save handler unconditionally runs SearchVector update on every save and re-runs when first_post; SQLite-incompatible and may cause recursion if downstream signals re-save.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add postgres-vendor guard and use update_fields check to avoid re-running unnecessarily.

**#275** Line 65: PlantSpecies post_save handler updates search_vector on every save without postgres vendor guard; breaks SQLite-based tests.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Guard against connection.vendor != 'postgresql'.

**#276** Line 79: PlantDiseaseDatabase post_save handler unconditionally runs SearchVector update; SQLite-incompatible.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add postgres vendor guard.

**#277** Line 95: BlogPostPage post_save handler runs SearchVector update on every save without postgres guard; breaks SQLite tests and references fields ('intro', 'body') that may not match BlogPostPage definition (was 'introduction' in search_service).

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add vendor guard and verify field names against BlogPostPage model.

### `backend/apps/search/views.py`

**#278** Line 35: Unified search endpoint is AllowAny with no rate limit; expensive multi-table FTS can be abused for DoS.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/architecture/rate-limiting.md
- **Suggested fix:** Add @ratelimit decorator and use the custom Ratelimited exception handler returning 429.

**#279** Line 105: Error response leaks internal exception text to clients (`f'Search failed: {str(e)}'`), exposing stack/internal detail.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/secret-management.md
- **Suggested fix:** Log the exception, return a generic error message in the response.

**#280** Line 140: Returning str(e) in the response body leaks internal error context to anonymous callers.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/secret-management.md
- **Suggested fix:** Return a generic 500 message; log the detail server-side.

**#281** Line 211: SearchFiltersView runs forum/blog/plant family/plant types/care levels/disease types queries on every request without Redis caching, despite this data being rarely-changed reference data.

- **Reviewer:** performance-reviewer
- **Rule:** backend/docs/patterns/architecture/caching.md (frequently-accessed, rarely-changed)
- **Suggested fix:** Wrap the assembled filters_data in cache.get_or_set with a long TTL keyed on a content-version sentinel.

**#282** Line 289: Raw exception text included in user-facing error response.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/secret-management.md
- **Suggested fix:** Replace with a generic message; keep details in logs.

**#283** Line 344: Loop performs days separate count() queries against searches queryset (N=days DB roundtrips); should aggregate via TruncDate annotation in a single query.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use .annotate(day=TruncDate('created_at')).values('day').annotate(count=Count('id')).

**#284** Line 344: search_trends loop issues one separate COUNT query per day (default 30 queries, up to user-supplied days) on the same SearchQuery table; this can be a single query using TruncDate + annotate(Count()).

- **Reviewer:** performance-reviewer
- **Rule:** Aggregations must use Count/annotate, not Python loops
- **Suggested fix:** Use searches.annotate(day=TruncDate('created_at')).values('day').annotate(count=Count('id')).

**#285** Line 372: Exception message returned in HTTP response could leak admin/database internals.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/secret-management.md
- **Suggested fix:** Return generic error string and rely on log entry for diagnostics.

**#286** Line 378: track_search_click is AllowAny without rate limiting, allowing arbitrary anonymous writes to SearchResultClick.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/architecture/rate-limiting.md
- **Suggested fix:** Add @ratelimit on key='ip' and validate result_type against an allowlist.

**#287** Line 432: Raw exception message returned to anonymous client in track_search_click error path.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/secret-management.md
- **Suggested fix:** Strip exception detail from response body.

### `backend/apps/users/email_preferences_views.py`

**#288** Line 24: email_preferences view (and ajax_update_preference, unsubscribe) has no @csrf_protect / @csrf_exempt decision and no DRF api_view — these are state-changing POST endpoints relying solely on Django's middleware. ajax_update_preference iterates user-supplied preference names; while ALLOWED_PREFERENCES is whitelisted, the endpoint should still document its CSRF posture.

- **Reviewer:** django-drf-reviewer
- **Rule:** csrf-protection
- **Suggested fix:** Add @csrf_protect explicitly to POST endpoints and confirm middleware is active.

### `backend/apps/users/firebase_auth_views.py`

**#289** Line 84: firebase_token_exchange has no @ratelimit decorator — Firebase token exchange is an unauthenticated endpoint that creates users; without rate limiting it is open to user-creation abuse and brute force token tries.

- **Reviewer:** django-drf-reviewer
- **Rule:** rate-limiting
- **Suggested fix:** Add @ratelimit(key='ip', rate='10/m', method='POST', block=True) similar to register/login.

**#290** Line 84: firebase_token_exchange has no rate limiting; an attacker can submit forged/stale tokens at high volume to probe behaviour, enumerate users, or trigger user-creation side effects.

- **Reviewer:** security-reviewer
- **Rule:** backend/docs/patterns/architecture/rate-limiting.md
- **Suggested fix:** Add `@ratelimit(key='ip', rate='20/m', block=True)` (and ideally one keyed on token-derived uid) plus a custom 429 handler so it returns 429 with Retry-After.

**#291** Line 195: Bare `except Exception` swallows Django's PermissionDenied/Ratelimited exceptions and returns 500 instead of letting DRF's exception handler convert them to 429/403; this defeats the project rate-limit handler pattern.

- **Reviewer:** django-drf-reviewer
- **Rule:** exception-handler-pattern
- **Suggested fix:** Re-raise Ratelimited / PermissionDenied / DRF APIException, or narrow the except.

**#292** Line 250: Username-collision check (`filter(username=...).exists()` then `User.objects.create`) is not transactional; two concurrent token exchanges can pass the check and race to create duplicate usernames, raising IntegrityError or producing unintended state.

- **Reviewer:** security-reviewer
- **Rule:** Django concurrency / TOCTOU
- **Suggested fix:** Wrap the lookup+create inside `with transaction.atomic():` and use `select_for_update`/`get_or_create` semantics, or catch IntegrityError and retry.

### `backend/apps/users/models.py`

**#293** Line 223: trust_level_updated has auto_now=True with null=True/blank=True — auto_now overwrites the value on every save() of any field, defeating the intent of recording 'last time trust level was recalculated' and creating misleading audit data.

- **Reviewer:** django-drf-reviewer
- **Rule:** model-timestamp-misuse
- **Suggested fix:** Drop auto_now=True; the field is already explicitly set in update_trust_level().

**#294** Line 424: UserPlantCollection.plant_count property calls self.plants.count(); since serializer marks plant_count as ReadOnlyField, this becomes one COUNT query per collection in list responses.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: Python @property hitting related_set.count()
- **Suggested fix:** Replace the property with a Count() annotation from the queryset, or memoize via prefetch_related and len().

**#295** Line 530: ActivityLog.created_at uses auto_now=True (updates on every save) instead of auto_now_add=True; combined with ordering=['-created_at'] this corrupts the activity feed timeline and indexes.

- **Reviewer:** django-drf-reviewer
- **Rule:** model-timestamp-misuse
- **Suggested fix:** Change auto_now=True to auto_now_add=True for created_at on ActivityLog.

### `backend/apps/users/oauth_adapters.py`

**#296** Line 39: pre_social_login connects a social account to an existing Django user solely by matching the OAuth `email` claim, with no verification that the OAuth provider has verified that email — an attacker with an unverified email matching a victim takes over the victim's account.

- **Reviewer:** security-reviewer
- **Rule:** django-allauth SOCIALACCOUNT_EMAIL_VERIFICATION / OWASP ASVS 2.7
- **Suggested fix:** Only auto-link when the provider explicitly reports the email as verified (e.g. Google `email_verified`, GitHub email's `verified` flag); otherwise force the new sign-up flow.

### `backend/apps/users/oauth_views.py`

**#297** Line 42: @ratelimit on oauth_login/oauth_callback with `block=True` raises Ratelimited (a PermissionDenied subclass) so DRF returns HTTP 403 instead of 429, and no Retry-After header is set — violates the documented gotcha #4.

- **Reviewer:** security-reviewer
- **Rule:** CLAUDE.md gotcha #4 / backend/docs/patterns/architecture/rate-limiting.md
- **Suggested fix:** Wire a custom exception handler that checks `isinstance(exc, Ratelimited)` before DRF default handling and returns 429 with Retry-After.

**#298** Line 50: Direct dict access settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id'] raises KeyError if google/github isn't configured, returning a 500 instead of the intended 503 'OAuth not configured' response below.

- **Reviewer:** django-drf-reviewer
- **Rule:** config-access-safety
- **Suggested fix:** Use settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP', {}).get('client_id') or wrap in try/except KeyError.

**#299** Line 203: requests.post(token_url, data=token_data) with no timeout — a slow Google/GitHub token endpoint will hang the worker indefinitely. Same issue at lines 212, 241, 255, 266.

- **Reviewer:** django-drf-reviewer
- **Rule:** external-call-no-timeout
- **Suggested fix:** Pass timeout=10 (or similar) to every requests call.

**#300** Line 203: Outbound requests to Google/GitHub token and userinfo endpoints have no timeout, allowing a slow upstream to tie up worker threads (DoS vector).

- **Reviewer:** security-reviewer
- **Rule:** OWASP ASVS 14.2 / requests best practice
- **Suggested fix:** Pass `timeout=(connect_timeout, read_timeout)` to every requests.get/post call (e.g. `timeout=(3.05, 10)`).

**#301** Line 211: Google OAuth access_token is passed as a query-string parameter to googleapis.com/userinfo, causing the secret to be written to upstream proxy logs, ad-block intermediaries, and Django request logs if request URL is logged.

- **Reviewer:** security-reviewer
- **Rule:** RFC 6750 §2.3 — bearer token in URI is NOT RECOMMENDED
- **Suggested fix:** Send the token via `Authorization: Bearer <token>` header instead of an `?access_token=` query parameter.

**#302** Line 322: Username uniqueness loop (`while User.objects.filter(username=username).exists(): ... create_user`) is racy and not atomic; concurrent OAuth callbacks can both observe a free username and one create_user will fail or duplicate state.

- **Reviewer:** security-reviewer
- **Rule:** TOCTOU on user creation
- **Suggested fix:** Wrap the lookup and create_user call in `transaction.atomic()` and handle IntegrityError by retrying with a new suffix.

### `backend/apps/users/serializers.py`

**#303** Line 82: UserSerializer exposes follower_count and following_count as ReadOnlyFields backed by model @property methods that call self.followers.count() / self.following.count() — each serialized user issues 2 extra COUNT queries, producing N+1 in any list endpoint that uses UserSerializer.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: SerializerMethodField/property calling related_set.count() is N+1
- **Suggested fix:** Annotate users in the ViewSet queryset with Count('followers') and Count('following', distinct=True) and read those annotations from the serializer.

**#304** Line 84: UserSerializer.get_avatar_thumbnail is a SerializerMethodField that triggers ImageKit thumbnail generation per row; combined with `many=True` callers this becomes an N+1 storage hit. The `obj.avatar` access on a queryset without .only/select_related fetches binary metadata for every row.

- **Reviewer:** django-drf-reviewer
- **Rule:** n-plus-one-serializer
- **Suggested fix:** Generate thumbnails offline, cache URLs, or compute on demand only on detail views.

**#305** Line 137: UserProfileSerializer.get_plant_collections_count calls obj.plant_collections.count() in a SerializerMethodField — BLOCKER N+1 if this serializer is ever used with many=True; the project pattern requires conditional annotations instead.

- **Reviewer:** django-drf-reviewer
- **Rule:** n-plus-one-serializer
- **Suggested fix:** Annotate at the queryset level (Count('plant_collections')) and read the annotated attribute.

**#306** Line 137: UserProfileSerializer.get_plant_collections_count() executes obj.plant_collections.count() per user — guaranteed N+1 if this serializer is ever used in a list view.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: SerializerMethodField calling reverse FK .count() per object
- **Suggested fix:** Annotate the queryset with Count('plant_collections') in get_queryset() and read from annotation in the serializer.

**#307** Line 147: UserPlantCollectionSerializer pulls in `plants` via SerializerMethodField (UserPlant.objects.filter(collection=obj)) AND `plant_count` via the model's plants.count() property — list endpoints (e.g., /me/collections/) execute 2 queries per collection (one for plant_count, one for the plant list + nested serialization).

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: nested SerializerMethodField + .count() property in list serializer
- **Suggested fix:** Annotate Count('plants') as plant_count in views.user_collections's queryset; prefetch_related('plants__species','plants__from_identification_request') and use a Prefetch object so plants reads from cache.

**#308** Line 156: UserPlantCollectionSerializer.get_plants does `UserPlant.objects.filter(collection=obj)` for every collection serialized — N+1 when listing collections via user_collections endpoint.

- **Reviewer:** django-drf-reviewer
- **Rule:** n-plus-one-serializer
- **Suggested fix:** Use prefetch_related on the queryset in views.user_collections and read obj.userplant_set.all().

### `backend/apps/users/services.py`

**#309** Line 76: TrustLevelService.setup_forum_permissions runs nested loops (forums x 3 groups x 2 permissions) calling GroupForumPermission.objects.get_or_create individually — 6*forum_count round-trips. With many forums this is slow and not idempotency-safe under contention.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: per-row get_or_create loop instead of bulk
- **Suggested fix:** Build the desired (perm, forum, group) tuples and use bulk_create(ignore_conflicts=True) once, or pre-fetch existing rows and only insert deltas.

**#310** Line 133: TrustLevelService.update_all_user_trust_levels iterates User.objects.all() and for every user calls update_trust_level() (which may .save()), then assign_user_to_trust_group() (which does 3 Group lookups + remove + add per user). On a user table of N rows this issues 6N+ queries with no batching or .iterator().

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: Python-loop over full table without iterator/bulk update
- **Suggested fix:** Cache the three Group instances once outside the loop, use User.objects.iterator() or batched .only() queries, and consider bulk_update for trust_level changes.

### `backend/apps/users/tests/test_account_lockout.py`

**#311** Line 250: test_lockout_window_time_limit patches the global `time.time` instead of `apps.core.security.time.time`; the SecurityMonitor module imported `time` as `import time` so the global patch will not take effect inside it, and the test silently asserts the wrong behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** Compare to test_lockout_expires_automatically which patches `apps.core.security.time.time`
- **Suggested fix:** Patch `apps.core.security.time.time` so the mocked timestamps actually flow into SecurityMonitor.

### `backend/apps/users/tests/test_rate_limiting.py`

**#312** Line 335: test_rate_limit_response_includes_retry_after is effectively a no-op: the inner block is just `pass` with a comment marking the header check optional, so the test never asserts anything about Retry-After.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion quality / coverage
- **Suggested fix:** Either assert the Retry-After header is present and parseable, or delete the test.

**#313** Line 363: test_anonymous_has_stricter_limits has no assertions and only contains a `pass` placeholder, providing zero coverage.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: coverage
- **Suggested fix:** Implement the test against a real rate-limited endpoint or remove the stub.

**#314** Line 382: test_authentication_increases_rate_limit logs in but never asserts anything (`pass`); the test will pass even if rate-limit behavior is broken.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: coverage
- **Suggested fix:** Add concrete request loops + status assertions for anon vs authenticated, or delete.

### `backend/apps/users/views.py`

**#315** Line 489: search_detail signature declares request_id: int but URL pattern is <uuid:request_id> (urls.py:36); the type hint contradicts the URL converter and the underlying field is a UUID — silently misleading but the lookup .get(request_id=request_id) only works because Django parses to UUID first.

- **Reviewer:** django-drf-reviewer
- **Rule:** type-hint-mismatch
- **Suggested fix:** Change parameter annotation to `request_id: str` (or `uuid.UUID`).

**#316** Line 1199: Bug masquerading as a performance fix: completion_stats['max_streak'] is a scalar from Max('longest_streak'), but the code does completion_stats['max_streak'].longest_streak — this raises AttributeError at runtime, which will look like a 500 perf issue under load.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: aggregation result misuse
- **Suggested fix:** Use completion_stats['max_streak'] or 0 directly.

### `firebase/firestore.rules`

**#317** Line 35: user_plants create rule does not validate that is_public is a boolean and does not constrain other fields, allowing clients to set arbitrary fields including server-managed ones.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Firestore rules: validate request.resource.data fields on create
- **Suggested fix:** Add `&& request.resource.data.is_public is bool` and a hasOnly() field whitelist

**#318** Line 59: sync_queue create rule only requires isAuthenticated() and does not enforce request.resource.data.user_id == request.auth.uid — any authenticated user can enqueue sync jobs attributed to another user (or with arbitrary user_id) which will then be processed by Cloud Functions as if owned by that user.

- **Reviewer:** security-reviewer
- **Rule:** firebase/docs/patterns/firestore-rules.md — write-time user_id binding
- **Suggested fix:** Change to 'allow create: if isAuthenticated() && request.resource.data.user_id == request.auth.uid;'.

### `firebase/storage.rules`

**#319** Line 14: isImage() matches the entire image/* family including image/svg+xml — SVG is an XSS/script vector when later rendered in a browser context, bypassing the intent of the upload allowlist.

- **Reviewer:** security-reviewer
- **Rule:** security/file-upload.md — Layer 2 MIME whitelist (jpeg/png/webp/heic only)
- **Suggested fix:** Replace regex with explicit list: contentType in ['image/jpeg','image/png','image/webp','image/heic'].

**#320** Line 24: plant-identifications images allow read by any authenticated user regardless of ownership, leaking private plant photos across accounts.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Storage rules: private user content must restrict read to isOwner(userId)
- **Suggested fix:** Change to `allow read: if isOwner(userId);` (or gate on a public flag in Firestore)

**#321** Line 24: Any authenticated user can read every other user's plant identification images — read rule only checks isAuthenticated(), not ownership, leaking private uploads across all users.

- **Reviewer:** security-reviewer
- **Rule:** firebase/docs/patterns/firestore-rules.md — least-privilege reads
- **Suggested fix:** Replace 'allow read: if isAuthenticated()' with 'allow read: if isOwner(userId)' to scope reads to the uploading user.

**#322** Line 33: disease-diagnoses images readable by any authenticated user, exposing potentially sensitive plant health photos to all signed-in accounts.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Storage rules: private user content must restrict read to isOwner(userId)
- **Suggested fix:** Change to `allow read: if isOwner(userId);`

**#323** Line 33: Disease diagnosis images are readable by any authenticated user — leaks potentially sensitive health-adjacent imagery to the entire user base.

- **Reviewer:** security-reviewer
- **Rule:** firebase/docs/patterns/firestore-rules.md — least-privilege reads
- **Suggested fix:** Tighten to 'allow read: if isOwner(userId)'; disease imagery should never be cross-user readable.

**#324** Line 42: user-plants images readable by any authenticated user, conflicting with the Firestore is_public gating on user_plants documents.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Storage rules: must mirror Firestore is_public semantics or restrict to owner
- **Suggested fix:** Restrict to `isOwner(userId)` (Storage cannot easily read Firestore is_public — use a /public/ subpath for public images instead)

**#325** Line 42: User plant photos are readable by any authenticated user even when the owning Firestore user_plants document has is_public == false — Storage rules do not honour the Firestore privacy flag.

- **Reviewer:** security-reviewer
- **Rule:** firebase/docs/patterns/firestore-rules.md — cross-service consistency
- **Suggested fix:** Default to 'allow read: if isOwner(userId)' and add an explicit public path (e.g. /user-plants-public/{userId}/{imageId}) for opted-in shares, or use firestore.exists() with a public flag.

### `plant_community_mobile/lib/services/api_service.dart`

**#326** Line 177: _dio.fetch(requestOptions) reuses the original RequestOptions including any consumed FormData/streamed body, which fails on multipart uploads (fromFile streams) and on bodies already read once; retries of multipart uploads will throw rather than succeed.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Retry safety — non-replayable bodies cannot be retried
- **Suggested fix:** Skip retry when requestOptions.data is FormData/streamed, or rebuild the request body before invoking _dio.fetch.

### `plant_community_mobile/lib/services/firebase_storage_service.dart`

**#327** Line 11: Provider declared with manual NotifierProvider constructor instead of the project-standard @riverpod annotation, bypassing the code-gen convention used elsewhere in the codebase.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Riverpod 3.x — new providers must use Notifier class with @riverpod annotation
- **Suggested fix:** Annotate FirebaseStorageService with @riverpod and add `part 'firebase_storage_service.g.dart';` so the provider is generated; remove the manual NotifierProvider declaration.

**#328** Line 27: FirebaseStorageService extends Notifier but uses a custom constructor with parameters (storage, uuid); Riverpod's NotifierProvider always invokes the no-arg constructor via FirebaseStorageService.new, so the storage/uuid injection points are unreachable in production and only function in tests that bypass the provider.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Riverpod 3.x — Notifier subclasses must rely on ref-based DI, not constructor args
- **Suggested fix:** Inject FirebaseStorage / Uuid via ref.read of dedicated overridable providers instead of constructor parameters.

**#329** Line 66: Upload path 'plant_images/$imageId$extension' has no user UID segment, so storage.rules cannot scope writes/reads to the owning user — anyone authenticated could potentially write to this bucket if rules use a permissive pattern.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** flutter-firebase-reviewer: Read storage.rules to verify the upload path is permitted for the user's auth state
- **Suggested fix:** Use 'plant_images/{uid}/$imageId$extension' so rules can enforce request.auth.uid == uid for writes.

**#330** Line 75: uploadTask.snapshotEvents.listen() returns a StreamSubscription that is never stored or cancelled, leaking the listener if the upload errors or the caller is disposed mid-upload.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** flutter-firebase-reviewer: Storage upload TaskSnapshot streams must be cancelled on dispose
- **Suggested fix:** Capture the subscription, cancel it in a finally block after await uploadTask, and also cancel on FirebaseException.

### `plant_community_mobile/lib/services/plant_identification_service.dart`

**#331** Line 10: Provider declared with manual NotifierProvider constructor instead of the @riverpod annotation pattern used by the rest of the project.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Riverpod 3.x — new providers must use Notifier class with @riverpod annotation
- **Suggested fix:** Convert PlantIdentificationService to use @riverpod with a generated *.g.dart part file.

**#332** Line 17: PlantIdentificationService extends Notifier but takes a Uuid via constructor; the manual NotifierProvider uses the no-arg `.new` tear-off, so the injected Uuid is always the default and the parameter is dead code outside direct instantiation.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Riverpod 3.x — Notifier subclasses must rely on ref-based DI, not constructor args
- **Suggested fix:** Drop the constructor parameter and read a `uuidProvider` (override-able in tests) inside the methods that need it.

### `web/src/components/diagnosis/StreamFieldEditor.tsx`

**#333** Line 33: handleValueChange parameter newValue has implicit any (no type annotation) — violates TypeScript discipline.

- **Reviewer:** react-typescript-reviewer
- **Rule:** no-implicit-any
- **Suggested fix:** Type as `(newValue: DiagnosisBlock['value']) => void` or `unknown`.

**#334** Line 272: ListEditor component props (items, onChange) are completely untyped — implicit any for both, plus implicit any in updateItem(index, value) and deleteItem(index).

- **Reviewer:** react-typescript-reviewer
- **Rule:** explicit-prop-interface
- **Suggested fix:** Add interface ListEditorProps { items: string[]; onChange: (items: string[]) => void }.

**#335** Line 322: BlockControls component props (onDelete, onMoveUp, onMoveDown, isFirst, isLast) are untyped — implicit any.

- **Reviewer:** react-typescript-reviewer
- **Rule:** explicit-prop-interface
- **Suggested fix:** Define BlockControlsProps interface mirroring the usage.

**#336** Line 361: Default-export StreamFieldEditor has no prop interface; value/onChange/readOnly are implicit any — main component lacks any type safety.

- **Reviewer:** react-typescript-reviewer
- **Rule:** explicit-prop-interface
- **Suggested fix:** Add StreamFieldEditorProps with value: DiagnosisBlock[], onChange: (blocks: DiagnosisBlock[]) => void, readOnly?: boolean.

### `web/src/contexts/RequestContext.test.tsx`

**#337** Line 239: Test sets global.crypto = undefined but the afterEach restores via Object.defineProperty with `if (originalCrypto)`; subsequent beforeEach (line 32) calls Object.defineProperty(global.crypto, 'randomUUID', ...) which throws TypeError when global.crypto is undefined, creating order-dependent test failures.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-isolation
- **Suggested fix:** In afterEach, unconditionally restore global.crypto via Object.defineProperty(global, 'crypto', { value: originalCrypto, ... }) before any other restoration runs.

---

## 🟡 Medium (427)

### `backend/apps/blog/admin_views.py`

**#338** Line 42: Dashboard recent_posts/recent_comments/popular_posts have no prefetch_related for fields rendered in templates — N+1 in admin dashboard.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author') and prefetch as needed.

**#339** Line 89: Magic number Paginator(comments, 20) — page size hardcoded; should come from constants.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality / constants
- **Suggested fix:** Use a constant from blog.constants for admin pagination size.

**#340** Line 144: Featured/recent posts querysets lack select_related('author') and prefetch_related('categories') — likely N+1 in admin templates.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Add select_related('owner','author') and prefetch_related('categories','tags') for admin list pages.

**#341** Line 144: featured/recent posts queries lack select_related/prefetch_related — admin listings hit N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author') and prefetch_related('categories').

**#342** Line 185: post.comments.order_by('-created_at') without select_related('author') — N+1 in template rendering of paginated comments.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author','post').

**#343** Line 217: ai_content_suggestions accepts POST but is decorated only with @staff_member_required — no rate limiting on AI endpoint; could be abused by staff to drive cost.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/rate-limiting.md
- **Suggested fix:** Apply AIRateLimiter to this view.

**#344** Line 266: blog_search posts/comments/categories queries have no select_related/prefetch_related — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related/prefetch_related and use icontains escaping.

**#345** Line 281: BlogComment search results returned without select_related on author/post for template rendering — N+1 risk.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Add .select_related('author','post').

**#346** Line 372: Export endpoint accepts CSV format from format_type but only handles JSON branches — CSV path returns 400 silently; may also leak internal errors.

- **Reviewer:** django-drf-reviewer
- **Rule:** API Design / error shapes
- **Suggested fix:** Implement CSV export or explicitly reject unknown formats with a clear message.

**#347** Line 376: Export endpoint lacks select_related/prefetch_related for serializer FK access — could be O(N) extra queries on large exports.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Add appropriate prefetch_related/select_related calls for the serializer fields.

### `backend/apps/blog/api/endpoints.py`

**#348** Line 31: BlogSeriesAPIViewSet body_fields/listing_default_fields reference 'cover_image' but model field is 'image'.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Rename serializer field to match model 'image' or remove cover_image from body_fields.

### `backend/apps/blog/api/serializers.py`

**#349** Line 49: get_url runs BlogCategoryPage.objects.filter(category=obj).live().first() per category - N+1.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Pre-fetch category->category_page map and pass via serializer context.

**#350** Line 80: BlogSeriesSerializer.get_posts_url builds a hardcoded /api/v2/pages/?... URL (Wagtail legacy v2) instead of using reverse() or a versioned route.

- **Reviewer:** api-design-reviewer
- **Rule:** Versioning + maintainability
- **Suggested fix:** Use reverse('wagtailapi_v2:pages:listing') with query params, or expose a constant for the API root.

**#351** Line 265: Fallback get_related_posts runs BlogPostPage.objects.live().public()...exclude/filter per post when prefetch flag missing — can hit N+1 in list contexts.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Avoid using BlogPostPageSerializer in list contexts, or guard the fallback with self.context['view'].action != 'list'.

**#352** Line 292: _get_author_page_url runs BlogAuthorPage.objects.filter(author=author).live().first() per post - N+1.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Prefetch author pages in viewset and pass via serializer context.

**#353** Line 307: _get_post_image calls get_rendition('fill-300x200') for each related_post; renditions not prefetched.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** prefetch_renditions('fill-300x200') on related_posts Prefetch.

### `backend/apps/blog/api/viewsets.py`

**#354** Line 178: Image.prefetch_renditions on featured_image (a ForeignKey, not reverse relation) may not behave as intended; verify it is actually prefetching renditions.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Confirm Wagtail-supported pattern — typically prefetch_renditions on a queryset of images.

**#355** Line 209: Detail prefetch loops over categories then prefetches blogpostpage_set with .live().public()[:3]; slicing inside Prefetch may not slice per-parent correctly — risk of fetching all posts per category.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use Subquery/window-function to limit, or accept per-category fetch with caching.

**#356** Line 278: Custom @action endpoint featured lacks @extend_schema annotation, so OpenAPI/Swagger docs do not describe it.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema: new endpoints must have @extend_schema
- **Suggested fix:** Add @extend_schema with response serializer and description.

**#357** Line 288: Custom @action endpoint recent lacks @extend_schema; query params and response shape are not documented in OpenAPI.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema: new endpoints must have @extend_schema
- **Suggested fix:** Add @extend_schema with parameters=[OpenApiParameter('limit', int)] and response serializer.

**#358** Line 299: Custom @action popular lacks @extend_schema; limit/days parameters are only described in the docstring, not in the OpenAPI schema.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema: new endpoints must have @extend_schema
- **Suggested fix:** Decorate with @extend_schema declaring query params and BlogPostPageListSerializer(many=True) response.

**#359** Line 387: Custom @action by_category returns an undeclared ad-hoc dict shape with no @extend_schema and no serializer class.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema: new endpoints must have @extend_schema
- **Suggested fix:** Define an inline OpenAPI response or a dedicated serializer and decorate the action.

**#360** Line 410: Custom @action search_suggestions lacks @extend_schema; q query param and response shape (list of {type,text}) are not documented.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema: new endpoints must have @extend_schema
- **Suggested fix:** Add @extend_schema with q parameter and a typed response.

**#361** Line 421: search_suggestions uses title__icontains and Tag name__icontains without GIN/trigram index — slow on large datasets.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md GIN indexes
- **Suggested fix:** Add pg_trgm GIN index on BlogPostPage.title and Tag.name, or use Wagtail search backend.

**#362** Line 436: Custom @action related lacks @extend_schema and uses pk=None integer lookup while the rest of the project uses UUID-keyed APIs.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema + UUID Endpoints checklist
- **Suggested fix:** Annotate with @extend_schema and consider migrating to UUID lookup.

**#363** Line 641: RSS/Atom @action endpoints rss and atom lack @extend_schema and return non-RSS JSON despite advertising format='rss'/'atom'.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema + API contract clarity
- **Suggested fix:** Either return real application/rss+xml or document the JSON envelope explicitly with @extend_schema.

### `backend/apps/blog/api_views.py`

**#364** Line 147: PlantSpecies.objects.filter(scientific_name__icontains=query) and common_names__icontains queries lack GIN/trigram indexes.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md GIN indexes
- **Suggested fix:** Add pg_trgm GIN index on PlantSpecies.scientific_name and common_names.

### `backend/apps/blog/management/commands/migrate_care_guides_to_blog.py`

**#365** Line 124: Bare except Exception swallows migration errors per-guide; combined with transaction.atomic() this can leave partial state.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality
- **Suggested fix:** Catch specific exceptions or always raise CommandError to abort the atomic block.

### `backend/apps/blog/middleware.py`

**#366** Line 97: Calls private method SecurityMonitor._get_client_ip() (leading underscore) — relies on internal API that may break without notice.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/services.md
- **Suggested fix:** Promote to a public helper (e.g., get_client_ip) in apps.core.security or use a dedicated utility module.

**#367** Line 132: Logging total_views=page.view_count + 1 reads stale page.view_count (the F() update has not refreshed the in-memory instance).

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Either refresh_from_db() or remove the count from the log line.

### `backend/apps/blog/models.py`

**#368** Line 410: BlogIndexPage.get_context blog_posts queryset has no select_related/prefetch_related — Wagtail template rendering hits N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related('author') and prefetch_related('categories','tags','featured_image').

**#369** Line 410: BlogIndexPage.get_context: blog_posts queryset has no select_related/prefetch_related.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Add select_related('author') + prefetch_related('categories','tags').

**#370** Line 467: BlogCategoryPage.get_context blog_posts queryset has no select_related/prefetch_related — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related/prefetch_related.

**#371** Line 467: BlogCategoryPage.get_context: queryset lacks select_related/prefetch_related.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Add select_related/prefetch_related.

**#372** Line 532: BlogAuthorPage.get_context blog_posts queryset has no select_related/prefetch_related — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Add select_related/prefetch_related.

**#373** Line 532: BlogAuthorPage.get_context: posts query has no select_related/prefetch_related.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Add select_related/prefetch_related.

**#374** Line 747: BlogPostPage.get_context related_posts queryset lacks select_related/prefetch_related.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Append select_related('author').prefetch_related('categories','tags').

### `backend/apps/blog/serializers.py`

**#375** Line 62: BlogSeriesSerializer.get_posts_url hardcodes /api/blog/series/{slug}/posts/ — unversioned legacy path with no /v1/ prefix and no documented deprecation.

- **Reviewer:** api-design-reviewer
- **Rule:** Versioning: all new endpoints must be under /api/v1/
- **Suggested fix:** Use a reverse() to a v1 route or note the legacy path in OpenAPI deprecation.

**#376** Line 118: BlogCommentSerializer exposes post as writable while only marking author/is_approved/timestamps read-only; combined with parent being writable this allows clients to spoof which post a comment belongs to.

- **Reviewer:** api-design-reviewer
- **Rule:** Serializers: write_only/read_only correctness
- **Suggested fix:** Move post to read_only_fields and supply it from the URL context in the view.

### `backend/apps/blog/services/ai_cache_service.py`

**#377** Line 42: CACHE_TTL = 2_592_000 (30 days) hardcoded — magic number that belongs in constants.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality / constants
- **Suggested fix:** Move to constants.py (e.g. AI_CACHE_TTL = 2_592_000).

### `backend/apps/blog/services/ai_rate_limiter.py`

**#378** Line 39: Magic numbers USER_LIMIT=10, GLOBAL_LIMIT=100, STAFF_LIMIT=50, TTL=3600 hardcoded as class attributes — should live in apps/blog/constants.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality / constants
- **Suggested fix:** Move to constants.py and import.

**#379** Line 60: Cache key ai_rate_limit:user:{user_id} does not follow app:feature:scope:identifier format — missing app prefix blog:.

- **Reviewer:** django-drf-reviewer
- **Rule:** architecture/caching.md
- **Suggested fix:** Use 'blog:ai:rate_limit:user:{user_id}'.

### `backend/apps/blog/services/plant_data_lookup_service.py`

**#380** Line 47: Magic number self.fuzzy_match_threshold = 85 hardcoded — should be a constant in constants.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality / constants
- **Suggested fix:** Move to FUZZY_MATCH_THRESHOLD in constants.py.

**#381** Line 49: Service method lookup_plant_data lacks type hint on user parameter.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality / type hints
- **Suggested fix:** Annotate user: Optional['User'] = None and tighten return type to a TypedDict or dataclass.

**#382** Line 70: Logger uses unbracketed prefix; project requires bracketed prefixes like [SERVICE], [CACHE], [PERF].

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality / logging
- **Suggested fix:** Use logger.info('[PLANT_LOOKUP] Found exact match...').

**#383** Line 170: _search_user_history loops user_requests then filters identification_results — prefetch_related doesn't apply the is_accepted filter, query per request — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use Prefetch('identification_results', queryset=PlantIdentificationResult.objects.filter(is_accepted=True)).

### `backend/apps/blog/signals.py`

**#384** Line 105: post_delete receiver registers without sender=BlogPostPage.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Use @receiver(post_delete, sender=BlogPostPage).

### `backend/apps/blog/tests/test_analytics.py`

**#385** Line 461: test_popular_posts_recent_views asserts only len > 0; never asserts ordering correctness despite testing recency.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: assertions must match intent
- **Suggested fix:** Assert ordering: posts[4] ranks higher than posts[0].

**#386** Line 522: test_popular_posts_query_optimization uses assertLessEqual(query_count, 30) instead of strict equality; loose bound cannot detect regression.

- **Reviewer:** test-quality-reviewer
- **Rule:** patterns/performance/query-optimization.md (strict equality)
- **Suggested fix:** Convert to assertEqual once N+1 is fixed.

**#387** Line 545: test_popular_posts_all_time_query_count uses assertLessEqual(query_count, 30); loose-bound issue.

- **Reviewer:** test-quality-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Tighten to strict equality.

### `backend/apps/blog/tests/test_blog_cache_service.py`

**#388** Line 195: test_invalidate_blog_category_removes_all_pages contains no assertion — comment explicitly states 'we don't assert here'.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: every test must assert
- **Suggested fix:** Assert that pages are None after invalidation.

**#389** Line 237: test_cache_clear_all_removes_all_blog_caches has no assertion on actual clearing behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: every test must assert
- **Suggested fix:** Assert posts are None after clear_all_blog_caches() on Redis backend.

### `backend/apps/blog/tests/test_blog_signals.py`

**#390** Line 197: test_signal_logs_cache_invalidation has no assertions — the test cannot fail.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: every test must assert
- **Suggested fix:** Assert mock_logger.info/debug was called or delete the test.

### `backend/apps/blog/tests/test_blog_viewsets_caching.py`

**#391** Line 147: test_list_cache_hit_logs_performance asserts on logger.info call args — couples test to log message format rather than caching behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: avoid testing implementation details
- **Suggested fix:** Assert behavior (DB query count drops to 0) instead of log content.

**#392** Line 192: test_retrieve_cache_hit_logs_performance similarly tests logger output rather than cache hit behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: avoid testing implementation details
- **Suggested fix:** Behavioral assertion (no DB queries on second call).

### `backend/apps/blog/tests/test_csp_nonces.py`

**#393** Line 64: test_blog_post_template_syntax silently passes when the template file is missing.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: tests must fail when subject is absent
- **Suggested fix:** Use self.fail or self.skipTest in else branch.

**#394** Line 84: test_admin_base_template_syntax silently passes when the template file is missing.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality: tests must fail when subject is absent
- **Suggested fix:** Use self.fail or self.skipTest when path does not exist.

### `backend/apps/blog/views.py`

**#395** Line 49: BlogPostPageViewSet duplicates much of the Wagtail API viewset.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Consolidate or mark legacy/internal.

**#396** Line 121: BlogPostPageViewSet.related lacks select_related/prefetch_related - N+1 in serializer.

- **Reviewer:** wagtail-reviewer
- **Rule:** docs/patterns/performance/query-optimization.md
- **Suggested fix:** Use self.get_queryset() or add explicit select_related/prefetch_related.

**#397** Line 144: comments action prefetches 'replies' but BlogCommentSerializer.get_replies calls obj.get_replies() which re-filters by is_approved — prefetch is wasted and an extra query fires per top-level comment (N+1).

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use Prefetch('replies', queryset=BlogComment.objects.filter(is_approved=True).select_related('author'), to_attr='approved_replies').

### `backend/apps/blog/wagtail_ai_integration.py`

**#398** Line 17: Imports django.contrib.auth.models.User but project uses custom AUTH_USER_MODEL='users.User'; unused.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Remove unused User import or use get_user_model().

**#399** Line 119: _determine_feature_type uses fragile substring heuristics on prompt text to derive cache feature key.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Pass feature/field name explicitly through kwargs.

### `backend/apps/blog/wagtail_ai_v3_integration.py`

**#400** Line 192: Cached path returns hand-built duck-typed CompletionResponse; fragile.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Use library's response dataclass or a small dedicated class.

**#401** Line 217: On rate-limit, returns faked CompletionResponse with error string instead of raising; caller cannot distinguish error from valid output.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Raise Ratelimited/PermissionDenied exception instead.

**#402** Line 327: cached_get_llm_service unconditionally creates CachedLLMService with user=None - per-user tier rate limits effectively disabled.

- **Reviewer:** wagtail-reviewer
- **Rule:** Wagtail AI 3.0 - rate limits 10/50/100 per tier
- **Suggested fix:** Thread user/request via thread-local or rate-limit at agent/view layer.

### `backend/apps/blog/wagtail_hooks.py`

**#403** Line 141: construct_homepage_summary_items issues separate count queries on each admin homepage request — duplicates queries.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Share/cache counts across hooks.

### `backend/apps/core/exceptions.py`

**#404** Line 76: Hardcoded Retry-After value '3600' assumes upload rate-limit window for ALL 429s.

- **Reviewer:** django-drf-reviewer
- **Rule:** Correctness
- **Suggested fix:** Compute Retry-After from actual rate limit window.

### `backend/apps/core/middleware.py`

**#405** Line 119: Cache key 'rate_limit_violations:{user_id}:{ip_address}' missing app prefix.

- **Reviewer:** django-drf-reviewer
- **Rule:** Cache key format
- **Suggested fix:** Use 'core:rate_limit_violations:{user_id}:{ip_address}'.

**#406** Line 137: RateLimitMonitoringMiddleware uses cache.get/cache.set on a Python list per 429 response.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Use Redis INCR with EXPIRE keyed by user/ip.

**#407** Line 277: Cache key 'security_metrics:{endpoint}:{method}' missing app prefix.

- **Reviewer:** django-drf-reviewer
- **Rule:** Cache key format
- **Suggested fix:** Use 'core:security_metrics:{endpoint}:{method}'.

**#408** Line 297: isinstance(metrics['unique_ips'], set) is only true on first call — afterwards cache returns a list.

- **Reviewer:** django-drf-reviewer
- **Rule:** Correctness
- **Suggested fix:** Always treat cached value as list and convert to set when manipulating.

**#409** Line 307: Magic number 86400 hardcoded.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Add SECURITY_METRICS_RETENTION_SECONDS constant.

**#410** Line 310: Magic number 5.0 (slow request threshold) hardcoded.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Add SLOW_REQUEST_THRESHOLD_SECONDS constant.

### `backend/apps/core/models.py`

**#411** Line 1: Core app exposes user-linked models but has no auditlog.py to register them for GDPR compliance.

- **Reviewer:** django-drf-reviewer
- **Rule:** New apps must register models in auditlog.py
- **Suggested fix:** Add backend/apps/core/auditlog.py and register user-linked models.

### `backend/apps/core/sanitizers.py`

**#412** Line 89: Sensitive-field substring matching ('auth', 'key') will incorrectly redact innocuous fields like 'author' or 'monkey'.

- **Reviewer:** django-drf-reviewer
- **Rule:** Input sanitization correctness
- **Suggested fix:** Use word-boundary regex or exact-match list.

**#413** Line 89: _sanitize_dict recomputes [f.lower() for f in cls.REMOVE_FIELDS] on every key for every dict during recursive sanitization.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Precompute REMOVE_FIELDS_LOWER / MASK_FIELDS_LOWER as frozensets at class level.

**#414** Line 115: _sanitize_string compiles SQL/XSS regex patterns on every call instead of using precompiled patterns.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Precompile SUSPICIOUS_SQL_PATTERNS and SUSPICIOUS_XSS_PATTERNS as module-level re.compile lists.

**#415** Line 186: _is_sensitive_field re-runs re.search per pattern per field name without compilation.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Compile SENSITIVE_PATTERNS once and combine into a single alternation regex.

### `backend/apps/core/security.py`

**#416** Line 72: SUSPICIOUS_ACTIVITY_THRESHOLD/TIME hardcoded inside class while constants.py defines them.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Import from constants.

**#417** Line 363: track_failed_login, _check_suspicious_login, track_file_upload, track_validation_failure, check_rate_limit all use list-rewrite cache patterns.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Switch counters to atomic INCR + EXPIRE.

**#418** Line 409: Cache key 'login_frequency:{user.id}' missing app prefix.

- **Reviewer:** django-drf-reviewer
- **Rule:** Cache key format — caching.md
- **Suggested fix:** Use 'security:login_frequency:{user_id}'.

**#419** Line 415: Magic number 3600 (login frequency window) hardcoded.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Define LOGIN_FREQUENCY_WINDOW constant.

**#420** Line 422: Magic number 10 for login-frequency threshold.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Add LOGIN_FREQUENCY_THRESHOLD constant.

**#421** Line 453: Magic number 60 (rate-limit window) hardcoded.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Use API_RATE_LIMIT_WINDOW constant.

**#422** Line 460: Magic number 30 (high frequency threshold) hardcoded.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Use API_RATE_LIMIT_MAX_REQUESTS constant.

**#423** Line 493: Cache key 'failed_uploads:{user_id}' missing app prefix.

- **Reviewer:** django-drf-reviewer
- **Rule:** Cache key format
- **Suggested fix:** Use 'security:failed_uploads:{user_id}'.

**#424** Line 498: Magic number 3600 hardcoded; UPLOAD_FAILURE_WINDOW exists.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Use UPLOAD_FAILURE_WINDOW constant.

**#425** Line 509: Magic number 20 hardcoded; MAX_UPLOAD_FAILURES_PER_HOUR exists.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Use MAX_UPLOAD_FAILURES_PER_HOUR constant.

**#426** Line 541: Cache key 'validation_failures:{user_id}' missing app prefix.

- **Reviewer:** django-drf-reviewer
- **Rule:** Cache key format
- **Suggested fix:** Use 'security:validation_failures:{user_id}'.

**#427** Line 546: Magic number 3600 hardcoded; VALIDATION_FAILURE_WINDOW exists.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Use VALIDATION_FAILURE_WINDOW constant.

**#428** Line 558: Magic number 50 hardcoded; MAX_VALIDATION_FAILURES_PER_HOUR exists.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Use MAX_VALIDATION_FAILURES_PER_HOUR constant.

**#429** Line 591: Cache key 'security_alert:{alert_type}:{ts}' inconsistent with documented convention.

- **Reviewer:** django-drf-reviewer
- **Rule:** Cache key format
- **Suggested fix:** Use 'core:security_alert:{alert_type}:{ts}'.

**#430** Line 592: Magic number 86400 (24h alert retention) hardcoded.

- **Reviewer:** django-drf-reviewer
- **Rule:** No magic numbers
- **Suggested fix:** Add SECURITY_ALERT_RETENTION_SECONDS constant.

**#431** Line 763: Cache key 'rate_limit:{user_id}:{action}' missing app prefix.

- **Reviewer:** django-drf-reviewer
- **Rule:** Cache key format
- **Suggested fix:** Use 'core:rate_limit:{user_id}:{action}'.

### `backend/apps/core/services/email_service.py`

**#432** Line 168: Type hint uses 'callable' (built-in) instead of typing.Callable; lacks parameter/return signature.

- **Reviewer:** django-drf-reviewer
- **Rule:** Type hints
- **Suggested fix:** Use Callable[[Union[str, User]], Dict[str, Any]].

**#433** Line 313: Per-email INSERT into EmailNotification inside send_bulk_email loop — N+1 writes.

- **Reviewer:** django-drf-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Collect notifications and bulk_create after the loop.

**#434** Line 313: EmailNotification.objects.create() called once per email send; bulk runs should use bulk_create.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Aggregate EmailNotification rows and persist with bulk_create.

**#435** Line 323: except (ImportError, Exception) — Exception subsumes ImportError.

- **Reviewer:** django-drf-reviewer
- **Rule:** Exception handling
- **Suggested fix:** Catch specific exceptions or remove redundant ImportError.

### `backend/apps/core/services/notification_service.py`

**#436** Line 55: schedule_for typed as Optional[timezone.datetime] — incorrect type.

- **Reviewer:** django-drf-reviewer
- **Rule:** Type hints
- **Suggested fix:** Use Optional[datetime.datetime] from datetime module.

**#437** Line 152: _send_in_app_notification does User.objects.get(email=recipient) per call; from a loop becomes N+1.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Resolve users in bulk before iteration.

**#438** Line 178: Same incorrect timezone.datetime annotation in _schedule_notification.

- **Reviewer:** django-drf-reviewer
- **Rule:** Type hints
- **Suggested fix:** Use datetime.datetime.

**#439** Line 348: hasattr(user, 'newsletter_subscription') triggers an extra query per user — N+1 in any list/admin view.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md
- **Suggested fix:** Annotate Exists(NewsletterSubscription.objects.filter(user=OuterRef('pk'))).

**#440** Line 367: user.save() in update_user_notification_preferences saves all fields — racy with concurrent updates.

- **Reviewer:** django-drf-reviewer
- **Rule:** Performance / concurrency
- **Suggested fix:** Use update_fields=[...] limited to mutated preference fields.

### `backend/apps/core/tests/test_csrf_meta_tag.py`

**#441** Line 67: test_csrf_cookie_set_with_httponly never actually verifies the HttpOnly flag on the cookie - the comment admits this and falls back to re-checking settings.CSRF_COOKIE_HTTPONLY (already covered by test_csrf_cookie_httponly_is_true). The test name is misleading.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion-quality
- **Suggested fix:** Inspect response.cookies['csrftoken']['httponly'] directly (Django SimpleCookie exposes morsels) to actually verify the flag, or remove this duplicate test.

**#442** Line 173: test_csrf_cookie_secure_in_production only asserts the setting is a bool, not that it has the documented value `not DEBUG`. The docstring says it verifies production-correct behaviour but the assertion is vacuous - any bool passes including a hardcoded False.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion-quality
- **Suggested fix:** Use override_settings(DEBUG=True/False) and reload settings, or directly assert `settings.CSRF_COOKIE_SECURE == (not settings.DEBUG)` to actually validate the documented relationship.

### `backend/apps/forum/models.py`

**#443** Line 798: Magic string 'helpful' for reaction_type in update_helpful_count — REACTION_HELPFUL constant exists in constants.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** Import REACTION_HELPFUL and use it in the filter.

**#444** Line 813: Magic string 'expert' used in calculate_trust_level instead of TRUST_LEVEL_EXPERT constant; same file already imports the constant.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** if self.trust_level == TRUST_LEVEL_EXPERT: return TRUST_LEVEL_EXPERT.

**#445** Line 820: Hard-coded list ['veteran', 'trusted', 'basic', 'new'] for trust-level iteration; should use the trust-level constants for consistency.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** for level in [TRUST_LEVEL_VETERAN, TRUST_LEVEL_TRUSTED, TRUST_LEVEL_BASIC, TRUST_LEVEL_NEW]:

### `backend/apps/forum/serializers/reaction_serializer.py`

**#446** Line 156: ReactionAggregateSerializer.get_aggregate_data fetches all active reactions and counts in Python, then issues an additional .filter(user=user).values_list query — should aggregate counts at the database level.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md — Count() annotations over Python loops
- **Suggested fix:** Use post.reactions.filter(is_active=True).aggregate(like=Count('id', filter=Q(reaction_type='like')), ...) and a single distinct values_list for user_reactions.

### `backend/apps/forum/services/spam_detection_service.py`

**#447** Line 132: Duplicate-content check loads all of the user's recent posts/threads into memory and runs SequenceMatcher().ratio() (O(n*m)) per item in Python; for prolific users this can exceed the documented '<50ms per check' target.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Limit recent_items via .order_by['-created_at'](:N), short-circuit on length mismatch, or use pg_trgm trigram_similarity for DB-side fuzzy match.

### `backend/apps/forum/tests.py`

**#448** Line 1: Forum app has no assertNumQueries-based performance test coverage — list views with annotations and prefetches need strict equality assertions to catch regressions (only one assertEqual on query result count was found across the test suite).

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer checklist — strict performance assertions
- **Suggested fix:** Add assertNumQueries(N) tests for ThreadViewSet list, PostViewSet list (with reactions), CategoryViewSet list, and ModerationQueueViewSet list, with docstrings citing the expected query count and rationale.

### `backend/apps/forum/tests/test_cache_integration.py`

**#449** Line 410: test_thread_list_cache_invalidation has no assertion verifying caches were cleared after invalidate_thread_lists() — only sets caches and calls the method, leaving behavior unverified.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Add self.assertIsNone(cache.get('forum:list:page1')) etc. after invalidation to confirm wildcard deletion worked.

### `backend/apps/forum/tests/test_post_performance.py`

**#450** Line 105: Performance test docstring states 'Without optimization: 41+ queries...With optimization: 3 queries', but the strict count of 3 has no margin for legitimate auth/middleware queries that may run; if middleware adds a query the test will fail unrelatedly.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Document that the override_settings MIDDLEWARE list is what makes 3 the exact count, and ensure middleware list is kept in sync.

### `backend/apps/forum/tests/test_post_transaction_boundaries.py`

**#451** Line 312: test_post_save_uses_transaction_atomic and test_implementation_matches_recommended_pattern use inspect.getsource string matching to verify implementation; this is brittle and tests source text, not behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Replace with behavior-based concurrency tests (or rely on existing F-expression SQL inspection) rather than asserting source text.

### `backend/apps/forum/tests/test_post_viewset.py`

**#452** Line 25: Spam detection is mocked for the entire PostViewSet test class, but spam detection is a domain service whose integration with the viewset is meaningful; class-wide mocking risks masking real issues.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Keep the class-wide mock for content tests but ensure dedicated test_spam_detection.py covers the un-mocked viewset path (it does).

**#453** Line 299: test_delete_post_soft_deletes bundles two unrelated assertions (permission failure for non-author + successful soft delete for author), violating the one-concept-per-test rule.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Split into test_delete_post_denied_for_non_author and test_delete_post_soft_deletes_for_author.

### `backend/apps/forum/tests/test_rate_limiting.py`

**#454** Line 281: Reaction rate-limit tests create 600 posts in setUp() to feed the limit tests — large fixture cost runs for every test in the class even when only a fraction are needed.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Use bulk_create or move the 600-post creation into the specific test that needs them.

### `backend/apps/forum/tests/test_user_profile_viewset.py`

**#455** Line 80: test_list_profiles_default_ordering relies on tied helpful_count/post_count ordering being deterministic; assertions assume expert/veteran are first, but expert and veteran do have unique values so this is acceptable — however test_new_members_default_limit (line 213) asserts ordering by created_at where multiple profiles may share timestamps in a fast setUp().

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Either explicitly stagger created_at in setUp or assert the set membership rather than positional order.

### `backend/apps/forum/viewsets/moderation_queue_viewset.py`

**#456** Line 92: status_filter from query param goes straight into queryset.filter(status=...) without verifying it is one of the allowed MODERATION_STATUSES; arbitrary unknown statuses silently return zero rows.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Validate against MODERATION_STATUSES choices and return 400 on invalid input.

**#457** Line 562: Q(Exists(expert_profiles)) wraps an Exists() inside Q() positionally — relies on Q accepting non-keyword expressions; intent is clearer with Q(pk__in=UserProfile.objects.filter(trust_level='expert').values('user_id')) and avoids fragile Q(Exists(...)) construction.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use a subquery on user_id instead of Q(Exists(...)).

**#458** Line 569: Magic string 'expert' for trust_level filter in dashboard endpoint; should use TRUST_LEVEL_EXPERT.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** Import TRUST_LEVEL_EXPERT and use it in the .filter().

**#459** Line 630: Unvalidated int() on the 'limit' query param in moderation_history.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Wrap in try/except returning 400.

**#460** Line 744: user_moderation_history runs flags_qs.count() twice (total_flags_count line 700 and total_flags line 744) plus four sequential .count() calls (lines 744-748) that can collapse into a single conditional Sum(Case(...)) aggregation — the same optimization already applied in moderation_stats/dashboard.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md — collapse repeat counts
- **Suggested fix:** Reuse total_flags_count, replace pending/approved/removed counts with one aggregate(Case-When-Sum) call and warnings_count with a single annotated query.

### `backend/apps/forum/viewsets/post_viewset.py`

**#461** Line 572: Pre-transaction MAX_ATTACHMENTS_PER_POST check is racey (TOCTOU) and is duplicated by the proper select_for_update guarded check at line 724; the pre-check is misleading.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/architecture/services.md
- **Suggested fix:** Remove the unguarded check at line 572 and rely solely on the locked check inside the transaction.

**#462** Line 783: delete_image performs a redundant inline author/moderator check; the @action permission_classes=[IsAuthorOrModerator] already covers this, and the inline check disagrees by treating any 'is_staff' user as a moderator without the permission class's safe-method bypass.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/architecture/viewsets.md
- **Suggested fix:** Remove the inline check; rely on permission_classes.

**#463** Line 927: Magic string 'pending' used for FlaggedContent.status filter instead of MODERATION_STATUS_PENDING constant.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** Use MODERATION_STATUS_PENDING from constants.py.

**#464** Line 940: Daily flag limit uses a 24-hour rolling window (timezone.now() - timedelta(days=1)) but the variable is named today_start; intent vs. behavior mismatch and not aligned with the @ratelimit '10/d' decorator on the same action.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/architecture/rate-limiting.md
- **Suggested fix:** Either drop the in-view counter and rely on @ratelimit, or compute today_start from now.replace(hour=0, ...).

**#465** Line 967: Magic string 'pending' passed for status when creating FlaggedContent — should reference MODERATION_STATUS_PENDING.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** Replace 'pending' with MODERATION_STATUS_PENDING constant.

### `backend/apps/forum/viewsets/thread_viewset.py`

**#466** Line 287: instance.refresh_from_db() with no fields argument refreshes every column after an F() update; if other fields were modified earlier in the request they will be silently overwritten.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use instance.refresh_from_db(fields=['view_count']) to limit the refresh.

**#467** Line 325: int(request.query_params.get('days', 7)) is unguarded — non-numeric ?days param yields HTTP 500.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Use try/except or DRF serializer validation.

**#468** Line 397: page_num and page_size are parsed via unguarded int() on user input; non-numeric values raise ValueError -> HTTP 500.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Validate inputs explicitly.

**#469** Line 461: Search action builds post_results without calling_annotate_reaction_counts, so PostSerializer.get_reaction_counts falls back to the Python-loop branch; the reactions prefetch is also unfiltered (no is_active=True), inflating loaded rows.

- **Reviewer:** performance-reviewer
- **Rule:** performance/query-optimization.md — annotate aggregates, filter prefetches
- **Suggested fix:** Apply self._annotate_reaction_counts(post_results) (extract helper to a mixin) and use Prefetch('reactions', queryset=Reaction.objects.filter(is_active=True)).

**#470** Line 558: Magic string 'pending' used for FlaggedContent.status; should use MODERATION_STATUS_PENDING constant.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** Replace literal with MODERATION_STATUS_PENDING.

**#471** Line 571: Same 24-hour-rolling vs. midnight-boundary mismatch in flag_thread; also missing @ratelimit decorator (post flag has '10/d' rate limit, thread flag does not).

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/architecture/rate-limiting.md
- **Suggested fix:** Add @method_decorator(ratelimit(key='user', rate='10/d', method='POST', block=True)) and rationalize the day-window definition.

**#472** Line 598: Magic string 'pending' passed for status when creating FlaggedContent on flag_thread.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md (no magic numbers/strings)
- **Suggested fix:** Use MODERATION_STATUS_PENDING constant.

### `backend/apps/forum/viewsets/user_profile_viewset.py`

**#473** Line 93: int(request.query_params.get('limit', 10)) is unguarded — a non-numeric ?limit=foo raises ValueError and returns HTTP 500.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Wrap in try/except or use serializers.IntegerField(min_value=1, max_value=100) to validate.

**#474** Line 114: Same unguarded int() conversion of the limit query param in most_helpful action.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Validate limit input.

**#475** Line 158: Same unguarded int() conversion of the limit query param in new_members action.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Validate limit input.

### `backend/apps/forum_integration/api_views.py`

**#476** Line 105: all_topics_list catches Exception and returns str(e); this leaks internal details and the function lacks any permission_classes/auth (it is a plain Django function view).

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF error handling
- **Suggested fix:** Convert to a DRF view with explicit permissions and a sanitized error response.

**#477** Line 218: forum_search returns up to 10 topics + 10 posts using TopicSerializer/PostSerializer, both of which trigger reverse-OneToOne N+1s on rich_content; PostSerializer also lacks select_related('rich_content').

- **Reviewer:** performance-reviewer
- **Rule:** N+1 cascade through serializers
- **Suggested fix:** Add select_related('rich_content') to the search querysets and consider switching to SimpleTopicSerializer for list contexts.

**#478** Line 222: Minimum search length of 3 is a magic literal; same threshold duplicated in views.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: no magic numbers
- **Suggested fix:** Define FORUM_SEARCH_MIN_LENGTH in constants.py and import.

**#479** Line 261: active_users uses .values('poster').distinct().count() over Post which scans potentially millions of rows; no index hint and no caching.

- **Reviewer:** performance-reviewer
- **Rule:** Expensive distinct-count without caching
- **Suggested fix:** Compute via a windowed aggregate with a partial index on (created, poster) or maintain a counter; cache with same key as forum_stats.

**#480** Line 264: Online-users heuristic uses magic constants 1, 20, and a 30-day window for active users.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: no magic numbers
- **Suggested fix:** Move these thresholds (FORUM_ACTIVE_USER_WINDOW_DAYS, FORUM_ONLINE_USERS_DIVISOR) to constants.py.

**#481** Line 281: forum_ai_assist takes user-controlled prompt input but performs no rate limiting; expensive AI endpoint should be throttled per user.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/docs/patterns/architecture/rate-limiting.md
- **Suggested fix:** Apply @ratelimit and ensure custom handler returns 429 (Issue #133).

**#482** Line 297: Function lacks type hints on parameters and return type, violating service/code-quality convention.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: type hints required
- **Suggested fix:** Add typed signatures: def generate_forum_ai_content(prompt_type: str, context: str, selected_text: str, user: User) -> str.

**#483** Line 310: Bare `except Exception` returns the raw exception message in the JSON body, leaking internal error detail to clients.

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF error handling
- **Suggested fix:** Log the exception, return a generic message, and use the project exception handler.

**#484** Line 432: topic.save(update_fields=['views_count']) after assigning F('views_count') + 1 leaves the in-memory model with an F-expression and no refresh; subsequent reads of topic.views_count return an F object.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django ORM correctness
- **Suggested fix:** Use Topic.objects.filter(id=topic_id).update(views_count=F('views_count') + 1) or call topic.refresh_from_db(fields=['views_count']).

**#485** Line 519: PostReactionView.post executes get_post_reaction_counts + get_user_reactions_for_post on every toggle without caching, hitting DB twice for read-after-write per click.

- **Reviewer:** performance-reviewer
- **Rule:** Hot reaction endpoint missing per-post cache
- **Suggested fix:** Cache reaction_counts in Redis keyed by post_id, invalidate on toggle, and only re-query the counts.

**#486** Line 539: Broad except Exception in PostReactionView.post leaks str(e) to the client and masks real failures.

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF error handling
- **Suggested fix:** Catch specific exceptions, log, return generic 500.

**#487** Line 645: PostImageUploadView counts existing images with a COUNT query then iterates uploads doing per-file ORM creates without bulk_create; acceptable for small batches but becomes hot on bulk uploads.

- **Reviewer:** performance-reviewer
- **Rule:** Use bulk_create where feasible
- **Suggested fix:** Use ForumPostImage.objects.bulk_create(...) once all valid files are validated (skip if upload_order auto-set logic required).

**#488** Line 655: Magic numbers: max_size = 5 *1024* 1024 and the literal 6 (max images) are hardcoded instead of imported from a constants module.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: no magic numbers
- **Suggested fix:** Move MAX_FORUM_IMAGE_SIZE_BYTES and FORUM_MAX_IMAGES_PER_POST to apps/forum_integration/constants.py.

**#489** Line 656: Allowed MIME list is a magic literal scattered in the view; should come from constants.py shared with validation layer.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: no magic numbers
- **Suggested fix:** Define ALLOWED_FORUM_IMAGE_MIME_TYPES in constants.py.

**#490** Line 800: Hardcoded upload_order range 0-5 duplicates the magic 6-image limit; should reuse the constant.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: no magic numbers
- **Suggested fix:** Validate against FORUM_MAX_IMAGES_PER_POST - 1.

**#491** Line 875: Python f-string syntax `{selected_text if selected_text else context}` is embedded in a `""""""` regular string, not an f-string; the placeholder will be passed verbatim into prompt_template.format, where the `if` expression will trigger a KeyError when `.format()` is applied.

- **Reviewer:** django-drf-reviewer
- **Rule:** Python correctness
- **Suggested fix:** Pre-compute the value in Python and reference it as a single named placeholder, or build the string with explicit logic.

**#492** Line 991: Topics feed limit cap of 50 is a hardcoded magic number for an external-facing pagination guard.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: no magic numbers
- **Suggested fix:** Define FORUM_FEED_MAX_LIMIT in constants.py.

**#493** Line 1048: user_trust_level returns f'Failed to check permissions: {str(e)}' to clients, leaking internals.

- **Reviewer:** django-drf-reviewer
- **Rule:** DRF error handling
- **Suggested fix:** Log details server-side and return a generic message.

**#494** Line 1058: user.date_joined is non-null on Django's AbstractUser, but the `if user.date_joined else 0` fallback hides bugs and the bare datetime arithmetic should still go through utc-safe helpers.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code quality
- **Suggested fix:** Drop the conditional and rely on the field's NOT NULL guarantee.

**#495** Line 1104: Trust-level thresholds (50/10/30, 20/5/14, 5/1/7) are embedded magic numbers driving authorization-adjacent behavior.

- **Reviewer:** django-drf-reviewer
- **Rule:** Backend convention: no magic numbers
- **Suggested fix:** Centralize trust-level thresholds in constants.py for auditability.

### `backend/apps/forum_integration/models.py`

**#496** Line 142: index.SearchField('content_blocks') over a StreamField is supported but only works correctly with the database search backend; on the Postgres backend / Wagtail search backends this can fail or be silently ignored without a get_searchable_content method.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/domain/wagtail.md
- **Suggested fix:** Verify the active WAGTAILSEARCH_BACKENDS supports StreamField indexing or expose plain text via get_searchable_content.

**#497** Line 184: ForumIndexPage.get_context returns a Forum queryset without prefetching topic/post counts; the template will likely trigger N+1 COUNT queries per forum row.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Annotate counts (Count('topics'), Count('topics__posts')) or prefetch needed relations in the queryset.

**#498** Line 252: ForumCategoryPage.get_context fetches Topic queryset without prefetching first_post images or rich_content — same N+1 concerns as TopicsFeedView when rendered.

- **Reviewer:** performance-reviewer
- **Rule:** Server-rendered list missing prefetch
- **Suggested fix:** Add select_related('first_post', 'first_post__poster', 'first_post__rich_content') and prefetch_related('first_post__images') on the queryset.

**#499** Line 253: Topic queryset selects last_post and poster but does not prefetch post counts or forum.parent; per-row reply counts and breadcrumb chains will N+1.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Annotate posts_count or use values()/annotate to consolidate counts; prefetch forum.parent for breadcrumbs.

**#500** Line 396: redirect('login') assumes a URL named 'login' is registered; Wagtail/Django auth typically uses 'wagtailadmin_login' or LOGIN_URL, so this can NoReverseMatch in some configurations.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Use settings.LOGIN_URL or redirect_to_login(request.get_full_path()) for robustness.

**#501** Line 407: ForumModerationPage.get_context runs a COUNT(*) on Post (approved=False) on every page render with no caching, which scales poorly as the post table grows.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/architecture/caching.md
- **Suggested fix:** Cache the pending count under a key like forum:pending_posts_count with short TTL, invalidated on Post approval.

**#502** Line 700: ForumPostImage.save() computes max(upload_order) and writes upload_order without locking; concurrent uploads to the same post can produce duplicate orders, violating unique_together (post, upload_order) and raising IntegrityError.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Wrap in a transaction with select_for_update on the parent post, or retry on IntegrityError.

### `backend/apps/forum_integration/serializers.py`

**#503** Line 26: SerializerMethodField fields (topics_count, posts_count, last_activity) lack @extend_schema_field type annotations, producing untyped 'object' entries in the OpenAPI schema.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema — explicit type annotations on serializer fields
- **Suggested fix:** Decorate each get_* method with @extend_schema_field(OpenApiTypes.INT or DATETIME) so drf-spectacular emits correct types.

**#504** Line 61: `forum` is a SerializerMethodField returning an inline dict instead of a nested serializer; OpenAPI schema cannot infer its shape.

- **Reviewer:** api-design-reviewer
- **Rule:** Nested serializers must use a real Serializer (not inline dicts in SerializerMethodField)
- **Suggested fix:** Define a small ForumBriefSerializer and use it as a nested read_only field, or annotate with @extend_schema_field(inline_serializer(...)).

**#505** Line 62: replies_count SerializerMethodField has no @extend_schema_field annotation; drf-spectacular infers it as untyped.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema — explicit type annotations
- **Suggested fix:** Add @extend_schema_field(OpenApiTypes.INT) above get_replies_count.

**#506** Line 90: TopicSerializer.forum/last_poster/replies_count SerializerMethodFields lack @extend_schema_field annotations, weakening OpenAPI schema fidelity.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema — explicit type annotations
- **Suggested fix:** Annotate get_forum/get_last_poster/get_replies_count with @extend_schema_field(...).

**#507** Line 126: PostSerializer.rich_content/content_format/ai_assisted SerializerMethodFields have no @extend_schema_field decorators, leaving response shape undefined in the schema.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema — explicit type annotations
- **Suggested fix:** Decorate each getter with @extend_schema_field for boolean/string/list-of-dict types.

**#508** Line 332: ValidationError uses `{'rich_content': 'message'}` (string value) — DRF normalizes ValidationError dict values to lists, producing `{'rich_content': ['message']}` rather than the project's `{'error': 'message'}` shape.

- **Reviewer:** api-design-reviewer
- **Rule:** Error Responses — consistent {'error': 'message'} shape
- **Suggested fix:** Wrap with serializers.ValidationError({'error': 'plant_mention block requires a valid plant_page id'}) or raise a non-field error to align with the documented error shape.

**#509** Line 338: ValidationError shape diverges from project convention `{'error': '...'}` — DRF will emit `{'rich_content': ['...']}`.

- **Reviewer:** api-design-reviewer
- **Rule:** Error Responses — consistent {'error': 'message'} shape
- **Suggested fix:** Raise via serializers.ValidationError({'error': f'Invalid plant_page id {plant_id}'}) or use a custom exception handler that normalizes.

**#510** Line 398: CreatePostSerializer.create issues an extra COUNT (Post.objects.filter(topic=topic, approved=True).count()) per post creation rather than incrementing the cached topic.posts_count via F('posts_count') + 1.

- **Reviewer:** performance-reviewer
- **Rule:** Avoid recomputing aggregates that can be incremented atomically
- **Suggested fix:** Use Topic.objects.filter(pk=topic.pk).update(posts_count=F('posts_count') + 1, last_post=post) (and refresh the local instance if needed).

### `backend/apps/forum_integration/tests/test_forum_api_roundtrip.py`

**#511** Line 13: Missing unauthenticated 401 case for the topic-create and reply endpoints — checklist requires authenticated success + unauthenticated 401 + invalid input 400 for new endpoints; only 200/400 are covered.

- **Reviewer:** test-quality-reviewer
- **Rule:** coverage (new API endpoints)
- **Suggested fix:** Add `test_create_topic_unauthenticated_returns_401` using a fresh APIClient with no force_authenticate.

**#512** Line 67: Hardcoded URL string instead of using reverse() — `reverse` is imported on line 2 but never used; URL changes will silently break tests.

- **Reviewer:** test-quality-reviewer
- **Rule:** test naming & structure (use named URL routing for resilience)
- **Suggested fix:** Replace f-string URLs with reverse('forum-categories-create-topic', kwargs={'pk': self.forum.id}) or remove the unused import.

**#513** Line 88: Assertion accepts either `type` or `block` key in the serialized output — tests should pin one canonical response shape, otherwise a serializer bug toggling shapes will not be caught.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion quality (strictness)
- **Suggested fix:** Decide which key is canonical (likely `type`) and assert that one explicitly.

**#514** Line 168: Fragile error-shape assertion uses `assertIn('rich_content', str(resp.data).lower())` against a stringified dict — passes even if 'rich_content' appears in unrelated parts of the error payload.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion quality
- **Suggested fix:** Assert on resp.data['rich_content'] (or a specific error code) directly rather than substring-matching a stringified dict.

### `backend/apps/forum_integration/tests/test_plant_mention_serialization.py`

**#515** Line 76: `assertRaises(ValidationError)` does not assert which field/error code triggered — a regression that raises ValidationError for the wrong reason will pass.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion quality (strictness)
- **Suggested fix:** Use `assertRaisesRegex` or capture the exception and assert exc.detail['rich_content'] / error code.

### `backend/apps/forum_integration/views.py`

**#516** Line 47: forum_category renders topics without select_related('first_post') even though templates may render OP/preview blocks — silent N+1 in template land.

- **Reviewer:** performance-reviewer
- **Rule:** Template-side N+1 risk
- **Suggested fix:** Add 'first_post', 'first_post__poster' to the existing select_related to cover template-side access.

### `backend/apps/forum_integration/wagtail_hooks.py`

**#517** Line 104: add_forum_stats_panel runs four COUNT(*) queries on every Wagtail admin homepage load without caching, hitting the DB on every editor visit.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/architecture/caching.md
- **Suggested fix:** Cache the four counts in Redis (e.g. forum:stats:summary, 60-300s TTL) and invalidate on post/topic create/approve.

**#518** Line 164: add_forum_summary_items also runs three COUNT(*) queries on every admin homepage load with no caching, duplicating queries from the stats panel.

- **Reviewer:** wagtail-reviewer
- **Rule:** backend/docs/patterns/architecture/caching.md
- **Suggested fix:** Reuse the cached counts from the stats panel rather than querying again.

### `backend/apps/garden/apps.py`

**#519** Line 6: Garden app has no auditlog.py registering Garden / GardenPlant / CareReminder / PestIssue / JournalEntry — GDPR compliance gap (rule: every new app must register models in auditlog.py).

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality — auditlog registration for GDPR
- **Suggested fix:** Create backend/apps/garden/auditlog.py registering user-data models with auditlog.register().

### `backend/apps/garden/firebase_config.py`

**#520** Line 148: Bare `except:` swallows all exceptions including KeyboardInterrupt and SystemExit; should catch Exception and log.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code quality — never bare except
- **Suggested fix:** Replace with `except Exception as e:` and log at warning level.

### `backend/apps/garden/serializers.py`

**#521** Line 28: MAX_PEST_IMAGES_PER_ISSUE and MAX_JOURNAL_IMAGES_PER_ENTRY are imported and documented (max 6 / max 10) but no serializer enforces these caps, allowing clients to upload unbounded image counts.

- **Reviewer:** api-design-reviewer
- **Rule:** serializer validation completeness
- **Suggested fix:** Add a validate() on PestIssueSerializer / JournalEntrySerializer (or in the view's perform_create) that rejects requests exceeding the per-record image cap.

**#522** Line 145: GardenPlantSerializer nests reminders, pest_issues, and journal_entries; GardenSerializer in turn nests plants + tasks + journal_entries — this 2-level nesting will cause N+1 query explosions and large payloads on list endpoints unless the view uses prefetch_related and a separate list serializer is enforced.

- **Reviewer:** api-design-reviewer
- **Rule:** DRF nested serializer payload/perf
- **Suggested fix:** Document required prefetch_related chain on the ViewSet and ensure list actions always use GardenListSerializer; consider lazy-loading nested children via separate endpoints.

**#523** Line 145: PestIssueSerializer exposes the user's PII via StringRelatedField -> User.**str** on every PestIssue; in user-scoped endpoints this is harmless, but the field is defined on the shared serializer class also reachable via GardenPlantSerializer nested → leaks owning username through other paths.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — minimize PII exposure
- **Suggested fix:** Replace with PrimaryKeyRelatedField(read_only=True) or remove the field from nested usages.

**#524** Line 252: GardenPlantSerializer nests reminders, pest_issues (with images), and journal_entries (with images) by default. Any list of GardenPlants — including via GardenSerializer.plants nesting — will trigger heavy prefetches; if a viewset omits the right prefetches, this becomes O(plants * subresources) queries.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/architecture/viewsets.md - keep list serializers slim
- **Suggested fix:** Provide a slim serializer for list contexts (no reminders/pest_issues/journal_entries) or guard nested fields by context (request.query_params or action).

**#525** Line 376: GardenSerializer nests `plants` (full GardenPlantSerializer) which itself nests reminders/pest_issues/journal_entries — payload size and N+1 risk grow quadratically; should split into a thin retrieve serializer or paginate plants.

- **Reviewer:** django-drf-reviewer
- **Rule:** Performance / API design — avoid deep nesting
- **Suggested fix:** Use a slim GardenPlantSummarySerializer for nested usage or expose plants only via /plants/?garden=<id>.

### `backend/apps/garden/services/care_assistant_service.py`

**#526** Line 191: OpenAI client.chat.completions.create called without an explicit timeout; if the upstream stalls the request worker is held indefinitely.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — service calls require timeouts (services pattern)
- **Suggested fix:** Pass timeout=... or wrap with circuit breaker / request_timeout setting.

**#527** Line 301: Second OpenAI call (diagnose_problem) also missing timeout — same hang risk.

- **Reviewer:** django-drf-reviewer
- **Rule:** Services — timeouts required
- **Suggested fix:** Add timeout=... to chat.completions.create.

**#528** Line 355: get_seasonal_tasks evaluates plants = garden.plants.all() then calls plants.count() and iterates plants[:10] — Django evaluates the queryset twice (one COUNT then one SELECT) when the cached list could serve both.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md - avoid duplicate queryset evaluation
- **Suggested fix:** plants_list = list(garden.plants.all()); use len(plants_list) and plants_list[:10].

**#529** Line 380: Third OpenAI call (get_seasonal_tasks) lacks timeout.

- **Reviewer:** django-drf-reviewer
- **Rule:** Services — timeouts required
- **Suggested fix:** Add timeout to chat.completions.create.

### `backend/apps/garden/services/firebase_notification_service.py`

**#530** Line 122: send_reminder_notification flips notification_sent=True without transaction around send+save; if save fails the FCM message has been delivered but DB still shows not-sent → duplicate notification on retry.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — at-least-once vs at-most-once messaging
- **Suggested fix:** Either save first (at-most-once) or wrap with idempotency key in FCM.

**#531** Line 360: Test notification timestamp uses naive datetime.now().isoformat(); minor consistency issue but matches the pattern of naive usage elsewhere.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.now().

### `backend/apps/garden/services/firebase_sync_service.py`

**#532** Line 76: updated_at uses naive datetime.now().isoformat() in the Firestore payload; mixed with serialized tz-aware fields elsewhere.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.now().isoformat().

**#533** Line 215: Naive datetime.now().isoformat() compared against Firestore documents whose scheduled_date came from tz-aware Django field via isoformat(); the strings won't sort/compare correctly across timezones.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.now().isoformat() to keep tz offset consistent with serialized data.

**#534** Line 298: cutoff_date computed from naive datetime.now() — completed_at in Firestore is tz-aware ISO; comparison may delete records 5–8 hours off.

- **Reviewer:** django-drf-reviewer
- **Rule:** Django timezone hygiene
- **Suggested fix:** Use timezone.now().

**#535** Line 340: sync_reminder_batch's batch counter is reset before commit when 500 ops reached, but `batch.commit()` may raise — resulting `synced` already incremented above. Partial-failure accounting is unreliable.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — accurate batch outcome tracking
- **Suggested fix:** Increment synced only after the corresponding batch.commit() succeeds; track per-batch counts.

### `backend/apps/garden/signals.py`

**#536** Line 23: post_save signal calls FirebaseSyncService.sync_reminder synchronously inside the save path; bulk operations (e.g., the recurring-instance creation in viewsets.py:248 and smart_reminder_service.py:143) will block the request/cron once per reminder on a network call to Firestore.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/domain/celery.md - offload external IO from signals
- **Suggested fix:** Dispatch a Celery task (transaction.on_commit) that batch-syncs to Firestore instead of a synchronous per-save call.

### `backend/apps/garden/tests/test_models.py`

**#537** Line 150: datetime.now() is naive but Django uses timezone-aware datetimes when USE_TZ=True; this triggers RuntimeWarning and may cause subtle bugs in scheduled_date comparisons.

- **Reviewer:** test-quality-reviewer
- **Rule:** Django timezone aware datetimes
- **Suggested fix:** Use django.utils.timezone.now() instead of datetime.now() for DateTimeField values.

**#538** Line 167: datetime.now() is naive; same issue as line 150 — should use timezone.now() for tz-aware DateTimeField.

- **Reviewer:** test-quality-reviewer
- **Rule:** Django timezone aware datetimes
- **Suggested fix:** Replace datetime.now() with django.utils.timezone.now().

### `backend/apps/garden/viewsets.py`

**#539** Line 49: PlantCareLibraryViewSet has no Redis cache layer; care library entries are reference data read on every plant view and care plan generation, qualifying for the 'frequently-accessed, rarely-changed' caching guidance.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/architecture/caching.md - Redis for reference data
- **Suggested fix:** Wrap list/retrieve responses in cache.get_or_set with a long TTL keyed by query params + pk.

**#540** Line 113: featured action constructs its own queryset with Garden.objects.filter(...) and bypasses any DRF filter_backends (search/ordering) configured for the ViewSet — inconsistent behavior vs list endpoint.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — reuse filter_queryset() in custom actions
- **Suggested fix:** Use self.filter_queryset(Garden.objects.filter(...)) so search/ordering applies.

**#541** Line 138: public action also bypasses self.filter_queryset() — search/order params will be ignored.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — reuse filter_queryset() in custom actions
- **Suggested fix:** Wrap queryset with self.filter_queryset().

**#542** Line 138: public() action uses GardenListSerializer which calls get_plant_count -> obj.plants.count(); but the queryset only prefetches plants without annotating Count, so each row triggers a COUNT query.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate plant_count=Count('plants') and read from the annotation in the serializer.

**#543** Line 156: GardenPlantViewSet has no perform_create that validates the GardenPlant.garden belongs to request.user — a user can post `garden=<other_user_id>` and create a plant in someone else's garden (queryset filter blocks reads but not writes).

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — IDOR / ownership check on FK in serializer payload
- **Suggested fix:** Override perform_create to assert serializer.validated_data['garden'].user == request.user; raise PermissionDenied otherwise.

**#544** Line 183: CareReminderViewSet.perform_create does not verify that garden_plant belongs to a garden owned by request.user — a user can create reminders pointing at another user's plant.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — ownership check on FK fields supplied by client
- **Suggested fix:** Validate garden_plant.garden.user == request.user in perform_create or in the serializer's validate_garden_plant.

**#545** Line 296: TaskViewSet.perform_create accepts garden FK from client without verifying garden.user == request.user.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — ownership check on FK fields
- **Suggested fix:** Validate ownership in perform_create.

**#546** Line 333: PestIssueViewSet.perform_create does not check garden_plant ownership — same IDOR class.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — ownership check on FK fields
- **Suggested fix:** Validate garden_plant ownership before save.

**#547** Line 368: Pest image count check uses pest_issue.images.count() then save — TOCTOU; concurrent uploads can exceed MAX_PEST_IMAGES_PER_ISSUE.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — atomic count-and-insert
- **Suggested fix:** Wrap in transaction.atomic with select_for_update on PestIssue, or rely on DB constraint.

**#548** Line 368: upload_image checks pest_issue.images.count() with a per-call COUNT query; under a tight loop of uploads from a client this produces extra round-trips. Minor but worth noting.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use pest_issue.images.all()[:MAX+1] length check or annotate, or rely on the serializer-level validation only when concurrency is a concern.

**#549** Line 395: JournalEntryViewSet.perform_create accepts arbitrary garden / garden_plant FKs from the request body without verifying the user owns them.

- **Reviewer:** django-drf-reviewer
- **Rule:** Security — ownership check on FK fields
- **Suggested fix:** Validate garden.user == request.user in serializer or perform_create.

**#550** Line 431: Journal image count check is also TOCTOU — concurrent uploads can exceed MAX_JOURNAL_IMAGES_PER_ENTRY.

- **Reviewer:** django-drf-reviewer
- **Rule:** Architecture — atomic count-and-insert
- **Suggested fix:** Wrap in transaction.atomic with select_for_update.

### `backend/apps/garden_calendar/api/serializers.py`

**#551** Line 169: SeasonalTemplateSerializer exposes 'id' (auto-increment) as the canonical identifier; other related serializers expose 'uuid'. Mixing public id types is inconsistent and complicates clients.

- **Reviewer:** api-design-reviewer
- **Rule:** UUID Endpoints checklist
- **Suggested fix:** Expose uuid (add to model if missing) and remove id from public fields, or document this exception.

**#552** Line 215: WeatherAlertSerializer exposes 'id' instead of 'uuid' as the primary identifier — same inconsistency as SeasonalTemplate and Harvest.

- **Reviewer:** api-design-reviewer
- **Rule:** UUID Endpoints checklist
- **Suggested fix:** Switch to UUID-based identifiers across the garden_calendar surface.

**#553** Line 497: HarvestSerializer field list omits 'taste_rating', but validate_taste_rating exists — validator will never run because the field is not declared/serialized.

- **Reviewer:** api-design-reviewer
- **Rule:** Serializers checklist
- **Suggested fix:** Add 'taste_rating' to fields, or remove the orphan validator.

**#554** Line 509: validate_taste_rating defined on HarvestSerializer, but 'taste_rating' is not in Meta.fields and not on the Harvest model. Dead code that masks the missing-field issue.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality
- **Suggested fix:** Remove the validator or add the field to model+serializer.

### `backend/apps/garden_calendar/api/views.py`

**#555** Line 95: Q(organizer__in=user.following.all()) executes user.following.all() as an outer subquery; ok in Django ORM but unbounded if user follows many — could degrade for power users.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use .values_list('id') subquery (Django optimizes IN with subquery), or precompute follower IDs once.

**#556** Line 154: rsvp action uses @method_decorator(ratelimit(..., block=True)). django-ratelimit raises Ratelimited (PermissionDenied) so DRF returns 403 instead of 429 unless a custom exception handler is in place. Same pattern across create/update/partial_update/destroy/complete/skip etc.

- **Reviewer:** django-drf-reviewer
- **Rule:** Permissions & Security — Issue #133
- **Suggested fix:** Confirm settings.REST_FRAMEWORK['EXCEPTION_HANDLER'] handles Ratelimited→429+Retry-After; otherwise users hitting the limit get a 403.

**#557** Line 211: calendar_feed action has no @extend_schema; OpenAPI cannot describe its custom response shape (events[], total_events) or query params (start_date, end_date).

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema checklist
- **Suggested fix:** Add @extend_schema with parameters and a typed response example.

**#558** Line 310: current_season action lacks @extend_schema documenting the bespoke response shape and is also missing rate limiting / caching despite being a public AllowAny endpoint.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema checklist
- **Suggested fix:** Add @extend_schema and document the response.

**#559** Line 385: active_alerts action and its custom response payload are not described via @extend_schema.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema checklist
- **Suggested fix:** Add @extend_schema with response schema/example.

**#560** Line 568: GardenBedViewSet.get_queryset disables plant_count annotation (commented out). Each list row then calls bed.plant_count (a property doing .filter(is_active=True).count()), producing one extra query per bed (N+1).

- **Reviewer:** django-drf-reviewer
- **Rule:** Performance — query-optimization.md
- **Suggested fix:** Re-enable annotate(plant_count=Count('plants', filter=Q(plants__is_active=True))) and rely on the annotation; serializer field already accepts it.

**#561** Line 657: analytics action loops Python-side over plants to build health_stats (line 657-658). Use a values('health_status').annotate(Count('uuid')) aggregation; current code triggers a full plant fetch even when only counts are needed.

- **Reviewer:** django-drf-reviewer
- **Rule:** Performance — N+1 / aggregation
- **Suggested fix:** Replace the for-loop with .filter(is_active=True).values('health_status').annotate(count=Count('uuid')).

**#562** Line 685: completion_rate is computed as (total_tasks - overdue_tasks) / total_tasks * 100, which conflates pending-but-not-overdue tasks with completed ones and overstates true completion.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality
- **Suggested fix:** Use completed_tasks / total_tasks * 100, where completed_tasks comes from CareTask.objects.filter(..., completed=True).count().

**#563** Line 815: PlantViewSet always prefetches all images even on list views where only the primary image is rendered, transferring extra rows; consider Prefetch with filter=is_primary=True for list action.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** On list, use Prefetch('images', queryset=PlantImage.objects.filter(is_primary=True)) to avoid fetching all images per plant.

**#564** Line 822: Plant detail prefetches care_tasks and care_logs without slicing; serializer only renders 3 tasks and 5 logs but full sets are loaded into memory per request.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use Prefetch with sliced queryset (or a windowed subquery) limited to top N tasks/logs to reduce memory transfer.

**#565** Line 918: upload_image calls plant.images.count() and later plant.images.exclude(...).update(...); the count + later filter cause two extra queries per upload.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Combine: fetch images list once or use plant.images.filter(is_primary=True).update(is_primary=False) only when needed.

**#566** Line 929: Image extension is taken as the trailing token after the last '.', so a file named 'evil.php.jpg' passes layer-1 checks. Combined with content_type from the client (also user-controllable) layers 1 and 2 can both be spoofed; layer 4 (PIL) is the real check, but the comment claims layered defense.

- **Reviewer:** django-drf-reviewer
- **Rule:** Permissions & Security — file-upload
- **Suggested fix:** Reject filenames containing additional dots in the basename or normalize/strip to a single safe extension before persisting.

**#567** Line 974: Allowed PIL image formats are hardcoded as ['jpeg','png','gif','webp'] instead of being driven by ALLOWED_IMAGE_EXTENSIONS / ALLOWED_IMAGE_MIME_TYPES in constants.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** Code Quality — no magic values
- **Suggested fix:** Derive the set from constants to keep extension/MIME/format checks in sync.

**#568** Line 1015: Setting is_primary on the new image and unsetting other images is two separate writes with no transaction; concurrent uploads can leave multiple primary images for the same plant.

- **Reviewer:** django-drf-reviewer
- **Rule:** Models & Queries
- **Suggested fix:** Wrap in transaction.atomic() and update siblings before/with the create.

**#569** Line 1302: calendar_feed and statistics (line 1435) custom actions return ad-hoc dicts with no @extend_schema; clients/Swagger will see unannotated responses.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema checklist
- **Suggested fix:** Add @extend_schema with explicit response examples for both.

**#570** Line 1417: HarvestViewSet uses lookup_field='id' (auto-increment integer) while every other Garden Planner ViewSet exposes UUIDs — leaks DB ids and is inconsistent with the rest of the API surface.

- **Reviewer:** api-design-reviewer
- **Rule:** UUID Endpoints checklist
- **Suggested fix:** Add a uuid field to Harvest model (or document why id is intentional) and switch lookup_field to 'uuid'.

**#571** Line 1483: PlantImageViewSet exposes ModelViewSet (POST/PUT/PATCH/DELETE) for image objects but has no @action upload + the Plant.upload_image action also writes to PlantImage; two parallel write paths bypass each other's validation (the plain create path skips the 4-layer security validation).

- **Reviewer:** api-design-reviewer
- **Rule:** API design / file-upload security
- **Suggested fix:** Restrict PlantImageViewSet to ReadOnlyModelViewSet (or PATCH/DELETE only) and route all uploads through Plant.upload_image.

**#572** Line 1540: GrowingZoneViewSet.lookup uses query string 'zone_code' but is also a list endpoint at /lookup/?zone_code= which should be designed as /lookup/<zone_code>/ for proper REST + cacheability.

- **Reviewer:** api-design-reviewer
- **Rule:** REST design
- **Suggested fix:** Convert to detail action with url_path='lookup/(?P<zone_code>[^/.]+)' or expose zone_code as the lookup_field.

**#573** Line 1548: lookup uses request.query_params.get('zone_code') without validating type/length, and the returned 404 body uses {'error': msg} but interpolates user-supplied input directly — minor XSS risk in JSON consumers and inconsistent error envelope (no 'detail').

- **Reviewer:** api-design-reviewer
- **Rule:** Error Responses checklist
- **Suggested fix:** Validate via serializer or DRF param + return {'error': 'not found', 'detail': f'zone {sanitized}'}.

### `backend/apps/garden_calendar/services/companion_planting_service.py`

**#574** Line 266: analyze_garden_bed calls plants.count() then list(plants) on the same queryset, executing two queries; second query also pulls all fields without select_related.

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Materialize once: plant_list = list(plants); plant_count = len(plant_list).

### `backend/apps/garden_calendar/services/garden_analytics_service.py`

**#575** Line 116: Calls beds.count() after iterating the queryset, executing an extra COUNT query that could be derived from the iteration (len of cached results).

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Use len(list(beds)) or capture count from prior iteration instead of beds.count().

**#576** Line 327: QuerySet.extra(select={'month': 'EXTRACT(month FROM harvest_date)'}) is deprecated and PostgreSQL-specific; will fail on SQLite test DBs.

- **Reviewer:** django-drf-reviewer
- **Rule:** Migrations / Models & Queries
- **Suggested fix:** Use ExtractMonth from django.db.models.functions or annotate(month=ExtractMonth('harvest_date')).

**#577** Line 327: Uses deprecated QuerySet.extra() with raw SQL fragment for month extraction; brittle and Django plans to remove .extra(). Also DB-specific (PostgreSQL EXTRACT).

- **Reviewer:** performance-reviewer
- **Rule:** —
- **Suggested fix:** Replace with .annotate(month=ExtractMonth('harvest_date')).values('month').annotate(...)

### `backend/apps/garden_calendar/tests/test_cache.py`

**#578** Line 81: Cache miss query count of 4 is asserted but docstring admits 'COUNT plants per bed (called twice for utilization_rate property)' — this enshrines a duplicate-property-call bug as expected behavior.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Cache the property result on the instance or annotate; reassert lower count.

**#579** Line 188: Test admits 'user2 still executes EXISTS check (not cached for empty results)' with a TODO at line 187 — the test passes by acknowledging an inefficiency rather than by exercising the desired contract.

- **Reviewer:** test-quality-reviewer
- **Rule:** backend/docs/patterns/performance/query-optimization.md
- **Suggested fix:** Cache empty results or extract the TODO to an issue and tighten the test once fixed.

**#580** Line 236: test_weather_cache_key_format and test_weather_cache_invalidation populate the cache via cache.set() directly rather than via WeatherService, so they verify dict keys but not that the service writes/reads/invalidates with that key.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Drive cache population through WeatherService.get_current_weather (with mocked requests) before asserting key + invalidation behavior.

### `backend/apps/garden_calendar/tests/test_integration.py`

**#581** Line 414: test_growth_stage_transition_workflow notes it skips CareScheduleService.update_tasks_for_growth_stage_change due to SERVICE BUG, leaving the integration workflow's most important transition unverified.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Track the bug and re-enable the assertion once the service writes created_by.

### `backend/apps/garden_calendar/tests/test_services.py`

**#582** Line 204: @skip with the message 'SERVICE BUG: creates CareTask without required created_by field' silently disables a happy-path test for generate_initial_tasks_for_plant — coverage gap on a service entry point.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Open an issue, link it in the skip reason, or fix the service so the test exercises the real code path.

**#583** Line 361: test_weather_service_requires_api_key asserts None when API_KEY is unset, but does not patch WEATHER_API_KEY — relies on test env not having the key, which makes the test environment-dependent and fragile.

- **Reviewer:** test-quality-reviewer
- **Rule:** —
- **Suggested fix:** Patch the API_KEY attribute to '' explicitly so the test deterministically exercises the no-key branch.

### `backend/apps/plant_identification/admin.py`

**#584** Line 92: PlantIdentificationRequestAdmin list_display includes user without list_select_related — admin N+1 on request list page.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add list_select_related = ('user',).

**#585** Line 184: PlantIdentificationResultAdmin.list_display references request, display_name (touches identified_species), without overriding get_queryset() — admin list page issues a query per row.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md (admin select_related)
- **Suggested fix:** Add list_select_related = ('request', 'request__user', 'identified_species') to the admin.

**#586** Line 246: UserPlantAdmin list_display reads user, collection, species without list_select_related — admin N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add list_select_related = ('user', 'collection', 'species').

### `backend/apps/plant_identification/api/diagnosis_serializers.py`

**#587** Line 251: value.request.user access assumes diagnosis_result.request exists and has both .user and .is_public; if request is null or missing attribute, raises AttributeError -> 500.

- **Reviewer:** api-design-reviewer
- **Rule:** Defensive validation
- **Suggested fix:** Use getattr with safe defaults or check value.request explicitly before access.

**#588** Line 363: DiagnosisReminderSerializer.validate() rejects past scheduled_date but doesn't account for partial updates where scheduled_date isn't being changed but is loaded from instance.

- **Reviewer:** api-design-reviewer
- **Rule:** Validation correctness
- **Suggested fix:** Skip the future-date check on partial_update when scheduled_date is unchanged.

### `backend/apps/plant_identification/api/diagnosis_viewsets.py`

**#589** Line 151: Custom @action endpoints (favorites, active_treatments, successful_treatments, toggle_favorite, snooze, cancel, acknowledge) lack @extend_schema annotations describing response shape and parameters.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema checklist
- **Suggested fix:** Add @extend_schema decorators to each @action with response serializer + status codes.

**#590** Line 331: int(request.data.get('hours', 24)) raises ValueError on non-numeric input, returning 500 instead of 400 with structured error.

- **Reviewer:** api-design-reviewer
- **Rule:** Error Responses checklist: 400 for validation
- **Suggested fix:** Wrap in try/except ValueError or use a serializer to validate hours field.

### `backend/apps/plant_identification/api/endpoints.py`

**#591** Line 99: PlantSpeciesAPIViewSet.families action runs N+1 by issuing PlantSpecies.objects.filter(family=family).count() for every distinct family in a Python loop.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md (aggregate-not-loop)
- **Suggested fix:** Single query: PlantSpecies.objects.exclude(family='').values('family').annotate(count=Count('id')).order_by('family').

**#592** Line 110: PlantSpeciesAPIViewSet.plant_types iterates distinct plant_types and runs a COUNT per type — same N+1 aggregate-in-loop.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use values('plant_type').annotate(count=Count('id')) once.

**#593** Line 130: PlantCategoryAPIViewSet and PlantCareGuideAPIViewSet do not set versioning_class=None like PlantSpeciesAPIViewSet — inconsistent and may break under DRF NamespaceVersioning.

- **Reviewer:** api-design-reviewer
- **Rule:** Versioning checklist consistency
- **Suggested fix:** Add versioning_class = None on all Wagtail BaseAPIViewSet subclasses, or remove from all with explanation.

**#594** Line 161: PlantCategoryAPIViewSet.get_queryset() prefetch_related('plant_species') is unused for plant_count — count is fed by serializer's per-object .count(), so the prefetch wastes memory without preventing N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Replace prefetch with annotate(plant_count=Count('plant_species')).

**#595** Line 220: PlantCareGuideAPIViewSet.difficulty_levels runs PlantCareGuide.objects.filter(care_difficulty=value).count() in a Python loop over choices — aggregate-in-loop N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Use values('care_difficulty').annotate(count=Count('id')) and merge with choices in Python.

**#596** Line 256: PlantSpeciesPageViewSet.get_queryset prefetches 'gallery_images' for both list and detail; list uses lighter PlantSpeciesPageListSerializer which doesn't render gallery_images — wasted IO on list responses.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Move gallery_images prefetch to get_object()/detail action; keep list queryset minimal (target 5-8 queries per checklist).

**#597** Line 309: PlantSpeciesPageViewSet.by_category runs the full base get_queryset() (with multi-table joins, distinct, prefetches) per category in a loop — multiplicative cost across featured categories.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Build a single annotated queryset filtered by categories__in=[...] then group results in Python by category, or cache the response.

**#598** Line 309: by_category action issues N category queries (one filtered queryset per featured category) plus per-page serializer dereferencing — query count scales with featured categories, not bounded.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Build one queryset filtering categories__in=featured_ids, then group in Python to bound queries.

### `backend/apps/plant_identification/api/serializers.py`

**#599** Line 137: PlantSpeciesPageSerializer pulls care_guide via 'plant_species.care_guide' OneToOne; PlantSpeciesPageViewSet.get_queryset() does select_related('plant_species', 'plant_species__care_guide') correctly, but list serializer does NOT include care_guide — confirm list version omits the join cost.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Verify list endpoint isn't dragging care_guide; if not used, drop the join in list path.

**#600** Line 155: get_gallery_images() calls image.get_rendition() in a Python loop per detail object — each rendition can hit DB to find existing rendition. With 6+ gallery images per page that adds 6+ extra queries per detail call.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md, patterns/architecture/caching.md
- **Suggested fix:** Use prefetch_renditions() on gallery_images prefetch (Wagtail supplies it), or cache the rendition URLs on the page model.

**#601** Line 245: PlantCategoryIndexPageSerializer.get_categories ignores obj/page configuration, hardcodes featured=True filter, and refetches PlantCategory.objects without prefetch_related('plant_species') — drives the N+1 from get_plant_count.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Prefetch plant_species (with Count annotation) and respect obj.categories_per_page for slicing.

**#602** Line 252: get_featured_plants queries PlantSpeciesPage.objects.live().public() without select_related/prefetch_related, then nested PlantSpeciesPageListSerializer dereferences plant_species/categories — additional N+1 when index page is rendered.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Add .select_related('plant_species').prefetch_related('categories') on the featured_plants queryset.

### `backend/apps/plant_identification/api/simple_views.py`

**#603** Line 80: Endpoint lacks @extend_schema annotation — request/response schema, 400/429/500 responses are not declared in OpenAPI/Swagger.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI Schema checklist
- **Suggested fix:** Add @extend_schema with request, responses (200/400/401/429/500), and rate limit notes.

**#604** Line 87: Docstring states endpoint is at /api/plant-identification/identify/ which is unversioned — should be under /api/v1/ per project convention.

- **Reviewer:** api-design-reviewer
- **Rule:** Versioning checklist
- **Suggested fix:** Mount under /api/v1/plant-identification/ or document deprecation note for legacy unversioned route.

**#605** Line 134: Hardcoded magic number `10 * 1024 * 1024` for max upload size; should come from constants.py per project rule.

- **Reviewer:** django-drf-reviewer
- **Rule:** no magic numbers
- **Suggested fix:** Add MAX_UPLOAD_SIZE_BYTES to constants.py and import.

**#606** Line 153: Endpoint returns HTTP 200 with `success: false` when identification fails; clients cannot rely on status codes for error handling.

- **Reviewer:** django-drf-reviewer
- **Rule:** api-design/error shapes
- **Suggested fix:** Return appropriate 4xx/5xx code based on error class instead of always 200.

### `backend/apps/plant_identification/auditlog.py`

**#607** Line 11: auditlog.py registers PlantIdentificationResult, Request, etc., but never registers DiagnosisCard, DiagnosisReminder, SavedDiagnosis, TreatmentAttempt — missing GDPR audit coverage for new sensitive models.

- **Reviewer:** django-drf-reviewer
- **Rule:** auditlog coverage / GDPR
- **Suggested fix:** Register the diagnosis-card and saved-diagnosis models with appropriate include_fields.

### `backend/apps/plant_identification/management/commands/test_plant_apis.py`

**#608** Line 1: File is a Django management command that hits live external APIs and prints to stdout — it is not a test (no TestCase, no asserts) but the filename `test_plant_apis.py` implies pytest will collect it; this can cause unexpected real API calls during test runs and inflate API costs.

- **Reviewer:** test-quality-reviewer
- **Rule:** external-api isolation
- **Suggested fix:** Rename to `verify_plant_apis.py` (or set pytest collect_ignore) so test runners do not pick it up; document as manual smoke command.

### `backend/apps/plant_identification/models.py`

**#609** Line 2289: PlantSpeciesPage.get_context dereferences self.plant_species.family with no None guard, but plant_species is null=True/blank=True (line 2211); template rendering of pages without a species link will crash.

- **Reviewer:** wagtail-reviewer
- **Rule:** —
- **Suggested fix:** Guard with `if self.plant_species:` before computing related_plants and care_guide.

### `backend/apps/plant_identification/permissions.py`

**#610** Line 103: IsAuthenticatedOrAnonymousWithStrictRateLimit unconditionally returns True and depends entirely on an external @ratelimit decorator; if a view forgets to apply the decorator (or the decorator misconfigures the key), there is no defence-in-depth and anonymous abuse of paid APIs is possible.

- **Reviewer:** security-reviewer
- **Rule:** defence-in-depth for paid third-party API quota
- **Suggested fix:** Document loudly in the docstring (and ideally enforce via a view-level check or test) that this class MUST be paired with @ratelimit; consider asserting at view init that a ratelimit decorator is present.

### `backend/apps/plant_identification/serializers.py`

**#611** Line 50: PlantIdentificationRequestSerializer exposes integer 'id' alongside UUID 'request_id' — inconsistent with project UUID-first convention; clients may rely on integer IDs.

- **Reviewer:** api-design-reviewer
- **Rule:** UUID Endpoints checklist
- **Suggested fix:** Drop 'id' from fields list and rely on UUID for external references.

**#612** Line 50: PlantIdentificationRequestSerializer doesn't validate `latitude`/`longitude` ranges; raw -123 / 999 values land in DB.

- **Reviewer:** django-drf-reviewer
- **Rule:** input-validation
- **Suggested fix:** Add validators or a validate() method enforcing -90<=lat<=90, -180<=lon<=180.

### `backend/apps/plant_identification/services/ai_care_service.py`

**#613** Line 27: AIPlantCareService.**init** has no type hints and no return type annotation; service-method type-hint rule applies.

- **Reviewer:** django-drf-reviewer
- **Rule:** type hints on service methods
- **Suggested fix:** Add `-> None` return annotation and type-hint the assigned settings.

### `backend/apps/plant_identification/services/ai_image_service.py`

**#614** Line 73: DALL-E botanical prompts (_create_botanical_prompt) are defined inside the service module rather than centralized in an ai_integration.py — the wagtail checklist requires AI prompts to live in ai_integration.py, not scattered through views/services.

- **Reviewer:** wagtail-reviewer
- **Rule:** wagtail checklist: AI Integration — prompts in ai_integration.py
- **Suggested fix:** Move base_prompts dict and_create_botanical_prompt to apps/plant_identification/ai_integration.py and import from there.

### `backend/apps/plant_identification/services/disease_diagnosis_service.py`

**#615** Line 29: DiseaseAutostorageService.**init** and several helper methods lack type annotations; service layer rule mandates them.

- **Reviewer:** django-drf-reviewer
- **Rule:** type hints
- **Suggested fix:** Add full type annotations to all helper methods.

### `backend/apps/plant_identification/services/identification_service.py`

**#616** Line 33: PlantIdentificationService.**init** lacks return annotation; downstream methods like _create_fallback_results,_update_species_with_data lack return-type hints.

- **Reviewer:** django-drf-reviewer
- **Rule:** type hints
- **Suggested fix:** Add `-> None` to **init** and annotate helper methods.

### `backend/apps/plant_identification/services/monitoring_service.py`

**#617** Line 52: record_api_call uses non-atomic cache.get + cache.set increment; concurrent workers will lose updates and undercount API calls used for alerts.

- **Reviewer:** django-drf-reviewer
- **Rule:** concurrency
- **Suggested fix:** Use cache.incr() (django-redis) or Redis INCR primitive for atomic counters.

### `backend/apps/plant_identification/services/plant_id_service.py`

**#618** Line 374: Cache TTL set to CACHE_TIMEOUT_24_HOURS (86400s) but PLANT_ID_CACHE_TIMEOUT (30 min) is imported and unused — duplicate constant intent.

- **Reviewer:** django-drf-reviewer
- **Rule:** no magic numbers consistency
- **Suggested fix:** Either use PLANT_ID_CACHE_TIMEOUT or remove the unused import.

### `backend/apps/plant_identification/services/quota_manager.py`

**#619** Line 78: datetime.utcnow() is deprecated in Python 3.12+ and silently produces naive UTC datetimes; quota expiry math will break on timezone-aware deployments.

- **Reviewer:** django-drf-reviewer
- **Rule:** deprecation
- **Suggested fix:** Use `datetime.now(timezone.utc)` and aware arithmetic.

### `backend/apps/plant_identification/tasks.py`

**#620** Line 15: Missing explicit task name — relies on auto-generated `apps.plant_identification.tasks.run_identification` which is fine but explicit `name=` makes refactors safer; also missing `on_failure` handler for a task that calls external services (Plant.id/PlantNet).

- **Reviewer:** celery-async-reviewer
- **Rule:** checklist: on_failure handler required for tasks that interact with external services
- **Suggested fix:** Subclass Task with on_failure that marks req.status='failed' and emits the websocket error event, so terminal failure after exhausted retries is consistent.

**#621** Line 47: Channel layer `group_send` exceptions are silently swallowed with no logging, making websocket delivery failures invisible in production.

- **Reviewer:** celery-async-reviewer
- **Rule:** checklist: Failures must be logged with [CELERY] prefix and task ID for traceability
- **Suggested fix:** Replace `pass` with `logger.warning('[CELERY] websocket emit failed for %s', request_uuid, exc_info=True)`.

**#622** Line 74: RateLimitExceeded retry uses `self.retry()` but the task is also configured with `autoretry_for=(Exception,)` and `max_retries=5`; the manual retry counts against the same budget, so a noisy upstream rate-limiter can exhaust retries before transient network errors get a chance.

- **Reviewer:** celery-async-reviewer
- **Rule:** checklist: max_retries must be set; permanent errors must NOT consume retry budget
- **Suggested fix:** Either give RateLimitExceeded its own higher max_retries via `self.retry(exc=e, countdown=retry_in, max_retries=10)` or split into a dedicated retry-policy task.

**#623** Line 75: Bare `except Exception` swallows then re-raises but the inner `req.save` is wrapped in another bare except that silently swallows DB write failures, hiding the failure-to-mark-failed condition.

- **Reviewer:** celery-async-reviewer
- **Rule:** checklist: Task failures must not silently swallow exceptions — always log or re-raise
- **Suggested fix:** Log the inner save failure with [CELERY] prefix and request_uuid before passing.

### `backend/apps/plant_identification/test_api.py`

**#624** Line 178: Loose assertion: assertIn(process_resp.status_code, [HTTP_200_OK, HTTP_400_BAD_REQUEST]) accepts both success and validation failure, masking regressions in the manual processing endpoint.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion strictness
- **Suggested fix:** Pin to the documented contract (200 expected here since mock supplies a result) and split bad-input cases into a separate test.

**#625** Line 451: TestAPIPerformance class is named 'Performance' but contains zero query-count assertions — without assertNumQueries, performance regressions (N+1) cannot be caught.

- **Reviewer:** test-quality-reviewer
- **Rule:** performance/query-optimization.md — strict equality query counts
- **Suggested fix:** Wrap list calls with self.assertNumQueries(N) and document why N is the expected value (e.g. 'select_related on user, family').

### `backend/apps/plant_identification/test_circuit_breaker_locks.py`

**#626** Line 252: test_concurrent_requests_cache_stampede_scenario uses a 0.1s time.sleep inside the mocked API call but only asserts api_call_count > 0 — it does not actually verify that the distributed lock prevents duplicate calls, defeating the test's stated purpose.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion strictness — assert the actual invariant the test name promises
- **Suggested fix:** Assert api_call_count == 1 (with real Redis) or restructure the test to use a real redis lock + threads, otherwise rename it as a smoke test.

### `backend/apps/plant_identification/test_executor_caching.py`

**#627** Line 105: test_cleanup_executor_sets_null contains a `global _EXECUTOR` declaration but never reads/writes _EXECUTOR — the global is dead code and the comment admits the test cannot verify the intended invariant.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion strictness — test must verify the documented behaviour
- **Suggested fix:** Import _EXECUTOR via the module (services.combined_identification_service._EXECUTOR) and assert it is None after _cleanup_executor().

**#628** Line 505: test_cache_respects_ttl uses time.sleep(1.1) which adds real latency to the suite and is flaky on slow CI; TTL behaviour should be exercised through the cache contract, not a literal sleep.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality-reviewer: avoid sleep-based assertions
- **Suggested fix:** Use freezegun or mock cache backend to advance time, or remove this test (it tests Django's own cache semantics, not project code).

### `backend/apps/plant_identification/test_services.py`

**#629** Line 287: test_api_rate_limit_handling mocks a 429 response but does not set raise_for_status side_effect, so the test passes via empty list rather than verifying that a real 429 path is handled — possibly hiding a regression.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality-reviewer: mock responses must reflect real API shape
- **Suggested fix:** Set mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('429') to exercise the actual error/retry path.

**#630** Line 416: test_api_cost_tracking conditionally asserts based on hasattr — silently passes if get_total_cost is missing, providing no coverage signal.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality-reviewer: tests must assert deterministic behaviour
- **Suggested fix:** Either delete the test or unconditionally call get_total_cost and add a TODO/skip when feature is implemented.

**#631** Line 521: Loose assertions like assertIn(status, ['identified', 'needs_help']) accept either outcome, hiding actual behaviour and silently passing if the service swaps states.

- **Reviewer:** test-quality-reviewer
- **Rule:** assertion strictness — one expected value per assertion
- **Suggested fix:** Pin the expected status to a single value matching current implementation; if both are valid, split into two tests with different mock fixtures.

**#632** Line 631: test_service_fallback_mechanisms is an empty stub (only `pass`) — it gives a false sense of coverage and is misleading in a coverage report.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality-reviewer: no skeleton tests
- **Suggested fix:** Implement the test or remove it (and add a TODO ticket) — empty tests pass and erode coverage credibility.

**#633** Line 638: test_disease_diagnosis_integration sets up a mock and then never calls the system under test (`pass` body) — the mock fixture and the test body do not interact.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-quality-reviewer: tests must exercise the SUT
- **Suggested fix:** Implement the integration assertion or delete the stub.

### `backend/apps/plant_identification/tests.py`

**#634** Line 1: tests.py is effectively empty (just a comment) — coverage of plant_identification public API depends entirely on the separate test_*.py files; misleading scaffold.

- **Reviewer:** django-drf-reviewer
- **Rule:** test-quality
- **Suggested fix:** Either remove tests.py or add at least a smoke test importing the package's test modules.

### `backend/apps/plant_identification/utils/file_validation.py`

**#635** Line 26: validate_image_file is missing a max-file-size layer (4-layer requirement: extension, MIME, size, PIL). Size is enforced separately in simple_views.py only — other upload entry points may skip it.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/file-upload (4-layer validation)
- **Suggested fix:** Add a size guard inside validate_image_file using a constant; remove the duplicate check in simple_views.

### `backend/apps/plant_identification/views.py`

**#636** Line 13: Module-level imports include `models` from django.db twice (line 16 imports `models`, then F separately) and re-imports inside functions (line 305, 642) — minor maintainability concern.

- **Reviewer:** django-drf-reviewer
- **Rule:** code quality
- **Suggested fix:** Consolidate model imports at module top.

**#637** Line 24: Silent fallback `def ratelimit(**kwargs)` no-op when django-ratelimit is missing leaves production unrestricted; should raise ImportError instead.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/rate-limiting
- **Suggested fix:** Remove the try/except fallback; require django-ratelimit as a hard dependency.

**#638** Line 73: PlantSpeciesViewSet.get_queryset() runs scientific_name__icontains | common_names__icontains | family__icontains across many rows without trigram index — slow for the public species browser.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Same trigram GIN index recommendation; also consider PostgreSQL full-text search (SearchVector field).

**#639** Line 141: User-controlled filename logged via f-string (image_file.name) — log injection / PII risk.

- **Reviewer:** django-drf-reviewer
- **Rule:** security/input-validation (log forging)
- **Suggested fix:** Use structured logging args (`logger.info('...', extra={'file': name})`) and sanitize newlines.

**#640** Line 222: PlantIdentificationRequestViewSet.results action loads results via .all().order_by(...) without select_related on identified_species/identified_by — serializer accesses these fields → N+1 on action.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** results = request_obj.identification_results.select_related('identified_species', 'identified_by').order_by(...).

**#641** Line 490: UserPlantViewSet.get_queryset() lacks select_related — UserPlantSerializer reads species, collection, user, from_identification_request per row → N+1 on list.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** select_related('user', 'species', 'collection', 'from_identification_request') in get_queryset().

**#642** Line 504: get_care_instructions: same `user_or_ip` key inconsistency with IsAuthenticated permission.

- **Reviewer:** django-drf-reviewer
- **Rule:** rate-limiting consistency
- **Suggested fix:** Use key='user'.

**#643** Line 807: PlantDiseaseRequestViewSet.results action returns diagnosis_results.all() without select_related on identified_disease, request, diagnosed_by → N+1 in serializer.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Add select_related('identified_disease', 'request', 'diagnosed_by').

**#644** Line 1011: PlantDiseaseDatabaseViewSet.queryset and get_queryset() do not annotate affected_plant_count, but serializer calls obj.affected_plants.count() per row — N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** Annotate affected_plant_count=Count('affected_plants') in get_queryset().

**#645** Line 1066: SavedDiagnosisViewSet.get_queryset() lacks select_related — SavedDiagnosisSerializer nests diagnosis_data (a full PlantDiseaseResultSerializer) and disease_name via FK chain → N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** select_related('diagnosis_result', 'diagnosis_result__request', 'diagnosis_result__diagnosed_by').

**#646** Line 1083: SavedCareInstructionsViewSet.get_queryset() lacks select_related('plant_species') — serializer embeds PlantSpeciesSerializer per row → N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** select_related('plant_species', 'user').

**#647** Line 1106: TreatmentAttemptViewSet.get_queryset() lacks select_related — serializer reads diagnosis_result and user per row → N+1.

- **Reviewer:** performance-reviewer
- **Rule:** patterns/performance/query-optimization.md
- **Suggested fix:** select_related('diagnosis_result', 'diagnosis_result__request', 'user').

**#648** Line 1484: regenerate_care_instructions: rate-limit decorator uses `key='user_or_ip'` but endpoint requires authentication — ip fallback is dead code and inconsistent with the policy doc.

- **Reviewer:** django-drf-reviewer
- **Rule:** rate-limiting consistency
- **Suggested fix:** Use key='user' since IsAuthenticated is enforced.

### `backend/apps/search/__init__.py`

**#649** Line 1: Search app does not register models with auditlog despite storing user search history (GDPR-relevant).

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md - GDPR auditlog
- **Suggested fix:** Add auditlog.py registering SearchQuery, SavedSearch, UserSearchPreferences.

### `backend/apps/search/admin.py`

**#650** Line 43: reverse('admin:auth_user_change', ...) hardcodes auth.User but project uses get_user_model(); URL will 404 if a custom User app_label/model is configured.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Build URL via get_user_model()._meta.app_label / model_name.

**#651** Line 74: Same auth.User reverse() issue in UserSearchPreferencesAdmin.user_link.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Derive admin URL from the active user model meta.

**#652** Line 100: Same auth.User reverse() issue in SavedSearchAdmin.user_link.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Use dynamic admin URL based on settings.AUTH_USER_MODEL.

**#653** Line 137: Same auth.User reverse() issue in SearchResultClickAdmin.user_link.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Use dynamic admin URL from get_user_model().

### `backend/apps/search/models.py`

**#654** Line 110: UserSearchPreferences.default_content_type max_length=20 but SearchQuery.content_type max_length=100; same choices used in both — pick one length.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Standardize max_length across SearchQuery, UserSearchPreferences, SavedSearch.

**#655** Line 161: SavedSearch has no DB unique constraint on (user, name); validate_name relies solely on race-prone Python check.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Add UniqueConstraint(fields=['user', 'name']) in Meta.constraints.

### `backend/apps/search/serializers.py`

**#656** Line 139: SearchResultSerializer.created_at is typed as CharField rather than DateTimeField, weakening serializer type safety and OpenAPI schema (no format=date-time).

- **Reviewer:** api-design-reviewer
- **Rule:** API checklist: serializers must have explicit type annotations
- **Suggested fix:** Use serializers.DateTimeField(required=False, allow_null=True) so OpenAPI emits a proper date-time type.

**#657** Line 162: pagination, result_counts, and applied_filters are bare DictField with no nested serializer, producing an opaque OpenAPI schema (additionalProperties: true) for these response components.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI: response components should have explicit shape
- **Suggested fix:** Define dedicated PaginationSerializer / ResultCountsSerializer / AppliedFiltersSerializer and reference them here.

**#658** Line 169: SearchResponseSerializer mixes success payload with an optional 'error' field, which conflicts with the project's standard error envelope shape ({"error": "message"}) returned via DRF exception handling.

- **Reviewer:** api-design-reviewer
- **Rule:** API checklist: error responses must use consistent shape
- **Suggested fix:** Remove the 'error' field; surface failures by raising a DRF exception so the standard handler emits the canonical {"error": ...} response.

**#659** Line 261: top_queries, search_trends, zero_result_queries, and content_types_searched are bare ListField with no child= argument, so OpenAPI schema items are untyped.

- **Reviewer:** api-design-reviewer
- **Rule:** OpenAPI: list fields should declare child= for typed items
- **Suggested fix:** Add child=serializers.CharField() (or a nested serializer) to each ListField so the schema documents item type.

### `backend/apps/search/services/search_service.py`

**#660** Line 29: Hardcoded weight letters in self.search_weights are unused magic values (the dict is never read elsewhere); either use them or remove.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Either reference these constants in *search** methods or delete the dead config.

**#661** Line 36: search() lacks type hint on `search_query` parameter (forwarded as PgSearchQuery) and other internal helpers omit the search_query type entirely; convention requires type hints on all service methods.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md - type hints
- **Suggested fix:** Add explicit type hints (PgSearchQuery, return annotations on *search**).

**#662** Line 74: PgSearchQuery(query) uses default plainto_tsquery without explicit search_type; user-supplied query strings can include parser-significant chars. Use search_type='websearch' for safer parsing.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** PgSearchQuery(query, search_type='websearch').

**#663** Line 99: Each content type is hard-limited to the top 20 results before pagination, but total_count is reported from len(sorted_results) (max 80) while result_counts uses qs.count() of the unlimited match set; pagination beyond page 4 is impossible and counts are inconsistent between fields.

- **Reviewer:** performance-reviewer
- **Rule:** Pagination must operate on the canonical queryset
- **Suggested fix:** Push pagination into the SQL layer (LIMIT/OFFSET on a UNION ALL or per-content-type) instead of slicing Python lists.

**#664** Line 113: Logging uses f-strings without bracketed prefix (e.g., [SEARCH] or [PERF]); convention requires bracketed log categories.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md - bracketed log prefixes
- **Suggested fix:** Prefix logger.error/info messages with [SEARCH] or [PERF].

**#665** Line 142: Bare except Exception catches all errors and surfaces str(e) into the returned dict (later flowed to client); also masks bugs.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Catch specific exceptions, log full trace, return a generic error indicator.

**#666** Line 169: Hardcoded 20-result-per-content-type cap is a magic number that should live in constants.py.

- **Reviewer:** django-drf-reviewer
- **Rule:** backend/CLAUDE.md - no magic numbers
- **Suggested fix:** Move to apps/search/constants.py (e.g., MAX_RESULTS_PER_CONTENT_TYPE).

**#667** Line 367: SearchQuery.objects.create runs synchronously in the request path on every search; under load this adds DB write latency and contention to a read-heavy endpoint.

- **Reviewer:** performance-reviewer
- **Rule:** Decouple analytics writes from request path
- **Suggested fix:** Dispatch the log write to a Celery task (transaction.on_commit) or buffer in Redis and flush asynchronously.

**#668** Line 368: content_type field max_length=100 stores comma-joined values; if all 4 future content types are added the joined string could exceed expected single-choice semantics, breaking the choices validator.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Store content_types as JSON list or use M2M; do not bypass choices validation by joining.

**#669** Line 408: query_text__icontains uses raw partial_query without escaping % and _, so user-supplied wildcards leak into LIKE patterns and force seq scans (project convention violation).

- **Reviewer:** performance-reviewer
- **Rule:** backend/CLAUDE.md (escape % and _ before icontains)
- **Suggested fix:** Apply partial_query.replace('%', r'\%').replace('_', r'\_') before filtering, or use trigram similarity with an index.

**#670** Line 420: PlantSpecies icontains lookups on scientific_name and common_names do not escape % and _ wildcards and are not backed by a trigram index, causing full table scans for autocomplete suggestions on every keystroke-style request.

- **Reviewer:** performance-reviewer
- **Rule:** backend/CLAUDE.md + query-optimization.md
- **Suggested fix:** Escape wildcards and add a pg_trgm GIN index on scientific_name/common_names, or use SearchVector with the persisted search_vector.

### `backend/apps/search/signals.py`

**#671** Line 39: post_save on Post triggers an extra SearchVector UPDATE on Topic (joining first_post__content) for every post save; under high forum activity this multiplies per-save DB work and serializes behind the request.

- **Reviewer:** performance-reviewer
- **Rule:** Defer expensive index updates
- **Suggested fix:** Move the topic re-index branch into a Celery task gated by transaction.on_commit.

**#672** Line 95: post_save on BlogPostPage runs an UPDATE with SearchVector('title')+('intro')+('body') synchronously inside the save transaction; body is a StreamField that can be large, making page saves slow and amplifying cost when Wagtail re-saves pages during publish workflows.

- **Reviewer:** performance-reviewer
- **Rule:** Defer expensive index updates
- **Suggested fix:** Wrap in transaction.on_commit and dispatch via Celery to update the search vector asynchronously.

### `backend/apps/search/views.py`

**#673** Line 99: Silently falls back to returning unserialized raw search_results dict when SearchResponseSerializer is invalid; bypasses contract checks.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Return a 500 (or log+sanitize) instead of returning unvalidated data.

**#674** Line 174: perform_destroy soft-deletes by setting is_active=False; since the queryset on this view includes all (active and inactive) but list view filters is_active=True, deleting twice is silent. No explicit issue but the asymmetry between get_queryset on list vs detail allows clients to keep 'deleting' inactive saved searches with 200 responses.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Either filter detail to active only or return 410 Gone for already-inactive instances.

**#675** Line 284: Same silent fallback to raw data when SearchFiltersSerializer is invalid.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Either fix the data shape or surface an error.

**#676** Line 307: int(request.GET.get('days', 30)) lacks validation and can raise ValueError on bad input or accept absurd values causing huge analytics scans.

- **Reviewer:** django-drf-reviewer
- **Rule:** patterns/security/input-validation.md
- **Suggested fix:** Use a serializer or clamp/validate days within an allowed range (e.g., 1-365).

**#677** Line 367: Silent fallback to raw analytics_data when SearchAnalyticsSerializer is invalid hides bugs.

- **Reviewer:** django-drf-reviewer
- **Rule:** —
- **Suggested fix:** Return 500 on serialization failure or correct the data shape.

**#678** Line 417: track_search_click writes a SearchResultClick row synchronously on every click ping; this is a fire-and-forget analytics signal that should be queued to keep the endpoint cheap and avoid DB write contention during traffic spikes.

- **Reviewer:** performance-reviewer
- **Rule:** Decouple analytics writes from request path
- **Suggested fix:** Move the create() call to a Celery task or batch via Redis stream.

### `backend/apps/users/auditlog.py`

**#679** Line 11: Audit log registration omits sensitive privacy/PII models created in this app (UserMessage, OnboardingAnalytics with ip_address/user_agent, PushSubscription, CareReminder, OnboardingProgress) — incomplete GDPR Article 30 coverage as required by the project pattern.

- **Reviewer:** django-drf-reviewer
- **Rule:** gdpr-auditlog-coverage
- **Suggested fix:** Register UserMessage and OnboardingAnalytics (at minimum) with appropriate include_fields.

### `backend/apps/users/authentication.py`

**#680** Line 137: Cookies are set with `domain=None` in production; if the deployment serves API and frontend from different subdomains, the access_token cookie will not be sent and developers may compensate by widening to a parent domain — better to make this explicit per environment.

- **Reviewer:** security-reviewer
- **Rule:** Cookie scoping
- **Suggested fix:** Read cookie domain from settings (e.g. `JWT_COOKIE_DOMAIN`) so prod can scope cookies correctly without relying on host-only behaviour.

### `backend/apps/users/email_preferences_views.py`

**#681** Line 89: Calling `User.objects.get(uuid=user_uuid)` with raw query-string user_uuid — if user_uuid contains non-UUID characters, Django raises ValueError (not DoesNotExist), bypassing the friendly error template and returning 500.

- **Reviewer:** django-drf-reviewer
- **Rule:** input-validation
- **Suggested fix:** Wrap in try/except (User.DoesNotExist, ValueError, ValidationError).

### `backend/apps/users/firebase_auth_views.py`

**#682** Line 197: Broad `except Exception` returns a generic 500 but logs `str(e)` directly, which can leak stack-trace-like internals if the exception message contains paths or DB driver errors.

- **Reviewer:** security-reviewer
- **Rule:** OWASP A09 — error handling
- **Suggested fix:** Log the exception with `logger.exception(...)` to a server-only sink and return a stable opaque error to the client without echoing exception text.

**#683** Line 260: Bare `except Exception as e:` after User.objects.create swallows IntegrityError silently — no rollback wrapper since there's no transaction; partial state possible.

- **Reviewer:** django-drf-reviewer
- **Rule:** transactional-integrity
- **Suggested fix:** Wrap user creation in transaction.atomic() and let specific exceptions surface.

### `backend/apps/users/management/commands/setup_trust_levels.py`

**#684** Line 95: Two follow-up queries (image_uploaders, staff_uploaders) ignore overlap (a staff user with trust_level 'basic' is double-counted), and update_all_user_trust_levels recomputes per-user without a transaction.

- **Reviewer:** django-drf-reviewer
- **Rule:** stat-correctness
- **Suggested fix:** Combine into a single query with Q-conditioned annotation.

### `backend/apps/users/oauth_urls.py`

**#685** Line 9: URL patterns `login/` and `callback/` are registered without a `<provider>` segment, but `oauth_login(request, provider)` and `oauth_callback(request, provider)` require it — these routes will raise TypeError when hit, indicating either dead code or missing routing that may bypass intended URL structure (e.g. ratelimit keying by path).

- **Reviewer:** security-reviewer
- **Rule:** URL/view contract mismatch
- **Suggested fix:** Change paths to `'login/<str:provider>/'` and `'callback/<str:provider>/'`, or remove the file if the real routing lives elsewhere.

### `backend/apps/users/oauth_views.py`

**#686** Line 36: FRONTEND_BASE_URL falls back to a hardcoded <http://localhost:3000> when the setting is missing in production, which is the wrong frontend port (the project uses 5174) and could leak OAuth success indicators to an unintended origin.

- **Reviewer:** security-reviewer
- **Rule:** CLAUDE.md (port 5174 for React)
- **Suggested fix:** Make FRONTEND_BASE_URL required in non-DEBUG settings and remove the localhost:3000 default, or align the default with the documented dev port (5174).

**#687** Line 64: OAuth authorize URLs are built by f-string concatenation without URL-encoding scope/redirect_uri values, so a misconfigured setting containing reserved characters silently breaks the flow or could be abused if values become user-influenced.

- **Reviewer:** security-reviewer
- **Rule:** RFC 3986 percent-encoding
- **Suggested fix:** Use `urllib.parse.urlencode` to assemble the query string.

**#688** Line 162: Calling django_login() establishes a session in addition to the JWT cookies but without rotating the session key (`request.session.cycle_key()`), preserving any attacker-supplied pre-auth session and enabling session fixation.

- **Reviewer:** security-reviewer
- **Rule:** OWASP Session Fixation
- **Suggested fix:** Call `request.session.cycle_key()` (or use logout+login pattern) before/after django_login to force a fresh session id on authentication.

**#689** Line 174: Bare `except Exception as e:` in oauth_callback redirects to frontend with `error=callback_failed` — generic error swallowing makes OAuth debugging impossible and may hide auth bypass issues in production.

- **Reviewer:** django-drf-reviewer
- **Rule:** exception-specificity
- **Suggested fix:** Catch specific exceptions; let unexpected errors surface to logging/monitoring.

**#690** Line 280: _find_or_create_user creates a UserPlantCollection inside the same flow without a transaction — if collection creation fails after user.create_user, the user is left dangling.

- **Reviewer:** django-drf-reviewer
- **Rule:** transactional-integrity
- **Suggested fix:** Wrap user creation and collection creation in `with transaction.atomic():`.

**#691** Line 322: Username uniqueness loop runs `User.objects.filter(username=...).exists()` in a while loop incrementing a counter — under high collision load (popular email prefixes like 'admin'/'john') this can issue many queries per signup. No cap.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: unbounded query loop
- **Suggested fix:** After 1-2 attempts, fall back to a UUID4 suffix (as firebase_auth_views does) instead of incrementing — bounded queries.

### `backend/apps/users/serializers.py`

**#692** Line 11: No `@extend_schema_serializer` / docstring example for OpenAPI; Swagger consumers cannot discover the duplicate-field aliasing or the registration error responses.

- **Reviewer:** api-design-reviewer
- **Rule:** api-design checklist — OpenAPI schema annotations
- **Suggested fix:** Add `@extend_schema_serializer(examples=[...])` documenting field choices and 400 response shape.

**#693** Line 16: Dual field names `password_confirm` and `confirmPassword` accept either snake_case or camelCase, creating an inconsistent public API contract; pick one canonical name and document it.

- **Reviewer:** api-design-reviewer
- **Rule:** REST API consistency — a single canonical field name per concept
- **Suggested fix:** Standardize on one field name (snake_case `password_confirm`) and have the frontend send that; remove the alias.

**#694** Line 52: Non-field validation errors are raised as plain strings rather than the standard DRF `{"error": "..."}` shape, producing `{"non_field_errors": ["..."]}` which is inconsistent with the project's documented error shape.

- **Reviewer:** api-design-reviewer
- **Rule:** api-design checklist — consistent error response shape `{"error": "message"}`
- **Suggested fix:** Use a consistent key (e.g., raise with `{"error": "..."}`) or document that registration uses DRF's default `non_field_errors` shape.

**#695** Line 86: `UserSerializer.Meta` exposes integer `id` as the public identifier; the project standard is UUID-based lookups and UUID slug refs to avoid leaking sequential IDs.

- **Reviewer:** api-design-reviewer
- **Rule:** api-design checklist — UUID endpoints / `slug_field='uuid'`
- **Suggested fix:** If `User` has a `uuid` field, expose it (and use it for lookups) instead of/along with integer `id`.

**#696** Line 149: `UserPlantCollectionSerializer.Meta` exposes integer `id` rather than a UUID slug; collections are user-owned resources that should use the project's UUID lookup pattern.

- **Reviewer:** api-design-reviewer
- **Rule:** api-design checklist — UUID lookup pattern
- **Suggested fix:** Add a `uuid` field to the model (if missing) and expose `uuid` instead of/in addition to `id` with `lookup_field='uuid'` on the ViewSet.

**#697** Line 156: `get_plants` lazy-imports `UserPlantSerializer` and serializes the full nested list on every read of a collection, double-loading data without an opt-in/expansion flag and risking large payloads.

- **Reviewer:** api-design-reviewer
- **Rule:** api-design — nested serializers should avoid double-loading; prefer expansion or a separate endpoint
- **Suggested fix:** Move plants to a dedicated `/collections/<uuid>/plants/` endpoint or gate inclusion behind an `?include=plants` query param; at minimum cap the page size.

### `backend/apps/users/services.py`

**#698** Line 38: Service methods (create_trust_level_groups, setup_forum_permissions, assign_user_to_trust_group, update_all_user_trust_levels, check_user_can_attach_files, update_user_post_count) lack type hints on parameters and return types — violates project 'all service methods must have type hints' rule.

- **Reviewer:** django-drf-reviewer
- **Rule:** type-hints
- **Suggested fix:** Add `-> Dict[str, Group]`, `-> None`, etc. on every staticmethod.

**#699** Line 39: TrustLevelService methods use `print(...)` for logging instead of logger.info/warning with bracketed prefixes — violates project log convention and pollutes stdout in production.

- **Reviewer:** django-drf-reviewer
- **Rule:** logging-convention
- **Suggested fix:** Replace prints with `logger.info('[TRUST_LEVEL] ...')` etc.

**#700** Line 132: update_all_user_trust_levels iterates `User.objects.all()` without batching — for any non-trivial user table this loads everything into memory and runs O(N) save() calls; will timeout management commands at scale.

- **Reviewer:** django-drf-reviewer
- **Rule:** bulk-iteration
- **Suggested fix:** Use .iterator(chunk_size=...) and consider bulk_update for trust_level changes.

**#701** Line 304: send_care_reminder_push evaluates the subscriptions queryset multiple times: subscriptions.exists() (query 1), iteration (query 2 — full SELECT), then subscriptions.count() twice (queries 3 & 4). Each .count() re-issues SQL even though the QS is already in memory.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: redundant queryset re-evaluation
- **Suggested fix:** Materialize once: subs = list(reminder.user.push_subscriptions.filter(is_active=True)); use len(subs) and `if not subs:` thereafter.

### `backend/apps/users/tests/test_account_lockout.py`

**#702** Line 296: test_lockout_security_alert_triggered patches the implementation method `_trigger_security_alert` instead of observing the externally visible side effect, coupling the test to internal naming.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: test behaviour, not implementation
- **Suggested fix:** Assert on the observable outcome (e.g., a security log entry, or an audit record) rather than mocking the private method.

**#703** Line 429: test_complete_lockout_flow_via_api accepts 401, 403, or 429 for intermediate attempts and 429-or-403 for the lockout, then conditionally skips the email assertion if rate-limit fired first; the multi-branch escape hatch lets real lockout regressions pass undetected.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness — one assertion concept per test
- **Suggested fix:** Disable the per-IP rate limiter via override_settings/cache.clear so the test can deterministically reach the 10-attempt lockout, then assert exact codes and email count.

### `backend/apps/users/tests/test_cookie_jwt_authentication.py`

**#704** Line 64: test_set_jwt_cookies and test_cookie_samesite_attribute branch on settings.DEBUG; under pytest-django DEBUG is forced to False, so the DEBUG=True branch (Lax SameSite, no Secure flag) is never exercised in CI.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: coverage / strict assertions
- **Suggested fix:** Use override_settings(DEBUG=True) for one test and DEBUG=False for another so both branches are covered.

**#705** Line 84: test_clear_jwt_cookies wraps each cookie assertion in `if access_cookie:`/`if refresh_cookie:`, so if clear_jwt_cookies stops setting the cookies entirely (a real regression) the test still passes silently.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness
- **Suggested fix:** Assert the cookies are present first, then assert max-age == 0.

**#706** Line 248: test_logout_clears_cookies uses `if access_cookie:` so a regression where logout no longer touches the cookie would not fail the test.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness
- **Suggested fix:** Drop the `if` guard and assert the cookie is set with max-age == 0.

### `backend/apps/users/tests/test_ip_spoofing_protection.py`

**#707** Line 54: test_get_client_ip_with_x_forwarded_for asserts the IP is in any of three values ['203.0.113.1', '198.51.100.1', '10.0.0.1']; this passes for any value the function returns and cannot detect a regression.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness
- **Suggested fix:** Pin the expected IP to whichever the documented contract dictates (rightmost trusted vs leftmost client) and use assertEqual.

**#708** Line 133: test_get_client_ip_ipv6_in_x_forwarded_for uses assertIn against the full set of candidate IPs, so any returned value passes.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness
- **Suggested fix:** Assert the exact expected IP (likely '2001:db8::1' if the function picks the first valid IP).

**#709** Line 203: test_multiple_proxies_in_x_forwarded_for asserts the result is in any of the four IPs, defeating the purpose of testing proxy-chain handling.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness
- **Suggested fix:** Codify the trusted-proxy policy and assert the single expected client IP.

**#710** Line 263: test_failed_login_tracking_with_spoofed_ip asserts only that some warning containing 'Invalid IP' OR 'Failed login' was logged, so even if invalid-IP detection regresses the test still passes (the 'Failed login' branch always fires).

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness
- **Suggested fix:** Assert specifically that an 'Invalid IP' warning fired AND that the tracked IP equals REMOTE_ADDR.

### `backend/apps/users/tests/test_rate_limiting.py`

**#711** Line 150: test_successful_login_not_rate_limited accepts both 200 and 429 as valid outcomes, which means the test cannot fail when the endpoint silently rate-limits successful logins (the documented expectation).

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: assertion strictness
- **Suggested fix:** Decide the contract (rate limit applies vs. exempts successes) and assert the exact expected status; if behavior is config-dependent, split into two tests with override_settings.

### `backend/apps/users/tests/test_token_refresh.py`

**#712** Line 542: test_production_vs_debug_token_lifetimes only asserts when ACCESS_TOKEN_LIFETIME_DEBUG is set, so if the key is missing in settings the test is a silent no-op.

- **Reviewer:** test-quality-reviewer
- **Rule:** checklist: coverage — explicit branch coverage
- **Suggested fix:** Either require the setting and assert directly, or split into two tests using override_settings to exercise both states.

### `backend/apps/users/views.py`

**#713** Line 14: Magic numbers throughout: pagination size 10 (line 465), search snippet 50 (line 843), recent activity 8 (line 685), 6-month ICS export 180 (line 1417), days_ahead cap 365 (line 1501), 30-day window. None come from constants.py per the project convention.

- **Reviewer:** django-drf-reviewer
- **Rule:** no-magic-numbers
- **Suggested fix:** Move to apps/users/constants.py: USER_SEARCHES_PAGE_SIZE, RECENT_ACTIVITY_LIMIT, ICS_EXPORT_DAYS, etc.

**#714** Line 31: create_error_response signature uses `details: str = None` without Optional[str] annotation; also `status_code: int = status.HTTP_400_BAD_REQUEST` is fine. Other helpers in this file (login, register, etc.) lack type hints on local variables — minor consistency concern.

- **Reviewer:** django-drf-reviewer
- **Rule:** type-hints
- **Suggested fix:** Use `details: Optional[str] = None`.

**#715** Line 444: Same 204-with-body pattern: user_collection_detail DELETE returns a message dict.

- **Reviewer:** django-drf-reviewer
- **Rule:** http-204-no-body
- **Suggested fix:** Drop the body for 204.

**#716** Line 449: previous_searches uses `select_related('assigned_to_collection').prefetch_related('identification_results__identified_species')` but the field name is plural; does not use `.only()` to limit columns despite the dashboard_stats pattern. Also page_size 10 is hardcoded.

- **Reviewer:** django-drf-reviewer
- **Rule:** query-optimization
- **Suggested fix:** Add .only(...) for required columns and move page size to constants.py.

**#717** Line 661: dashboard_stats materializes Topic.first_post_id list with `list(first_post_ids)` and then uses `id__in=list(...)` — for users with many topics this loads all IDs into Python before sending an IN clause; for moderately active users it works, but it should use a subquery to keep evaluation in DB.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: materialized list passed to id__in
- **Suggested fix:** Drop `list(...)` and pass the values_list QuerySet directly to id__in — Django turns it into a subquery.

**#718** Line 726: forum_permissions calls request.user.groups.all() and TrustLevelService.check_user_can_attach_files (which instantiates Machina's PermissionHandler) on every request — no caching. This endpoint is hit on most authenticated frontend page loads.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: hot endpoint without Redis cache layer
- **Suggested fix:** Cache the computed permission payload per user keyed by trust_level + group membership hash for ~5 minutes; invalidate on trust-level change signal.

**#719** Line 1051: DELETE care_reminder_detail returns Response(..., HTTP_204_NO_CONTENT) WITH a body — RFC 7230 forbids 204 responses from having a body and DRF's renderer may strip or some clients reject this.

- **Reviewer:** django-drf-reviewer
- **Rule:** http-204-no-body
- **Suggested fix:** Return Response(status=status.HTTP_204_NO_CONTENT) with no message body, or use 200.

**#720** Line 1151: care_reminder_stats issues 4 separate aggregate queries on CareReminder for the same user (count active, count total, aggregate completion stats, aggregate avg/max streak); these can be combined with conditional aggregation into one DB round-trip.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: aggregate fan-out without combining
- **Suggested fix:** Use a single .aggregate(active=Count('id', filter=Q(is_active=True)), total=Count('id'), total_completed=Sum('total_completed'), ...).

**#721** Line 1217: onboarding_progress GET path serializes via dict-by-hand and accesses progress.user.id — get_or_create returned `progress` without select_related('user'), so the .user.id access can hit a follow-up query depending on caching. Minor.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: missing select_related on FK in returned object
- **Suggested fix:** Use OnboardingProgress.objects.select_related('user').get_or_create(user=request.user) or just return request.user.id.

**#722** Line 1217: onboarding_progress uses get_or_create on every GET — this performs a SELECT then an INSERT path inside a transaction. Heavy read endpoint should not implicitly create.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: get_or_create on read path
- **Suggested fix:** Split: try `OnboardingProgress.objects.get(user=request.user)` then create on signup signal (already exists) or return defaults dict if missing.

**#723** Line 1393: export_care_reminders_calendar calls reminders.exists() and then iterates the same queryset, causing the SELECT to run twice (exists() doesn't cache rows for the subsequent iteration).

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: exists() + iteration on same QS = double query
- **Suggested fix:** reminders = list(reminders_qs); if not reminders: return 404 — single SELECT.

**#724** Line 1578: care_reminder_calendar_preview returns reminders.count() at the end after the queryset has already been fully iterated — this triggers a second SELECT COUNT(*) on a row set already in memory.

- **Reviewer:** performance-reviewer
- **Rule:** performance-reviewer: extra .count() after queryset iteration
- **Suggested fix:** Convert to `reminders = list(reminders_qs)` at the top, then use len(reminders) for total_reminders.

### `firebase/firestore.rules`

**#725** Line 25: plant_identifications create allows write but does not constrain field set; client can write status/created_at fields that should be server-controlled.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Firestore rules: use hasOnly() to whitelist fields on create
- **Suggested fix:** Add `&& request.resource.data.keys().hasOnly(['user_id', 'image_url', 'created_at', ...])`

**#726** Line 27: plant_identifications update rule lets the owner mutate any field including user_id, allowing a user to reassign their own document to another user (or to manipulate immutable created_at).

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Firestore rules: prevent owner from mutating identity fields
- **Suggested fix:** Add `&& request.resource.data.user_id == resource.data.user_id` and freeze created_at

**#727** Line 27: Update rules on plant_identifications/user_plants/disease_diagnoses do not pin the user_id field — an owner can rewrite user_id on update, transferring ownership to another uid or breaking referential integrity.

- **Reviewer:** security-reviewer
- **Rule:** firebase/docs/patterns/firestore-rules.md — immutable owner field
- **Suggested fix:** Add '&& request.resource.data.user_id == resource.data.user_id' to each update rule (lines 27, 38, 46) to keep user_id immutable.

**#728** Line 33: user_plants read uses `resource.data.is_public == true` without verifying is_public is actually a boolean, and a missing field evaluates to error which fails closed (acceptable) but should be explicit.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Firestore rules: defensive type checks
- **Suggested fix:** Use `(resource.data.get('is_public', false) == true)`

**#729** Line 38: user_plants update has no field-level guard, so a user can flip is_public on any of their own plants without auditing, and could remove user_id (orphaning the doc from queries).

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Firestore rules: validate immutable fields on update
- **Suggested fix:** Add `&& request.resource.data.user_id == resource.data.user_id`

### `firebase/storage.rules`

**#730** Line 10: isOwner() is not gated by isAuthenticated(); when request.auth is null, request.auth.uid raises an error which Firebase treats as deny but is fragile and inconsistent with firestore.rules helper.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** Defensive helpers: chain auth check before uid access
- **Suggested fix:** Change to `return isAuthenticated() && request.auth.uid == userId;`

**#731** Line 14: isImage() relies solely on client-provided contentType, which is trivially spoofable; combined with no magic-byte validation server-side this allows non-image payloads to be uploaded under image MIME.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** File upload validation: 4-layer check (extension, MIME, size, content)
- **Suggested fix:** Add a Cloud Function trigger that validates magic bytes after upload, or restrict to specific MIME types and add file extension matcher on the path

**#732** Line 18: Storage rules enforce only size + content-type; no file extension whitelist (Layer 1) so users can upload e.g. .exe.jpg-style names that may bypass downstream extension-based handlers.

- **Reviewer:** security-reviewer
- **Rule:** security/file-upload.md — 4-layer validation
- **Suggested fix:** Add a regex on the {imageId} path segment, e.g. imageId.matches('.*\\.(jpg|jpeg|png|webp|heic)$'), to enforce allowed extensions.

### `plant_community_mobile/lib/core/routing/navigation_extensions.dart`

**#733** Line 84: popToHome() pops every route imperatively in a loop and then calls go(home); with go_router this can interact oddly with declarative redirects and is redundant since go(AppRoutes.home) already replaces the stack.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** go_router/declarative-navigation
- **Suggested fix:** Drop the while-pop loop and just call go(AppRoutes.home) (or use context.go with a fresh stack).

### `plant_community_mobile/lib/core/theme/app_typography.dart`

**#734** Line 12: fontFamilySans/fontFamilyMono are defined as CSS-style font stacks with multiple fallbacks separated by commas; Flutter's fontFamily parameter expects a single family name and would treat the entire string as one literal family if used.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** flutter-patterns/typography
- **Suggested fix:** Use a single family name (or supply fontFamilyFallback as a List<String>) instead of a CSS font-stack string.

### `plant_community_mobile/lib/features/garden/models/care_task.dart`

**#735** Line 226: Enum values use snake_case (pest_control, disease_treatment) violating Dart's constant_identifier_names lint and project conventions; should be lowerCamelCase.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** dart-style/constant_identifier_names
- **Suggested fix:** Rename to pestControl/diseaseTreatment and keep the snake_case backend value in the .value field.

### `plant_community_mobile/lib/features/garden/models/garden_plant.dart`

**#736** Line 190: Enum value pest_damaged uses snake_case identifier, violating Dart's constant_identifier_names lint and project conventions.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** dart-style/constant_identifier_names
- **Suggested fix:** Rename to pestDamaged and keep the backend snake_case in .value.

### `plant_community_mobile/lib/features/splash/splash_screen.dart`

**#737** Line 71: Future.delayed for navigation runs even after the user backgrounds/exits; the mounted check is correct but stacking a delayed navigation inside a setState inside a Timer is fragile and can fire after a route change.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** splash-navigation-pattern
- **Suggested fix:** Use a single AnimationController.addStatusListener or a single Timer that drives _progress and fires navigation once on completion outside setState.

### `plant_community_mobile/lib/services/auth_service.dart`

**#738** Line 71: FlutterSecureStorage is instantiated with default options; on Android this skips encryptedSharedPreferences (KeyStore-backed) and on iOS skips accessibility configuration, weakening token-at-rest protection.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Token storage — flutter_secure_storage hardening
- **Suggested fix:** Pass AndroidOptions(encryptedSharedPreferences: true) and IOSOptions(accessibility: KeychainAccessibility.first_unlock).

**#739** Line 123: _exchangeFirebaseTokenForJWT(currentUser) is fire-and-forget in build() and races with the authStateChanges listener (line 91) which will also fire for the existing user, doubling the exchange call and HTTP request on cold start.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** flutter-firebase-reviewer: race-free token exchange
- **Suggested fix:** Rely solely on the authStateChanges listener (which emits the current user immediately on subscription) or guard with a flag.

**#740** Line 252: user.getIdToken() returns a possibly stale cached token; right after sign-in the cached Firebase token may still reflect the prior user, leading the backend to refuse the exchange with the new identity.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Firebase auth token freshness
- **Suggested fix:** Call `user.getIdToken(true)` to force a refresh during the JWT exchange.

### `plant_community_mobile/lib/services/firebase_storage_service.dart`

**#741** Line 45: Synchronous file I/O (existsSync, lengthSync, openSync/readSync/closeSync) blocks the main isolate; for 5MB+ images this can stutter the UI on lower-end devices.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** flutter-firebase-reviewer: client-side validation
- **Suggested fix:** Use the async file APIs (exists(), length(), open()/read()) or move validation onto a compute() isolate.

**#742** Line 84: getDownloadURL returns a long-lived public token URL for plant images; for any non-public content this should be a signed URL with expiry generated server-side.

- **Reviewer:** flutter-firebase-reviewer
- **Rule:** flutter-firebase-reviewer: Storage download URLs must use signed URLs with expiry for private content
- **Suggested fix:** If plant images are user-private, generate signed URLs from a Cloud Function/backend instead of using getDownloadURL.

**#743** Line 101: openSync/readSync/closeSync block the UI isolate; image signature validation should not stall the event loop on large files.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Avoid sync I/O on the UI isolate
- **Suggested fix:** Use `await file.openRead(0, 12).first` or `RandomAccessFile.read(...)` async API.

### `plant_community_mobile/lib/services/firestore_service.dart`

**#744** Line 50: Settings.persistenceEnabled and Settings.CACHE_SIZE_UNLIMITED are deprecated in cloud_firestore; the modern API uses the localCache parameter (PersistentCacheSettings) and will eventually be removed.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Firestore SDK migration
- **Suggested fix:** Use `Settings(cacheSizeBytes: Settings.CACHE_SIZE_UNLIMITED, persistenceEnabled: true)` migrated to `Settings(localCache: PersistentCacheSettings(sizeBytes: Settings.CACHE_SIZE_UNLIMITED))`.

**#745** Line 187: Stream.handleError returns a value but the callback signature is void; returning <Plant>[] does nothing and the stream continues to surface errors to listeners.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Dart stream semantics
- **Suggested fix:** Use .transform/StreamTransformer or rxdart .onErrorReturn to truly substitute an empty list, or remove the misleading return.

### `plant_community_mobile/lib/services/plant_identification_service.dart`

**#746** Line 40: After uploading the image to Firebase Storage, the same file is also uploaded multipart to the Django backend — so every identification incurs two full uploads (and two billable storage egress paths) for the same image.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Performance / cost
- **Suggested fix:** Either send only the Firebase URL (`apiService.post` with image_url) or skip the Firebase upload when sending multipart; pick a single source of truth.

### `plant_community_mobile/lib/shared/widgets/gradient_button.dart`

**#747** Line 60: GradientButtonSize.small uses vertical padding AppSpacing.sm with 14px font, likely producing a tap target shorter than the 48x48 Material 3 minimum.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Material 3 — minimum tap target 48x48
- **Suggested fix:** Wrap with ConstrainedBox(minHeight: 48) or increase vertical padding for the small variant.

**#748** Line 90: Disabled state uses hardcoded Colors.grey, ignoring Material 3 disabled color semantics and dark mode adaptation.

- **Reviewer:** flutter-dart-reviewer
- **Rule:** Material Design 3 — dark mode adaptation
- **Suggested fix:** Use Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.12) or surfaceContainerHighest for the disabled background to match M3 disabled state.

### `web/src/components/StreamFieldRenderer.tsx`

**#749** Line 135: Destructures block.value.code and language without verifying value is an object — if backend sends a malformed block.value (string/null), runtime TypeError.

- **Reviewer:** react-typescript-reviewer
- **Rule:** defensive-destructure
- **Suggested fix:** Guard with `const value = block.value ?? {};` or narrow with a type check before destructuring.

**#750** Line 162: Renders <img src={value.image.url}> directly from API content without URL validation — if a malicious StreamField inserts javascript:, browsers ignore but data: URLs could be abused.

- **Reviewer:** react-typescript-reviewer
- **Rule:** url-validation
- **Suggested fix:** Reuse getSafeHref-style validation for image URLs or restrict to http(s)/relative.

### `web/src/components/diagnosis/ReminderManager.tsx`

**#751** Line 219: loadReminders has no cancellation/unmount guard; if user navigates away mid-fetch, setReminders/setError may run on unmounted component.

- **Reviewer:** react-typescript-reviewer
- **Rule:** react-cleanup
- **Suggested fix:** Use AbortController or a cancelled flag in the useEffect; abort on cleanup.

**#752** Line 247: useEffect disables exhaustive-deps for loadReminders — eslint-disable hides the actual issue (loadReminders is recreated each render).

- **Reviewer:** react-typescript-reviewer
- **Rule:** react-hooks/exhaustive-deps
- **Suggested fix:** Wrap loadReminders in useCallback with [diagnosisCardUuid] dependency, then include it in the effect deps.

### `web/src/components/diagnosis/SaveDiagnosisModal.tsx`

**#753** Line 74: Cast `cardData as unknown as CreateDiagnosisCardInput` defeats type safety; cardData is typed Record<string, unknown> rather than the actual input shape.

- **Reviewer:** react-typescript-reviewer
- **Rule:** no-double-cast
- **Suggested fix:** Type cardData as CreateDiagnosisCardInput directly so the structure is checked at construction time.

**#754** Line 91: Modal lacks role="dialog", aria-modal="true", focus trap, and ESC-to-close — fails accessibility for an overlay dialog.

- **Reviewer:** react-typescript-reviewer
- **Rule:** a11y-modal
- **Suggested fix:** Add role="dialog" aria-modal="true" aria-labelledby on heading, focus management on open, and Escape key handler.

### `web/src/components/diagnosis/StreamFieldEditor.tsx`

**#755** Line 289: List item .map uses array index as React key for editable items — reorder/delete will reuse keys and cause input state bleed.

- **Reviewer:** react-typescript-reviewer
- **Rule:** react-keys
- **Suggested fix:** Use a stable id per list item or include the item value in the key when items are simple strings.

**#756** Line 367: addBlock(blockType), updateBlock(index, updatedBlock), deleteBlock(index), moveBlockUp(index), moveBlockDown(index) all use implicit any parameters.

- **Reviewer:** react-typescript-reviewer
- **Rule:** no-implicit-any
- **Suggested fix:** Annotate parameter types (blockType: DiagnosisBlock['type'], index: number, etc.).

**#757** Line 410: deleteBlock uses window.confirm() inside a render-bound handler; blocks main thread and not testable. Same UX concern in DiagnosisCard and ReminderManager.

- **Reviewer:** react-typescript-reviewer
- **Rule:** ux-confirm
- **Suggested fix:** Replace with a modal-based confirm or extract to a utility that can be mocked in tests.

**#758** Line 463: Top-level block .map uses index as key while supporting reorder/delete — leads to wrong block state after move/delete operations.

- **Reviewer:** react-typescript-reviewer
- **Rule:** react-keys
- **Suggested fix:** Generate a stable id (uuid) when blocks are created and key on that.

### `web/src/components/forum/CategoryCard.tsx`

**#759** Line 64: category.children.map is called inside the `hasChildren` branch, but `category.children` is still typed possibly-undefined; relies on a runtime narrowing that TS may not infer (depends on Category typing).

- **Reviewer:** react-typescript-reviewer
- **Rule:** type-narrowing
- **Suggested fix:** Use `category.children?.map(...)` or extract `const children = category.children ?? []`.

### `web/src/components/forum/PostCard.tsx`

**#760** Line 53: Hover-only edit/delete affordance (onMouseEnter/onMouseLeave to setShowActions) is inaccessible on touch devices and keyboard users — controls become invisible.

- **Reviewer:** react-typescript-reviewer
- **Rule:** a11y-hover
- **Suggested fix:** Show actions always (on small screens) or trigger via focus-within / explicit toggle with keyboard support.

### `web/src/contexts/AuthContext.test.tsx`

**#761** Line 180: act(() => { result.current.login(credentials); }) fires an async operation without awaiting inside act; the immediate isLoading assertion can race the state update and produce an act() warning when the promise resolves outside the wrapper.

- **Reviewer:** test-quality-reviewer
- **Rule:** frontend-tests/no-unresolved-act-warnings
- **Suggested fix:** Wrap async fire in `let promise; act(() => { promise = result.current.login(...); }); expect(...isLoading).toBe(true); await act(async () => { await promise; });`.

**#762** Line 316: Same unawaited-promise-inside-act pattern as the login loading test; risks act() warnings on signup.

- **Reviewer:** test-quality-reviewer
- **Rule:** frontend-tests/no-unresolved-act-warnings
- **Suggested fix:** Capture the returned promise inside act and await it in a follow-up await act() block.

### `web/src/contexts/RequestContext.test.tsx`

**#763** Line 98: Storage.prototype.getItem/setItem are mutated inline without try/finally — if assertions fail, prototype remains stubbed and pollutes other tests in the file.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-isolation
- **Suggested fix:** Use vi.spyOn(Storage.prototype, 'getItem').mockImplementation(...) so vi.restoreAllMocks in afterEach reverts cleanly, or wrap assertions in try/finally.

**#764** Line 124: Same prototype-mutation pattern repeated; restoration only happens on success path, leaving Storage.prototype dirty on test failure.

- **Reviewer:** test-quality-reviewer
- **Rule:** test-isolation
- **Suggested fix:** Replace direct prototype assignment with vi.spyOn so afterEach restores automatically.

---

## 🟢 Low (239)

- **#765** `backend/apps/blog/admin_views.py:11` — Avg imported from django.db.models but never used. *(django-drf-reviewer)*
- **#766** `backend/apps/blog/admin_views.py:13` — csrf_exempt imported but never used. *(django-drf-reviewer)*
- **#767** `backend/apps/blog/admin_views.py:320` — Hardcoded settings dict (posts_per_page, featured_posts_limit, etc.) — magic numbers should reference constants.py. *(django-drf-reviewer)*
- **#768** `backend/apps/blog/api/serializers.py:84` — BlogAuthorPageSerializer.Meta.fields concatenates two list literals — stylistic noise. *(api-design-reviewer)*
- **#769** `backend/apps/blog/api/serializers.py:155` — featured_image_thumb (fill-300x200) in detail serializer; viewset only prefetches 'fill-800x600' and 'width-1200' - extra rendition build. *(wagtail-reviewer)*
- **#770** `backend/apps/blog/api/viewsets.py:99` — BlogPostPage.objects.live().public().specific() called on every list/detail; .specific() materialises subclass models and is expensive. *(performance-reviewer)*
- **#771** `backend/apps/blog/api/viewsets.py:281` — Magic number [:6] in featured action contradicts the project's no-magic-numbers convention; limit should be in constants.py. *(api-design-reviewer)*
- **#772** `backend/apps/blog/api/viewsets.py:318` — Popular posts cache TTL documented as 30 min; canonical TTL for blog:popular is 1h. *(wagtail-reviewer)*
- **#773** `backend/apps/blog/api/viewsets.py:644` — RSS/Atom feeds hardcode [:20] rather than referencing a constant. *(api-design-reviewer)*
- **#774** `backend/apps/blog/api_views.py:75` — PlantLookupView passes user=None when not authenticated; staff_member_required already enforces auth - dead code. *(wagtail-reviewer)*
- **#775** `backend/apps/blog/management/commands/create_demo_blog_posts.py:325` — Demo content uses 'care_instructions' StreamField block that has been removed. *(wagtail-reviewer)*
- **#776** `backend/apps/blog/management/commands/create_demo_blog_posts.py:435` — Demo content emits 'video_embed' StreamField block but BlogStreamBlocks no longer defines it (TODO #033). *(wagtail-reviewer)*
- **#777** `backend/apps/blog/management/commands/migrate_care_guides_to_blog.py:47` — Bare except Exception for accessing PlantCareGuide.objects.all() — masks ImportError vs DB errors. *(django-drf-reviewer)*
- **#778** `backend/apps/blog/middleware.py:52` — Middleware tracks views on every 200 response, including non-blog responses, before filtering; adds overhead on every request. *(django-drf-reviewer)*
- **#779** `backend/apps/blog/serializers.py:232` — extra_kwargs = {'email': {'write_only': False}} is a no-op (write_only defaults to False) and is misleading. *(api-design-reviewer)*
- **#780** `backend/apps/blog/services/ai_cache_service.py:71` — SHA-256 hash truncated to 16 hex chars (64 bits) for cache key — collision-resistant enough but inconsistent with blog_cache_service.py. *(django-drf-reviewer)*
- **#781** `backend/apps/blog/services/blog_cache_service.py:124` — Filter hash uses str(sorted(filters.items())) inside SHA-256 — non-canonical Python repr can produce different keys. *(performance-reviewer)*
- **#782** `backend/apps/blog/services/plant_data_lookup_service.py:117` — Bare except Exception swallows real DB errors silently; only logs and returns 'not found'. *(django-drf-reviewer)*
- **#783** `backend/apps/blog/services/plant_data_lookup_service.py:129` — _fuzzy_search_local_database iterates PlantSpecies.objects.all() in Python with fuzz.ratio — O(N) per request and unbounded memory. *(performance-reviewer)*
- **#784** `backend/apps/blog/services/plant_data_lookup_service.py:154` — Bare except Exception in fuzzy search — same concern as above. *(django-drf-reviewer)*
- **#785** `backend/apps/blog/tests/test_ai_cache_service.py:130` — test_cache_ttl_is_30_days asserts a constant value; change-detector test mirroring implementation. *(test-quality-reviewer)*
- **#786** `backend/apps/blog/tests/test_ai_cache_service.py:176` — test_warm_cache_logs_warming verifies log line emission; testing log strings is fragile. *(test-quality-reviewer)*
- **#787** `backend/apps/blog/tests/test_ai_rate_limiter.py:213` — test_cache_ttl_is_one_hour asserts on TTL constant — change-detector test. *(test-quality-reviewer)*
- **#788** `backend/apps/blog/tests/test_blog_viewsets_caching.py:286` — Strict query count of 13 lacks issue/PR reference linking the count to a specific regression incident. *(test-quality-reviewer)*
- **#789** `backend/apps/blog/views.py:334` — REMOTE_ADDR used directly without considering trusted X-Forwarded-For for IP tracking. *(wagtail-reviewer)*
- **#790** `backend/apps/blog/wagtail_hooks.py:99` — Manual title truncation logic with len()/slice/'...' is brittle. *(wagtail-reviewer)*
- **#791** `backend/apps/blog/wagtail_hooks.py:287` — insert_global_admin_css/js use raw <link>/<script> tags bypassing Django's static() helper. *(wagtail-reviewer)*
- **#792** `backend/apps/core/exceptions.py:173` — Unhandled-exception branch passes both extra={'traceback': traceback.format_exc()} and exc_info=True, formatting traceback twice. *(performance-reviewer)*
- **#793** `backend/apps/core/models.py:155` — mark_failed parameter typed 'error_message: str = None' should be Optional[str]. *(django-drf-reviewer)*
- **#794** `backend/apps/core/security.py:249` — _send_lockout_notification calls User.objects.get(username=username); fetching only email avoids loading the full User row. *(performance-reviewer)*
- **#795** `backend/apps/core/security.py:462` — Log lacks bracketed prefix. *(django-drf-reviewer)*
- **#796** `backend/apps/core/security.py:482` — File-upload log lacks bracketed prefix. *(django-drf-reviewer)*
- **#797** `backend/apps/core/security.py:535` — Validation-failure log lacks bracketed prefix. *(django-drf-reviewer)*
- **#798** `backend/apps/core/security.py:587` — Log message uses 'SECURITY ALERT [...]' format instead of bracketed prefix '[SECURITY] ALERT'. *(django-drf-reviewer)*
- **#799** `backend/apps/core/security.py:743` — log_security_event message lacks bracketed prefix. *(django-drf-reviewer)*
- **#800** `backend/apps/core/security.py:773` — check_rate_limit log lacks bracketed prefix. *(django-drf-reviewer)*
- **#801** `backend/apps/core/services/email_service.py:383` — Welcome email subject hardcodes English copy and emoji — i18n unfriendly. *(django-drf-reviewer)*
- **#802** `backend/apps/core/test_basic.py:1` — Test file lives at apps/core/test_basic.py instead of apps/core/tests/test_basic.py. The tests/ package already exists; placing tests outside it splits discovery and breaks the convention used by other tests in this app. *(test-quality-reviewer)*
- **#803** `backend/apps/core/test_basic.py:9` — Trivial sanity tests (test_addition, test_string_operations, test_list_operations) provide no real coverage of the codebase and exist only to verify the test runner. They consume CI time without value and clutter the test suite. *(test-quality-reviewer)*
- **#804** `backend/apps/core/tests/test_csrf_meta_tag.py:58` — test_csrf_token_in_context only asserts response.context is not None, which is true for any rendered template response. It does not actually verify the csrf_token is in context as the docstring claims. *(test-quality-reviewer)*
- **#805** `backend/apps/core/tests/test_pii_safe_logging.py:26` — test_normal_username asserts an exact length of 14 ('joh***' + 8 char hash) but does not validate the hash characters themselves are hex/expected charset. A regression that produces 8 wrong-but-equal-length characters would still pass. *(test-quality-reviewer)*
- **#806** `backend/apps/core/tests/test_pii_safe_logging.py:148` — LogSafeUserContextTests creates a real DB user but only uses .username and .email attributes. The DB hit is unnecessary; an in-memory User instance would be faster and equally valid since the function under test does not query the DB. *(test-quality-reviewer)*
- **#807** `backend/apps/core/validators.py:95` — validate_image_file opens the image twice with PIL on every upload. *(performance-reviewer)*
- **#808** `backend/apps/core/validators.py:155` — Bare 'except Exception' silently swallows non-ValidationError errors. *(django-drf-reviewer)*
- **#809** `backend/apps/forum/models.py:264` — increment_view_count refreshes view_count from DB after the F() update; this is correct, but ThreadViewSet.retrieve duplicates the same logic inline (line 284) instead of calling the model method — keep one or the other to avoid drift. *(django-drf-reviewer)*
- **#810** `backend/apps/forum/permissions.py:122` — `CanCreateThread.has_permission` returns True for any non-POST request including unauthenticated users; safe only when combined with IsAuthenticated at the viewset level — relying on this alone would expose update/delete actions. *(security-reviewer)*
- **#811** `backend/apps/forum/permissions.py:291` — `message` is declared as a class attribute and reassigned via `self.message = ...` inside `has_permission`; while Python creates an instance attribute on assignment (so no cross-request leakage in practice), the pattern is fragile and could regress to class-level mutation if refactored. *(security-reviewer)*
- **#812** `backend/apps/forum/serializers/post_serializer.py:163` — attachments is implemented as a SerializerMethodField that wraps AttachmentSerializer with many=True; replacing it with `attachments = AttachmentSerializer(many=True, read_only=True)` is simpler and equivalent given the prefetched ordering in the viewset. *(django-drf-reviewer)*
- **#813** `backend/apps/forum/services/forum_cache_service.py:297` — Fallback path catches AttributeError to detect missing delete_pattern but django-redis raises AttributeError only on the cache backend instance lookup; on locmem caches you get a NotImplementedError. The fallback may not be exercised on all backends. *(django-drf-reviewer)*
- **#814** `backend/apps/forum/tests/test_attachment_soft_delete.py:71` — Method name test_attachment_soft_delete_sets_is_active_false omits expected-result wording in the canonical test_{feature}*{condition}*{expected} convention; many tests in this batch use the looser style. *(test-quality-reviewer)*
- **#815** `backend/apps/forum/tests/test_post_viewset.py:703` — test_upload_image_rejects_decompression_bomb swallows DecompressionBombError silently — if Pillow blocks creation the test passes without exercising server-side rejection. *(test-quality-reviewer)*
- **#816** `backend/apps/forum/tests/test_post_viewset_permissions.py:544` — Skipped test test_rate_limit_resets_after_timeout has good documentation but should be tracked with an issue or removed entirely; skipped tests rot. *(test-quality-reviewer)*
- **#817** `backend/apps/forum/tests/test_reaction_race_conditions.py:184` — test_many_concurrent_toggles_produces_correct_final_state runs 50 concurrent toggles with ThreadPoolExecutor; while it asserts only one row exists, this kind of stress test can be flaky on CI under load. *(test-quality-reviewer)*
- **#818** `backend/apps/forum/tests/test_spam_detection_service.py:174` — test_duplicate_detection_uses_cache claims to verify caching but only asserts result1 == result2; it doesn't measure cache hit (e.g., query count or mock call count) so cache use is unverified. *(test-quality-reviewer)*
- **#819** `backend/apps/forum/tests/utils.py:207` — simulate_cache_stampede helper is unused by any test in the batch; dead helper code increases maintenance load. *(test-quality-reviewer)*
- **#820** `backend/apps/forum/viewsets/moderation_queue_viewset.py:744` — user_moderation_history runs flags_qs.count() twice (line 700 and line 744) and re-issues four additional COUNT queries for the summary block; a single .aggregate(...Case(When(...)...)) call would replace 5 separate queries. *(django-drf-reviewer)*
- **#821** `backend/apps/forum/viewsets/post_viewset.py:195` — Action allowlist for super().get_permissions() omits 'first_posts' (line 391), which is GET-only but still relies on the default branch — works today but brittle if the action ever gains a permission_classes override. *(django-drf-reviewer)*
- **#822** `backend/apps/forum/viewsets/post_viewset.py:685` — Catch-all 'except Exception' for PIL parsing collapses real errors into a single 'Invalid image file' response; a finer-grained except (UnidentifiedImageError, OSError) would avoid masking unrelated bugs (e.g., AttributeError, ImportError). *(django-drf-reviewer)*
- **#823** `backend/apps/forum/viewsets/thread_viewset.py:415` — Bare 'except ValueError: pass' on date_from parsing silently swallows malformed input; user gets no feedback that their filter was ignored. *(django-drf-reviewer)*
- **#824** `backend/apps/forum/viewsets/thread_viewset.py:421` — Same silent ValueError pass for date_to parsing. *(django-drf-reviewer)*
- **#825** `backend/apps/forum_integration/api_views.py:11` — Unused import: `from machina.core.loading import get_class` is used here, but `from rest_framework.decorators import api_view, permission_classes` overlaps with class-based usage; many imports listed at top (e.g., `Paginator` from django.core.paginator imported twice — module-level and inside all_topics_list at line 59). *(django-drf-reviewer)*
- **#826** `backend/apps/forum_integration/api_views.py:19` — Module-level get_class('forum_permission.handler', 'PermissionHandler') runs at import time; combined with views.py also importing it, behavior is fine but a per-instance handler is created in many handlers (PermissionHandler() repeatedly) instead of reusing the module-level one. *(django-drf-reviewer)*
- **#827** `backend/apps/forum_integration/api_views.py:25` — ForumAIUsage is imported but never referenced in this module. *(django-drf-reviewer)*
- **#828** `backend/apps/forum_integration/api_views.py:67` — page_size is taken directly from query string with no upper bound; clients can request arbitrary page sizes. *(django-drf-reviewer)*
- **#829** `backend/apps/forum_integration/api_views.py:100` — Pagination next/previous URLs are constructed without preserving other query params and ignore the page_size param the client supplied. *(django-drf-reviewer)*
- **#830** `backend/apps/forum_integration/api_views.py:254` — from django.utils import timezone and from datetime import timedelta are imported inside the function body even though timezone is already imported at module top. *(django-drf-reviewer)*
- **#831** `backend/apps/forum_integration/api_views.py:294` — PlantAIPrompts is imported but never used after import in forum_ai_assist. *(django-drf-reviewer)*
- **#832** `backend/apps/forum_integration/api_views.py:466` — TopicUpdateView mutates topic.type/status without validating boolean coercion of request.data['is_pinned']/['is_locked']; truthy strings like 'false' would be set as truthy. *(django-drf-reviewer)*
- **#833** `backend/apps/forum_integration/management/commands/setup_forums.py:32` — PermissionHandler() is instantiated at module import time, which runs DB/import-time work whenever the management command module is loaded (e.g. test discovery). *(wagtail-reviewer)*
- **#834** `backend/apps/forum_integration/models.py:82` — PlantMentionBlock is defined as a nested class inside ForumStreamBlocks; convention (and CLAUDE.md guidance) is to define block types in a dedicated blocks.py rather than inline in models / inside other blocks. *(wagtail-reviewer)*
- **#835** `backend/apps/forum_integration/models.py:700` — ForumPostImage.save calls a per-row Max() aggregate to compute upload_order; for bulk uploads this is repeated per save. *(performance-reviewer)*
- **#836** `backend/apps/forum_integration/serializers.py:20` — UserSerializer exposes id/username/first_name/last_name without explicit read_only=True; relying on ModelSerializer defaults works, but is brittle if the serializer is reused for input. *(api-design-reviewer)*
- **#837** `backend/apps/forum_integration/serializers.py:229` — content_format CharField allows arbitrary strings; schema/clients have no enum constraint despite only a small set of valid formats (e.g. 'plain', 'rich'). *(api-design-reviewer)*
- **#838** `backend/apps/forum_integration/serializers.py:405` — CreatePostSerializer._normalize_rich_content delegates by calling CreateTopicSerializer._normalize_rich_content(self, ...) — fragile cross-class invocation that bypasses MRO and complicates schema/documentation tooling. *(api-design-reviewer)*
- **#839** `backend/apps/forum_integration/serializers.py:411` — url/thumbnail_url declared as CharField rather than URLField, which yields `string` in OpenAPI schema instead of `string<uri>`. *(api-design-reviewer)*
- **#840** `backend/apps/forum_integration/tests.py:1` — tests.py is empty (no real tests). The forum_integration app has substantial DRF surface area but no test coverage in this module (a tests/ package exists separately). *(django-drf-reviewer)*
- **#841** `backend/apps/forum_integration/tests/test_forum_api_roundtrip.py:42` — Hardcoded password literal `password123!` — minor; consider a module-level constant or test fixture to avoid repetition if more user fixtures are added. *(test-quality-reviewer)*
- **#842** `backend/apps/forum_integration/tests/test_forum_api_roundtrip.py:49` — Test name `test_create_topic_with_plant_mention_and_fetch_enriched` bundles two distinct behaviours (create + fetch-enriched) — checklist asks for one assertion concept per test for clearer regression diagnosis. *(test-quality-reviewer)*
- **#843** `backend/apps/forum_integration/tests/test_forum_api_roundtrip.py:49` — Inconsistent payload shape between tests — line 59 sends `plant_page: {'id': N}` while line 119 sends `plant_page: N` — ambiguous as to which is canonical input contract. *(test-quality-reviewer)*
- **#844** `backend/apps/forum_integration/tests/test_forum_api_roundtrip.py:81` — Critical assertions lack descriptive failure messages — e.g., `assertGreaterEqual(len(results), 1)` will fail with no context about what posts were expected. *(test-quality-reviewer)*
- **#845** `backend/apps/forum_integration/tests/test_plant_mention_serialization.py:16` — Coverage gaps for normalization: no tests for empty rich_content list, missing `value` key, missing `plant_page` key, or non-plant_mention block types — only happy-path and one invalid-id case. *(test-quality-reviewer)*
- **#846** `backend/apps/forum_integration/views.py:21` — Module-level perm_handler is instantiated but unused in this file (all handler refs in views.py are commented out); dead code increases cognitive overhead. *(django-drf-reviewer)*
- **#847** `backend/apps/forum_integration/views.py:41` — Permission checks are commented out ("Temporarily bypass permissions for debugging") and shipped in production code; can_see_forum / can_read_forum are not enforced for forum index, category, and topic views. *(django-drf-reviewer)*
- **#848** `backend/apps/forum_integration/wagtail_hooks.py:50` — Forum management menu item links to '/forum/', which is the public forum, not a Wagtail admin URL; clicking from /cms/ takes editors out of the admin context. *(wagtail-reviewer)*
- **#849** `backend/apps/forum_integration/wagtail_hooks.py:154` — Bare except Exception swallows all errors silently in admin panel construction, including programming bugs; this hides regressions during development. *(wagtail-reviewer)*
- **#850** `backend/apps/forum_integration/wagtail_hooks.py:194` — Bare except Exception in summary items hook silently hides errors; same pattern as construct_homepage_panels. *(wagtail-reviewer)*
- **#851** `backend/apps/forum_integration/wagtail_hooks.py:248` — Hardcoded /static/ URL ignores STATIC_URL/CDN configuration; will 404 if STATIC_URL is set to e.g. a CDN host. *(wagtail-reviewer)*
- **#852** `backend/apps/forum_integration/wagtail_hooks.py:258` — Hardcoded /static/ URL for admin.js has the same STATIC_URL portability issue as the CSS hook. *(wagtail-reviewer)*
- **#853** `backend/apps/garden/serializers.py:87` — Validation errors use a free-form string rather than the project-standard `{"error": "message"}` shape — DRF will wrap them, but consistency note: nested image errors will appear under the field key, which is fine, but clients should be aware that pattern differs from the wider error envelope. *(api-design-reviewer)*
- **#854** `backend/apps/garden/serializers.py:92` — Extension extraction value.name.split['.'](-1).lower() returns the full filename for files with no '.' (e.g. 'photo' becomes 'photo'), which is a fragile validation primitive. *(api-design-reviewer)*
- **#855** `backend/apps/garden/serializers.py:92` — value.name.split['.'](-1) without a dot returns the whole filename and falsely passes the extension check for files named 'noextension'. Edge-case but trivial bypass. *(django-drf-reviewer)*
- **#856** `backend/apps/garden/serializers.py:124` — Same fragile extension check duplicated in JournalImageSerializer.validate_image — split['.'](-1) returns whole name for extensionless files. *(api-design-reviewer)*
- **#857** `backend/apps/garden/serializers.py:296` — Same fragile extension check duplicated in GardenPlantSerializer.validate_image; logic should be shared with PestImageSerializer / JournalImageSerializer. *(api-design-reviewer)*
- **#858** `backend/apps/garden/serializers.py:319` — isinstance(value['x'], (int, float)) accepts bool because bool is a subclass of int — clients could submit {'x': true, 'y': false} and pass validation. *(api-design-reviewer)*
- **#859** `backend/apps/garden/serializers.py:433` — validate_dimensions accepts bool for width/height because bool is a subclass of int (e.g. width=True passes). *(api-design-reviewer)*
- **#860** `backend/apps/garden/serializers.py:469` — validate_location accepts bool for lat/lng (bool subclass of int); also silently passes when only one of lat/lng is present (the `if 'lat' in value and 'lng' in value` block is skipped, so a payload with only lat/lng goes unvalidated). *(api-design-reviewer)*
- **#861** `backend/apps/garden/services/care_assistant_service.py:192` — Magic literal model 'gpt-4o-mini', max_tokens 1000/500/800, temperature 0.7 — not sourced from constants.py. *(django-drf-reviewer)*
- **#862** `backend/apps/garden/services/care_assistant_service.py:211` — json.loads(content) inside the broad try/except — but the exception path falls through to fallback only on the outer try; an unparseable model response results in cache miss every call until the AI happens to return valid JSON. Consider tighter handling and a backoff. *(django-drf-reviewer)*
- **#863** `backend/apps/garden/services/companion_planting_service.py:119` — Compatibility check uses substring/element membership against possibly-empty companion_plants JSON list, which permits 'plant_x' to match 'plant_x_jr' if list contains substrings — currently it uses `in` on a list, which is exact match, so safe; but the symmetrical fallback (line 142) only fires when relationship == 'neutral', missing cases where care1 returned non-neutral but care2 has stronger evidence. *(django-drf-reviewer)*
- **#864** `backend/apps/garden/services/companion_planting_service.py:364` — suggest_optimal_position calls garden.plants.all() and iterates; if this is called in request handlers it should select_related('plant_species') to avoid extra queries when accessed downstream, and to be consistent with viewset behavior. *(performance-reviewer)*
- **#865** `backend/apps/garden/services/firebase_notification_service.py:161` — User-facing notification body strings contain emoji/Unicode hard-coded inline; if i18n is added later these will be hard to translate. *(django-drf-reviewer)*
- **#866** `backend/apps/garden/services/firebase_sync_service.py:37` — Magic strings 'care_reminders' and 'user_reminders' as collection names; OK as class constants but consider moving to constants.py to keep configuration centralized. *(django-drf-reviewer)*
- **#867** `backend/apps/garden/services/firebase_sync_service.py:348` — Hardcoded Firestore batch limit 500 — should reference a named constant. *(django-drf-reviewer)*
- **#868** `backend/apps/garden/services/smart_reminder_service.py:254` — Magic numbers 0.3, 0.1, 90, 75, 50 in adjust_watering_frequency aren't sourced from constants.py per the project no-magic-numbers rule. *(django-drf-reviewer)*
- **#869** `backend/apps/garden/tests.py:1` — Empty placeholder tests.py while a `tests/` package also exists — unclear which is canonical; legacy file should be removed to avoid Django picking up the wrong module. *(django-drf-reviewer)*
- **#870** `backend/apps/garden/tests/test_models.py:24` — Tests cover only happy paths — no error/validation cases (e.g. invalid visibility, missing required fields, invalid health_status choice, negative interval_days, or model clean()/full_clean() behaviour). *(test-quality-reviewer)*
- **#871** `backend/apps/garden/tests/test_models.py:27` — User setUp duplicated verbatim across six TestCase classes; extract a shared base class or fixture/factory to reduce drift risk. *(test-quality-reviewer)*
- **#872** `backend/apps/garden/tests/test_models.py:35` — Test names follow test_<feature> pattern but lack explicit condition/expected_result segment recommended by the team naming convention (test_{feature}*{condition}*{expected_result}). *(test-quality-reviewer)*
- **#873** `backend/apps/garden/tests/test_models.py:47` — Bundled unrelated assertions in one test (name, user, dimensions, climate_zone, visibility, featured) — failure of the first masks the others; consider one-concept-per-test or descriptive failure messages. *(test-quality-reviewer)*
- **#874** `backend/apps/garden/tests/test_models.py:316` — PlantCareLibraryModelTests has only one create test — no error path, no test for default values or unique constraints (e.g. duplicate scientific_name). *(test-quality-reviewer)*
- **#875** `backend/apps/garden_calendar/api/serializers.py:138` — validate_end_datetime reads from self.initial_data and re-parses the datetime; on partial_update where start_datetime is unchanged the validator silently passes because initial_data lacks it. *(api-design-reviewer)*
- **#876** `backend/apps/garden_calendar/api/serializers.py:232` — RSVPSerializer.validate_status duplicates the ChoiceField validation; redundant and likely to drift. *(api-design-reviewer)*
- **#877** `backend/apps/garden_calendar/api/views.py:11` — Imports get_object_or_404 and Count but neither is used at module level (Count is also re-imported inside get_queryset/statistics) — dead imports. *(api-design-reviewer)*
- **#878** `backend/apps/garden_calendar/api/views.py:67` — get_serializer_class falls through to Detail serializer for any non-list/non-write action including custom actions like rsvp/calendar_feed; while the actions instantiate their own serializers, Swagger will document the wrong response schema. *(api-design-reviewer)*
- **#879** `backend/apps/garden_calendar/api/views.py:211` — calendar_feed action on CommunityEventViewSet is unauthenticated (default IsAuthenticatedOrReadOnly) but slices to [:500] without pagination; large public exposure. *(django-drf-reviewer)*
- **#880** `backend/apps/garden_calendar/api/views.py:224` — calendar_feed evaluates queryset[:500] then iterates serializer.data with len() and slicing per item; acceptable but could use .iterator(chunk_size=...) for memory. *(performance-reviewer)*
- **#881** `backend/apps/garden_calendar/api/views.py:245` — Truncating description with '...' inside the API payload assumes consumers can't truncate — better to return the raw description and let clients format. *(api-design-reviewer)*
- **#882** `backend/apps/garden_calendar/api/views.py:261` — _get_event_color and_get_task_color (line 1351) hardcode hex color maps rather than importing from constants (HEALTH_STATUS_COLORS pattern already exists). *(django-drf-reviewer)*
- **#883** `backend/apps/garden_calendar/api/views.py:685` — Division by total_tasks guarded but the round() returns 0 (int) when total_tasks==0 versus float otherwise; type-inconsistent response. *(api-design-reviewer)*
- **#884** `backend/apps/garden_calendar/auditlog.py:25` — include_fields lists 'last_fertilized' and 'last_watered' which are not present on the GardenBed model; auditlog will raise at registration time. *(django-drf-reviewer)*
- **#885** `backend/apps/garden_calendar/auditlog.py:38` — Plant include_fields lists 'expected_harvest_date' which is not defined on the Plant model. *(django-drf-reviewer)*
- **#886** `backend/apps/garden_calendar/auditlog.py:67` — Harvest include_fields lists 'taste_rating' and 'shared_with_community', neither of which exist on Harvest model. *(django-drf-reviewer)*
- **#887** `backend/apps/garden_calendar/services/care_schedule_service.py:281` — Type hint uses User (the result of get_user_model()) directly; for static type-checkers this works at runtime but fails type-checking. Minor. *(django-drf-reviewer)*
- **#888** `backend/apps/garden_calendar/services/care_schedule_service.py:441` — f-string with no interpolation: notes=f"Rescheduled from overdue status". *(django-drf-reviewer)*
- **#889** `backend/apps/garden_calendar/services/garden_analytics_service.py:359` — get_comprehensive_dashboard composes 4 stats methods sequentially; each does its own queries with no shared queryset — could be cached as a single dashboard key. *(performance-reviewer)*
- **#890** `backend/apps/garden_calendar/signals.py:152` — A management Command class is defined inside signals.py. Management commands belong in apps/<app>/management/commands/<name>.py and will not be discovered here. *(django-drf-reviewer)*
- **#891** `backend/apps/garden_calendar/tests/test_file_upload_security.py:203` — test_max_size_file_accepted docstring claims 'Files at max size should be accepted' but uploads a tiny 100x100 image — does not actually exercise the boundary condition. *(test-quality-reviewer)*
- **#892** `backend/apps/garden_calendar/tests/test_integration.py:140` — Uses assertGreater(len(results), 0) where exact count is known (1 task was just created) — weakens regression detection. *(test-quality-reviewer)*
- **#893** `backend/apps/garden_calendar/tests/test_integration.py:301` — assertGreater(len(beneficial_pairs), 0) — exact count is deterministic (tomato+basil = 1 pair) and should be asserted strictly. *(test-quality-reviewer)*
- **#894** `backend/apps/garden_calendar/tests/test_models.py:42` — assertRaises(Exception) is too broad — it will accept any error including unrelated bugs (TypeError, AttributeError) and pass spuriously. *(test-quality-reviewer)*
- **#895** `backend/apps/garden_calendar/tests/test_performance.py:187` — Comment claims 'SELECT user (authentication)' as a 1-query baseline, but force_authenticate bypasses DB lookups — comment is inaccurate and will mislead future maintainers tightening counts. *(test-quality-reviewer)*
- **#896** `backend/apps/garden_calendar/tests/test_services.py:246` — Assertion 'assertGreater(task.scheduled_date, timezone.now() - timedelta(days=1))' is far too loose — the rescheduled date should be a specific computed value or window. *(test-quality-reviewer)*
- **#897** `backend/apps/plant_identification/api/diagnosis_serializers.py:199` — DiagnosisCardDetailSerializer.validate_care_instructions duplicates logic in Update/Create serializers — DRY violation; consider moving validation to a shared mixin or model-level validation. *(api-design-reviewer)*
- **#898** `backend/apps/plant_identification/api/diagnosis_viewsets.py:30` — DiagnosisCardViewSet docstring lists query parameters in prose only — they aren't declared in OpenAPI schema (no OpenApiParameter annotations). *(api-design-reviewer)*
- **#899** `backend/apps/plant_identification/api/diagnosis_viewsets.py:65` — get_queryset() applies user-supplied filter parameters without strict validation; an unknown treatment_status string silently passes Django ORM with empty result. *(django-drf-reviewer)*
- **#900** `backend/apps/plant_identification/api/diagnosis_viewsets.py:89` — Boolean query param parsing (`is_favorite`, `plant_recovered`, `sent`) is hand-rolled and duplicated; rejects falsy/empty without normalization. *(api-design-reviewer)*
- **#901** `backend/apps/plant_identification/api/diagnosis_viewsets.py:197` — Custom @action `toggle_favorite` performs a PATCH semantic with POST and accepts no body — convention is PATCH for partial updates or include explicit `is_favorite` in payload. *(api-design-reviewer)*
- **#902** `backend/apps/plant_identification/api/diagnosis_viewsets.py:331` — snooze action does `int(request.data.get('hours', 24))` without try/except; non-integer payload returns 500 instead of 400. *(django-drf-reviewer)*
- **#903** `backend/apps/plant_identification/api/serializers.py:61` — Hardcoded `/api/v2/care-guides/` path in get_care_guide_url — couples serializer to a specific URL pattern; will break if the API mount path changes. *(wagtail-reviewer)*
- **#904** `backend/apps/plant_identification/api/serializers.py:195` — PlantSpeciesPageSerializer.get_related_plants splits common_names by comma inline; logic duplicated across files. May raise on plant_species without family. *(api-design-reviewer)*
- **#905** `backend/apps/plant_identification/api/simple_views.py:134` — Magic number `10 * 1024 * 1024` for max file size; project convention is to put limits in constants.py. *(api-design-reviewer)*
- **#906** `backend/apps/plant_identification/api/simple_views.py:195` — Health check exposes internal state (plant_id_available, plantnet_available) that may aid attackers in fingerprinting service availability. *(api-design-reviewer)*
- **#907** `backend/apps/plant_identification/circuit_monitoring.py:124` — Accesses `cb._state_storage.counter` (private attribute) — fragile against pybreaker version upgrades. *(django-drf-reviewer)*
- **#908** `backend/apps/plant_identification/management/commands/optimize_species_database.py:120` — Uses `values('scientific_name__iexact').annotate(count=Count('scientific_name__iexact'))` — `__iexact` is not a valid annotation expression and may raise FieldError; even if it works it's surprising. *(django-drf-reviewer)*
- **#909** `backend/apps/plant_identification/permissions.py:36` — request.user truthiness check before is_authenticated is redundant in DRF (request.user is always set, defaulting to AnonymousUser) and can mask logic errors; it also obscures that the second return path treats anonymous identical to authenticated. *(security-reviewer)*
- **#910** `backend/apps/plant_identification/serializers.py:100` — PlantDiseaseRequestSerializer is duplicated (defined twice in this file at lines 100 and 339), causing maintenance hazard and silently shadowed import behavior. *(api-design-reviewer)*
- **#911** `backend/apps/plant_identification/serializers.py:339` — PlantDiseaseRequestSerializer is defined twice in this file (also at line 100) — second copy shadows first; dead code or maintenance hazard. *(django-drf-reviewer)*
- **#912** `backend/apps/plant_identification/serializers.py:387` — PlantDiseaseRequestCreateSerializer also duplicated (also at line 148) and PlantDiseaseResultSerializer duplicated at line 409 — multiple class redefinitions in serializers.py. *(django-drf-reviewer)*
- **#913** `backend/apps/plant_identification/services/combined_identification_service.py:27` — MAX_WORKER_THREADS imported but logic uses min(max_workers, MAX_WORKER_THREADS) — if env override exceeds max it gets capped silently (no warning). *(django-drf-reviewer)*
- **#914** `backend/apps/plant_identification/services/identification_service.py:729` — _create_fallback_results hardcodes plant data inside the service — should live in constants.py or a fixtures file. *(django-drf-reviewer)*
- **#915** `backend/apps/plant_identification/services/plant_id_service.py:477` — Cache key `plant_id_details_{plant_name.lower()}` lacks colon separators and app prefix. *(django-drf-reviewer)*
- **#916** `backend/apps/plant_identification/services/plantnet_service.py:461` — get_all_projects has no caching; called from get_project_info and get_available_projects loops, hitting external API per call. *(django-drf-reviewer)*
- **#917** `backend/apps/plant_identification/tasks.py:15` — Task returns a dict with status/results_count but no `ignore_result` is set; if callers do not consume the result, this fills the result backend (Redis) needlessly. *(celery-async-reviewer)*
- **#918** `backend/apps/plant_identification/tasks.py:66` — Log message uses f-string instead of lazy `%`-style formatting used elsewhere in this module (lines 36, 76); minor consistency / perf nit. *(celery-async-reviewer)*
- **#919** `backend/apps/plant_identification/test_circuit_breaker_locks.py:117` — Comment says 'In real tests, you'd use time.sleep(reset_timeout)' then bypasses the timeout via service.circuit.half_open(); this short-circuits the actual reset_timeout invariant. *(test-quality-reviewer)*
- **#920** `backend/apps/plant_identification/test_circuit_breaker_locks.py:364` — test_cache_key_generation duplicates a string-formatting check on hashlib output — it tests f-string concatenation, not project logic. *(test-quality-reviewer)*
- **#921** `backend/apps/plant_identification/test_diagnosis_models.py:231` — Loop iterates choices and creates+deletes one card per iteration; if any iteration leaves residue, later test ordering becomes order-dependent — better to use sub-tests. *(test-quality-reviewer)*
- **#922** `backend/apps/plant_identification/test_executor_caching.py:481` — test_cache_hit_is_instant asserts cache.get under 10ms — measures Django's own cache backend (likely LocMem) rather than project behaviour, contributing noise to CI. *(test-quality-reviewer)*
- **#923** `backend/apps/plant_identification/test_models.py:415` — create_test_image is decorated with @pytest.mark.slow — the marker is meant for tests, not fixture helpers; it has no effect here and is misleading. *(test-quality-reviewer)*
- **#924** `backend/apps/plant_identification/views.py:1204` — search_local_plants uses .exclude(id__in=auto_stored.values_list('id', flat=True)) — Django will materialize and re-execute the inner subquery; cleaner to combine via Q or use exclude(id__in=Subquery(...)). *(performance-reviewer)*
- **#925** `backend/apps/plant_identification/views.py:1349` — search_plant_species: `int(request.query_params.get('limit', 20))` can ValueError on bad input; bypasses pagination defenses too. *(django-drf-reviewer)*
- **#926** `backend/apps/search/serializers.py:75` — forum_category is IntegerField (PK) while blog_category is CharField (slug); inconsistent identifier conventions across filters of the same response. *(api-design-reviewer)*
- **#927** `backend/apps/search/serializers.py:113` — validate() mutates data['content_types'] when filtering 'all'; MultipleChoiceField returns a set, so list comprehension/'in' works but ordering is non-deterministic and the special handling could be expressed as a dedicated validator/normalizer for clarity. *(api-design-reviewer)*
- **#928** `backend/apps/search/serializers.py:117` — Hardcoded list ['forum', 'plants', 'blog', 'diseases'] omits 'care_guides' which is in CONTENT_TYPE_CHOICES, so 'all' silently excludes care_guides results. *(api-design-reviewer)*
- **#929** `backend/apps/search/serializers.py:117` — Validation hardcodes the list of non-'all' content types ['forum', 'plants', 'blog', 'diseases'] separately from CONTENT_TYPE_CHOICES; if choices change (e.g., care_guides) this list silently drifts. *(django-drf-reviewer)*
- **#930** `backend/apps/search/serializers.py:127` — SearchResultSerializer.type and SearchSuggestionSerializer.type are free-form CharField but the request serializer constrains content types via CONTENT_TYPE_CHOICES; response 'type' should be a ChoiceField for schema/enum consistency. *(api-design-reviewer)*
- **#931** `backend/apps/search/serializers.py:128` — SearchResultSerializer.id is CharField without read_only=True; while this is a response serializer, missing read_only=True allows accidental input use if reused for write contexts. *(api-design-reviewer)*
- **#932** `backend/apps/search/services/search_service.py:7` — Unused imports SearchVectorField is imported in models but SearchHeadline imported in service is unused. *(django-drf-reviewer)*
- **#933** `backend/apps/search/services/search_service.py:105` — Pagination is computed in Python over the merged list (max ~80 items). Acceptable but means 'total_count' = sum of fetched (capped) items, not true total — pagination claims may be misleading for queries with > cap matches. *(django-drf-reviewer)*
- **#934** `backend/apps/search/services/search_service.py:169` — Per-content-type cap of 20 is a hard-coded magic number violating the project's no-magic-numbers convention; should live in apps/search/constants.py. *(performance-reviewer)*
- **#935** `backend/apps/search/services/search_service.py:174` — Slice [:200] + '...' assumes content is a string; getattr can return non-string falsy values that crash on slicing inconsistency was already mitigated, but the redundancy is noisy. *(django-drf-reviewer)*
- **#936** `backend/apps/search/views.py:12` — Direct `from django.db.models import ... Q` imported but Q is never used in this file. *(django-drf-reviewer)*
- **#937** `backend/apps/search/views.py:78` — request.session.session_key may be None even if session middleware is present until session is created; not a bug but document or call request.session.save() if you need a stable key. *(django-drf-reviewer)*
- **#938** `backend/apps/search/views.py:240` — Plant families aggregation uses .values_list('family').annotate(Count('family')).order_by['-count'](:20) which scans PlantSpecies on every filters request; combined with the missing cache, the cost compounds. *(performance-reviewer)*
- **#939** `backend/apps/search/views.py:397` — result_position cast via int() without try/except; bad input causes ValueError caught by outer generic handler returning 500 instead of 400. *(django-drf-reviewer)*
- **#940** `backend/apps/users/apps.py:18` — Bare `except RuntimeError: pass` swallows all RuntimeError types from auditlog import; comment is helpful but could narrow further. *(django-drf-reviewer)*
- **#941** `backend/apps/users/firebase_auth_views.py:246` — Username derived from email local-part is truncated to 8 hex chars on collision, giving 2^32 namespace; unlikely to collide but worth using a longer suffix or random salt for predictability resistance. *(security-reviewer)*
- **#942** `backend/apps/users/models.py:235` — Custom Meta.db_table = 'auth_user' to mirror Django's default user table is brittle if a future migration alters AUTH_USER_MODEL behavior; comment explaining the historical reason is missing. *(django-drf-reviewer)*
- **#943** `backend/apps/users/oauth_views.py:36` — Default FRONTEND_BASE_URL fallback is '<http://localhost:3000>' but actual frontend is on port 5174 per project CLAUDE.md — silent misconfiguration if the env var is missing. *(django-drf-reviewer)*
- **#944** `backend/apps/users/oauth_views.py:309` — GitHub `login` field is used directly as Django username without sanitization beyond uniqueness — GitHub allows characters that may interact poorly with downstream URL or filter logic. *(security-reviewer)*
- **#945** `backend/apps/users/serializers.py:14` — `password` field lacks an explicit `validators=[validate_password]` declaration; validation is performed in `validate()` instead. Field-level validators are more discoverable and surface in OpenAPI. *(api-design-reviewer)*
- **#946** `backend/apps/users/serializers.py:14` — `password` lacks a documented minimum length / `min_length` kwarg; the JSON schema produced for OpenAPI will not declare a constraint even though `validate_password` enforces one at runtime. *(api-design-reviewer)*
- **#947** `backend/apps/users/serializers.py:88` — `UserSerializer` (public) exposes `date_joined` and identity counters but does not honor the `profile_visibility` / `show_email` / `show_location` privacy flags defined in `UserProfileSerializer`. *(api-design-reviewer)*
- **#948** `backend/apps/users/serializers.py:124` — `read_only_fields` correctly protects stats but `id` is missing despite being model-managed; explicit declaration improves clarity even though DRF treats PK read-only by default. *(api-design-reviewer)*
- **#949** `backend/apps/users/services.py:26` — logger usage is fine but several lines use plain `logger.info('Push notification sent ...')` style without a bracketed prefix tag (e.g. [PUSH], [TRUST_LEVEL]); inconsistent with the [CACHE]/[PERF]/[ERROR]/[SECURITY] convention. *(django-drf-reviewer)*
- **#950** `backend/apps/users/services.py:168` — ForumPostService.update_user_post_count counts approved Posts for a user, then unconditionally saves and possibly calls update_trust_level (another save). When called frequently from signals this can produce 3 writes per post creation. *(performance-reviewer)*
- **#951** `backend/apps/users/tests.py:1` — tests.py is an empty stub — actual tests live elsewhere (e.g. tests/ directory) but this file should either be deleted or contain a comment pointing to the real test package to avoid confusion. *(django-drf-reviewer)*
- **#952** `backend/apps/users/tests/test_account_lockout.py:23` — MagicMock import in test_cookie_jwt_authentication and time import in test_account_lockout's mock_time block are inconsistent; minor cleanup of unused imports across the suite would improve clarity. *(test-quality-reviewer)*
- **#953** `backend/apps/users/tests/test_firebase_auth.py:36` — Test sends `email` in the request body; if the view trusts the request email rather than the verified Firebase claim, this test's mock decoded_token (email='<test@example.com>') happens to match, masking a potential bug where the body could spoof a different user. Worth a dedicated test where the body email differs from the verified token email. *(test-quality-reviewer)*
- **#954** `backend/apps/users/tests/test_firebase_auth.py:139` — test_firebase_verification_exception swallows a bare Exception, so any unexpected change in firebase-admin error hierarchy still passes; this couples the test to the catch-all branch only. *(test-quality-reviewer)*
- **#955** `backend/apps/users/tests/test_rate_limiting.py:1` — Module imports `time` and `override_settings` but neither is used. *(test-quality-reviewer)*
- **#956** `backend/apps/users/tests/test_rate_limiting.py:56` — Use of `assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED])` with a single-element list — should be assertEqual. *(test-quality-reviewer)*
- **#957** `backend/apps/users/tests/test_token_refresh.py:220` — test_token_refresh_rate_limiting accepts 200 OR 401 on each successful request, masking a regression where every refresh fails with 401 yet still triggers the 11th-request 429. *(test-quality-reviewer)*
- **#958** `backend/apps/users/tests/test_token_refresh.py:282` — test_token_refresh_updates_last_login uses `time.sleep(0.1)` plus a soft `assertIsNotNone` — neither verifies that last_login was actually updated. *(test-quality-reviewer)*
- **#959** `backend/apps/users/views.py:156` — Login flow: emojis in flash messages (✅/❌) appear in email_preferences_views.py and elsewhere — projects that emit messages to logs/UI should avoid emoji in server-side strings unless explicitly needed. *(django-drf-reviewer)*
- **#960** `backend/apps/users/views.py:668` — `exclude(id__in=list(first_post_ids))` materializes the values_list before exclusion; using the lazy queryset as a subquery would be more efficient. *(django-drf-reviewer)*
- **#961** `backend/apps/users/views.py:870` — care_reminders GET builds reminder_data manually inside a Python loop calling reminder.get_reminder_type_display() and reminder.get_frequency_display() per row — fine, but the loop also performs reminder.saved_care_instructions.display_name access; select_related is in place so this is OK, but a serializer would consolidate. *(performance-reviewer)*
- **#962** `firebase/firestore.indexes.json:21` — user_plants composite index uses collection_name but no public-discovery index (is_public + created_at); if the read rule supports public viewing, queries by is_public will fail without this index at scale. *(flutter-firebase-reviewer)*
- **#963** `firebase/firestore.rules:19` — Users cannot delete their own user document (allow delete: if false) — this conflicts with GDPR right-to-erasure unless a Cloud Function handles deletion server-side; verify a deletion path exists. *(security-reviewer)*
- **#964** `firebase/storage.rules:50` — Avatars are publicly readable with no enumeration protection; predictable {userId}/{imageId} paths leak account presence to scrapers. *(flutter-firebase-reviewer)*
- **#965** `plant_community_mobile/lib/core/routing/app_router.dart:93` — state.extra is cast with 'as Plant?' which will throw a runtime CastError if a non-null value of an unexpected type is passed; the safer 'is Plant ? : null' pattern (or the existing getExtra<Plant>() helper in navigation_extensions.dart) avoids the throw. *(flutter-dart-reviewer)*
- **#966** `plant_community_mobile/lib/core/routing/app_router.dart:99` — Exception('No plant data provided') is constructed in a pageBuilder on every navigation lacking extra; a const-or-cached error is cheaper and more idiomatic. *(flutter-dart-reviewer)*
- **#967** `plant_community_mobile/lib/core/routing/app_router.dart:160` — Inline _buildPageWithTransition duplicates RouteTransitions.fade() from route_transitions.dart, defeating the purpose of the shared transitions module. *(flutter-dart-reviewer)*
- **#968** `plant_community_mobile/lib/core/theme/app_theme.dart:251` — Dark-theme elevated button uses AppColors.lightPrimaryForeground for foregroundColor; while the value (white) is correct, referencing a 'light*' constant inside the dark theme is misleading. *(flutter-dart-reviewer)*
- **#969** `plant_community_mobile/lib/features/camera/camera_screen.dart:35` — _uploadProgress field is updated via setState on every progress callback but is never rendered, causing wasted rebuilds during upload. *(flutter-dart-reviewer)*
- **#970** `plant_community_mobile/lib/features/garden/models/garden_plant.dart:175` — isUnhealthy and other invariant checks compare enum values directly which is fine, but tags is exposed as List<String> without const/unmodifiable wrapper, allowing external mutation of the model's internal state. *(flutter-dart-reviewer)*
- **#971** `plant_community_mobile/lib/features/garden/models/weather_data.dart:57` — Indexing weather[0] without checking the list is non-empty; a malformed OpenWeatherMap payload would throw RangeError instead of a parsing exception. *(flutter-dart-reviewer)*
- **#972** `plant_community_mobile/lib/features/garden/models/weather_data.dart:70` — humidity is parsed as 'int' directly; OpenWeatherMap can return humidity as a JSON number that decodes to double on some platforms, causing a runtime cast failure. *(flutter-dart-reviewer)*
- **#973** `plant_community_mobile/lib/features/home/home_page.dart:140` — Description Text uses maxLines: 3 with no overflow: TextOverflow.ellipsis; long translations could clip awkwardly. *(flutter-dart-reviewer)*
- **#974** `plant_community_mobile/lib/features/results/results_screen.dart:134` — _buildImagePlaceholder uses AppColors.lightCard unconditionally; placeholder is washed out in dark mode (no Brightness check). *(flutter-dart-reviewer)*
- **#975** `plant_community_mobile/lib/features/splash/splash_screen.dart:67` — Calling setState inside Timer.periodic after timer.cancel() and scheduling a Future.delayed for navigation inside the same setState couples animation, scheduling, and navigation; brittle if rebuilds happen. *(flutter-dart-reviewer)*
- **#976** `plant_community_mobile/lib/services/api_service.dart:101` — headers['retry-after']?.first will throw StateError on an empty list — Dio sometimes exposes the header key with an empty list when the value is malformed. *(flutter-dart-reviewer)*
- **#977** `plant_community_mobile/lib/services/auth_service.dart:39` — AuthState.copyWith cannot reset jwtToken or firebaseUser to null because of the `?? this.x` fallback — passing null is silently ignored. *(flutter-dart-reviewer)*
- **#978** `plant_community_mobile/lib/services/auth_service.dart:95` — debugPrint logs full email addresses (and again on lines 137, 147, 176, 189); even gated by kDebugMode this can leak via attached debuggers and on-device logs in side-loaded debug builds. *(flutter-firebase-reviewer)*
- **#979** `plant_community_mobile/lib/services/auth_service.dart:433` — Default-case error message returns Firebase's raw e.message which may include internal details; user-facing string should be a generic fallback. *(flutter-firebase-reviewer)*
- **#980** `plant_community_mobile/lib/services/firebase_storage_service.dart:11` — NotifierProvider with FirebaseStorageService.new tear-off ignores the constructor's optional named parameters (storage, uuid), making it impossible to override dependencies in tests through the provider. *(flutter-firebase-reviewer)*
- **#981** `plant_community_mobile/lib/services/firebase_storage_service.dart:41` — Parameter typed as `Function(double progress)?` rather than the more specific `void Function(double progress)?`, weakening type-checking on the callback. *(flutter-dart-reviewer)*
- **#982** `plant_community_mobile/lib/services/firestore_service.dart:261` — doc.data()! null-force-unwrap; although doc.exists is true, defensive code should still use a null check rather than `!`. *(flutter-dart-reviewer)*
- **#983** `plant_community_mobile/lib/services/plant_identification_service.dart:27` — Same issue — onUploadProgress typed as untyped Function instead of `void Function(double progress)?`. *(flutter-dart-reviewer)*
- **#984** `plant_community_mobile/lib/shared/widgets/feature_card.dart:92` — Description text color is sourced from textTheme.bodySmall.color (a different text style) which conflates style tokens; prefer colorScheme.onSurfaceVariant for secondary body text in M3. *(flutter-dart-reviewer)*
- **#985** `plant_community_mobile/lib/shared/widgets/gradient_button.dart:87` — Container with BoxDecoration is rebuilt on every build; consider extracting the gradient/decoration outside build or using DecoratedBox for slightly clearer intent (cosmetic). *(flutter-dart-reviewer)*
- **#986** `plant_community_mobile/lib/shared/widgets/gradient_button.dart:121` — SizedBox(width: AppSpacing.sm) is not marked const although all arguments are constants. *(flutter-dart-reviewer)*
- **#987** `plant_community_mobile/lib/shared/widgets/loading_indicator.dart:61` — Default color is hardcoded to AppColors.green600 instead of falling back to Theme.of(context).colorScheme.primary, breaking themeability for non-green contexts. *(flutter-dart-reviewer)*
- **#988** `plant_community_mobile/lib/shared/widgets/loading_indicator.dart:65` — Overlay uses Colors.black.withValues(alpha: 0.5) for scrim; Material 3 recommends colorScheme.scrim for the modal scrim color. *(flutter-dart-reviewer)*
- **#989** `web/src/components/PlantIdentification/FileUpload.tsx:24` — useEffect cleanup revokes the previous preview URL only because it's keyed on [preview]; clearing preview manually via clearPreview already revokes — small redundancy but correct. No action required, just verify intent. *(react-typescript-reviewer)*
- **#990** `web/src/components/PlantIdentification/IdentificationResults.tsx:52` — Uses array index as React key for suggestions list — fine here since list isn't mutated, but a stable id (e.g., scientific_name) would be safer. *(react-typescript-reviewer)*
- **#991** `web/src/components/diagnosis/DiagnosisCard.tsx:73` — Uses native alert() / confirm() for user feedback — blocks main thread, not testable, no styling. Prefer a toast/notification system. *(react-typescript-reviewer)*
- **#992** `web/src/components/diagnosis/ReminderManager.tsx:211` — formData useState uses an inline object with `as ReminderType` cast — type narrows only for the initial value; safer with explicit useState<ReminderFormData>(). *(react-typescript-reviewer)*
- **#993** `web/src/components/diagnosis/SaveDiagnosisModal.tsx:31` — formData state initializer is an inline object literal without an explicit type — TS infers loose types and any later field added to the shape goes unchecked. *(react-typescript-reviewer)*
- **#994** `web/src/components/forum/ImageUploadWidget.tsx:58` — useEffect copies `attachments` prop into local `orderedAttachments` state on every prop change — triggers re-render churn during reorder mid-flight (can clobber optimistic update if parent re-emits). *(react-typescript-reviewer)*
- **#995** `web/src/components/forum/TipTapEditor.tsx:165` — Insert link uses window.prompt() — same UX/test concerns; also prompt doesn't sanitize the URL, could insert javascript: link (TipTap Link extension does validate but worth confirming). *(react-typescript-reviewer)*
- **#996** `web/src/contexts/AuthContext.test.tsx:380` — Memoization test on the context object value tests an implementation detail (useMemo dependency stability) rather than user-visible behavior; brittle to legitimate refactors that still avoid unnecessary re-renders. *(test-quality-reviewer)*
- **#997** `web/src/contexts/AuthContext.test.tsx:461` — Test name 'error has correct structure with code and message' bundles structure assertions with NETWORK_ERROR categorization — the categorization is already covered in the Error Categorization describe block; mixing both reduces clarity per 'one assertion concept per test'. *(test-quality-reviewer)*
- **#998** `web/src/contexts/AuthContext.test.tsx:594` — Test asserts on `removeItemSpy.toHaveBeenCalledWith('requestId')` rather than the observable outcome (sessionStorage.getItem('requestId') being null) — this couples the test to the current implementation detail of how the request ID is rotated. *(test-quality-reviewer)*
- **#999** `web/src/contexts/AuthContext.test.tsx:621` — Same implementation-detail coupling: spies on removeItem rather than asserting sessionStorage state after signup. *(test-quality-reviewer)*
- **#1000** `web/src/contexts/AuthContext.tsx:218` — login, signup, logout, and clearError handlers are not wrapped in useCallback so they get a new identity on every render of AuthProvider, defeating downstream memoization for any consumer that lists them as effect/callback deps. *(react-typescript-reviewer)*
- **#1001** `web/src/contexts/AuthContext.tsx:300` — useMemo dependency array omits login/logout/signup/clearError; those functions are recreated every render and the memo retains stale references (safe today since they only use stable setters/module imports, but ESLint exhaustive-deps will flag it and it becomes a footgun if these handlers ever close over state). *(react-typescript-reviewer)*
- **#1002** `web/src/contexts/RequestContext.test.tsx:53` — vi.unstubAllEnvs() called in afterEach but no test in the file uses vi.stubEnv — dead code that misleads readers about teardown semantics. *(test-quality-reviewer)*
- **#1003** `web/src/contexts/RequestContext.test.tsx:146` — Memoization test relies on referential equality (firstValue === secondValue) for a primitive string — strings of identical content are always equal by reference in JS, so this test cannot detect a memoization regression. *(test-quality-reviewer)*

---

## ℹ️ Info (40)

- **#1004** `backend/apps/blog/_services_deprecated.py:1` — File is named *_deprecated.py but still defines live services that duplicate code in services/plant_data_lookup_service.py and services/block_auto_population_service.py. *(django-drf-reviewer)*
- **#1005** `backend/apps/blog/admin.py:1` — Empty admin.py — fine for Wagtail apps but explicit comment 'Wagtail handles admin via wagtail_hooks.py' would aid future maintainers. *(django-drf-reviewer)*
- **#1006** `backend/apps/blog/api/endpoints.py:15` — Wagtail API viewsets intentionally set versioning_class = None, bypassing DRF NamespaceVersioning. No OpenAPI deprecation note distinguishing legacy /api/v2/ (Wagtail) routes from /api/v1/ DRF versioned routes. *(api-design-reviewer)*
- **#1007** `backend/apps/blog/api/viewsets.py:66` — versioning_class=None disables DRF API versioning for Wagtail API. *(wagtail-reviewer)*
- **#1008** `backend/apps/blog/models.py:564` — BlogPostPage inherits HeadlessPreviewMixin and BlogBasePage (multi-table inheritance via Wagtail Page). *(wagtail-reviewer)*
- **#1009** `backend/apps/blog/services/ai_cache_service.py:71` — Cache key truncates SHA-256 to 16 hex chars (64 bits) — collision probability low but present at scale. *(performance-reviewer)*
- **#1010** `backend/apps/blog/tests.py:1` — Empty stub tests.py file alongside a tests/ package — confusing. *(django-drf-reviewer)*
- **#1011** `backend/apps/blog/tests/test_ai_integration.py:221` — Entire GenerateBlogFieldContentAPITestCase is @unittest.skip with note about removed endpoint. *(test-quality-reviewer)*
- **#1012** `backend/apps/blog/tests/test_analytics.py:115` — Pattern of mocking django.db.transaction.on_commit to run callbacks synchronously bypasses transaction semantics. *(test-quality-reviewer)*
- **#1013** `backend/apps/core/management/commands/test_email.py:1` — Filename starts with test_ which can be picked up by Django's test discovery if commands directory ends up on the test path. This is a management command, not a test. *(test-quality-reviewer)*
- **#1014** `backend/apps/core/tests/test_query_sanitization.py:153` — IntegrationTestCase is named 'Integration' but performs no DB or end-to-end interaction - all assertions are pure-string equality identical to the unit tests above. The naming is misleading. *(test-quality-reviewer)*
- **#1015** `backend/apps/forum/permissions.py:351` — Bare `except Exception` swallows all errors when generating the trust-level progress message; acceptable since it falls back to a generic message and does not affect the deny decision, but masks underlying bugs from logs. *(security-reviewer)*
- **#1016** `backend/apps/forum/tests.py:1` — Top-level tests.py is a stub; real tests live in apps/forum/tests/. The stub is harmless but confusing — Django's test runner picks both up. *(django-drf-reviewer)*
- **#1017** `backend/apps/forum/tests/fixtures.py:263` — create_user_progression_scenario is described as a 'placeholder for future use' — confirm it is actually used by tests; otherwise remove. *(test-quality-reviewer)*
- **#1018** `backend/apps/forum/views.py:1` — views.py is unused (only the default 'Create your views here.' comment); urls.py wires viewsets directly. Could be removed. *(django-drf-reviewer)*
- **#1019** `backend/apps/forum_integration/models.py:26` — Code targets Wagtail 7.1.2 (dev) / 7.4 (prod); StreamField use_json_field=True is the default in Wagtail >=5 and the kwarg is deprecated in 7.x — harmless today but will warn/break in a future bump. *(wagtail-reviewer)*
- **#1020** `backend/apps/forum_integration/tests.py:1` — tests.py is empty (60 bytes); no performance test assertions (assertNumQueries) for forum_integration list endpoints. *(performance-reviewer)*
- **#1021** `backend/apps/garden/models.py:25` — Garden, GardenPlant, CareReminder, PestIssue, JournalEntry use auto-incrementing BigAutoField PKs but are exposed via API; project guidance prefers UUIDField for API-exposed models to avoid enumeration. Not a hard violation. *(django-drf-reviewer)*
- **#1022** `backend/apps/garden/serializers.py:41` — Serializers expose integer `id` lookups (via default ModelSerializer); if Garden / GardenPlant / etc. use UUID primary keys per the project's UUID-endpoint convention, switch to `lookup_field='uuid'` on viewsets and consider exposing `uuid` instead of `id`. *(api-design-reviewer)*
- **#1023** `backend/apps/garden/tests.py:1` — tests.py is the default Django stub with no tests; performance regressions in this app cannot be caught by query-count assertions because no perf tests exist. *(performance-reviewer)*
- **#1024** `backend/apps/garden_calendar/api/views.py:568` — TODO note about plant_count annotation indicates a known N+1 in list view; serializer reads garden_bed.plant_count which currently triggers a query per row. *(api-design-reviewer)*
- **#1025** `backend/apps/garden_calendar/services/garden_analytics_service.py:210` — get_care_task_stats has no caching despite being called from get_comprehensive_dashboard; consider Redis cache like the other analytics methods. *(performance-reviewer)*
- **#1026** `backend/apps/garden_calendar/tests/test_file_upload_security.py:277` — Patching PIL.Image.open globally during file validation correctly simulates DecompressionBombError; this is the only allowed external-style mock in the file and is appropriate. *(test-quality-reviewer)*
- **#1027** `backend/apps/plant_identification/api/diagnosis_serializers.py:304` — DiagnosisReminderSerializer correctly uses SlugRelatedField with slug_field='uuid' for diagnosis_card — matches UUID Endpoints pattern. *(api-design-reviewer)*
- **#1028** `backend/apps/plant_identification/models.py:21` — PlantSpecies has no indexes declared in Meta — search-heavy fields (scientific_name, common_names, family, plant_type, auto_stored, identification_count) lack supporting indexes for the common access patterns. *(performance-reviewer)*
- **#1029** `backend/apps/plant_identification/models.py:1862` — PlantCareBlocks defined inline in models.py — checklist recommends StreamField block types live in a dedicated blocks.py for separation of concerns. *(wagtail-reviewer)*
- **#1030** `backend/apps/plant_identification/models.py:2226` — PlantSpeciesPage.content_blocks (StreamField) is exposed via Wagtail API v2 and may serialize as a JSON string in some configurations — consumers must parse with try/except per the StreamField & API checklist. *(wagtail-reviewer)*
- **#1031** `backend/apps/plant_identification/test_diagnosis_models.py:165` — Good practice: docstring documents historical migration rationale (unique_together removal in 0023) — preserves design context for future readers. *(test-quality-reviewer)*
- **#1032** `backend/apps/plant_identification/views.py:727` — PlantDiseaseRequestViewSet has no explicit serializer_class attribute (only get_serializer_class) — DRF schema generation tools (drf-spectacular) may not infer correctly. *(django-drf-reviewer)*
- **#1033** `backend/apps/search/serializers.py:12` — No @extend_schema decorators present in this file (typically applied at the view), so OpenAPI documentation completeness depends on the corresponding views being annotated. *(api-design-reviewer)*
- **#1034** `backend/apps/users/tests.py:1` — tests.py file is essentially empty (only `from django.test import TestCase`); the real tests live in apps/users/tests/. Confirmed there are no query-count assertions for hot endpoints (forum_permissions, dashboard_stats, care_reminders list) — without strict assertEqual(query_count, N) regressions on these will not be caught. *(performance-reviewer)*
- **#1035** `backend/apps/users/tests/test_migrations.py:10` — Coverage is thin — only two tests check default constraints; consider adding a test that exercises a representative data migration's RunPython forward function with synthetic pre-migration rows. *(test-quality-reviewer)*
- **#1036** `firebase/docs/patterns/.gitkeep:1` — Pattern directory is empty; firebase-auth, firestore-rules, and iam pattern docs referenced by the reviewer persona do not yet exist under firebase/docs/patterns/. *(flutter-firebase-reviewer)*
- **#1037** `plant_community_mobile/lib/core/routing/app_router.dart:189` — SettingsScreen and ErrorScreen are declared inside app_router.dart; they would be easier to test and reuse if extracted to features/settings/ and core/widgets/ respectively. *(flutter-dart-reviewer)*
- **#1038** `plant_community_mobile/lib/features/camera/camera_screen.dart:23` — Screen uses ConsumerStatefulWidget but only ever calls ref.read; ConsumerWidget + StatefulConsumerWidget split or local state isolation could simplify the widget. Not a defect, just noted. *(flutter-dart-reviewer)*
- **#1039** `plant_community_mobile/lib/features/garden/models/care_task.dart:187` — isOverdue computes against scheduledDate without normalizing to start-of-day; a task scheduled for today at 9am but called at 9:01am will report overdue rather than dueToday. *(flutter-dart-reviewer)*
- **#1040** `web/src/components/StreamFieldRenderer.tsx:16` — SafeHTML loading state shows the literal text 'Loading...' inline; can cause layout flash. Acceptable trade-off for async DOMPurify import but worth noting. *(react-typescript-reviewer)*
- **#1041** `web/src/components/layout/UserMenu.tsx:69` — useEffect cleanup is only registered when `isOpen` is true; when isOpen flips false the event listener is removed correctly, but if a state change re-runs effect mid-event the listener may briefly miss. Working as intended; documenting. *(react-typescript-reviewer)*
- **#1042** `web/src/contexts/AuthContext.tsx:143` — Timer ref is typed as number, which assumes browser setInterval; correct for this code path but ReturnType<typeof setInterval> is more portable and matches the project's documented gotcha pattern. *(react-typescript-reviewer)*
- **#1043** `web/src/contexts/RequestContext.test.tsx:232` — Hard-coded UUID '00010203-0405-4607-8809-0a0b0c0d0e0f' encodes specific RFC 4122 v4 bit-flipping; informative but tightly coupled to implementation; acceptable since the implementation is the spec. *(test-quality-reviewer)*

---

## ⚠️ Failed Invocations (7)

- `react-typescript-reviewer` · `web/pages` — rate-limit reached during wave 8 dispatch (Anthropic limit reset 2026-05-07 20:30 UTC)
- `react-typescript-reviewer` · `web/services` — rate-limit reached during wave 8 dispatch (Anthropic limit reset 2026-05-07 20:30 UTC)
- `test-quality-reviewer` · `web/services` — rate-limit reached during wave 8 dispatch (Anthropic limit reset 2026-05-07 20:30 UTC)
- `react-typescript-reviewer` · `web/tests` — rate-limit reached during wave 8 dispatch (Anthropic limit reset 2026-05-07 20:30 UTC)
- `react-typescript-reviewer` · `web/types` — rate-limit reached during wave 8 dispatch (Anthropic limit reset 2026-05-07 20:30 UTC)
- `react-typescript-reviewer` · `web/utils` — rate-limit reached during wave 8 dispatch (Anthropic limit reset 2026-05-07 20:30 UTC)
- `test-quality-reviewer` · `web/utils` — rate-limit reached during wave 8 dispatch (Anthropic limit reset 2026-05-07 20:30 UTC)
