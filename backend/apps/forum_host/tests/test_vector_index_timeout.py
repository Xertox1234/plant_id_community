"""The query-embedding client carries an explicit timeout.

Similar-topics and ``?semantic=1`` search embed the query on the request
path. The OpenAI SDK's default timeout is 600 s, and uvicorn has no
per-request hard kill the way gunicorn's ``--timeout 120`` had (live forum
replies, slice 1), so the bound has to be on the client itself.
"""

from unittest.mock import patch

from apps.forum_host import constants, vector_indexes
from django.test import SimpleTestCase, override_settings


@override_settings(OPENAI_API_KEY="sk-test-placeholder")  # pragma: allowlist secret
class EmbeddingClientTimeoutTest(SimpleTestCase):
    @patch.object(vector_indexes, "CachedEmbeddingTransformer")
    @patch.object(vector_indexes, "CoreEmbeddingTransformer")
    @patch.object(vector_indexes.LLMService, "create")
    def test_embedding_client_is_built_with_the_embed_timeout(
        self, create, _core, _cached
    ):
        vector_indexes._build_embedding_transformer()

        create.assert_called_once()
        self.assertEqual(
            create.call_args.kwargs.get("timeout"), constants.EMBED_TIMEOUT_SECONDS
        )

    def test_embed_timeout_is_well_under_the_old_gunicorn_backstop(self):
        self.assertLessEqual(constants.EMBED_TIMEOUT_SECONDS, 60)
