import pytest

from src.adapters.reddit_adapter import RedditAdapter, RedditPost


def test_reddit_adapter_processes_business_pain_posts():
    posts = [
        RedditPost(
            subreddit="smallbusiness",
            title="Clients stop replying after quotes",
            body="I keep losing leads because manual follow up takes too long.",
            url="https://reddit.example/post-1",
        ),
        RedditPost(
            subreddit="smallbusiness",
            title="Nice dashboard colour",
            body="I like blue dashboards for personal projects.",
            url="https://reddit.example/post-2",
        ),
    ]

    result = RedditAdapter().process_posts(posts=posts, industry="home services")

    assert result.processed_count == 2
    assert result.accepted_count == 1
    assert result.rejected_count == 1
    assert result.results[0].opportunity.source.value == "reddit"
    assert result.results[0].report_path.exists()


def test_reddit_adapter_blocks_too_many_posts():
    posts = [
        RedditPost(
            subreddit="smallbusiness",
            title="Manual follow up",
            body="Clients stop replying after quotes and I keep losing leads.",
        )
        for _ in range(51)
    ]

    with pytest.raises(ValueError):
        RedditAdapter().process_posts(posts=posts, industry="home services")


def test_reddit_post_full_text_combines_title_and_body():
    post = RedditPost(
        subreddit="entrepreneur",
        title="Missed bookings",
        body="Manual appointment reminders are annoying.",
    )

    assert "Missed bookings" in post.full_text
    assert "Manual appointment reminders are annoying." in post.full_text
