from io import BytesIO
from typing import Any, Dict, Optional

import pytest

from features.command_render import GhostwriterRender


@pytest.mark.parametrize(
    (
        "is_strict_undefined",
        "is_remove_multiple_newline",
        "template_content",
        "context",
        "is_successful",
        "result_message",
        "error_message",
    ),
    [
        # Test case on success
        pytest.param(True, True, b"Hello {{ name }}!", {"name": "World"}, True, "Hello World!", None),
        pytest.param(False, True, b"Hello {{ name }}!", {}, True, "Hello !", None),
        # Test case on failed
        pytest.param(True, True, b"Hello {{ user }}!", {"name": "World"}, False, None, "'user' is undefined"),
        pytest.param(
            True,
            True,
            b"\x80\x81\x82\x83",
            {"name": "World"},
            False,
            None,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
        ),
        pytest.param(True, True, b"Hello {{ name }!", {"name": "World"}, False, None, "unexpected '}'"),
    ],
)
def test_apply(
    is_strict_undefined: bool,
    is_remove_multiple_newline: bool,
    template_content: bytes,
    context: Dict[str, Any],
    is_successful: bool,
    result_message: str,
    error_message: Optional[str],
) -> None:
    render = GhostwriterRender(is_strict_undefined, is_remove_multiple_newline)
    render.load_template_file(BytesIO(template_content))

    assert render.apply_context(context) == is_successful
    assert render.render_content == result_message
    assert render.error_message == error_message
