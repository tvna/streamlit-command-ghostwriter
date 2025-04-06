import json
from io import BytesIO
from typing import Any, Dict, Final, Optional

import pytest
import toml
import yaml
from _pytest.mark.structures import MarkDecorator
from streamlit.testing.v1 import AppTest

INTEGRATION: MarkDecorator = pytest.mark.integration

# Constants for UI element counts and messages
BASE_TEXT_AREA_COUNT: Final[int] = 6
BASE_MARKDOWN_COUNT: Final[int] = 2
RENDERED_MARKDOWN_COUNT: Final[int] = BASE_MARKDOWN_COUNT + 1
RENDERED_TEXT_AREA_COUNT: Final[int] = 1
NO_RENDERED_TEXT_AREA: Final[int] = 0
NO_JSON_OUTPUT: Final[int] = 0
ONE_JSON_OUTPUT: Final[int] = 1
NO_MESSAGES: Final[int] = 0
ONE_MESSAGE: Final[int] = 1
TWO_MESSAGES: Final[int] = 2


@INTEGRATION
@pytest.mark.parametrize(
    (
        "active_button",
        "config_file_content",
        "template_file_content",
        "expected_text_area_len_delta",  # Changed name for clarity
        "expected_markdown_len",
        "expected_text_area_value",
        "expected_error_objects",
        "expected_warning_objects",
        "expected_success_objects",
    ),
    [
        pytest.param(
            "tab1_execute_text",
            b'key = "POSITIVE"',
            b"# This is {{ key }} #",
            RENDERED_TEXT_AREA_COUNT,
            BASE_MARKDOWN_COUNT,
            "# This is POSITIVE #",
            NO_MESSAGES,
            NO_MESSAGES,
            ONE_MESSAGE,
            id="text_render_valid_basic_template",
        ),
        pytest.param(
            "tab1_execute_text",
            None,
            b"# This is {{ key }} #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            NO_MESSAGES,
            ONE_MESSAGE,
            NO_MESSAGES,
            id="text_render_invalid_missing_config",
        ),
        pytest.param(
            "tab1_execute_text",
            b'key = "POSITIVE"',
            None,
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            NO_MESSAGES,
            ONE_MESSAGE,
            NO_MESSAGES,
            id="text_render_invalid_missing_template",
        ),
        pytest.param(
            "tab1_execute_text",
            b"date = 2024-04-01",
            b"# Day is {{ date }} #",
            RENDERED_TEXT_AREA_COUNT,
            BASE_MARKDOWN_COUNT,
            "# Day is 2024-04-01 #",
            NO_MESSAGES,
            NO_MESSAGES,
            ONE_MESSAGE,
            id="text_render_valid_date_format",
        ),
        pytest.param(
            "tab1_execute_text",
            b"date = 2024-04-01",
            b"\x00\x01\x02\x03\x04",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="text_render_invalid_template_bytes",
        ),
        pytest.param(
            "tab1_execute_text",
            b"\x00\x01\x02\x03\x04",
            b"# Day is {{ date }} #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="text_render_invalid_config_bytes",
        ),
        pytest.param(
            "tab1_execute_text",
            b"date = 2024-04-00",
            b"# Day is {{ date }} #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="text_render_invalid_date_format",
        ),
        pytest.param(
            "tab1_execute_text",
            b'key = "POSITIVE"',
            b"# This is {{ key #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="text_render_invalid_syntax_error",
        ),
        pytest.param(
            "tab1_execute_text",
            b"\x00\x01\x02\x03\x04",
            b"# This is {{ key #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            TWO_MESSAGES,
            NO_MESSAGES,
            NO_MESSAGES,
            id="text_render_invalid_multiple_errors",
        ),
        pytest.param(
            "tab1_execute_text",
            b"\x00\x01\x02\x03\x04",
            b"\x00\x01\x02\x03\x04",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            TWO_MESSAGES,
            NO_MESSAGES,
            NO_MESSAGES,
            id="text_render_invalid_all_bytes",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b'key = "POSITIVE"',
            b"# This is {{ key }} #",
            NO_RENDERED_TEXT_AREA,  # Markdown render adds markdown, not text area
            RENDERED_MARKDOWN_COUNT,
            "# This is POSITIVE #",  # Value is stored in session state but not text area
            NO_MESSAGES,
            NO_MESSAGES,
            ONE_MESSAGE,
            id="markdown_render_valid_basic_template",
        ),
        pytest.param(
            "tab1_execute_markdown",
            None,
            b"# This is {{ key }} #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            NO_MESSAGES,
            ONE_MESSAGE,
            NO_MESSAGES,
            id="markdown_render_invalid_missing_config",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b'key = "POSITIVE"',
            None,
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            NO_MESSAGES,
            ONE_MESSAGE,
            NO_MESSAGES,
            id="markdown_render_invalid_missing_template",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b"date = 2024-04-01",
            b"# Day is {{ date }} #",
            NO_RENDERED_TEXT_AREA,
            RENDERED_MARKDOWN_COUNT,
            "# Day is 2024-04-01 #",
            NO_MESSAGES,
            NO_MESSAGES,
            ONE_MESSAGE,
            id="markdown_render_valid_date_format",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b"date = 2024-04-01",
            b"\x00\x01\x02\x03\x04",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="markdown_render_invalid_template_bytes",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b"\x00\x01\x02\x03\x04",
            b"# Day is {{ date }} #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="markdown_render_invalid_config_bytes",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b"date = 2024-04-00",
            b"# Day is {{ date }} #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="markdown_render_invalid_date_format",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b'key = "POSITIVE"',
            b"# This is {{ key #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            ONE_MESSAGE,
            NO_MESSAGES,
            NO_MESSAGES,
            id="markdown_render_invalid_syntax_error",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b"\x00\x01\x02\x03\x04",
            b"# This is {{ key #",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            TWO_MESSAGES,
            NO_MESSAGES,
            NO_MESSAGES,
            id="markdown_render_invalid_multiple_errors",
        ),
        pytest.param(
            "tab1_execute_markdown",
            b"\x00\x01\x02\x03\x04",
            b"\x00\x01\x02\x03\x04",
            NO_RENDERED_TEXT_AREA,
            BASE_MARKDOWN_COUNT,
            None,
            TWO_MESSAGES,
            NO_MESSAGES,
            NO_MESSAGES,
            id="markdown_render_invalid_all_bytes",
        ),
    ],
)
def test_main_tab1(
    active_button: str,
    config_file_content: Optional[bytes],
    template_file_content: Optional[bytes],
    expected_text_area_len_delta: int,
    expected_markdown_len: int,
    expected_text_area_value: Optional[str],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
) -> None:
    """Testcase for tab1."""

    config_file = None
    template_file = None
    # Use the constant for base text area count
    current_base_text_area_len = BASE_TEXT_AREA_COUNT

    if isinstance(config_file_content, bytes):
        config_file = BytesIO(config_file_content)
        config_file.name = "config.toml"

    if isinstance(template_file_content, bytes):
        template_file = BytesIO(template_file_content)
        template_file.name = "template.j2"

    at = AppTest.from_file("app.py")
    at.session_state["tab1_config_file"] = config_file
    at.session_state["tab1_template_file"] = template_file
    at.session_state["result_format_type"] = 3  # Assuming 3 means text/markdown, keep if meaningful
    at.session_state[active_button] = True
    at.run()

    assert at.session_state["tab1_config_file"] == config_file, "Config file in session state mismatch"
    assert at.session_state["tab1_template_file"] == template_file, "Template file in session state mismatch"
    assert at.session_state["tab1_result_content"] == expected_text_area_value, "Result content in session state mismatch"
    assert at.button(key=active_button).value is True, f"Button {active_button} should be active"
    # Calculate expected total text area length using constant
    expected_total_text_area_len = current_base_text_area_len + expected_text_area_len_delta
    assert at.text_area.len == expected_total_text_area_len, f"Expected {expected_total_text_area_len} text areas, found {at.text_area.len}"

    # Check text area value only if one was expected to be added
    if expected_text_area_len_delta == RENDERED_TEXT_AREA_COUNT:
        assert at.text_area(key="tab1_result_textarea").value == expected_text_area_value, "Rendered text area value mismatch"

    assert at.markdown.len == expected_markdown_len, f"Expected {expected_markdown_len} markdown elements, found {at.markdown.len}"
    assert at.error.len == expected_error_objects, f"Expected {expected_error_objects} error messages, found {at.error.len}"
    assert at.warning.len == expected_warning_objects, f"Expected {expected_warning_objects} warning messages, found {at.warning.len}"
    assert at.success.len == expected_success_objects, f"Expected {expected_success_objects} success messages, found {at.success.len}"


