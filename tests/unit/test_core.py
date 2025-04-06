from io import BytesIO
from typing import Any, Dict, Optional

import pytest
from _pytest.mark.structures import MarkDecorator
from pydantic import BaseModel, PrivateAttr

from features.core import AppCore

UNIT: MarkDecorator = pytest.mark.unit


class MockParser(BaseModel):
    __is_successful: bool = False
    __csv_rows_name: str = PrivateAttr(default="csv_rows")
    __content: Optional[str] = None
    __enable_fill_nan: bool = PrivateAttr(default=False)
    __fill_nan_with: Optional[str] = None

    def __init__(self: "MockParser", file: BytesIO) -> None:
        super().__init__()

        self.__content = file.read().decode()

    def parse(self: "MockParser") -> bool:
        if self.__content != "POSITIVE":
            return False

        self.__is_successful = True
        return True

    @property
    def csv_rows_name(self: "MockParser") -> str:
        return self.__csv_rows_name

    @csv_rows_name.setter
    def csv_rows_name(self: "MockParser", rows_name: str) -> None:
        self.__csv_rows_name = rows_name

    @property
    def enable_fill_nan(self: "MockParser") -> bool:
        return self.__enable_fill_nan

    @enable_fill_nan.setter
    def enable_fill_nan(self: "MockParser", is_fillna: bool) -> None:
        self.__enable_fill_nan = is_fillna

    @property
    def fill_nan_with(self: "MockParser") -> Optional[str]:
        return self.__fill_nan_with

    @fill_nan_with.setter
    def fill_nan_with(self: "MockParser", fillna_value: str) -> None:
        self.__fill_nan_with = fillna_value

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


class MockRender(BaseModel):
    __is_successful: bool = False
    __render_content: str = "This is POSITIVE"

    def __init__(self: "MockRender", file: BytesIO) -> None:
        super().__init__()

        content = file.read().decode()

        if content == "POSITIVE":
            self.__is_successful = True

    @property
    def is_valid_template(self: "MockRender") -> bool:
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


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> AppCore:
    monkeypatch.setattr("features.core.ConfigParser", MockParser)
    monkeypatch.setattr("features.core.DocumentRender", MockRender)
    return AppCore("[CONFIG_ERROR]", "[TEMPLATE_ERROR]")


# テスト: モックオブジェクトの動作確認
@UNIT
@pytest.mark.parametrize(
    (
        "config_content",
        "is_successful",
        "expected_dict",
        "expected_text",
        "expected_error",
    ),
    [
        pytest.param(b"POSITIVE", True, {"key": "POSITIVE"}, "{'key':POSITIVE'}", None, id="mock_parser_valid_config"),
        pytest.param(b"negative", False, None, None, "parser_module_error", id="mock_parser_invalid_config"),
    ],
)
def test_mock_parser(
    config_content: bytes,
    is_successful: bool,
    expected_dict: Optional[Dict[str, Any]],
    expected_text: Optional[str],
    expected_error: Optional[str],
) -> None:
    """MockParserの動作をテストする。"""
    # Arrange
    config_file = BytesIO(config_content)
    config_file.name = "config.toml"

    # Act
    parser = MockParser(config_file)

    # Assert
    assert parser.csv_rows_name == "csv_rows", "Default csv_rows_name should be 'csv_rows'"
    assert parser.enable_fill_nan is False, "Default enable_fill_nan should be False"
    assert parser.fill_nan_with is None, "Default fill_nan_with should be None"
    assert parser.parse() == is_successful
    assert parser.parsed_dict == expected_dict, f"Parsed dict mismatch. Expected: {expected_dict}, Got: {parser.parsed_dict}"
    assert parser.parsed_str == expected_text, f"Parsed string mismatch. Expected: {expected_text}, Got: {parser.parsed_str}"
    if expected_error is None:
        assert parser.error_message is None, f"Expected no error message, but got: {parser.error_message}"
    else:
        assert expected_error in str(parser.error_message), (
            f"Error message mismatch. Expected to contain: '{expected_error}', Got: '{parser.error_message}'"
        )


