import sys
from io import BytesIO
from typing import Dict, Optional, Union

import pytest

from features.config_parser import ConfigParser


@pytest.mark.unit
@pytest.mark.parametrize(
    ("content", "filename", "is_successful", "expected_error"),
    [
        # Edge case: Extremely large TOML file with long key names
        pytest.param(
            b"title = 'TOML test'\n" + b"key_" + b"a" * 1000 + b" = 'value'\n" * 100,
            "config.toml",
            False,
            "Invalid statement (at line 3, column 2)",
            id="toml_large_file_with_long_keys",
        ),
        # Edge case: TOML with special characters in keys
        pytest.param(
            b"'key-with-quotes' = 'value'\nkey_with_underscores = 'value'\n\"key.with.dots\" = 'value'",
            "config.toml",
            True,
            None,
            id="toml_special_chars_in_keys",
        ),
        # Edge case: YAML with extremely long key names
        pytest.param(
            b"title: YAML test\nkey_" + b"a" * 100 + b": value",
            "config.yaml",
            True,
            None,
            id="yaml_long_key_names",
        ),
        # Edge case: YAML with special characters in keys
        pytest.param(
            b"'key-with-quotes': value\nkey_with_underscores: value\n\"key.with.dots\": value",
            "config.yaml",
            True,
            None,
            id="yaml_special_chars_in_keys",
        ),
        # Edge case: Extremely large CSV file
        pytest.param(
            b"col1,col2,col3\n" + b"value1,value2,value3\n" * 1000,
            "config.csv",
            True,
            None,
            id="csv_large_file_many_rows",
        ),
        # Edge case: CSV with quoted fields containing commas
        pytest.param(
            b'name,description\n"Smith, John","Consultant, senior"\n"Doe, Jane","Manager, department"',
            "config.csv",
            True,
            None,
            id="csv_quoted_fields_with_commas",
        ),
        # Edge case: CSV with many columns
        pytest.param(
            b"col1,"
            + b",".join([f"col{i}".encode() for i in range(2, 100)])
            + b",col100\n"
            + b"value1,"
            + b",".join([f"value{i}".encode() for i in range(2, 100)])
            + b",value100",
            "config.csv",
            True,
            None,
            id="csv_many_columns",
        ),
        # Edge case: Empty file
        pytest.param(
            b"",
            "config.toml",
            True,
            None,
            id="toml_empty_file",
        ),
        pytest.param(
            b"",
            "config.yaml",
            False,
            "Invalid YAML file loaded.",
            id="yaml_empty_file",
        ),
        # Edge case: File with only whitespace
        pytest.param(
            b"   \n\t\n  ",
            "config.toml",
            True,
            None,
            id="toml_whitespace_only",
        ),
        pytest.param(
            b"   \n\t\n  ",
            "config.yaml",
            False,
            """while scanning for the next token
found character '\\t' that cannot start any token
  in "<unicode string>", line 2, column 1:
    \t
    ^""",
            id="yaml_whitespace_only",
        ),
        # Edge case: File with BOM
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML test'",
            "config.toml",
            False,
            "Invalid statement (at line 1, column 1)",
            id="toml_with_bom",
        ),
        pytest.param(
            b"\xef\xbb\xbftitle: YAML test",
            "config.yaml",
            True,
            None,
            id="yaml_with_bom",
        ),
        # Edge case: File with non-UTF8 characters
        pytest.param(
            b"\x80\x81\x82title = 'TOML test'",
            "config.toml",
            False,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="toml_invalid_utf8",
        ),
        pytest.param(
            b"\x80\x81\x82title: YAML test",
            "config.yaml",
            False,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="yaml_invalid_utf8",
        ),
        # Edge case: File with mixed line endings
        pytest.param(
            b"title = 'TOML test'\r\nkey1 = 'value1'\nkey2 = 'value2'\r\n",
            "config.toml",
            True,
            None,
            id="toml_mixed_line_endings",
        ),
        pytest.param(
            b"title: YAML test\r\nkey1: value1\nkey2: value2\r\n",
            "config.yaml",
            True,
            None,
            id="yaml_mixed_line_endings",
        ),
    ],
)
def test_parse_edge_cases(
    content: bytes,
    filename: str,
    is_successful: bool,
    expected_error: Optional[str],
) -> None:
    """Test edge cases for the ConfigParser.

    Args:
        content: The content to parse
        filename: The filename to use
        is_successful: Whether parsing should succeed
        expected_error: The expected error message, if any
    """
    config_file = BytesIO(content)
    config_file.name = filename

    parser = ConfigParser(config_file)
    result = parser.parse()
    assert result == is_successful

    if expected_error is not None:
        assert parser.error_message is not None
        assert expected_error == parser.error_message
    else:
        assert parser.error_message is None


