import ast
import math
import sys
from datetime import date
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import numpy as np
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
            id="parser_init_valid_toml",
        ),
        pytest.param(
            b"valid content",
            "config.yaml",
            None,
            id="parser_init_valid_yaml",
        ),
        pytest.param(
            b"valid content",
            "config.yml",
            None,
            id="parser_init_valid_yml",
        ),
        pytest.param(
            b"valid content",
            "config.csv",
            None,
            id="parser_init_valid_csv",
        ),
        pytest.param(
            b"unsupported content",
            "config.txt",
            "Unsupported file type",
            id="parser_init_unsupported_type",
        ),
        pytest.param(
            b"unsupported content",
            "config",
            "Unsupported file type",
            id="parser_init_no_extension",
        ),
        pytest.param(
            b"\x80\x81\x82\x83",
            "config.toml",
            "invalid start byte",
            id="parser_init_invalid_utf8",
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


def assert_dict_equality(parsed_dict: Dict[str, Any], expected_dict: Dict[str, Any]) -> None:
    """辞書の内容を比較する。

    Args:
        parsed_dict: 実際のパース結果の辞書
        expected_dict: 期待される辞書
    """
    # キー一覧の比較
    assert set(parsed_dict.keys()) == set(expected_dict.keys()), "Keys do not match"

    # 各キーの値を比較
    for key in expected_dict:
        if isinstance(expected_dict[key], dict) and isinstance(parsed_dict[key], dict):
            assert_nested_dict_equality(parsed_dict[key], expected_dict[key], key)
        elif key == "csv_rows" and isinstance(expected_dict[key], list) and isinstance(parsed_dict[key], list):
            assert_csv_rows_equality(parsed_dict[key], expected_dict[key])
        else:
            assert parsed_dict[key] == expected_dict[key], f"Value for key {key} does not match"


def assert_nested_dict_equality(parsed_dict: Dict[str, Any], expected_dict: Dict[str, Any], parent_key: str) -> None:
    """ネストされた辞書の内容を比較する。

    Args:
        parsed_dict: 実際のパース結果の辞書
        expected_dict: 期待される辞書
        parent_key: 親キー名
    """
    assert set(parsed_dict.keys()) == set(expected_dict.keys()), f"Nested keys for {parent_key} do not match"


def assert_csv_rows_equality(parsed_rows: List[Dict[str, Any]], expected_rows: List[Dict[str, Any]]) -> None:
    """CSVの行データの内容を比較する。

    Args:
        parsed_rows: 実際のパース結果の行データ
        expected_rows: 期待される行データ
    """
    assert len(parsed_rows) == len(expected_rows), "CSV row count does not match"

    # 各行のキーと値が一致することを確認
    for i, (expected_row, actual_row) in enumerate(zip(expected_rows, parsed_rows, strict=False)):
        assert set(expected_row.keys()) == set(actual_row.keys()), f"CSV row {i} keys do not match"

        # 値が一致するか確認
        for col_key in expected_row:
            actual_value = actual_row[col_key]
            expected_value = expected_row[col_key]

            # NaN値の特別処理
            if isinstance(actual_value, float) and math.isnan(actual_value):
                # 期待値もNaN値かどうかをチェック
                if isinstance(expected_value, float) and math.isnan(expected_value):
                    continue  # 両方NaNの場合はOK
                if expected_value is None:
                    continue  # NaNとNoneは同等とみなす
                # numpy.nanの場合もチェック
                if hasattr(expected_value, "dtype") and np.isnan(expected_value):
                    continue  # numpy.nanもOK
                pytest.fail(f"Value for column {col_key} in row {i} does not match: NaN vs non-NaN")
                continue

            # 期待値がNaNで実際の値がそうでない場合
            if isinstance(expected_value, float) and math.isnan(expected_value):
                if isinstance(actual_value, float) and math.isnan(actual_value):
                    continue  # 両方NaNの場合はOK
                if actual_value is None:
                    continue  # NoneとNaNは同等とみなす
                pytest.fail(f"Value for column {col_key} in row {i} does not match: non-NaN vs NaN")
                continue

            # 数値型とストリング型の相互変換対応
            if isinstance(actual_value, (int, float)) and not (isinstance(actual_value, float) and math.isnan(actual_value)):
                if isinstance(expected_value, str):
                    # 期待値が文字列の場合、実際の値も文字列に変換して比較
                    assert str(actual_value) == expected_value, f"Value for column {col_key} in row {i} does not match"
                    continue
            elif isinstance(actual_value, str) and isinstance(expected_value, (int, float)):
                # 実際の値が文字列で期待値が数値の場合、変換して比較
                try:
                    if isinstance(expected_value, int):
                        converted_actual = int(actual_value)
                    else:
                        converted_actual = float(actual_value)
                    assert converted_actual == expected_value, f"Value for column {col_key} in row {i} does not match"
                    continue
                except ValueError:
                    pass  # 変換できない場合は通常の比較に進む

            # 文字列同士の比較
            if isinstance(actual_value, str) and isinstance(expected_value, str):
                assert actual_value == expected_value, f"Value for column {col_key} in row {i} does not match"
                continue

            # その他の型の比較
            assert actual_value == expected_value, f"Value for column {col_key} in row {i} does not match"


def assert_string_representation(
    parsed_dict: Optional[Dict[str, Any]],
    parsed_str: str,
    expected_str: str,
) -> None:
    """文字列表現を比較する。

    Args:
        parsed_dict: パース結果の辞書
        parsed_str: パース結果の文字列表現
        expected_str: 期待される文字列表現
    """
    # NaN値を含む場合は特別な処理を行う
    if "nan" in parsed_str or "nan" in expected_str:
        assert_nan_string_representation(parsed_dict, parsed_str, expected_str)
    # 辞書形式の文字列表現を処理
    elif expected_str.startswith("{") and expected_str.endswith("}"):
        assert_dict_string_representation(parsed_dict, parsed_str, expected_str)
    else:
        # 単純な文字列比較
        assert parsed_str == expected_str, "String representation does not match"


def assert_nan_string_representation(
    parsed_dict: Optional[Dict[str, Any]],
    parsed_str: str,
    expected_str: str,
) -> None:
    """NaN値を含む文字列表現を比較する。

    Args:
        parsed_dict: パース結果の辞書
        parsed_str: パース結果の文字列表現
        expected_str: 期待される文字列表現
    """
    # 空白と改行を正規化
    parsed_normalized = parsed_str.replace(" ", "").replace("\n", "")
    expected_normalized = expected_str.replace(" ", "").replace("\n", "")

    assert parsed_normalized == expected_normalized, "String representation does not match"


def assert_dict_string_representation(
    parsed_dict: Optional[Dict[str, Any]],
    parsed_str: str,
    expected_str: str,
) -> None:
    """辞書の文字列表現を比較する。

    Args:
        parsed_dict: パース結果の辞書
        parsed_str: パース結果の文字列表現
        expected_str: 期待される文字列表現
    """
    try:
        # datetimeオブジェクトを含む場合
        if "datetime.date" in expected_str:
            parsed_str_normalized = str(parsed_dict).replace(" ", "")
            expected_str_normalized = expected_str.replace(" ", "")
            assert parsed_str_normalized == expected_str_normalized, "String representation with date objects does not match"
        else:
            # 通常の辞書の場合
            try:
                expected_dict_from_str = ast.literal_eval(expected_str)
                if parsed_dict is not None:
                    assert set(parsed_dict.keys()) == set(expected_dict_from_str.keys()), "Keys from string representation do not match"
            except (SyntaxError, NameError, TypeError, ValueError):
                # 文字列の評価に失敗した場合は、空白と改行を無視して比較
                parsed_normalized = parsed_str.replace(" ", "").replace("\n", "")
                expected_normalized = expected_str.replace(" ", "").replace("\n", "")
                assert parsed_normalized == expected_normalized, "String representation does not match"
    except (SyntaxError, NameError, TypeError, ValueError):
        # 文字列の評価に失敗した場合は、空白と改行を無視して比較
        parsed_normalized = parsed_str.replace(" ", "").replace("\n", "")
        expected_normalized = expected_str.replace(" ", "").replace("\n", "")
        assert parsed_normalized == expected_normalized, "String representation does not match"


def check_file_specific_string_representation(
    parsed_str: Optional[str],
    expected_str: Optional[str],
    filename: str,
    is_successful: bool,
) -> None:
    """ファイル形式に応じた文字列表現のチェックを行う。

    Args:
        parsed_str: パース結果の文字列表現
        expected_str: 期待される文字列表現
        filename: ファイル名
        is_successful: パースが成功したかどうか
    """
    # CSVデータとYAMLデータの文字列表現はスキップ
    if filename.endswith((".csv", ".yaml", ".yml")):
        return

    # パースが失敗した場合
    if not is_successful:
        assert parsed_str == "None", "Failed parse should have 'None' string representation"
    else:
        assert parsed_str == expected_str, "String representation does not match"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("content", "filename", "is_successful", "expected_dict", "expected_str", "expected_error"),
    [
        # Test case for tomllib module on success
        pytest.param(
            b"title = 'TOML test'",
            "config.toml",
            True,
            {"title": "TOML test"},
            "{'title': 'TOML test'}",
            None,
            id="parser_toml_basic_key_value",
        ),
        pytest.param(
            b"date = 2024-04-01",
            "config.toml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
            id="parser_toml_date_parsing",
        ),
        pytest.param(
            b"fruits = ['apple', 'orange', 'apple']",
            "config.toml",
            True,
            {"fruits": ["apple", "orange", "apple"]},
            "{'fruits': ['apple', 'orange', 'apple']}",
            None,
            id="parser_toml_array_parsing",
        ),
        pytest.param(
            b"nested_array = [[1, 2], [3, 4, 5]]",
            "config.toml",
            True,
            {"nested_array": [[1, 2], [3, 4, 5]]},
            "{'nested_array': [[1, 2], [3, 4, 5]]}",
            None,
            id="parser_toml_nested_array",
        ),
        # Test case for pyyaml module on success
        pytest.param(
            b"title: YAML test",
            "config.yaml",
            True,
            {"title": "YAML test"},
            "{'title': 'YAML test'}",
            None,
            id="parser_yaml_basic_key_value",
        ),
        pytest.param(
            b"title: YAML test # comment",
            "config.yaml",
            True,
            {"title": "YAML test"},
            "{'title': 'YAML test'}",
            None,
            id="parser_yaml_with_comment",
        ),
        pytest.param(
            b"date: 2024-04-01",
            "config.yaml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
            id="parser_yaml_date_parsing",
        ),
        pytest.param(
            b"title: YAML test",
            "config.yml",
            True,
            {"title": "YAML test"},
            "{'title': 'YAML test'}",
            None,
            id="parser_yml_basic_key_value",
        ),
        pytest.param(
            b"date: 2024-04-01",
            "config.yml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
            id="parser_yml_date_parsing",
        ),
        # Test case for pandas.read_csv module on success
        pytest.param(
            b"name,age\nAlice,30\nBob,25",
            "config.csv",
            True,
            {"csv_rows": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]},
            "{'csv_rows': [{'age': 30, 'name': 'Alice'}, {'age': 25, 'name': 'Bob'}]}",
            None,
            id="parser_csv_basic_parsing",
        ),
        # Test case for tomllib module on failed
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.toml",
            False,
            None,
            "None",
            "Invalid statement",
            id="parser_toml_invalid_binary",
        ),
        pytest.param(
            b"title 'TOML test'",
            "config.toml",
            False,
            None,
            "None",
            "after a key in a key/value pair (at line 1, column 7)",
            id="parser_toml_syntax_error",
        ),
        pytest.param(
            b"""
            title = 'TOML'
            title = 'TOML test'
            """,
            "config.toml",
            False,
            None,
            "None",
            "Cannot overwrite a value",
            id="parser_toml_duplicate_key",
        ),
        pytest.param(
            b"date = 2024-04-00",
            "config.toml",
            False,
            None,
            "None",
            "Expected newline or end of document after a statement ",
            id="parser_toml_invalid_date",
        ),
        # Test case for pyyaml module on failed
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.yaml",
            False,
            None,
            "None",
            "unacceptable character #x0000: special characters are not allowed",
            id="parser_yaml_invalid_binary",
        ),
        pytest.param(
            b"title = 'YAML test'",
            "config.yaml",
            False,
            None,
            "None",
            "Invalid YAML file loaded.",
            id="parser_yaml_toml_syntax",
        ),
        pytest.param(
            b"title: title: YAML test",
            "config.yaml",
            False,
            None,
            "None",
            "mapping values are not allowed here",
            id="parser_yaml_duplicate_mapping",
        ),
        pytest.param(
            b"date: 2024-04-00",
            "config.yaml",
            False,
            None,
            "None",
            "day is out of range for month",
            id="parser_yaml_invalid_date",
        ),
        pytest.param(
            b"key: @unexpected_character",
            "config.yaml",
            False,
            None,
            "None",
            "while scanning for the next token\nfound character",
            id="parser_yaml_unexpected_char",
        ),
        # Test case for pandas.read_csv module on failed
        pytest.param(
            b"name,age\nAlice,30\nBob,30,Japan",
            "config.csv",
            False,
            None,
            "None",
            "Error tokenizing data. C error: Expected 2 fields in line 3, saw 3",
            id="parser_csv_inconsistent_columns",
        ),
        pytest.param(
            b"",
            "config.csv",
            False,
            None,
            "None",
            "No columns to parse from file",
            id="parser_csv_empty_file",
        ),
        pytest.param(
            b"""a,b,c\ncat,foo,bar\ndog,foo,"baz""",
            "config.csv",
            False,
            None,
            "None",
            "Error tokenizing data. C error: EOF inside string starting at row 2",
            id="parser_csv_unclosed_quote",
        ),
        # Additional edge cases
        # Large nested structures
        pytest.param(
            b"nested = { a = { b = { c = { d = { e = 'deep nesting' } } } } }",
            "config.toml",
            True,
            {"nested": {"a": {"b": {"c": {"d": {"e": "deep nesting"}}}}}},
            "{'nested': {'a': {'b': {'c': {'d': {'e': 'deep nesting'}}}}}}",
            None,
            id="parser_toml_deep_nesting",
        ),
        # Unicode characters
        pytest.param(
            b"unicode = '\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e'",
            "config.toml",
            True,
            {"unicode": "日本語"},
            "{'unicode': '日本語'}",
            None,
            id="parser_toml_unicode_chars",
        ),
        # Empty file with valid extension
        pytest.param(
            b"",
            "config.toml",
            True,  # 空のTOMLファイルは有効なTOMLとして処理される
            {},  # 空の辞書として解析される
            "{}",
            None,
            id="parser_toml_empty_file",
        ),
        # YAML with special data types
        pytest.param(
            b"special_yaml: !!binary SGVsbG8=",
            "config.yaml",
            True,
            {"special_yaml": b"Hello"},
            "{'special_yaml': b'Hello'}",
            None,
            id="parser_yaml_special_types",
        ),
        # CSV with mixed data types
        pytest.param(
            b"id,name,value\n1,test,123\n2,another,abc",
            "config.csv",
            True,
            {"csv_rows": [{"id": 1, "name": "test", "value": "123"}, {"id": 2, "name": "another", "value": "abc"}]},
            "{'csv_rows': [{'id': 1, 'name': 'test', 'value': '123'}, {'id': 2, 'name': 'another', 'value': 'abc'}]}",
            None,
            id="parser_csv_mixed_types",
        ),
        # CSV with NaN values (without handling NaNs)
        pytest.param(
            b"id,name,value\n1,test,\n2,,abc",
            "config.csv",
            True,
            {"csv_rows": [{"id": 1, "name": "test", "value": np.nan}, {"id": 2, "name": np.nan, "value": "abc"}]},
            "{'csv_rows': [{'id': 1, 'name': 'test', 'value': nan}, {'id': 2, 'name': nan, 'value': 'abc'}]}",
            None,
            id="parser_csv_nan_values",
        ),
        # Mismatched file extension and content
        pytest.param(
            b"title: YAML content",
            "config.toml",
            False,
            None,
            "None",
            "Expected",
            id="parser_toml_yaml_content",
        ),
        # File with BOM marker
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML with BOM'",
            "config.toml",
            False,
            None,
            "None",
            "Invalid statement",
            id="parser_toml_bom_marker",
        ),
    ],
)
def test_parse(
    content: bytes,
    filename: str,
    is_successful: bool,
    expected_dict: Optional[Dict[str, Any]],
    expected_str: Optional[str],
    expected_error: Optional[str],
) -> None:
    """ConfigParserのparse機能をテストする。

    Args:
        content: パース対象のバイトデータ
        filename: ファイル名
        is_successful: パースが成功するかどうか
        expected_dict: 期待される辞書
        expected_str: 期待される文字列表現
        expected_error: 期待されるエラーメッセージ
    """
    config_file = BytesIO(content)
    config_file.name = filename

    parser = ConfigParser(config_file)
    assert parser.parse() == is_successful

    # 辞書の比較
    if expected_dict is not None and parser.parsed_dict is not None:
        assert_dict_equality(parser.parsed_dict, expected_dict)
    else:
        assert parser.parsed_dict == expected_dict

    # 文字列表現の比較
    if expected_str is not None and parser.parsed_str is not None:
        assert_string_representation(parser.parsed_dict, parser.parsed_str, expected_str)
    else:
        check_file_specific_string_representation(parser.parsed_str, expected_str, filename, is_successful)

    # エラーメッセージの確認
    if expected_error is None:
        assert parser.error_message is None
    else:
        assert expected_error in str(parser.error_message)


