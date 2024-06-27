from io import BytesIO
from typing import Any, Dict, Optional

import pytest

from features.core import GhostwriterCore


class MockParser:
    def __init__(self: "MockParser") -> None:
        self.__is_successful: bool = False
        self.__content: Optional[str] = None

    def load_config_file(self: "MockParser", file: BytesIO) -> "MockParser":
        self.__content = file.read().decode()

        return self

    def set_csv_rows_name(self: "MockParser", _: str) -> "MockParser":
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
    def __init__(self: "MockRender") -> None:
        self.__is_successful: bool = False
        self.__render_content: str = "This is POSITIVE"

    def load_template_file(self: "MockRender", file: BytesIO) -> "MockRender":
        content = file.read().decode()

        if content == "POSITIVE":
            self.__is_successful = True

        return self

    def validate_template(self: "MockRender") -> bool:
        return self.__is_successful

    def apply_context(self: "MockRender", content: Dict[str, Any], format_type: int = 3, is_strict_undefined: bool = True) -> bool:
        if not self.__is_successful:
            return False

        if is_strict_undefined and content != {"key": "POSITIVE"}:
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


@pytest.fixture()
def model(monkeypatch: pytest.MonkeyPatch) -> GhostwriterCore:
    monkeypatch.setattr("features.core.GhostwriterParser", MockParser)
    monkeypatch.setattr("features.core.GhostwriterRender", MockRender)
    return GhostwriterCore("[CONFIG_ERROR]", "[TEMPLATE_ERROR]")


@pytest.mark.unit()
@pytest.mark.parametrize(
    (
        "config_content",
        "is_successful",
        "expected_dict",
        "expected_text",
        "expected_error",
    ),
    [
        pytest.param(b"POSITIVE", True, {"key": "POSITIVE"}, "{'key':POSITIVE'}", None),
        pytest.param(b"negative", False, None, None, "parser_module_error"),
    ],
)
def test_mock_parser(
    config_content: bytes,
    is_successful: bool,
    expected_dict: Optional[Dict[str, Any]],
    expected_text: Optional[str],
    expected_error: Optional[str],
) -> None:
    """Test mock-parser."""

    config_file = BytesIO(config_content)
    config_file.name = "config.toml"

    parser = MockParser()
    assert parser.load_config_file(config_file).parse() == is_successful
    assert parser.parsed_dict == expected_dict
    assert parser.parsed_str == expected_text
    if expected_error is None:
        assert parser.error_message is None
    else:
        assert expected_error in str(parser.error_message)


@pytest.mark.unit()
@pytest.mark.parametrize(
    (
        "is_strict_undefined",
        "template_content",
        "context",
        "expected_validate_template",
        "expected_apply_succeeded",
        "expected_content",
        "expected_error",
    ),
    [
        pytest.param(True, b"POSITIVE", {"key": "POSITIVE"}, True, True, "This is POSITIVE", None),
        pytest.param(True, b"negative", {"key": "POSITIVE"}, False, False, None, "render_module_error"),
        pytest.param(True, b"POSITIVE", {"key": "negative"}, True, False, None, "render_module_error"),
    ],
)
def test_mock_render(
    is_strict_undefined: bool,
    template_content: bytes,
    context: Dict[str, Any],
    expected_validate_template: bool,
    expected_apply_succeeded: bool,
    expected_content: str,
    expected_error: Optional[str],
) -> None:
    """Test mock-render."""

    render = MockRender()
    assert type(render.load_template_file(BytesIO(template_content))) == render.__class__

    assert render.validate_template() == expected_validate_template
    assert render.apply_context(context, 3, is_strict_undefined) == expected_apply_succeeded
    assert render.render_content == expected_content
    assert render.error_message == expected_error


@pytest.mark.unit()
@pytest.mark.parametrize(
    ("config_content", "expected_dict", "expected_text", "expected_error"),
    [
        pytest.param(None, None, None, None),
        pytest.param(b"POSITIVE", {"key": "POSITIVE"}, "{'key':POSITIVE'}", None),
        pytest.param(b"negative", None, None, "[CONFIG_ERROR]: parser_module_error in 'config.toml'"),
    ],
)
def test_load_config_file(
    config_content: Optional[bytes],
    expected_dict: Optional[Dict[str, Any]],
    expected_text: Optional[str],
    expected_error: Optional[str],
    model: GhostwriterCore,
) -> None:
    """Test load_config_file."""
    if isinstance(config_content, bytes):
        config_file, config_file.name = BytesIO(config_content), "config.toml"
    else:
        config_file = None

    assert type(model.load_config_file(config_file, "csv_rows")) == model.__class__
    assert model.config_dict == expected_dict
    assert model.config_str == expected_text
    assert model.config_error_message == expected_error


@pytest.mark.unit()
@pytest.mark.parametrize(
    ("is_strict_undefined", "template_content", "config_data", "expected_result", "expected_error"),
    [
        pytest.param(True, None, None, None, None),
        pytest.param(True, None, {"key": "POSITIVE"}, None, None),
        pytest.param(True, b"POSITIVE", None, None, None),
        pytest.param(True, b"POSITIVE", {"key": "POSITIVE"}, "This is POSITIVE", None),
        pytest.param(True, b"negative", {"key": "POSITIVE"}, None, "[TEMPLATE_ERROR]: render_module_error in 'template.j2'"),
        pytest.param(True, b"POSITIVE", {"key": "negative"}, None, "[TEMPLATE_ERROR]: render_module_error in 'template.j2'"),
        pytest.param(True, b"negative", {"key": "negative"}, None, "[TEMPLATE_ERROR]: render_module_error in 'template.j2'"),
        pytest.param(False, None, None, None, None),
        pytest.param(False, None, {"key": "POSITIVE"}, None, None),
        pytest.param(False, b"POSITIVE", None, None, None),
        pytest.param(False, b"POSITIVE", {"key": "POSITIVE"}, "This is POSITIVE", None),
        pytest.param(False, b"POSITIVE", {"key": "negative"}, "This is POSITIVE", None),
        pytest.param(False, b"negative", {"key": "POSITIVE"}, None, "[TEMPLATE_ERROR]: render_module_error in 'template.j2'"),
        pytest.param(False, b"negative", {"key": "negative"}, None, "[TEMPLATE_ERROR]: render_module_error in 'template.j2'"),
    ],
)
def test_load_template_file(
    is_strict_undefined: bool,
    template_content: Optional[bytes],
    config_data: Optional[Dict[str, Any]],
    expected_result: Optional[str],
    expected_error: Optional[str],
    model: GhostwriterCore,
) -> None:
    """Test load_template_file."""

    assert type(model.set_config_dict(config_data)) == model.__class__

    if isinstance(template_content, bytes):
        template_file, template_file.name = BytesIO(template_content), "template.j2"
    else:
        template_file = None

    assert type(model.load_template_file(template_file)) == model.__class__
    assert type(model.apply_context("3", is_strict_undefined)) == model.__class__
    assert model.formatted_text == expected_result
    assert model.template_error_message == expected_error


@pytest.mark.unit()
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
    model: GhostwriterCore,
) -> None:
    """Test filename for download contents."""

    filename = model.get_download_filename(name_prefix, name_suffix, is_append_timestamp)

    if not isinstance(filename, str):
        assert filename is None
        assert expected_prefix == ""
        assert expected_suffix == ""
        return

    if is_append_timestamp:
        assert filename.startswith(expected_prefix)
        assert filename.endswith(expected_suffix)
    else:
        assert filename == f"{expected_prefix}{expected_suffix}"
