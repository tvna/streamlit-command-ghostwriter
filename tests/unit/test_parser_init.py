from io import BytesIO
from typing import Optional

import pytest

from features.config_parser import ConfigParser


@pytest.mark.unit
@pytest.mark.parametrize(
    ("content", "filename", "expected_error"),
    [
        pytest.param(
            b"valid content",
            "config.toml",
            None,
            id="Valid TOML file initialization",
        ),
        pytest.param(
            b"valid content",
            "config.yaml",
            None,
            id="Valid YAML file initialization",
        ),
        pytest.param(
            b"valid content",
            "config.yml",
            None,
            id="Valid YML file initialization",
        ),
        pytest.param(
            b"valid content",
            "config.csv",
            None,
            id="Valid CSV file initialization",
        ),
        pytest.param(
            b"unsupported content",
            "config.txt",
            "Unsupported file type",
            id="Unsupported file type initialization",
        ),
        pytest.param(
            b"unsupported content",
            "config",
            "Unsupported file type",
            id="No extension initialization",
        ),
        pytest.param(
            b"\x80\x81\x82\x83",
            "config.toml",
            "invalid start byte",
            id="Invalid UTF-8 initialization",
        ),
    ],
)
def test_initialization(
    content: bytes,
    filename: str,
    expected_error: Optional[str],
) -> None:
    """ConfigParserの初期化をテストする。

    Args:
        content: パース対象のバイトデータ
        filename: ファイル名
        expected_error: 期待されるエラーメッセージ
    """
    config_file = BytesIO(content)
    config_file.name = filename

    parser = ConfigParser(config_file)

    if expected_error is None:
        assert parser.error_message is None
    else:
        assert expected_error in str(parser.error_message)


@pytest.mark.unit
def test_default_properties() -> None:
    """ConfigParserのデフォルトプロパティをテストする。"""
    config_file = BytesIO(b"content")
    config_file.name = "config.toml"

    parser = ConfigParser(config_file)

    # Test default properties
    assert parser.csv_rows_name == "csv_rows"
    assert parser.enable_fill_nan is False
    assert parser.fill_nan_with is None
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert parser.error_message is None
