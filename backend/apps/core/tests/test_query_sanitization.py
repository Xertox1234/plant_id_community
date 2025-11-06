"""
Tests for query sanitization utilities.

Tests the escape_search_query() function to ensure SQL wildcards are properly
escaped before using in Django ORM icontains queries.
"""

from django.test import TestCase
from apps.core.utils.query_sanitization import escape_search_query, escape_search_query_optional


class EscapeSearchQueryTestCase(TestCase):
    """Test SQL wildcard escaping in search queries."""

    def test_escape_percent_wildcard(self):
        """Test that % wildcard is properly escaped."""
        result = escape_search_query("test%")
        self.assertEqual(result, r"test\%")

    def test_escape_underscore_wildcard(self):
        """Test that _ wildcard is properly escaped."""
        result = escape_search_query("test_name")
        self.assertEqual(result, r"test\_name")

    def test_escape_both_wildcards(self):
        """Test that both % and _ wildcards are escaped."""
        result = escape_search_query("test%_data")
        self.assertEqual(result, r"test\%\_data")

    def test_escape_multiple_percent_wildcards(self):
        """Test multiple % wildcards are all escaped."""
        result = escape_search_query("test%something%else")
        self.assertEqual(result, r"test\%something\%else")

    def test_escape_multiple_underscore_wildcards(self):
        """Test multiple _ wildcards are all escaped."""
        result = escape_search_query("test_some_name")
        self.assertEqual(result, r"test\_some\_name")

    def test_no_wildcards_unchanged(self):
        """Test that normal text without wildcards is unchanged."""
        result = escape_search_query("normal text")
        self.assertEqual(result, "normal text")

    def test_empty_string(self):
        """Test that empty string is returned unchanged."""
        result = escape_search_query("")
        self.assertEqual(result, "")

    def test_whitespace_only(self):
        """Test that whitespace-only string is unchanged."""
        result = escape_search_query("   ")
        self.assertEqual(result, "   ")

    def test_special_characters_except_wildcards(self):
        """Test that other special characters are not escaped."""
        # Only % and _ should be escaped, not other characters
        result = escape_search_query("test@email.com")
        self.assertEqual(result, "test@email.com")

        result = escape_search_query("test-value")
        self.assertEqual(result, "test-value")

        result = escape_search_query("test's value")
        self.assertEqual(result, "test's value")

    def test_backslash_not_escaped(self):
        """Test that backslashes are NOT escaped (not SQL wildcards).

        Backslash is not a special character in PostgreSQL ILIKE patterns.
        Only % (any characters) and _ (single character) are wildcards.
        This test documents that backslashes pass through unchanged, while
        SQL wildcards in the same string ARE escaped.
        """
        # Test 1: Windows file path with backslashes - unchanged
        result = escape_search_query(r"C:\Users\test")
        self.assertEqual(result, r"C:\Users\test")

        # Test 2: Backslash followed by percent - both preserved, but % gets escaped
        # Input has: backslash + percent
        # Output has: backslash + escaped percent (\%)
        result = escape_search_query("test\\%value")  # Has: \ and %
        self.assertEqual(result, "test\\\\%value")    # Has: \ and \%

        # Test 3: Backslash followed by underscore - both preserved, but _ gets escaped
        result = escape_search_query("test\\_name")  # Has: \ and _
        self.assertEqual(result, "test\\\\_name")    # Has: \ and \_

        # Test 4: Simple backslash without wildcards - completely unchanged
        result = escape_search_query("test\\data")
        self.assertEqual(result, "test\\data")

    def test_wildcard_at_start(self):
        """Test wildcard at the beginning of string."""
        result = escape_search_query("%test")
        self.assertEqual(result, r"\%test")

        result = escape_search_query("_test")
        self.assertEqual(result, r"\_test")

    def test_wildcard_at_end(self):
        """Test wildcard at the end of string."""
        result = escape_search_query("test%")
        self.assertEqual(result, r"test\%")

        result = escape_search_query("test_")
        self.assertEqual(result, r"test\_")

    def test_only_wildcards(self):
        """Test string containing only wildcards."""
        result = escape_search_query("%%")
        self.assertEqual(result, r"\%\%")

        result = escape_search_query("__")
        self.assertEqual(result, r"\_\_")

        result = escape_search_query("%_")
        self.assertEqual(result, r"\%\_")

    def test_unicode_text_with_wildcards(self):
        """Test that Unicode text is handled correctly."""
        result = escape_search_query("café%")
        self.assertEqual(result, r"café\%")

        result = escape_search_query("测试_data")
        self.assertEqual(result, r"测试\_data")


class EscapeSearchQueryOptionalTestCase(TestCase):
    """Test None-safe wrapper for escape_search_query."""

    def test_escape_with_value(self):
        """Test that non-None values are properly escaped."""
        result = escape_search_query_optional("test%")
        self.assertEqual(result, r"test\%")

    def test_none_value_returns_none(self):
        """Test that None input returns None."""
        result = escape_search_query_optional(None)
        self.assertIsNone(result)

    def test_empty_string(self):
        """Test that empty string is handled correctly."""
        result = escape_search_query_optional("")
        self.assertEqual(result, "")

    def test_whitespace(self):
        """Test that whitespace is handled correctly."""
        result = escape_search_query_optional("  ")
        self.assertEqual(result, "  ")


class IntegrationTestCase(TestCase):
    """Integration tests to verify wildcard escaping works in practice."""

    def test_escaped_query_matches_literal_percent(self):
        r"""
        Test that escaped % matches literal % character, not as wildcard.

        This is a conceptual test - actual behavior depends on database backend.
        In PostgreSQL, \% in ILIKE pattern matches literal %.
        """
        # Input: "test%"
        # Without escape: matches "test", "testing", "test123", etc.
        # With escape: matches only "test%" (literal)
        input_query = "test%"
        escaped = escape_search_query(input_query)

        # Verify escaping occurred
        self.assertEqual(escaped, r"test\%")
        self.assertIn(r'\%', escaped)
        self.assertNotEqual(escaped, input_query)

    def test_escaped_query_matches_literal_underscore(self):
        """
        Test that escaped _ matches literal _ character, not as wildcard.

        Without escape: "test_" matches "test1", "testa", etc. (any single char)
        With escape: "test_" matches only "test_" (literal underscore)
        """
        input_query = "test_name"
        escaped = escape_search_query(input_query)

        # Verify escaping occurred
        self.assertEqual(escaped, r"test\_name")
        self.assertIn(r'\_', escaped)

    def test_typical_user_input_scenarios(self):
        """Test common real-world user input patterns."""
        # Scenario 1: User searches for "C++" (common in tech)
        result = escape_search_query("C++")
        self.assertEqual(result, "C++")  # No wildcards, unchanged

        # Scenario 2: User searches for "test_file.txt"
        result = escape_search_query("test_file.txt")
        self.assertEqual(result, r"test\_file.txt")  # Underscore escaped

        # Scenario 3: User searches for "50% off"
        result = escape_search_query("50% off")
        self.assertEqual(result, r"50\% off")  # Percent escaped

        # Scenario 4: User searches for "python_django"
        result = escape_search_query("python_django")
        self.assertEqual(result, r"python\_django")  # Underscore escaped
