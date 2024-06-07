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
        "expected_validate_template",
        "expected_apply_succeeded",
        "expected_content",
        "expected_error",
    ),
    [
        # Test case on success
        pytest.param(True, True, b"Hello {{ name }}!", {"name": "World"}, True, True, "Hello World!", None),
        pytest.param(False, True, b"Hello {{ name }}!", {}, True, True, "Hello !", None),
        # Test case on failed
        pytest.param(True, True, b"Hello {{ user }}!", {"name": "World"}, True, False, None, "'user' is undefined"),
        pytest.param(
            True,
            True,
            b"\x80\x81\x82\x83",
            {"name": "World"},
            False,
            False,
            None,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
        ),
        pytest.param(True, True, b"Hello {{ name }!", {"name": "World"}, False, False, None, "unexpected '}'"),
    ],
)
def test_apply(
    is_strict_undefined: bool,
    is_remove_multiple_newline: bool,
    template_content: bytes,
    context: Dict[str, Any],
    expected_validate_template: bool,
    expected_apply_succeeded: bool,
    expected_content: str,
    expected_error: Optional[str],
) -> None:
    render = GhostwriterRender(is_strict_undefined, is_remove_multiple_newline)
    render.load_template_file(BytesIO(template_content))

    assert render.validate_template() == expected_validate_template
    assert render.apply_context(context) == expected_apply_succeeded
    assert render.render_content == expected_content
    assert render.error_message == expected_error
