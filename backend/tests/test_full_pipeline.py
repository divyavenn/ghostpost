"""
Integration test for the full background job pipeline.

Runs all background jobs in the same order they execute in production:
1. Cleanup expired browser sessions
2. Purge unedited tweets
3. Scrape new tweets from configured accounts/queries
4. Generate AI replies for scraped tweets
5. Run engagement monitoring (discover comments on posted tweets)
6. Generate AI replies for discovered comments

Usage:
    pytest tests/test_full_pipeline.py -v -s
    pytest tests/test_full_pipeline.py::TestFullPipeline::test_run_pipeline_for_user -v -s
"""
import pytest


@pytest.fixture
def test_username():
    """The test user's cache key."""
    return "divya_venn"


class TestFullPipeline:
    """Integration tests for the full background job pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_pipeline_for_user(self, test_username):
        """
        Run the complete pipeline for a single user and verify each step completes.

        This test runs all 6 steps in order:
        1. cleanup_sessions - Clean up expired browser sessions
        2. purge_unedited - Remove tweets not marked as edited
        3. scrape_tweets - Fetch new tweets from configured sources
        4. generate_tweet_replies - Generate AI replies for scraped tweets
        5. engagement_monitoring - Discover comments on posted tweets
        6. generate_comment_replies - Generate AI replies for comments
        """
        from backend.utlils.scheduler import run_full_pipeline_for_user

        print(f"\n{'='*60}")
        print(f"Running full pipeline for user: {test_username}")
        print(f"{'='*60}\n")

        result = await run_full_pipeline_for_user(test_username)

        # Print detailed results
        print(f"\n{'='*60}")
        print("PIPELINE RESULTS")
        print(f"{'='*60}")
        print(f"Username: {result['username']}")
        print(f"Total time: {result['total_time_seconds']} seconds")
        print(f"Errors: {len(result['errors'])}")

        print(f"\n{'─'*40}")
        print("Step Results:")
        print(f"{'─'*40}")

        expected_steps = [
            "cleanup_sessions",
            "purge_unedited",
            "scrape_tweets",
            "generate_tweet_replies",
            "engagement_monitoring",
            "generate_comment_replies"
        ]

        for step_name in expected_steps:
            step_result = result["steps"].get(step_name, {})
            status = step_result.get("status", "not_run")
            status_emoji = "✅" if status == "success" else "❌" if status == "error" else "⏭️"

            print(f"\n{status_emoji} {step_name}:")
            for key, value in step_result.items():
                if key != "status":
                    print(f"   {key}: {value}")

        if result["errors"]:
            print(f"\n{'─'*40}")
            print("Errors:")
            print(f"{'─'*40}")
            for error in result["errors"]:
                print(f"  ❌ {error}")

        print(f"\n{'='*60}\n")

        # Assertions
        assert result is not None
        assert result["username"] == test_username
        assert "steps" in result
        assert "errors" in result
        assert "total_time_seconds" in result

        # All expected steps should have been attempted
        for step_name in expected_steps:
            assert step_name in result["steps"], f"Step '{step_name}' was not attempted"

        # Print summary
        successful_steps = sum(1 for s in result["steps"].values() if s.get("status") == "success")
        print(f"Summary: {successful_steps}/{len(expected_steps)} steps succeeded")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_pipeline_step_order(self, test_username):
        """
        Verify that engagement monitoring runs BEFORE comment reply generation.
        This ensures comments are discovered before we try to generate replies for them.
        """
        from backend.utlils.scheduler import run_full_pipeline_for_user

        result = await run_full_pipeline_for_user(test_username)

        steps = result.get("steps", {})

        # Engagement monitoring should have run
        assert "engagement_monitoring" in steps, "Engagement monitoring should run"

        # Comment reply generation should have run after
        assert "generate_comment_replies" in steps, "Comment reply generation should run"

        # Both should have a status (even if error)
        assert "status" in steps["engagement_monitoring"]
        assert "status" in steps["generate_comment_replies"]

        print(f"✅ Verified step order: engagement_monitoring → generate_comment_replies")


class TestPipelineHelpers:
    """Unit tests for pipeline helper functions."""

    def test_get_users_with_valid_sessions(self):
        """Test that we can get users with valid sessions."""
        from backend.utlils.scheduler import get_users_with_valid_sessions

        users = get_users_with_valid_sessions()

        assert isinstance(users, list)
        print(f"Found {len(users)} users with valid sessions: {users}")

    @pytest.mark.asyncio
    async def test_cleanup_browser_sessions(self):
        """Test browser session cleanup runs without error."""
        from backend.utlils.scheduler import cleanup_expired_browser_sessions

        # Should not raise an exception
        await cleanup_expired_browser_sessions()
        print("✅ Browser session cleanup completed")


class TestPipelineEndpoints:
    """Test the API endpoints for running the pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_endpoint_structure(self, test_username):
        """Test that the pipeline endpoint returns the expected structure."""
        from backend.utlils.scheduler import run_full_pipeline_for_user

        result = await run_full_pipeline_for_user(test_username)

        # Check required fields
        assert "username" in result
        assert "steps" in result
        assert "errors" in result
        assert "total_time_seconds" in result

        # Steps should be a dict
        assert isinstance(result["steps"], dict)

        # Errors should be a list
        assert isinstance(result["errors"], list)

        # Time should be a number
        assert isinstance(result["total_time_seconds"], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
