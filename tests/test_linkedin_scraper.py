import sys
import types
import unittest


# The project installs these in GitHub Actions. Stubs keep unit tests focused on
# the local validation helpers and avoid network access in a fresh checkout.
sys.modules.setdefault("requests", types.ModuleType("requests"))
sys.modules.setdefault("feedparser", types.ModuleType("feedparser"))

import linkedin_scraper


class DraftQualityTests(unittest.TestCase):
    SOURCE = (
        "Anthropic said entry-level technical hires were 10% of its hires in 2025, "
        "down from 20% two years earlier. The company did not give a reason."
    )

    def test_preserves_a_reported_number(self):
        post = "Anthropic said entry-level technical hires were 10% of its hires in 2025."
        self.assertFalse(linkedin_scraper.omits_available_numeric_fact(post, self.SOURCE))
        self.assertFalse(linkedin_scraper.has_unsupported_numeric_fact(post, self.SOURCE))

    def test_rejects_new_or_vague_numeric_claims(self):
        invented = "Anthropic said entry-level technical hires were 15% of its hires."
        vague = "Anthropic said entry-level technical hiring changed."
        self.assertTrue(linkedin_scraper.has_unsupported_numeric_fact(invented, self.SOURCE))
        self.assertTrue(linkedin_scraper.omits_available_numeric_fact(vague, self.SOURCE))

    def test_rejects_causal_explanation_missing_from_source(self):
        post = "Anthropic reduced entry-level hiring because AI tools now do the work."
        self.assertTrue(linkedin_scraper.has_unsupported_causality(post, self.SOURCE))

    def test_allows_causality_when_source_states_it(self):
        source = self.SOURCE + " It said this was because some work is now automated."
        post = "Anthropic said this changed because some work is now automated."
        self.assertFalse(linkedin_scraper.has_unsupported_causality(post, source))

    def test_prompt_allows_only_grounded_questions(self):
        prompt = linkedin_scraper.build_post_prompt("A headline", "https://example.com", self.SOURCE)
        self.assertIn("single grounded question is allowed", prompt)
        self.assertIn("If the source has a useful number", prompt)


if __name__ == "__main__":
    unittest.main()
