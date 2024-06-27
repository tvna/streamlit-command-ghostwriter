from io import BytesIO
from typing import Optional

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.integration()
@pytest.mark.parametrize(
    (
        "active_button",
        "config_file_content",
        "template_file_content",
        "expected_text_area_len",
        "expected_markdown_len",
        "expected_text_area_value",
        "expected_error_objects",
        "expected_warning_objects",
        "expected_success_objects",
    ),
    [
        pytest.param("tab1_execute_text", b'key = "POSITIVE"', b"# This is {{ key }} #", 1, 4, "# This is POSITIVE #", 0, 0, 1),
        pytest.param("tab1_execute_text", None, b"# This is {{ key }} #", 0, 4, None, 0, 1, 0),
        pytest.param("tab1_execute_text", b'key = "POSITIVE"', None, 0, 4, None, 0, 1, 0),
        pytest.param("tab1_execute_text", b"date = 2024-04-01", b"# Day is {{ date }} #", 1, 4, "# Day is 2024-04-01 #", 0, 0, 1),
        pytest.param("tab1_execute_text", b"date = 2024-04-00", b"# Day is {{ date }} #", 0, 4, None, 1, 0, 0),
        pytest.param("tab1_execute_text", b'key = "POSITIVE"', b"# This is {{ key #", 0, 4, None, 1, 0, 0),
        pytest.param("tab1_execute_markdown", b'key = "POSITIVE"', b"# This is {{ key }} #", 0, 5, "# This is POSITIVE #", 0, 0, 1),
        pytest.param("tab1_execute_markdown", None, b"# This is {{ key }} #", 0, 4, None, 0, 1, 0),
        pytest.param("tab1_execute_markdown", b'key = "POSITIVE"', None, 0, 4, None, 0, 1, 0),
        pytest.param("tab1_execute_markdown", b"date = 2024-04-01", b"# Day is {{ date }} #", 0, 5, "# Day is 2024-04-01 #", 0, 0, 1),
        pytest.param("tab1_execute_markdown", b"date = 2024-04-00", b"# Day is {{ date }} #", 0, 4, None, 1, 0, 0),
        pytest.param("tab1_execute_markdown", b'key = "POSITIVE"', b"# This is {{ key #", 0, 4, None, 1, 0, 0),
    ],
)
def test_main_tab1(
    active_button: str,
    config_file_content: Optional[bytes],
    template_file_content: Optional[bytes],
    expected_text_area_len: int,
    expected_markdown_len: int,
    expected_text_area_value: Optional[str],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
) -> None:
    """Testcase for tab1."""

    config_file = None
    template_file = None

    if isinstance(config_file_content, bytes):
        config_file = BytesIO(config_file_content)
        config_file.name = "config.toml"

    if isinstance(template_file_content, bytes):
        template_file = BytesIO(template_file_content)
        template_file.name = "template.j2"

    at = AppTest.from_file("app.py")
    at.session_state["tab1_config_file"] = config_file
    at.session_state["tab1_template_file"] = template_file
    at.session_state["result_format_type"] = "3: testing type"
    at.session_state[active_button] = True
    at.run()

    assert at.session_state["tab1_config_file"] == config_file
    assert at.session_state["tab1_template_file"] == template_file
    assert at.session_state["tab1_result_content"] == expected_text_area_value
    assert at.button(key=active_button).value is True
    assert at.text_area.len == expected_text_area_len
    if expected_text_area_len > 0:
        assert at.text_area(key="tab1_result_textarea").value == expected_text_area_value
    assert at.markdown.len == expected_markdown_len
    assert len(at.error) == expected_error_objects
    assert len(at.warning) == expected_warning_objects
    assert len(at.success) == expected_success_objects


@pytest.mark.integration()
@pytest.mark.parametrize(
    (
        "config_file_content",
        "expected_text_area_len",
        "expected_text_area_value",
        "expected_error_objects",
        "expected_warning_objects",
        "expected_success_objects",
    ),
    [
        pytest.param(b'key = "POSITIVE"', 1, "{'key': 'POSITIVE'}", 0, 0, 1),
        pytest.param(None, 0, None, 0, 1, 0),
        pytest.param(b"key=", 0, None, 1, 1, 0),
    ],
)
def test_main_tab2(
    config_file_content: Optional[bytes],
    expected_text_area_len: int,
    expected_text_area_value: Optional[str],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
) -> None:
    """Testcase for tab2."""

    if isinstance(config_file_content, bytes):
        config_file = BytesIO(config_file_content)
        config_file.name = "config.toml"
    else:
        config_file = None

    at = AppTest.from_file("app.py")
    at.session_state["tab2_config_file"] = config_file
    at.session_state["tab2_execute"] = True
    at.run()

    assert at.session_state["tab2_config_file"] == config_file
    assert at.session_state["tab2_result_content"] == expected_text_area_value
    assert at.button(key="tab2_execute").value is True
    assert at.text_area.len == expected_text_area_len
    if expected_text_area_len > 0:
        assert at.text_area(key="tab2_result_textarea").value == expected_text_area_value
    assert len(at.error) == expected_error_objects
    assert len(at.warning) == expected_warning_objects
    assert len(at.success) == expected_success_objects
