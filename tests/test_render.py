from io import BytesIO
from typing import Any, Dict, Optional

import pytest

from features.document_render import DocumentRender


@pytest.mark.unit()
@pytest.mark.parametrize(
    (
        "template_content",
        "format_type",
        "is_strict_undefined",
        "context",
        "expected_validate_template",
        "expected_apply_succeeded",
        "expected_content",
        "expected_error",
    ),
    [
        # Test case on success
        pytest.param(b"Hello {{ name }}!", 3, True, {"name": "World"}, True, True, "Hello World!", None),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            4,
            True,
            {"name": "World"},
            True,
            True,
            "Hello World!\nGood bye World!",
            None,
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            3,
            True,
            {"name": "World"},
            True,
            True,
            "Hello World!\n\nGood bye World!",
            None,
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            2,
            True,
            {"name": "World"},
            True,
            True,
            "Hello World!\n\n  \nGood bye World!",
            None,
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            1,
            True,
            {"name": "World"},
            True,
            True,
            "Hello World!\n\nGood bye World!",
            None,
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            0,
            True,
            {"name": "World"},
            True,
            True,
            "Hello World!\n\n\n  \nGood bye World!",
            None,
        ),
        pytest.param(b"Hello {{ name }}!", 3, False, {}, True, True, "Hello !", None),
        # Test case on failed
        pytest.param(b"Hello {{ user }}!", 3, True, {"name": "World"}, True, False, None, "'user' is undefined"),
        pytest.param(
            b"\x80\x81\x82\x83",
            3,
            True,
            {"name": "World"},
            False,
            False,
            None,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
        ),
        pytest.param(b"Hello {{ name }!", 3, True, {"name": "World"}, False, False, None, "unexpected '}'"),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            -1,
            True,
            {"name": "World"},
            True,
            False,
            None,
            "Unsupported format type",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            99,
            True,
            {"name": "World"},
            True,
            False,
            None,
            "Unsupported format type",
        ),
    ],
)
def test_render(
    template_content: bytes,
    format_type: int,
    is_strict_undefined: bool,
    context: Dict[str, Any],
    expected_validate_template: bool,
    expected_apply_succeeded: bool,
    expected_content: str,
    expected_error: Optional[str],
) -> None:
    """Test render."""

    render = DocumentRender(BytesIO(template_content))

    assert render.is_valid_template == expected_validate_template
    assert render.apply_context(context, format_type, is_strict_undefined) == expected_apply_succeeded
    assert render.render_content == expected_content
    assert render.error_message == expected_error