@UNIT
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
        pytest.param(
            True, b"POSITIVE", {"key": "POSITIVE"}, True, True, "This is POSITIVE", None, id="mock_render_valid_template_valid_context"
        ),
        pytest.param(True, b"negative", {"key": "POSITIVE"}, False, False, None, "render_module_error", id="mock_render_invalid_template"),
        pytest.param(
            True,
            b"POSITIVE",
            {"key": "negative"},
            True,
            False,
            None,
            "render_module_error",
            id="mock_render_valid_template_invalid_context_strict",
        ),
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
    """MockRenderの動作をテストする。"""
    # Arrange
    render = MockRender(BytesIO(template_content))

    # Act & Assert
    assert render.is_valid_template == expected_validate_template, (
        f"Template validation mismatch. Expected: {expected_validate_template}, Got: {render.is_valid_template}"
    )
    assert render.apply_context(context, 3, is_strict_undefined) == expected_apply_succeeded, (
        f"Context application mismatch. Expected: {expected_apply_succeeded}, Got: {render.apply_context(context, 3, is_strict_undefined)}"
    )
    assert render.render_content == expected_content, f"Render content mismatch. Expected: {expected_content}, Got: {render.render_content}"
    assert render.error_message == expected_error, f"Error message mismatch. Expected: {expected_error}, Got: {render.error_message}"


# テスト: AppCore.load_config_file メソッド
@UNIT
@pytest.mark.parametrize(
    ("config_content", "expected_dict", "expected_error"),
    [
        pytest.param(None, None, None, id="core_config_no_file"),
        pytest.param(b"POSITIVE", {"key": "POSITIVE"}, None, id="core_config_valid_file"),
        pytest.param(b"negative", None, "[CONFIG_ERROR]: parser_module_error in 'config.toml'", id="core_config_invalid_file"),
    ],
)
def test_app_core_load_config_file(
    config_content: Optional[bytes],
    expected_dict: Optional[Dict[str, Any]],
    expected_error: Optional[str],
    model: AppCore,
) -> None:
    """AppCore.load_config_fileメソッドをテストする。"""
    # Arrange
    if config_content is None:
        config_file = None
    else:
        config_file = BytesIO(config_content)
        config_file.name = "config.toml"

    # Act
    result = model.load_config_file(config_file, "csv_rows", False)

    # Assert
    assert result is model, "Method should return self for chaining"
    assert model.config_dict == expected_dict, f"Config dict mismatch. Expected: {expected_dict}, Got: {model.config_dict}"
    assert model.config_error_message == expected_error, (
        f"Config error message mismatch. Expected: {expected_error}, Got: {model.config_error_message}"
    )


# テスト: AppCore.load_template_file メソッド
@UNIT
@pytest.mark.parametrize(
    ("template_content", "expected_error"),
    [
        pytest.param(None, None, id="core_template_no_file"),
        pytest.param(b"POSITIVE", None, id="core_template_valid_file"),
        pytest.param(b"negative", "[TEMPLATE_ERROR]: render_module_error in 'template.j2'", id="core_template_invalid_file"),
    ],
)
def test_app_core_load_template_file(
    template_content: Optional[bytes],
    expected_error: Optional[str],
    model: AppCore,
) -> None:
    """AppCore.load_template_fileメソッドをテストする。"""
    # Arrange
    if template_content is None:
        template_file = None
    else:
        template_file = BytesIO(template_content)
        template_file.name = "template.j2"

    # Act
    result = model.load_template_file(template_file, False)

    # Assert
    assert result is model, "Method should return self for chaining"
    assert model.template_error_message == expected_error, (
        f"Template error message mismatch. Expected: {expected_error}, Got: {model.template_error_message}"
    )


