import json
from io import BytesIO
from typing import Any, Dict, Optional

import pytest
import toml
import yaml
from streamlit.testing.v1 import AppTest


@pytest.mark.integration
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
        pytest.param("tab1_execute_text", b'key = "POSITIVE"', b"# This is {{ key }} #", 1, 2, "# This is POSITIVE #", 0, 0, 1),
        pytest.param("tab1_execute_text", None, b"# This is {{ key }} #", 0, 2, None, 0, 1, 0),
        pytest.param("tab1_execute_text", b'key = "POSITIVE"', None, 0, 2, None, 0, 1, 0),
        pytest.param("tab1_execute_text", b"date = 2024-04-01", b"# Day is {{ date }} #", 1, 2, "# Day is 2024-04-01 #", 0, 0, 1),
        pytest.param("tab1_execute_text", b"date = 2024-04-01", b"\x00\x01\x02\x03\x04", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_text", b"\x00\x01\x02\x03\x04", b"# Day is {{ date }} #", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_text", b"date = 2024-04-00", b"# Day is {{ date }} #", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_text", b'key = "POSITIVE"', b"# This is {{ key #", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_text", b"\x00\x01\x02\x03\x04", b"# This is {{ key #", 0, 2, None, 2, 0, 0),
        pytest.param("tab1_execute_text", b"\x00\x01\x02\x03\x04", b"\x00\x01\x02\x03\x04", 0, 2, None, 2, 0, 0),
        pytest.param("tab1_execute_markdown", b'key = "POSITIVE"', b"# This is {{ key }} #", 0, 3, "# This is POSITIVE #", 0, 0, 1),
        pytest.param("tab1_execute_markdown", None, b"# This is {{ key }} #", 0, 2, None, 0, 1, 0),
        pytest.param("tab1_execute_markdown", b'key = "POSITIVE"', None, 0, 2, None, 0, 1, 0),
        pytest.param("tab1_execute_markdown", b"date = 2024-04-01", b"# Day is {{ date }} #", 0, 3, "# Day is 2024-04-01 #", 0, 0, 1),
        pytest.param("tab1_execute_markdown", b"date = 2024-04-01", b"\x00\x01\x02\x03\x04", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_markdown", b"\x00\x01\x02\x03\x04", b"# Day is {{ date }} #", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_markdown", b"date = 2024-04-00", b"# Day is {{ date }} #", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_markdown", b'key = "POSITIVE"', b"# This is {{ key #", 0, 2, None, 1, 0, 0),
        pytest.param("tab1_execute_markdown", b"\x00\x01\x02\x03\x04", b"# This is {{ key #", 0, 2, None, 2, 0, 0),
        pytest.param("tab1_execute_markdown", b"\x00\x01\x02\x03\x04", b"\x00\x01\x02\x03\x04", 0, 2, None, 2, 0, 0),
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
    base_text_area_len = 6

    if isinstance(config_file_content, bytes):
        config_file = BytesIO(config_file_content)
        config_file.name = "config.toml"

    if isinstance(template_file_content, bytes):
        template_file = BytesIO(template_file_content)
        template_file.name = "template.j2"

    at = AppTest.from_file("app.py")
    at.session_state["tab1_config_file"] = config_file
    at.session_state["tab1_template_file"] = template_file
    at.session_state["result_format_type"] = 3
    at.session_state[active_button] = True
    at.run()

    assert at.session_state["tab1_config_file"] == config_file
    assert at.session_state["tab1_template_file"] == template_file
    assert at.session_state["tab1_result_content"] == expected_text_area_value
    assert at.button(key=active_button).value is True
    assert at.text_area.len == base_text_area_len + expected_text_area_len
    if expected_text_area_len > 0:
        assert at.text_area(key="tab1_result_textarea").value == expected_text_area_value
    assert at.markdown.len == expected_markdown_len
    assert at.error.len == expected_error_objects
    assert at.warning.len == expected_warning_objects
    assert at.success.len == expected_success_objects


@pytest.mark.integration
@pytest.mark.parametrize(
    (
        "active_button",
        "config_file_content",
        "expected_text_area_value",
        "expected_error_objects",
        "expected_warning_objects",
        "expected_success_objects",
    ),
    [
        pytest.param("tab2_execute_visual", b'key = "POSITIVE"', {"key": "POSITIVE"}, 0, 0, 1),
        pytest.param("tab2_execute_visual", None, None, 0, 1, 0),
        pytest.param("tab2_execute_visual", b"key=", None, 1, 1, 0),
        pytest.param("tab2_execute_toml", b'key = "POSITIVE"', {"key": "POSITIVE"}, 0, 0, 1),
        pytest.param("tab2_execute_toml", None, None, 0, 1, 0),
        pytest.param("tab2_execute_toml", b"key=", None, 1, 1, 0),
        pytest.param("tab2_execute_yaml", b'key = "POSITIVE"', {"key": "POSITIVE"}, 0, 0, 1),
        pytest.param("tab2_execute_yaml", None, None, 0, 1, 0),
        pytest.param("tab2_execute_yaml", b"key=", None, 1, 1, 0),
    ],
)
def test_main_tab2(
    active_button: str,
    config_file_content: Optional[bytes],
    expected_text_area_value: Optional[Dict[str, Any]],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
) -> None:
    """Testcase for tab2."""

    base_text_area_len = 6

    if config_file_content is None:
        config_file = None
    else:
        config_file = BytesIO(config_file_content)
        config_file.name = "config.toml"

    at = AppTest.from_file("app.py")
    at.session_state["tab2_config_file"] = config_file
    at.session_state[active_button] = True
    at.run()

    assert at.session_state["tab2_config_file"] == config_file
    assert at.button(key=active_button).value is True

    if expected_text_area_value is None:
        assert at.session_state["tab2_result_content"] is None
    else:
        assert isinstance(at.session_state["tab2_result_content"], dict) is True
        assert at.session_state["tab2_result_content"] == expected_text_area_value

    if active_button == "tab2_execute_visual":
        if expected_text_area_value is None:
            assert at.json.len == 0
        else:
            assert at.json.len == 1
            assert at.json[0].value == json.dumps(expected_text_area_value, ensure_ascii=False)
        assert at.text_area.len == base_text_area_len

    if active_button == "tab2_execute_toml":
        assert at.json.len == 0
        if expected_text_area_value is None:
            assert at.text_area.len == base_text_area_len
        else:
            assert at.text_area.len == base_text_area_len + 1
            assert at.text_area(key="tab2_result_textarea").value == toml.dumps(expected_text_area_value)

    if active_button == "tab2_execute_yaml":
        assert at.json.len == 0
        if expected_text_area_value is None:
            assert at.text_area.len == base_text_area_len
        else:
            assert at.text_area.len == base_text_area_len + 1
            assert at.text_area(key="tab2_result_textarea").value == yaml.dump(
                expected_text_area_value, default_flow_style=False, allow_unicode=True, indent=8
            )

    assert at.error.len == expected_error_objects
    assert at.warning.len == expected_warning_objects
    assert at.success.len == expected_success_objects