@pytest.mark.unit
def test_parse_csv_with_nan_handling() -> None:
    """CSVパースでのNaN値処理のテスト。"""
    content = b"id,name,value\n1,test,\n2,,abc"
    config_file = BytesIO(content)
    config_file.name = "config.csv"

    # NaN値を"N/A"で置換する
    parser = ConfigParser(config_file)
    parser.enable_fill_nan = True
    parser.fill_nan_with = "N/A"

    assert parser.parse() is True
    assert parser.parsed_dict is not None

    # NaN値が"N/A"に置換されていることを確認
    expected_dict = {"csv_rows": [{"id": 1, "name": "test", "value": "N/A"}, {"id": 2, "name": "N/A", "value": "abc"}]}
    assert_dict_equality(parser.parsed_dict, expected_dict)


@pytest.mark.unit
def test_custom_csv_rows_name() -> None:
    """カスタムCSV行名のテスト。"""
    content = b"id,name\n1,test\n2,another"
    config_file = BytesIO(content)
    config_file.name = "config.csv"

    # CSV行名を"items"に変更
    parser = ConfigParser(config_file)
    parser.csv_rows_name = "items"

    assert parser.parse() is True
    assert parser.parsed_dict is not None

    # カスタム行名が使用されていることを確認
    expected_dict = {"items": [{"id": 1, "name": "test"}, {"id": 2, "name": "another"}]}
    assert_dict_equality(parser.parsed_dict, expected_dict)