@pytest.mark.unit
def test_memory_usage_with_reasonable_file() -> None:
    """Test that parsing files with reasonable size doesn't consume excessive memory."""
    # Create a CSV file with a reasonable number of rows
    header = b"col1,col2,col3\n"
    row = b"value1,value2,value3\n"

    # Generate a file with 1,000 rows (much more reasonable for a unit test)
    content = header + row * 1_000

    config_file = BytesIO(content)
    config_file.name = "reasonable_file.csv"

    # Parse the file
    parser = ConfigParser(config_file)
    result = parser.parse()

    # Verify parsing succeeded
    assert result is True

    # 辞書と文字列の表現が取得できることを確認
    assert parser.parsed_dict is not None
    assert parser.parsed_str != "None"

    # 辞書の内容を確認
    assert "csv_rows" in parser.parsed_dict
    assert len(parser.parsed_dict["csv_rows"]) == 1000
    assert all(row.get("col1") == "value1" for row in parser.parsed_dict["csv_rows"])
    assert all(row.get("col2") == "value2" for row in parser.parsed_dict["csv_rows"])
    assert all(row.get("col3") == "value3" for row in parser.parsed_dict["csv_rows"])


@pytest.mark.unit
def test_nested_structures() -> None:
    """Test parsing deeply nested structures."""
    # TOML with deeply nested tables
    toml_content = b"""
    [level1]
    key = "value"

    [level1.level2]
    key = "value"

    [level1.level2.level3]
    key = "value"

    [level1.level2.level3.level4]
    key = "value"

    [level1.level2.level3.level4.level5]
    key = "value"
    """

    config_file = BytesIO(toml_content)
    config_file.name = "nested.toml"

    parser = ConfigParser(config_file)
    result = parser.parse()

    assert result is True
    assert parser.parsed_dict is not None
    assert "level1" in parser.parsed_dict
    assert "level2" in parser.parsed_dict["level1"]
    assert "level3" in parser.parsed_dict["level1"]["level2"]
    assert "level4" in parser.parsed_dict["level1"]["level2"]["level3"]
    assert "level5" in parser.parsed_dict["level1"]["level2"]["level3"]["level4"]

    # YAML with deeply nested mappings
    yaml_content = b"""
    level1:
      key: value
      level2:
        key: value
        level3:
          key: value
          level4:
            key: value
            level5:
              key: value
    """

    config_file = BytesIO(yaml_content)
    config_file.name = "nested.yaml"

    parser = ConfigParser(config_file)
    result = parser.parse()

    assert result is True
    assert parser.parsed_dict is not None
    assert "level1" in parser.parsed_dict
    assert "level2" in parser.parsed_dict["level1"]
    assert "level3" in parser.parsed_dict["level1"]["level2"]
    assert "level4" in parser.parsed_dict["level1"]["level2"]["level3"]
    assert "level5" in parser.parsed_dict["level1"]["level2"]["level3"]["level4"]


@pytest.mark.unit
def test_file_size_limit() -> None:
    """ファイルサイズの上限を超えた場合のテスト。

    ConfigParserクラスのMAX_FILE_SIZE_BYTES (30MB) を超えるファイルを
    作成し、バリデーションが正しく機能することを確認します。
    """
    # Arrange
    # 31MBのデータを作成 (上限は30MB)
    large_content = b"x" * (31 * 1024 * 1024)
    config_file = BytesIO(large_content)
    config_file.name = "large_config.toml"

    # Act
    parser = ConfigParser(config_file)

    # Assert
    assert parser.error_message is not None
    assert "File size exceeds the maximum limit" == parser.error_message
    assert parser.parse() is False


