from io import BytesIO
from typing import Any, Dict, Optional

import pytest
from streamlit.testing.v1 import AppTest

from app import AppModel


class MockParser:
    def __init__(self: "MockParser") -> None:
        self.__is_successful: bool = False
        self.__content: Optional[str] = None

    def load_config_file(self: "MockParser", file: BytesIO) -> "MockParser":
        self.__content = file.read().decode()

        return self

    def parse(self: "MockParser") -> bool:
        if self.__content != "POSITIVE":
            return False

        self.__is_successful = True
        return True

    @property
    def parsed_dict(self: "MockParser") -> Optional[Dict[str, Any]]:
        if not self.__is_successful:
            return None

        return {"key": "POSITIVE"}

    @property
    def parsed_str(self: "MockParser") -> Optional[str]:
        if not self.__is_successful:
            return None

        return "{'key':POSITIVE'}"

    @property
    def error_message(self: "MockParser") -> Optional[str]:
        if not self.__is_successful:
            return "parser_module_error"

        return None


class MockRender:
    def __init__(self: "MockRender", is_strict_undefined: bool = True, is_remove_multiple_newline: bool = True) -> None:
        self.__is_successful: bool = False
        self.__is_strict_undefined: bool = is_strict_undefined
        self.__render_content: str = "This is POSITIVE"

    def load_template_file(self: "MockRender", file: BytesIO) -> "MockRender":
        content = file.read().decode()

        if content == "POSITIVE":
            self.__is_successful = True

        return self

    def validate_template(self: "MockRender") -> bool:
        return self.__is_successful

    def apply_context(self: "MockRender", content: Dict[str, Any]) -> bool:
        if not self.__is_successful:
            return False

        if self.__is_strict_undefined and content != {"key": "POSITIVE"}:
            self.__is_successful = False
            return False

        return True

    @property
    def render_content(self: "MockRender") -> Optional[str]:
        if not self.__is_successful:
            return None

        return self.__render_content

    @property
    def error_message(self: "MockRender") -> Optional[str]:
        if not self.__is_successful:
            return "render_module_error"

        return None


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> AppModel:
    monkeypatch.setattr("app.GhostwriterParser", MockParser)
    monkeypatch.setattr("app.GhostwriterRender", MockRender)
    return AppModel()


@pytest.mark.parametrize(
    ("config_content", "expected_dict", "expected_text", "expected_error"),
    [
        pytest.param(None, None, None, None),
        pytest.param(b"POSITIVE", {"key": "POSITIVE"}, "{'key':POSITIVE'}", None),
        pytest.param(b"negative", None, None, "[ERROR_HEADER]: parser_module_error in 'config.toml'"),
    ],
)
def test_load_config_file(
    config_content: Optional[bytes],
    expected_dict: Optional[Dict[str, Any]],
    expected_text: Optional[str],
    expected_error: Optional[str],
    model: AppModel,
) -> None:
    if isinstance(config_content, bytes):
        config_file, config_file.name = BytesIO(config_content), "config.toml"
    else:
        config_file = None

    model.load_config_file(config_file, "[ERROR_HEADER]")
    assert model.config_dict == expected_dict
    assert model.config_str == expected_text
    assert model.config_error_message == expected_error


@pytest.mark.parametrize(
    ("is_strict_undefined", "template_content", "config_data", "expected_result", "expected_error"),
    [
        pytest.param(True, None, None, None, None),
        pytest.param(True, None, {"key": "POSITIVE"}, None, None),
        pytest.param(True, b"POSITIVE", None, None, None),
        pytest.param(True, b"POSITIVE", {"key": "POSITIVE"}, "This is POSITIVE", None),
        pytest.param(True, b"negative", {"key": "POSITIVE"}, None, "[ERROR_HEADER]: render_module_error in 'template.j2'"),
        pytest.param(True, b"POSITIVE", {"key": "negative"}, None, "[ERROR_HEADER]: render_module_error in 'template.j2'"),
        pytest.param(True, b"negative", {"key": "negative"}, None, "[ERROR_HEADER]: render_module_error in 'template.j2'"),
        pytest.param(False, None, None, None, None),
        pytest.param(False, None, {"key": "POSITIVE"}, None, None),
        pytest.param(False, b"POSITIVE", None, None, None),
        pytest.param(False, b"POSITIVE", {"key": "POSITIVE"}, "This is POSITIVE", None),
        pytest.param(False, b"POSITIVE", {"key": "negative"}, "This is POSITIVE", None),
        pytest.param(False, b"negative", {"key": "POSITIVE"}, None, "[ERROR_HEADER]: render_module_error in 'template.j2'"),
        pytest.param(False, b"negative", {"key": "negative"}, None, "[ERROR_HEADER]: render_module_error in 'template.j2'"),
    ],
)
def test_load_template_file(
    is_strict_undefined: bool,
    template_content: Optional[bytes],
    config_data: Optional[Dict[str, Any]],
    expected_result: Optional[str],
    expected_error: Optional[str],
    model: AppModel,
) -> None:
    model.set_config_dict(config_data)

    if isinstance(template_content, bytes):
        template_file, template_file.name = BytesIO(template_content), "template.j2"
    else:
        template_file = None

    model.load_template_file(template_file, "[ERROR_HEADER]", is_strict_undefined, True)
    assert model.formatted_text == expected_result
    assert model.template_error_message == expected_error