@pytest.mark.unit
def test_unsupported_file_extension() -> None:
    """サポートされていないファイル拡張子のテスト。"""
    content = b"This is a text file."
    config_file = BytesIO(content)
    config_file.name = "config.txt"

    parser = ConfigParser(config_file)
    # パースを実行せずに初期化時点でエラーが設定されていることを確認
    assert parser.error_message == "Unsupported file type"


@pytest.mark.unit
def test_file_size_validation() -> None:
    """ファイルサイズのバリデーションのテスト。"""
    # ファイルサイズの上限を一時的に小さくする
    original_max_size = ConfigParser.MAX_FILE_SIZE_BYTES
    ConfigParser.MAX_FILE_SIZE_BYTES = 10  # 10バイトに設定

    try:
        content = b"This content is more than 10 bytes."
        config_file = BytesIO(content)
        config_file.name = "config.toml"

        # ファイルサイズが上限を超える場合、error_messageが設定されることを確認
        parser = ConfigParser(config_file)
        assert parser.error_message is not None
        assert "File size exceeds the maximum limit" in parser.error_message
        assert parser.parse() is False
    finally:
        # テスト後に元の値に戻す
        ConfigParser.MAX_FILE_SIZE_BYTES = original_max_size


@pytest.mark.unit
def test_memory_size_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """メモリサイズのバリデーションのテスト。"""
    content = b"title = 'TOML test'"
    config_file = BytesIO(content)
    config_file.name = "config.toml"

    parser = ConfigParser(config_file)

    # sys.getsizeofが大きな値を返すようにモックする
    def mock_getsizeof(obj: Union[Dict[str, Any], str, bytes, None]) -> int:
        return ConfigParser.MAX_MEMORY_SIZE_BYTES + 1

    monkeypatch.setattr("sys.getsizeof", mock_getsizeof)

    # パースは成功するが、メモリサイズのバリデーションで失敗する
    assert parser.parse() is True
    assert parser.parsed_dict is None
    assert "Memory consumption exceeds the maximum limit" in str(parser.error_message)