# テスト: AppCore.apply メソッド
@UNIT
@pytest.mark.parametrize(
    ("is_strict_undefined", "template_content", "config_data", "expected_result", "expected_error"),
    [
        pytest.param(True, None, None, None, None, id="core_apply_no_template_no_config"),
        pytest.param(True, None, {"key": "POSITIVE"}, None, None, id="core_apply_no_template_valid_config"),
        pytest.param(True, b"POSITIVE", None, None, None, id="core_apply_valid_template_no_config"),
        pytest.param(True, b"POSITIVE", {"key": "POSITIVE"}, "This is POSITIVE", None, id="core_apply_valid_template_valid_config"),
        pytest.param(
            True,
            b"negative",
            {"key": "POSITIVE"},
            None,
            "[TEMPLATE_ERROR]: render_module_error in 'template.j2'",
            id="core_apply_invalid_template_valid_config",
        ),
        pytest.param(
            True,
            b"POSITIVE",
            {"key": "negative"},
            None,
            "[TEMPLATE_ERROR]: render_module_error in 'template.j2'",
            id="core_apply_valid_template_invalid_config_strict",
        ),
        pytest.param(
            False, b"POSITIVE", {"key": "negative"}, "This is POSITIVE", None, id="core_apply_valid_template_invalid_config_non_strict"
        ),
    ],
)
def test_app_core_apply(
    is_strict_undefined: bool,
    template_content: Optional[bytes],
    config_data: Optional[Dict[str, Any]],
    expected_result: Optional[str],
    expected_error: Optional[str],
    model: AppCore,
) -> None:
    """AppCore.applyメソッドをテストする。"""
    # Arrange
    model.config_dict = config_data

    if template_content is None:
        template_file = None
    else:
        template_file = BytesIO(template_content)
        template_file.name = "template.j2"

    model.load_template_file(template_file, False)

    # Act
    result = model.apply(3, is_strict_undefined)

    # Assert
    assert result is model, "Method should return self for chaining"
    assert model.formatted_text == expected_result, f"Formatted text mismatch. Expected: {expected_result}, Got: {model.formatted_text}"
    assert model.template_error_message == expected_error, (
        f"Template error message mismatch. Expected: {expected_error}, Got: {model.template_error_message}"
    )


# テスト: AppCore.get_download_filename メソッド
@UNIT
@pytest.mark.parametrize(
    ("is_append_timestamp", "name_prefix", "name_suffix", "expected_filename_pattern", "expected_none"),
    [
        # 正常系: すべてのパラメータが提供される
        pytest.param(True, "output", "txt", r"output_\d{4}-\d{2}-\d{2}_\d{6}\.txt", False, id="core_filename_all_params_with_timestamp"),
        # 正常系: タイムスタンプなし
        pytest.param(False, "output", "txt", r"output\.txt", False, id="core_filename_all_params_no_timestamp"),
        # 異常系: プレフィックスなし
        pytest.param(True, None, "txt", r"", True, id="core_filename_no_prefix"),
        # 異常系: サフィックスなし
        pytest.param(True, "output", None, r"", True, id="core_filename_no_suffix"),
        # 異常系: プレフィックスとサフィックスなし、タイムスタンプのみ
        pytest.param(True, None, None, r"", True, id="core_filename_only_timestamp"),
        # 異常系: プレフィックスのみ
        pytest.param(False, "output", None, r"", True, id="core_filename_only_prefix"),
        # 異常系: サフィックスのみ
        pytest.param(False, None, "txt", r"", True, id="core_filename_only_suffix"),
        # 異常系: パラメータなし
        pytest.param(False, None, None, r"", True, id="core_filename_no_params"),
        # 正常系: 特殊文字を含むプレフィックスとサフィックス
        pytest.param(False, "output-file_name", "doc.txt", r"output-file_name\.doc\.txt", False, id="core_filename_special_chars"),
    ],
)
def test_app_core_get_download_filename(
    is_append_timestamp: bool,
    name_prefix: Optional[str],
    name_suffix: Optional[str],
    expected_filename_pattern: str,
    expected_none: bool,
    model: AppCore,
) -> None:
    """AppCore.get_download_filenameメソッドをテストする。"""
    # Arrange & Act
    import re

    filename = model.get_download_filename(name_prefix, name_suffix, is_append_timestamp)

    # Assert
    if expected_none:
        assert filename is None, f"Expected None filename, but got: {filename}"
    else:
        assert filename is not None, "Expected non-None filename"
        pattern = re.compile(f"^{expected_filename_pattern}$")
        assert pattern.match(filename), f"Filename '{filename}' does not match pattern '{expected_filename_pattern}'"