@pytest.mark.parametrize(
    ("is_append_timestamp", "name_prefix", "name_suffix", "expected_prefix", "expected_suffix"),
    [
        pytest.param(True, "output", "txt", "output_", ".txt"),
        pytest.param(True, None, "txt", "", ""),
        pytest.param(True, "output", None, "", ""),
        pytest.param(False, "output", "txt", "output", ".txt"),
        pytest.param(False, None, "txt", "", ""),
        pytest.param(False, "output", None, "", ""),
    ],
)
def test_get_download_filename(
    is_append_timestamp: bool,
    name_prefix: Optional[str],
    name_suffix: Optional[str],
    expected_prefix: str,
    expected_suffix: str,
    model: AppModel,
) -> None:
    filename = model.get_download_filename(name_prefix, name_suffix, is_append_timestamp)

    if not isinstance(filename, str):
        assert filename is None
        assert expected_prefix == ""
        assert expected_suffix == ""
        return None

    if is_append_timestamp:
        assert filename.startswith(expected_prefix)
        assert filename.endswith(expected_suffix)
    else:
        assert filename == f"{expected_prefix}{expected_suffix}"


###################################
#
# Integration Tests
#
###################################


def test_main_layout() -> None:
    at = AppTest.from_file("app.py").run()

    # startup
    assert at.title.len == 1
    assert len(at.tabs) == 3
    assert len(at.columns) == 12
    assert len(at.sidebar) == 2
    assert len(at.markdown) == 3
    assert at.button.len == 3
    assert at.button[0].value is False
    assert at.button[1].value is False
    assert at.button[2].value is False
    assert len(at.error) == 0
    assert len(at.warning) == 0
    assert len(at.success) == 0
    assert at.radio.len == 1
    assert at.toggle.len == 3
    assert at.text_input.len == 1
    assert at.text_area.len == 0

    # click "generate_text_button" without uploaded files
    at.button[0].click().run()
    assert at.button[0].value is True
    assert at.button[1].value is False
    assert at.button[2].value is False
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert len(at.success) == 0

    # click "generate_markdown_button" without uploaded files
    at.button[1].click().run()
    assert at.button[0].value is False
    assert at.button[1].value is True
    assert at.button[2].value is False
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert len(at.success) == 0

    # click "generate_debug_config" without uploaded file
    at.button[2].click().run()
    assert at.button[0].value is False
    assert at.button[1].value is False
    assert at.button[2].value is True
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert len(at.success) == 0


@pytest.mark.parametrize(
    (
        "active_button",
        "config_filename",
        "config_file_content",
        "template_filename",
        "template_file_content",
        "expected_text_area_len",
        "expected_markdown_len",
        "expected_text_area_value",
        "expected_error_objects",
        "expected_warning_objects",
        "expected_success_objects",
    ),
    [
        pytest.param(0, "config.toml", b'key="POSITIVE"', "template.j2", b"### This is {{ key }} ###", 1, 3, "", 0, 0, 1),  # broken
        pytest.param(0, "config.toml", b"date=2024-04-00", "template.j2", b"### This is {{ key }} ###", 1, 3, "", 0, 0, 1),  # broken
        pytest.param(0, "config.toml", b'key="POSITIVE"', "template.j2", b"### This is {{ key ###", 1, 3, "", 0, 0, 1),  # broken
        pytest.param(1, "config.toml", b'key="POSITIVE"', "template.j2", b"### This is {{ key }} ###", 0, 4, "", 0, 0, 1),  # broken
    ],
)
def test_main_tab1(
    active_button: int,
    config_filename: Optional[str],
    config_file_content: bytes,
    template_filename: Optional[str],
    template_file_content: bytes,
    expected_text_area_len: int,
    expected_markdown_len: int,
    expected_text_area_value: Optional[str],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
) -> None:
    config_file = None
    template_file = None

    if isinstance(config_filename, str):
        config_file = BytesIO(config_file_content)
        config_file.name = config_filename

    if isinstance(template_filename, str):
        template_file = BytesIO(template_file_content)
        template_file.name = template_filename

    at = AppTest.from_file("app.py")
    at.session_state["tab1_config_file"] = config_file
    at.session_state["tab1_template_file"] = template_file
    at.run()
    at.button[active_button].click().run()
    assert at.session_state["tab1_config_file"] == config_file
    assert at.session_state["tab1_template_file"] == template_file
    assert at.session_state["tab1_result_content"] == expected_text_area_value  # broken
    assert at.button[active_button].value is True
    assert at.text_area.len == expected_text_area_len
    assert at.markdown.len == expected_markdown_len
    assert len(at.error) == expected_error_objects
    assert len(at.warning) == expected_warning_objects
    assert len(at.success) == expected_success_objects


@pytest.mark.parametrize(
    (
        "config_filename",
        "config_file_content",
        "expected_text_area_len",
        "expected_text_area_value",
        "expected_error_objects",
        "expected_warning_objects",
        "expected_success_objects",
    ),
    [
        pytest.param("config.toml", b'key="POSITIVE"', 1, "{}", 0, 0, 1),  # broken
        pytest.param(None, b"", 0, None, 0, 1, 0),
        pytest.param("config.toml", b"key=", 1, "{}", 0, 0, 1),  # broken
    ],
)
def test_main_tab2(
    config_filename: Optional[str],
    config_file_content: bytes,
    expected_text_area_len: int,
    expected_text_area_value: Optional[str],
    expected_error_objects: int,
    expected_warning_objects: int,
    expected_success_objects: int,
) -> None:
    if isinstance(config_filename, str):
        config_file = BytesIO(config_file_content)
        config_file.name = config_filename
    else:
        config_file = None

    at = AppTest.from_file("app.py")
    at.session_state["tab2_config_file"] = config_file
    at.run()
    at.button[2].click().run()
    assert at.button[2].value is True
    assert at.text_area.len == expected_text_area_len
    if expected_text_area_len > 0:
        assert at.text_area[0].value == expected_text_area_value
    assert len(at.error) == expected_error_objects
    assert len(at.warning) == expected_warning_objects
    assert len(at.success) == expected_success_objects