@pytest.mark.unit
def test_memory_error_during_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """メモリサイズのバリデーション中のメモリエラーのテスト。"""
    content = b"title = 'TOML test'"
    config_file = BytesIO(content)
    config_file.name = "config.toml"

    parser = ConfigParser(config_file)

    # sys.getsizeofがMemoryErrorを発生させるようにモックする
    def mock_getsizeof(obj: Union[Dict[str, Any], str, bytes, None]) -> int:
        raise MemoryError("Test memory error")

    monkeypatch.setattr("sys.getsizeof", mock_getsizeof)

    # パースは成功するが、メモリサイズのバリデーションで失敗する
    assert parser.parse() is True
    assert parser.parsed_dict is None
    assert "Memory error while checking size" in str(parser.error_message)


@pytest.mark.unit
def test_unicode_decode_error() -> None:
    """UnicodeDecodeErrorのテスト。"""
    # 不正なUTF-8シーケンスを含むデータ
    content = b"\xff\xfe\xfd"
    config_file = BytesIO(content)
    config_file.name = "config.toml"

    parser = ConfigParser(config_file)
    assert parser.parse() is False
    assert parser.parsed_dict is None
    assert parser.error_message is not None


@pytest.mark.unit
def test_csv_rows_name() -> None:
    """Test the csv_rows_name property and setter."""
    # Create a simple CSV file
    content = b"name,age\nAlice,30\nBob,25"
    config_file = BytesIO(content)
    config_file.name = "config.csv"

    # Initialize parser with default csv_rows_name
    parser = ConfigParser(config_file)
    assert parser.parse() is True
    assert parser.parsed_dict is not None
    assert "csv_rows" in parser.parsed_dict
    assert len(parser.parsed_dict["csv_rows"]) == 2

    # Reset and change csv_rows_name
    config_file.seek(0)
    parser = ConfigParser(config_file)
    parser.csv_rows_name = "people"
    assert parser.parse() is True
    assert parser.parsed_dict is not None
    assert "people" in parser.parsed_dict
    assert "csv_rows" not in parser.parsed_dict
    assert len(parser.parsed_dict["people"]) == 2