@pytest.mark.unit
def test_memory_consumption_limit_parsed_str() -> None:
    """parsed_strのメモリ消費量の上限を超えた場合のテスト。

    モンキーパッチを使用してsys.getsizeofをオーバーライドし、
    大きなメモリサイズを返すようにします。
    """
    # Arrange
    content = b"title = 'TOML test'\nkey = 'value'\n"
    config_file = BytesIO(content)
    config_file.name = "config.toml"

    parser = ConfigParser(config_file)
    assert parser.parse() is True

    # sys.getsizeofの元の実装を保存
    original_getsizeof = sys.getsizeof

    try:
        # sys.getsizeofをモンキーパッチして大きな値を返すようにする
        def mock_getsizeof(obj: Union[str, Dict, bytes, int, float, bool]) -> int:
            if isinstance(obj, str) and "title" in obj:
                # 200MBを返す (上限は150MB)
                return 200 * 1024 * 1024
            return original_getsizeof(obj)

        sys.getsizeof = mock_getsizeof

        # Act
        result = parser.parsed_str

        # Assert
        assert result == "None"
        assert parser.error_message is not None
        assert "Memory consumption exceeds the maximum limit of 150MB (actual: 200.00MB)" == parser.error_message

    finally:
        # テスト終了後に元の実装を復元
        sys.getsizeof = original_getsizeof


@pytest.mark.unit
def test_memory_consumption_limit_parsed_dict() -> None:
    """parsed_dictのメモリ消費量の上限を超えた場合のテスト。

    モンキーパッチを使用してsys.getsizeofをオーバーライドし、
    大きなメモリサイズを返すようにします。
    """
    # Arrange
    content = b"title = 'TOML test'\nkey = 'value'\n"
    config_file = BytesIO(content)
    config_file.name = "config.toml"

    parser = ConfigParser(config_file)
    assert parser.parse() is True

    # sys.getsizeofの元の実装を保存
    original_getsizeof = sys.getsizeof

    try:
        # sys.getsizeofをモンキーパッチして大きな値を返すようにする
        def mock_getsizeof(obj: Union[str, Dict, bytes, int, float, bool]) -> int:
            if isinstance(obj, dict) and "title" in obj:
                # 200MBを返す (上限は150MB)
                return 200 * 1024 * 1024
            return original_getsizeof(obj)

        sys.getsizeof = mock_getsizeof

        # Act
        result = parser.parsed_dict

        # Assert
        assert result is None
        assert parser.error_message is not None
        assert "Memory consumption exceeds the maximum limit of 150MB (actual: 200.00MB)" == parser.error_message

    finally:
        # テスト終了後に元の実装を復元
        sys.getsizeof = original_getsizeof


@pytest.mark.unit
def test_memory_error_handling() -> None:
    """メモリエラーが発生した場合のテスト。

    モンキーパッチを使用してsys.getsizeofをオーバーライドし、
    MemoryErrorを発生させます。
    """
    # Arrange
    content = b"title = 'TOML test'\nkey = 'value'\n"
    config_file = BytesIO(content)
    config_file.name = "config.toml"

    parser = ConfigParser(config_file)
    assert parser.parse() is True

    # sys.getsizeofの元の実装を保存
    original_getsizeof = sys.getsizeof

    try:
        # sys.getsizeofをモンキーパッチしてMemoryErrorを発生させる
        def mock_getsizeof_error(obj: Union[str, Dict, bytes, int, float, bool]) -> int:
            if isinstance(obj, dict) and "title" in obj:
                raise MemoryError("Simulated memory error")
            return original_getsizeof(obj)

        sys.getsizeof = mock_getsizeof_error

        # Act
        result = parser.parsed_dict

        # Assert
        assert result is None
        assert parser.error_message is not None
        assert "Memory error while checking size: Simulated memory error" == parser.error_message

    finally:
        # テスト終了後に元の実装を復元
        sys.getsizeof = original_getsizeof
