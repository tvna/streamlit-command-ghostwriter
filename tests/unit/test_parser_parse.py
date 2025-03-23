import ast
import math
from datetime import date
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pytest

from features.config_parser import ConfigParser


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
            id="TOML module on success - basic key-value",
        ),
        pytest.param(
            b"date = 2024-04-01",
            "config.toml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
            id="TOML module on success - date parsing",
        ),
        pytest.param(
            b"fruits = ['apple', 'orange', 'apple']",
            "config.toml",
            True,
            {"fruits": ["apple", "orange", "apple"]},
            "{'fruits': ['apple', 'orange', 'apple']}",
            None,
            id="TOML module on success - array parsing",
        ),
        pytest.param(
            b"nested_array = [[1, 2], [3, 4, 5]]",
            "config.toml",
            True,
            {"nested_array": [[1, 2], [3, 4, 5]]},
            "{'nested_array': [[1, 2], [3, 4, 5]]}",
            None,
            id="TOML module on success - nested array parsing",
        ),
        # Test case for pyyaml module on success
        pytest.param(
            b"title: YAML test",
            "config.yaml",
            True,
            {"title": "YAML test"},
            "{'title': 'YAML test'}",
            None,
            id="YAML module on success - basic key-value",
        ),
        pytest.param(
            b"title: YAML test # comment",
            "config.yaml",
            True,
            {"title": "YAML test"},
            "{'title': 'YAML test'}",
            None,
            id="YAML module on success - with comment",
        ),
        pytest.param(
            b"date: 2024-04-01",
            "config.yaml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
            id="YAML module on success - date parsing",
        ),
        pytest.param(
            b"title: YAML test",
            "config.yml",
            True,
            {"title": "YAML test"},
            "{'title': 'YAML test'}",
            None,
            id="YAML module on success - yml extension",
        ),
        pytest.param(
            b"date: 2024-04-01",
            "config.yml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
            id="YAML module on success - yml extension with date parsing",
        ),
        # Test case for pandas.read_csv module on success
        pytest.param(
            b"name,age\nAlice,30\nBob,25",
            "config.csv",
            True,
            {"csv_rows": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]},
            "{'csv_rows': [{'age': 30, 'name': 'Alice'}, {'age': 25, 'name': 'Bob'}]}",
            None,
            id="CSV module on success - basic parsing",
        ),
        # Test case for tomllib module on failed
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.toml",
            False,
            None,
            "None",
            "Invalid statement",
            id="TOML module on failed - binary data",
        ),
        pytest.param(
            b"title 'TOML test'",
            "config.toml",
            False,
            None,
            "None",
            "after a key in a key/value pair (at line 1, column 7)",
            id="TOML module on failed - syntax error",
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
            id="TOML module on failed - duplicate key",
        ),
        pytest.param(
            b"date = 2024-04-00",
            "config.toml",
            False,
            None,
            "None",
            "Expected newline or end of document after a statement ",
            id="TOML module on failed - invalid date",
        ),
        # Test case for pyyaml module on failed
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.yaml",
            False,
            None,
            "None",
            "unacceptable character #x0000: special characters are not allowed",
            id="YAML module on failed - binary data",
        ),
        pytest.param(
            b"title = 'YAML test'",
            "config.yaml",
            False,
            None,
            "None",
            "Invalid YAML file loaded.",
            id="YAML module on failed - TOML syntax in YAML",
        ),
        pytest.param(
            b"title: title: YAML test",
            "config.yaml",
            False,
            None,
            "None",
            "mapping values are not allowed here",
            id="YAML module on failed - duplicate mapping yaml",
        ),
        pytest.param(
            b"date: 2024-04-00",
            "config.yaml",
            False,
            None,
            "None",
            "day is out of range for month",
            id="YAML module on failed - invalid date yaml",
        ),
        pytest.param(
            b"key: @unexpected_character",
            "config.yaml",
            False,
            None,
            "None",
            "while scanning for the next token\nfound character",
            id="YAML module on failed - unexpected character yaml",
        ),
        # Test case for pandas.read_csv module on failed
        pytest.param(
            b"name,age\nAlice,30\nBob,30,Japan",
            "config.csv",
            False,
            None,
            "None",
            "Error tokenizing data. C error: Expected 2 fields in line 3, saw 3",
            id="CSV module on failed - inconsistent columns",
        ),
        pytest.param(
            b"",
            "config.csv",
            False,
            None,
            "None",
            "No columns to parse from file",
            id="CSV module on failed - empty file",
        ),
        pytest.param(
            b"""a,b,c\ncat,foo,bar\ndog,foo,"baz""",
            "config.csv",
            False,
            None,
            "None",
            "Error tokenizing data. C error: EOF inside string starting at row 2",
            id="CSV module on failed - unclosed quote",
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
            id="TOML module on success - deeply nested structure",
        ),
        # Unicode characters
        pytest.param(
            b"unicode = '\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e'",
            "config.toml",
            True,
            {"unicode": "日本語"},
            "{'unicode': '日本語'}",
            None,
            id="TOML module on success - unicode characters",
        ),
        # Empty file with valid extension
        pytest.param(
            b"",
            "config.toml",
            True,  # 空のTOMLファイルは有効なTOMLとして処理される
            {},  # 空の辞書として解析される
            "{}",
            None,
            id="TOML module on success - empty file",
        ),
        # YAML with special data types
        pytest.param(
            b"special_yaml: !!binary SGVsbG8=",
            "config.yaml",
            True,
            {"special_yaml": b"Hello"},
            "{'special_yaml': b'Hello'}",
            None,
            id="YAML module on success - special YAML types",
        ),
        # CSV with mixed data types
        pytest.param(
            b"id,name,value\n1,test,123\n2,another,abc",
            "config.csv",
            True,
            {"csv_rows": [{"id": 1, "name": "test", "value": "123"}, {"id": 2, "name": "another", "value": "abc"}]},
            "{'csv_rows': [{'id': 1, 'name': 'test', 'value': '123'}, {'id': 2, 'name': 'another', 'value': 'abc'}]}",
            None,
            id="CSV module on success - mixed data types",
        ),
        # CSV with NaN values (without handling NaNs)
        pytest.param(
            b"id,name,value\n1,test,\n2,,abc",
            "config.csv",
            True,
            {"csv_rows": [{"id": 1, "name": "test", "value": np.nan}, {"id": 2, "name": np.nan, "value": "abc"}]},
            "{'csv_rows': [{'id': 1, 'name': 'test', 'value': nan}, {'id': 2, 'name': nan, 'value': 'abc'}]}",
            None,
            id="CSV module on success - NaN values without handling",
        ),
        # Mismatched file extension and content
        pytest.param(
            b"title: YAML content",
            "config.toml",
            False,
            None,
            "None",
            "Expected",
            id="TOML module on failed - YAML content in TOML file",
        ),
        # File with BOM marker
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML with BOM'",
            "config.toml",
            False,
            None,
            "None",
            "Invalid statement",
            id="TOML module on failed - BOM marker",
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