@pytest.fixture
def base_text_area_len() -> int:
    """Return base number of text areas in the app."""
    # Use the constant
    return BASE_TEXT_AREA_COUNT


@pytest.fixture
def config_file(config_file_content: Optional[bytes]) -> Optional[BytesIO]:
    """Create a config file from content."""
    if config_file_content is None:
        return None
    file = BytesIO(config_file_content)
    file.name = "config.toml"
    return file


def verify_common_state(
    at: AppTest,
    config_file: Optional[BytesIO],
    active_button: str,
    expected_text_area_value: Optional[Dict[str, Any]],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
) -> None:
    """Verify common test state and assertions."""
    assert at.session_state["tab2_config_file"] == config_file, "Config file in session state mismatch (Tab 2)"
    assert at.button(key=active_button).value is True, f"Button {active_button} should be active (Tab 2)"

    if expected_text_area_value is None:
        assert at.session_state["tab2_result_content"] is None, "Result content should be None (Tab 2)"
    else:
        assert isinstance(at.session_state["tab2_result_content"], dict) is True, "Result content should be a dict (Tab 2)"
        assert at.session_state["tab2_result_content"] == expected_text_area_value, "Result content mismatch (Tab 2)"

    assert at.error.len == expected_error_objects, f"Expected {expected_error_objects} error messages, found {at.error.len} (Tab 2)"
    assert at.warning.len == expected_warning_objects, (
        f"Expected {expected_warning_objects} warning messages, found {at.warning.len} (Tab 2)"
    )
    assert at.success.len == expected_success_objects, (
        f"Expected {expected_success_objects} success messages, found {at.success.len} (Tab 2)"
    )