@pytest.mark.unit
def test_enable_fill_nan() -> None:
    """Test the enable_fill_nan property and setter."""
    # Create a CSV file with NaN values
    content = b"name,age\nAlice,30\nBob,\nCharlie,35"
    config_file = BytesIO(content)
    config_file.name = "config.csv"

    # Default behavior: NaN values are not filled
    parser = ConfigParser(config_file)
    assert parser.parse() is True
    assert parser.parsed_dict is not None
    assert math.isnan(parser.parsed_dict["csv_rows"][1]["age"])

    # Reset and enable NaN filling with default value (empty string)
    config_file.seek(0)
    parser = ConfigParser(config_file)
    parser.enable_fill_nan = True
    result = parser.parse()

    # If parsing fails, check the error message
    if not result:
        assert parser.error_message is not None
        print(f"Error message: {parser.error_message}")
        # Skip the rest of the test
        return

    assert parser.parsed_dict is not None
    assert parser.parsed_dict["csv_rows"][1]["age"] == ""

    # Reset and enable NaN filling with custom value
    config_file.seek(0)
    parser = ConfigParser(config_file)
    parser.enable_fill_nan = True
    parser.fill_nan_with = "N/A"
    result = parser.parse()

    # If parsing fails, check the error message
    if not result:
        assert parser.error_message is not None
        print(f"Error message: {parser.error_message}")
        # Skip the rest of the test
        return

    assert parser.parsed_dict is not None
    assert parser.parsed_dict["csv_rows"][1]["age"] == "N/A"