# テスト: AppCore.get_download_content メソッド
@UNIT
def test_app_core_get_download_content(model: AppCore) -> None:
    """AppCore.get_download_contentメソッドをテストする。"""
    # Arrange
    expected_result = "This is POSITIVE"
    model.config_dict = {"key": "POSITIVE"}
    template_file = BytesIO(b"POSITIVE")
    template_file.name = "template.j2"
    model.load_template_file(template_file, False)
    model.apply(3, True)

    # Act & Assert
    # 正常系: 有効なエンコーディング
    shift_jis_data = model.get_download_content("Shift_JIS")
    assert isinstance(shift_jis_data, bytes)
    assert shift_jis_data.decode("Shift_JIS") == expected_result

    euc_jp_data = model.get_download_content("EUC-JP")
    assert isinstance(euc_jp_data, bytes)
    assert euc_jp_data.decode("EUC-JP") == expected_result

    utf8_data = model.get_download_content("utf-8")
    assert isinstance(utf8_data, bytes)
    assert utf8_data.decode("utf-8") == expected_result

    # 異常系: 無効なエンコーディング
    assert model.get_download_content("utf-9") is None


# テスト: AppCoreの統合テスト
@UNIT
@pytest.mark.parametrize(
    (
        "config_content",
        "template_content",
        "is_strict_undefined",
        "enable_auto_transcoding",
        "expected_result",
        "expected_config_error",
        "expected_template_error",
    ),
    [
        # 両方のファイルがNone
        pytest.param(None, None, True, False, None, None, None, id="core_integration_both_files_none"),
        # 設定ファイルは有効だがテンプレートファイルがNone
        pytest.param(b"POSITIVE", None, True, False, None, None, None, id="core_integration_valid_config_no_template"),
        # 設定ファイルはNoneだがテンプレートファイルは有効
        pytest.param(None, b"POSITIVE", True, False, None, None, None, id="core_integration_no_config_valid_template"),
        # 両方のファイルが有効
        pytest.param(b"POSITIVE", b"POSITIVE", True, False, "This is POSITIVE", None, None, id="core_integration_both_files_valid"),
        # 設定ファイルは無効だがテンプレートファイルは有効
        pytest.param(
            b"negative", b"POSITIVE", True, False, None, "parser_module_error", None, id="core_integration_invalid_config_valid_template"
        ),
        # 設定ファイルは有効だがテンプレートファイルは無効
        pytest.param(
            b"POSITIVE", b"negative", True, False, None, None, "render_module_error", id="core_integration_valid_config_invalid_template"
        ),
        # 両方のファイルが無効
        pytest.param(
            b"negative",
            b"negative",
            True,
            False,
            None,
            "parser_module_error",
            "render_module_error",
            id="core_integration_both_files_invalid",
        ),
        # 自動トランスコーディングが有効
        pytest.param(b"POSITIVE", b"POSITIVE", True, True, "This is POSITIVE", None, None, id="core_integration_auto_transcoding_enabled"),
        # 厳密な未定義変数チェックが無効
        pytest.param(
            b"POSITIVE", b"POSITIVE", False, False, "This is POSITIVE", None, None, id="core_integration_strict_undefined_disabled"
        ),
    ],
)
def test_app_core_integration(
    config_content: Optional[bytes],
    template_content: Optional[bytes],
    is_strict_undefined: bool,
    enable_auto_transcoding: bool,
    expected_result: Optional[str],
    expected_config_error: Optional[str],
    expected_template_error: Optional[str],
    model: AppCore,
) -> None:
    """AppCoreの統合テストを行う。"""
    # Arrange
    # 設定ファイルの準備
    if config_content is None:
        config_file = None
    else:
        config_file = BytesIO(config_content)
        config_file.name = "config.toml"

    # テンプレートファイルの準備
    if template_content is None:
        template_file = None
    else:
        template_file = BytesIO(template_content)
        template_file.name = "template.j2"

    # モックオブジェクトをリセット - 新しいインスタンスを作成
    model = AppCore("[CONFIG_ERROR]", "[TEMPLATE_ERROR]")

    # Act
    # 設定ファイルとテンプレートの読み込み
    model.load_config_file(config_file, "csv_rows", enable_auto_transcoding)
    model.load_template_file(template_file, enable_auto_transcoding)
    model.apply(3, is_strict_undefined)

    # Assert
    # 結果の確認
    assert model.formatted_text == expected_result

    # エラーメッセージの検証
    if expected_config_error is None:
        assert model.config_error_message is None
    else:
        assert expected_config_error in str(model.config_error_message)

    if expected_template_error is None:
        assert model.template_error_message is None
    else:
        assert expected_template_error in str(model.template_error_message)
