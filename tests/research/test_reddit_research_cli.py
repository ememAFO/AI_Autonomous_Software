import pytest

from scripts.run_reddit_research import validate_cli_inputs


class Args:
    def __init__(
        self,
        query: str = "manual follow up",
        subreddit: str = "smallbusiness",
        industry: str = "home services",
        limit: int = 2,
    ):
        self.query = query
        self.subreddit = subreddit
        self.industry = industry
        self.limit = limit


def test_cli_validation_accepts_safe_inputs():
    args = Args()

    validate_cli_inputs(args)


def test_cli_validation_blocks_empty_query():
    args = Args(query="")

    with pytest.raises(ValueError):
        validate_cli_inputs(args)


def test_cli_validation_blocks_empty_industry():
    args = Args(industry="")

    with pytest.raises(ValueError):
        validate_cli_inputs(args)


def test_cli_validation_blocks_excessive_limit():
    args = Args(limit=100)

    with pytest.raises(ValueError):
        validate_cli_inputs(args)


def test_cli_validation_blocks_unknown_subreddit():
    args = Args(subreddit="unknownprivatecommunity")

    with pytest.raises(ValueError):
        validate_cli_inputs(args)

def test_cli_validation_blocks_zero_limit():
    args = Args(limit=0)

    with pytest.raises(ValueError):
        validate_cli_inputs(args)