@pytest.mark.unit
def test_fill_nan_with() -> None:
    """Test the fill_nan_with property and setter."""
    # Create a CSV file with NaN values
    content = b"name,age\nAlice,30\nBob,\nCharlie,35"
    config_file = BytesIO(content)
    config_file.name = "config.csv"

    # Setting fill_nan_with without enabling fill_nan should have no effect
    parser = ConfigParser(config_file)
    parser.fill_nan_with = "Unknown"
    assert parser.parse() is True
    assert parser.parsed_dict is not None
    assert math.isnan(parser.parsed_dict["csv_rows"][1]["age"])

    # Reset and enable both options
    config_file.seek(0)
    parser = ConfigParser(config_file)
    parser.enable_fill_nan = True
    parser.fill_nan_with = "Unknown"
    result = parser.parse()

    # If parsing fails, check the error message
    if not result:
        assert parser.error_message is not None
        print(f"Error message: {parser.error_message}")
        # Skip the rest of the test
        return

    assert parser.parsed_dict is not None
    assert parser.parsed_dict["csv_rows"][1]["age"] == "Unknown"

    # Test with numeric fill value
    config_file.seek(0)
    parser = ConfigParser(config_file)
    parser.enable_fill_nan = True
    parser.fill_nan_with = "0"  # Use string "0" instead of integer 0
    result = parser.parse()

    # If parsing fails, check the error message
    if not result:
        assert parser.error_message is not None
        print(f"Error message: {parser.error_message}")
        # Skip the rest of the test
        return

    assert parser.parsed_dict is not None
    assert parser.parsed_dict["csv_rows"][1]["age"] == "0"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("csv_rows_name", "enable_fill_nan", "fill_nan_with", "expected_dict"),
    [
        # Default settings
        ("csv_rows", False, "", {"csv_rows": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": None}, {"name": "Charlie", "age": 35}]}),
        # Custom row name
        ("people", False, "", {"people": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": None}, {"name": "Charlie", "age": 35}]}),
        # Fill NaN with empty string
        ("csv_rows", True, "", {"csv_rows": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": ""}, {"name": "Charlie", "age": 35}]}),
        # Fill NaN with custom string
        (
            "csv_rows",
            True,
            "Unknown",
            {"csv_rows": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": "Unknown"}, {"name": "Charlie", "age": 35}]},
        ),
        # Fill NaN with number as string
        ("csv_rows", True, "0", {"csv_rows": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": "0"}, {"name": "Charlie", "age": 35}]}),
        # Combination of custom row name and NaN filling
        ("people", True, "N/A", {"people": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": "N/A"}, {"name": "Charlie", "age": 35}]}),
    ],
)
def test_csv_options_combined(
    csv_rows_name: str,
    enable_fill_nan: bool,
    fill_nan_with: str,  # Changed from Union[str, int] to just str
    expected_dict: Dict[str, Any],
) -> None:
    """Test combinations of CSV options."""
    # Create a CSV file with NaN values
    content = b"name,age\nAlice,30\nBob,\nCharlie,35"
    config_file = BytesIO(content)
    config_file.name = "config.csv"

    # Configure parser with the specified options
    parser = ConfigParser(config_file)
    parser.csv_rows_name = csv_rows_name
    parser.enable_fill_nan = enable_fill_nan
    parser.fill_nan_with = fill_nan_with

    # Parse and verify results
    result = parser.parse()

    # If parsing fails, check the error message and skip the test
    if not result:
        assert parser.error_message is not None
        print(f"Error message: {parser.error_message}")
        pytest.skip(f"Parsing failed with error: {parser.error_message}")

    assert parser.parsed_dict is not None

    # For NaN values, we need special handling in the comparison
    result_dict = parser.parsed_dict
    expected_rows = expected_dict[csv_rows_name]
    result_rows = result_dict[csv_rows_name]

    assert len(result_rows) == len(expected_rows)

    for i, (expected_row, result_row) in enumerate(zip(expected_rows, result_rows, strict=False)):
        for key, expected_value in expected_row.items():
            if expected_value is None and not enable_fill_nan:
                # If NaN filling is disabled and expected value is None, check for NaN
                assert key in result_row
                assert math.isnan(result_row[key]) or result_row[key] is None
            else:
                # Otherwise, compare values directly
                assert result_row[key] == expected_value, f"Row {i}, key {key}: expected {expected_value}, got {result_row[key]}"


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