def verify_visual_output(
    at: AppTest,
    expected_text_area_value: Optional[Dict[str, Any]],
    base_text_area_len: int,  # Now correctly passed from fixture
) -> None:
    """Verify visual JSON output format."""
    if expected_text_area_value is None:
        assert at.json.len == NO_JSON_OUTPUT, f"Expected {NO_JSON_OUTPUT} json outputs, found {at.json.len}"
    else:
        assert at.json.len == ONE_JSON_OUTPUT, f"Expected {ONE_JSON_OUTPUT} json output, found {at.json.len}"
        assert at.json[0].value == json.dumps(expected_text_area_value, ensure_ascii=False), "JSON output value mismatch"
    # Check total text area count
    assert at.text_area.len == base_text_area_len, f"Expected {base_text_area_len} text areas for visual output, found {at.text_area.len}"


def verify_toml_output(
    at: AppTest,
    expected_text_area_value: Optional[Dict[str, Any]],
    base_text_area_len: int,  # Now correctly passed from fixture
) -> None:
    """Verify TOML output format."""
    assert at.json.len == NO_JSON_OUTPUT, f"Expected {NO_JSON_OUTPUT} json outputs for TOML format, found {at.json.len}"
    if expected_text_area_value is None:
        # Check total text area count when no output
        assert at.text_area.len == base_text_area_len, (
            f"Expected {base_text_area_len} text areas for failed TOML output, found {at.text_area.len}"
        )
    else:
        # Calculate expected total text area length using constant
        expected_total_text_area_len = base_text_area_len + RENDERED_TEXT_AREA_COUNT
        assert at.text_area.len == expected_total_text_area_len, (
            f"Expected {expected_total_text_area_len} text areas for TOML output, found {at.text_area.len}"
        )
        assert at.text_area(key="tab2_result_textarea").value == toml.dumps(expected_text_area_value), "TOML output value mismatch"


