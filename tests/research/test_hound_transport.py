import pytest

from src.adapters.hound_transport import (
    HoundTransportError,
    MCPStdioTransport,
)


def test_hound_transport_accepts_pinned_hound_command() -> None:
    transport = MCPStdioTransport(("hound", "--stdio"))

    assert transport.command == ("hound", "--stdio")


@pytest.mark.parametrize(
    "command",
    [
        ("python", "-c", "print('unexpected')"),
        ("/tmp/hound",),
        ("bash", "-c", "echo unexpected"),
    ],
)
def test_hound_transport_rejects_arbitrary_executable(
    command: tuple[str, ...],
) -> None:
    with pytest.raises(HoundTransportError, match="pinned"):
        MCPStdioTransport(command)


def test_hound_transport_rejects_plain_string_command() -> None:
    with pytest.raises(HoundTransportError, match="sequence"):
        MCPStdioTransport("hound")  # type: ignore[arg-type]


def test_hound_transport_rejects_empty_argument() -> None:
    with pytest.raises(HoundTransportError, match="non-empty"):
        MCPStdioTransport(("hound", ""))