def verify_yaml_output(
    at: AppTest,
    expected_text_area_value: Optional[Dict[str, Any]],
    base_text_area_len: int,  # Now correctly passed from fixture
) -> None:
    """Verify YAML output format."""
    assert at.json.len == NO_JSON_OUTPUT, f"Expected {NO_JSON_OUTPUT} json outputs for YAML format, found {at.json.len}"
    if expected_text_area_value is None:
        # Check total text area count when no output
        assert at.text_area.len == base_text_area_len, (
            f"Expected {base_text_area_len} text areas for failed YAML output, found {at.text_area.len}"
        )
    else:
        # Calculate expected total text area length using constant
        expected_total_text_area_len = base_text_area_len + RENDERED_TEXT_AREA_COUNT
        assert at.text_area.len == expected_total_text_area_len, (
            f"Expected {expected_total_text_area_len} text areas for YAML output, found {at.text_area.len}"
        )
        assert at.text_area(key="tab2_result_textarea").value == yaml.dump(
            expected_text_area_value, default_flow_style=False, allow_unicode=True, indent=8
        ), "YAML output value mismatch"


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
        pytest.param(
            "tab2_execute_visual",
            b'key = "POSITIVE"',
            {"key": "POSITIVE"},
            NO_MESSAGES,
            NO_MESSAGES,
            ONE_MESSAGE,
            id="visual_config_valid_basic_JSON",
        ),
        pytest.param(
            "tab2_execute_visual",
            None,
            None,
            NO_MESSAGES,
            ONE_MESSAGE,
            NO_MESSAGES,
            id="visual_config_invalid_missing_file",
        ),
        pytest.param(
            "tab2_execute_visual",
            b"key=",
            None,
            ONE_MESSAGE,  # Error in parsing
            ONE_MESSAGE,  # Warning for missing file content essentially
            NO_MESSAGES,
            id="visual_config_invalid_TOML_syntax",
        ),
        pytest.param(
            "tab2_execute_toml",
            b'key = "POSITIVE"',
            {"key": "POSITIVE"},
            NO_MESSAGES,
            NO_MESSAGES,
            ONE_MESSAGE,
            id="TOML_config_valid_basic_format",
        ),
        pytest.param(
            "tab2_execute_toml",
            None,
            None,
            NO_MESSAGES,
            ONE_MESSAGE,
            NO_MESSAGES,
            id="TOML_config_invalid_missing_file",
        ),
        pytest.param(
            "tab2_execute_toml",
            b"key=",
            None,
            ONE_MESSAGE,  # Error in parsing
            ONE_MESSAGE,  # Warning for missing file content essentially
            NO_MESSAGES,
            id="TOML_config_invalid_syntax",
        ),
        pytest.param(
            "tab2_execute_yaml",
            b'key = "POSITIVE"',
            {"key": "POSITIVE"},
            NO_MESSAGES,
            NO_MESSAGES,
            ONE_MESSAGE,
            id="YAML_config_valid_basic_format",
        ),
        pytest.param(
            "tab2_execute_yaml",
            None,
            None,
            NO_MESSAGES,
            ONE_MESSAGE,
            NO_MESSAGES,
            id="YAML_config_invalid_missing_file",
        ),
        pytest.param(
            "tab2_execute_yaml",
            b"key=",
            None,
            ONE_MESSAGE,  # Error in parsing
            ONE_MESSAGE,  # Warning for missing file content essentially
            NO_MESSAGES,
            id="YAML_config_invalid_syntax",
        ),
    ],
)
def test_main_tab2(
    active_button: str,
    config_file_content: Optional[bytes],
    expected_text_area_value: Optional[Dict[str, Any]],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
    base_text_area_len: int,  # Fixture injected
    config_file: Optional[BytesIO],  # Fixture injected
) -> None:
    """Test tab2 functionality for different output formats."""
    at = AppTest.from_file("app.py")
    at.session_state["tab2_config_file"] = config_file
    at.session_state[active_button] = True
    at.run()

    verify_common_state(
        at,
        config_file,
        active_button,
        expected_text_area_value,
        expected_error_objects,
        expected_warning_objects,
        expected_success_objects,
    )

    # Pass base_text_area_len from the fixture to verification functions
    if active_button == "tab2_execute_visual":
        verify_visual_output(at, expected_text_area_value, base_text_area_len)
    elif active_button == "tab2_execute_toml":
        verify_toml_output(at, expected_text_area_value, base_text_area_len)
    elif active_button == "tab2_execute_yaml":
        verify_yaml_output(at, expected_text_area_value, base_text_area_len)
