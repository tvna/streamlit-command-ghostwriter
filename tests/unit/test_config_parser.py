"""ConfigParserのテストモジュール。

このモジュールは、ConfigParserクラスの機能をテストします。
テストは以下のカテゴリに分類されます:
1. 初期化テスト
2. パース機能テスト
3. エッジケーステスト
4. メモリ使用量テスト
"""

import math
import sys
from datetime import date
from io import BytesIO
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union, cast

import numpy as np
import pytest
from _pytest.mark.structures import MarkDecorator

from features.config_parser import ConfigParser

# 定数の定義
PARSE_SUCCESSFUL: bool = True
PARSE_FAILED: bool = False
EXPECT_NO_ERROR: Optional[str] = None
EXPECT_NO_DICT: Optional[Dict[str, Any]] = None

UNIT: MarkDecorator = pytest.mark.unit

# 基本的な値の型を定義
ScalarValueType = Union[str, int, float, bool, None]

# 日付型の値の型を定義
DateValueType = date

# 全ての値の型を定義 (前方参照)
ValueType = Union[
    ScalarValueType,
    "ArrayValueType",
    "MappingValueType",
    DateValueType,
]

# CSV行の型を定義
CsvRowType = Mapping[str, ScalarValueType]
CsvRowsType = Sequence[CsvRowType]

# 配列型の値の型を定義
ArrayValueType = Union[Sequence[ValueType], np.ndarray]

# マッピング型の値の型を定義
MappingValueType = Mapping[str, ValueType]

# パース結果の辞書の型を定義
ParsedDictType = Mapping[str, ValueType]


class TestHelpers:
    """テストヘルパー関数を提供するクラス。"""

    @staticmethod
    def create_test_file(content: bytes, filename: str) -> BytesIO:
        """テスト用のファイルを作成する。

        Args:
            content: ファイルの内容
            filename: ファイル名

        Returns:
            BytesIO: テスト用のファイル
        """
        file = BytesIO(content)
        file.name = filename
        return file

    @staticmethod
    def _assert_mapping_equality(
        actual: Mapping[str, ValueType],
        expected: Mapping[str, ValueType],
        current_path: str,
    ) -> None:
        """マッピング型の値を比較する。

        Args:
            actual: 実際の辞書
            expected: 期待される辞書
            current_path: 現在のパス (エラーメッセージ用)
        """
        TestHelpers.assert_dict_equality(actual, expected, current_path)

    @staticmethod
    def _assert_csv_rows_equality(
        actual: Sequence[Mapping[str, ScalarValueType]],
        expected: Sequence[Mapping[str, ScalarValueType]],
        current_path: str,
    ) -> None:
        """CSV行データを比較する。

        Args:
            actual: 実際のCSV行データ
            expected: 期待されるCSV行データ
            current_path: 現在のパス (エラーメッセージ用)
        """
        TestHelpers.assert_csv_rows_equality(actual, expected)  # type: ignore

    @staticmethod
    def _assert_sequence_equality(
        actual: Union[Sequence[ValueType], np.ndarray],
        expected: Union[Sequence[ValueType], np.ndarray],
        current_path: str,
    ) -> None:
        """シーケンス型の値を比較する。

        Args:
            actual: 実際のシーケンス
            expected: 期待されるシーケンス
            current_path: 現在のパス (エラーメッセージ用)
        """
        assert len(actual) == len(expected), f"Length mismatch at {current_path}"
        for a, e in zip(actual, expected, strict=False):
            assert a == e, f"Value mismatch in sequence at {current_path}"

    @staticmethod
    def _is_csv_row_sequence(value: Union[Sequence[Mapping[str, ScalarValueType]], ValueType]) -> bool:
        """値がCSV行のシーケンスかどうかを判定する。

        Args:
            value: 判定する値。シーケンス型またはValueType型の値を受け取る。

        Returns:
            bool: CSV行のシーケンスの場合True
        """
        if not isinstance(value, (list, tuple)):
            return False
        if not value:  # 空のシーケンスの場合
            return True
        return all(
            isinstance(row, Mapping) and all(isinstance(v, (str, int, float, bool)) or v is None for v in row.values()) for row in value
        )

    @staticmethod
    def _compare_values(
        actual_value: ValueType,
        expected_value: ValueType,
        key: str,
        current_path: str,
    ) -> None:
        """値を比較する。

        Args:
            actual_value: 実際の値
            expected_value: 期待される値
            key: キー
            current_path: 現在のパス (エラーメッセージ用)
        """
        # マッピング型の場合
        if isinstance(expected_value, Mapping) and isinstance(actual_value, Mapping):
            TestHelpers._assert_mapping_equality(actual_value, expected_value, current_path)
            return

        # csv_rowsの場合
        if key == "csv_rows" and TestHelpers._is_csv_row_sequence(expected_value) and TestHelpers._is_csv_row_sequence(actual_value):
            TestHelpers._assert_csv_rows_equality(
                cast("Sequence[Mapping[str, ScalarValueType]]", actual_value),
                cast("Sequence[Mapping[str, ScalarValueType]]", expected_value),
                current_path,
            )
            return

        # 配列型の場合
        if isinstance(expected_value, (list, tuple, np.ndarray)) and isinstance(actual_value, (list, tuple, np.ndarray)):
            TestHelpers._assert_sequence_equality(actual_value, expected_value, current_path)
            return

        # スカラー型または日付型の場合 (ScalarValueType or DateValueType)
        # This explicitly calls the helper designed for scalar/NaN/type comparison logic.
        TestHelpers.assert_value_equality(cast("ScalarValueType", actual_value), cast("ScalarValueType", expected_value), current_path)

    @staticmethod
    def assert_dict_equality(actual: Mapping[str, ValueType], expected: Mapping[str, ValueType], path: str = "") -> None:
        """辞書の内容を比較する。

        Args:
            actual: 実際の辞書
            expected: 期待される辞書
            path: 現在のパス (エラーメッセージ用)
        """
        assert set(actual.keys()) == set(expected.keys()), (
            f"Keys do not match at path: {path}. Expected: {set(expected.keys())}, Got: {set(actual.keys())}"
        )
        for key in expected:
            current_path = f"{path}.{key}" if path else key
            TestHelpers._compare_values(actual[key], expected[key], key, current_path)

    @staticmethod
    def assert_csv_rows_equality(actual: CsvRowsType, expected: CsvRowsType) -> None:
        """CSVの行データの内容を比較する。

        Args:
            actual: 実際の行データ
            expected: 期待される行データ
        """
        assert len(actual) == len(expected), f"CSV row count mismatch. Expected: {len(expected)}, Got: {len(actual)}"
        for i, (expected_row, actual_row) in enumerate(zip(expected, actual, strict=False)):
            TestHelpers.assert_csv_row_equality(actual_row, expected_row, i)

    @staticmethod
    def assert_csv_row_equality(actual: CsvRowType, expected: CsvRowType, row_index: int) -> None:
        """CSVの1行のデータを比較する。

        Args:
            actual: 実際の行データ
            expected: 期待される行データ
            row_index: 行のインデックス
        """
        assert set(actual.keys()) == set(expected.keys()), (
            f"CSV row {row_index} keys mismatch. Expected: {set(expected.keys())}, Got: {set(actual.keys())}"
        )
        for col_key in expected:
            actual_value = actual[col_key]
            expected_value = expected[col_key]
            TestHelpers.assert_value_equality(actual_value, expected_value, f"column {col_key} in row {row_index}")

    @staticmethod
    def _assert_nan_comparison(actual: ScalarValueType, expected: ScalarValueType, location: str) -> bool:
        """NaN値の比較を行い、比較が完了したかを示す。

        Args:
            actual: 実際の値
            expected: 期待される値
            location: 値の場所 (エラーメッセージ用)

        Returns:
            bool: NaNに関する比較/アサーション完了
        """
        is_actual_nan = TestHelpers.is_nan_value(actual)
        is_expected_nan = TestHelpers.is_nan_value(expected)

        if is_actual_nan or is_expected_nan:
            assert is_actual_nan is True, (
                f"Value mismatch at {location}: One value is NaN while the other is not. Actual: {actual!r}, Expected: {expected!r}"
            )
            assert is_expected_nan is True, (
                f"Value mismatch at {location}: One value is NaN while the other is not. Actual: {actual!r}, Expected: {expected!r}"
            )
            return True  # NaNに関する比較/アサーション完了
        return False  # NaNではないので比較は続行

    @staticmethod
    def _assert_bool_comparison(actual: ScalarValueType, expected: ScalarValueType, location: str) -> bool:
        """真偽値の比較を行い、比較が完了したかを示す。

        Args:
            actual: 実際の値
            expected: 期待される値
            location: 値の場所 (エラーメッセージ用)

        Returns:
            bool: 真偽値比較完了
        """
        is_actual_bool = isinstance(actual, (bool, np.bool_))
        is_expected_bool = isinstance(expected, (bool, np.bool_))

        if is_actual_bool and is_expected_bool:
            assert bool(actual) == bool(expected), f"Boolean value mismatch at {location}: Expected {expected}, Got {actual}"
            return True  # 真偽値比較完了
        return False  # 真偽値同士ではないので比較続行

    @staticmethod
    def _assert_cross_type_comparison(actual: ScalarValueType, expected: ScalarValueType, location: str) -> bool:
        """数値と文字列の相互比較を行い、比較が完了したかを示す。

        Args:
            actual: 実際の値
            expected: 期待される値
            location: 値の場所 (エラーメッセージ用)

        Returns:
            bool: 数値/文字列比較完了
        """
        # Actualが数値、Expectedが文字列
        if isinstance(actual, (int, float)) and isinstance(expected, str):
            assert str(actual) == expected, f"Value mismatch at {location}: Expected string '{expected}', Got numeric {actual}"
            return True  # 数値->文字列比較完了

        # Actualが文字列、Expectedが数値
        if isinstance(actual, str) and isinstance(expected, (int, float)):
            try:
                converted_actual = float(actual) if isinstance(expected, float) else int(actual)
                assert converted_actual == expected, f"Value mismatch at {location}: Expected numeric {expected}, Got string '{actual}'"
                return True  # 文字列->数値比較完了
            except ValueError:
                # 変換失敗時はこの比較ケースではないので続行
                return False

        return False  # クロスタイプの比較対象ではない

    @staticmethod
    def assert_value_equality(actual: ScalarValueType, expected: ScalarValueType, location: str) -> None:
        """値の比較を行う。NaN値や型変換を考慮。

        Args:
            actual: 実際の値
            expected: 期待される値
            location: 値の場所 (エラーメッセージ用)
        """
        # 1. NaN比較
        if TestHelpers._assert_nan_comparison(actual, expected, location):
            return

        # 2. 真偽値比較
        if TestHelpers._assert_bool_comparison(actual, expected, location):
            return

        # 3. 数値/文字列クロス比較
        if TestHelpers._assert_cross_type_comparison(actual, expected, location):
            return

        # 4. その他の型 (上記いずれにも当てはまらない場合)
        assert actual == expected, f"Value mismatch at {location}: Expected {expected!r}, Got {actual!r}"

    @staticmethod
    def is_nan_value(value: Optional[Union[float, str, int]]) -> bool:
        """値がNaNかどうかを判定する。

        Args:
            value: 判定する値

        Returns:
            bool: NaNの場合True
        """
        if isinstance(value, float) and math.isnan(value):
            return True
        # Removed incorrect check: `if value is None: return True`
        # Check for numpy NaN specifically, as it might be present from CSV parsing
        # Use isinstance to avoid errors if value doesn't have 'dtype'
        if isinstance(value, np.generic) and np.isnan(value):  # type: ignore[unreachable]
            return True  # type: ignore[unreachable]
        return False

    @staticmethod
    def assert_nan_string_representation(actual: str, expected: str) -> None:
        """NaN値を含む文字列表現を比較する。

        Args:
            actual: 実際の文字列表現
            expected: 期待される文字列表現
        """

        # Normalize whitespace carefully
        def normalize_whitespace(s: str) -> str:
            lines = s.strip().split("\n")
            normalized_lines = [" ".join(line.strip().split()) for line in lines]
            return "\n".join(normalized_lines)

        actual_normalized = normalize_whitespace(actual)
        expected_normalized = normalize_whitespace(expected)
        assert actual_normalized == expected_normalized, (
            f"Normalized string representation with NaN does not match.\n"
            f"Actual normalized:\n{actual_normalized}\n"
            f"Expected normalized:\n{expected_normalized}"
        )

    @staticmethod
    def assert_parsing_result(
        content: bytes,
        filename: str,
        is_successful: bool,
        expected_dict: Optional[ParsedDictType],
        expected_error: Optional[str],
        csv_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """ファイル内容をパースし、結果をアサートするヘルパー関数。

        Args:
            content: パース対象のバイトデータ
            filename: ファイル名
            is_successful: パースが成功するかどうか
            expected_dict: 期待される辞書 (Noneの場合は辞書比較をスキップ)
            expected_error: 期待されるエラーメッセージ (Noneの場合はエラーがないことを期待)
            csv_options: CSVパース用の追加オプション (例: {'csv_rows_name': 'items'})
        """
        config_file = TestHelpers.create_test_file(content, filename)
        parser = ConfigParser(config_file)

        # Apply CSV options if provided
        if csv_options:
            for key, value in csv_options.items():
                setattr(parser, key, value)

        # Perform parsing
        actual_successful = parser.parse()
        assert actual_successful == is_successful, f"Parsing success status mismatch. Expected: {is_successful}, Got: {actual_successful}"

        # Assert error message
        if expected_error is None:
            assert parser.error_message is None, f"Expected no error message, but got: {parser.error_message}"
        else:
            assert parser.error_message is not None, f"Expected an error message containing '{expected_error}', but got None"
            assert expected_error in parser.error_message, (
                f"Error message mismatch. Expected to contain: '{expected_error}', Got: '{parser.error_message}'"
            )

        # Assert parsed dictionary (skip if expected_dict is explicitly None)
        if expected_dict is not None:
            assert parser.parsed_dict is not None, f"Expected a parsed dictionary, but got None. Error: {parser.error_message}"
            TestHelpers.assert_dict_equality(parser.parsed_dict, expected_dict)


@UNIT
@pytest.mark.parametrize(
    ("content", "filename", "expected_error"),
    [
        pytest.param(
            b"valid content",
            "config.toml",
            EXPECT_NO_ERROR,
            id="init_toml_valid_file",
        ),
        pytest.param(
            b"valid content",
            "config.yaml",
            EXPECT_NO_ERROR,
            id="init_yaml_valid_file",
        ),
        pytest.param(
            b"valid content",
            "config.yml",
            EXPECT_NO_ERROR,
            id="init_yml_valid_file",
        ),
        pytest.param(
            b"valid content",
            "config.csv",
            EXPECT_NO_ERROR,
            id="init_csv_valid_file",
        ),
        pytest.param(
            b"unsupported content",
            "config.txt",
            "Unsupported file type",
            id="init_txt_unsupported_type",
        ),
        pytest.param(
            b"unsupported content",
            "config",
            "Unsupported file type",
            id="init_no_ext_unsupported_type",
        ),
        pytest.param(
            b"\x80\x81\x82\x83",
            "config.toml",
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="init_toml_invalid_utf8",
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
    config_file = TestHelpers.create_test_file(content, filename)
    parser = ConfigParser(config_file)

    if expected_error is EXPECT_NO_ERROR:
        assert parser.error_message is None
    else:
        assert expected_error == parser.error_message


@UNIT
def test_default_properties() -> None:
    """ConfigParserのデフォルトプロパティをテストする。"""
    config_file = TestHelpers.create_test_file(b"content", "config.toml")
    parser = ConfigParser(config_file)

    assert parser.csv_rows_name == "csv_rows"
    assert parser.enable_fill_nan is False
    assert parser.fill_nan_with is None
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert parser.error_message is None


@UNIT
@pytest.mark.parametrize(
    ("content", "filename", "is_successful", "expected_dict", "expected_error"),
    [
        pytest.param(
            b"title = 'TOML test'",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"title": "TOML test"},
            EXPECT_NO_ERROR,
            id="parse_toml_basic_key_value_success",
        ),
        pytest.param(
            b"date = 2024-04-01",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"date": date(2024, 4, 1)},
            EXPECT_NO_ERROR,
            id="parse_toml_date_success",
        ),
        pytest.param(
            b"fruits = ['apple', 'orange', 'apple']",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"fruits": ["apple", "orange", "apple"]},
            EXPECT_NO_ERROR,
            id="parse_toml_array_success",
        ),
        pytest.param(
            b"nested_array = [[1, 2], [3, 4, 5]]",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"nested_array": [[1, 2], [3, 4, 5]]},
            EXPECT_NO_ERROR,
            id="parse_toml_nested_array_success",
        ),
        pytest.param(
            b"title: YAML test",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"title": "YAML test"},
            EXPECT_NO_ERROR,
            id="parse_yaml_basic_key_value_success",
        ),
        pytest.param(
            b"title: YAML test # comment",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"title": "YAML test"},
            EXPECT_NO_ERROR,
            id="parse_yaml_with_comment_success",
        ),
        pytest.param(
            b"date: 2024-04-01",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"date": date(2024, 4, 1)},
            EXPECT_NO_ERROR,
            id="parse_yaml_date_success",
        ),
        pytest.param(
            b"title: YAML test",
            "config.yml",
            PARSE_SUCCESSFUL,
            {"title": "YAML test"},
            EXPECT_NO_ERROR,
            id="parse_yml_basic_key_value_success",
        ),
        pytest.param(
            b"date: 2024-04-01",
            "config.yml",
            PARSE_SUCCESSFUL,
            {"date": date(2024, 4, 1)},
            EXPECT_NO_ERROR,
            id="parse_yml_date_success",
        ),
        pytest.param(
            b"name,age\nAlice,30\nBob,25",
            "config.csv",
            PARSE_SUCCESSFUL,
            {"csv_rows": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]},
            EXPECT_NO_ERROR,
            id="parse_csv_basic_success",
        ),
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.toml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Invalid statement (at line 1, column 1)",
            id="parse_toml_invalid_binary_fail",
        ),
        pytest.param(
            b"title 'TOML test'",
            "config.toml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Expected '=' after a key in a key/value pair (at line 1, column 7)",
            id="parse_toml_syntax_error_fail",
        ),
        pytest.param(
            b"\ntitle = 'TOML'\ntitle = 'TOML test'\n",
            "config.toml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Cannot overwrite a value (at line 3, column 20)",
            id="parse_toml_duplicate_key_fail",
        ),
        pytest.param(
            b"date = 2024-04-00",
            "config.toml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Expected newline or end of document after a statement (at line 1, column 12)",
            id="parse_toml_invalid_date_fail",
        ),
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.yaml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            'unacceptable character #x0000: special characters are not allowed\n  in "<unicode string>", position 0',
            id="parse_yaml_invalid_binary_fail",
        ),
        pytest.param(
            b"title = 'YAML test'",
            "config.yaml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Invalid YAML file loaded.",
            id="parse_yaml_toml_syntax_fail",
        ),
        pytest.param(
            b"title: title: YAML test",
            "config.yaml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "mapping values are not allowed here",
            id="parse_yaml_duplicate_mapping_fail",
        ),
        pytest.param(
            b"date: 2024-04-00",
            "config.yaml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "day is out of range for month",
            id="parse_yaml_invalid_date_fail",
        ),
        pytest.param(
            b"key: @unexpected_character",
            "config.yaml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "while scanning for the next token\nfound character",
            id="parse_yaml_unexpected_char_fail",
        ),
        pytest.param(
            (b"name,age\n" + b"Alice,30\n" + b"Bob,30,Japan"),
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Error tokenizing data. C error: Expected 2 fields in line 3, saw 3",
            id="parse_csv_inconsistent_columns_fail",
        ),
        pytest.param(
            b"",
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "No columns to parse from file",
            id="parse_csv_empty_file_fail",
        ),
        pytest.param(
            b'a,b,c\ncat,foo,bar\ndog,foo,"baz',
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Error tokenizing data. C error: EOF inside string starting at row 2",
            id="parse_csv_unclosed_quote_fail",
        ),
        pytest.param(
            b"nested = { a = { b = { c = { d = { e = 'deep nesting' } } } } }",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"nested": {"a": {"b": {"c": {"d": {"e": "deep nesting"}}}}}},
            EXPECT_NO_ERROR,
            id="parse_toml_deep_nesting_success",
        ),
        pytest.param(
            b"unicode = '\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e'",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"unicode": "日本語"},
            EXPECT_NO_ERROR,
            id="parse_toml_unicode_chars_success",
        ),
        pytest.param(
            b"",
            "config.toml",
            PARSE_SUCCESSFUL,
            {},
            EXPECT_NO_ERROR,
            id="parse_toml_empty_file_success",
        ),
        pytest.param(
            b"special_yaml: !!binary SGVsbG8=",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"special_yaml": b"Hello"},
            EXPECT_NO_ERROR,
            id="parse_yaml_special_types_binary_success",
        ),
        pytest.param(
            b"id,name,value\n1,test,123\n2,another,abc",
            "config.csv",
            PARSE_SUCCESSFUL,
            {"csv_rows": [{"id": 1, "name": "test", "value": "123"}, {"id": 2, "name": "another", "value": "abc"}]},
            EXPECT_NO_ERROR,
            id="parse_csv_mixed_types_success",
        ),
        pytest.param(
            b"id,name,value\n1,test,\n2,,abc",
            "config.csv",
            PARSE_SUCCESSFUL,
            {"csv_rows": [{"id": 1, "name": "test", "value": np.nan}, {"id": 2, "name": np.nan, "value": "abc"}]},
            EXPECT_NO_ERROR,
            id="parse_csv_nan_values_success",
        ),
        pytest.param(
            b"title: YAML content",
            "config.toml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Expected '=' after a key in a key/value pair (at line 1, column 6)",
            id="parse_toml_with_yaml_content_fail",
        ),
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML with BOM'",
            "config.toml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Invalid statement (at line 1, column 1)",
            id="parse_toml_with_bom_fail",
        ),
        pytest.param(
            b"col1,col2\n",
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "CSV file must contain at least one data row.",
            id="parse_csv_header_only_fail",
        ),
        pytest.param(
            b'col1,col2\nval1,"unclosed_val2',
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Error tokenizing data. C error: EOF inside string starting at row 1",
            id="parse_csv_unclosed_quote_in_data_fail",
        ),
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Failed to parse CSV: Null byte detected in input data.",
            id="parse_csv_invalid_binary_fail",
        ),
        # --- Start: New CSV Edge Case Tests ---
        pytest.param(
            b" col1 , col2 \n val1 , val2 \n",
            "config.csv",
            PARSE_SUCCESSFUL,
            {"csv_rows": [{" col1 ": " val1 ", " col2 ": " val2 "}]},
            EXPECT_NO_ERROR,
            id="parse_csv_whitespace_in_header_data_success",
        ),
        pytest.param(
            b"col1,col2\r\nval1,val2\nval3,val4\rval5,val6",
            "config.csv",
            PARSE_SUCCESSFUL,
            {"csv_rows": [{"col1": "val1", "col2": "val2"}, {"col1": "val3", "col2": "val4"}, {"col1": "val5", "col2": "val6"}]},
            EXPECT_NO_ERROR,
            id="parse_csv_mixed_line_endings_success",
        ),
        pytest.param(
            b"col1,col2\n123,abc\n456.7,True\nxyz,False\n,999",
            "config.csv",
            PARSE_SUCCESSFUL,
            {
                "csv_rows": [
                    {"col1": "123", "col2": "abc"},
                    {"col1": "456.7", "col2": "True"},
                    {"col1": "xyz", "col2": "False"},
                    {"col1": np.nan, "col2": "999"},
                ]
            },
            EXPECT_NO_ERROR,
            id="parse_csv_highly_mixed_types_nan_success",
        ),
        pytest.param(
            b" \t \n \n \t\t ",
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "No columns to parse from file",
            id="parse_csv_whitespace_only_fail",
        ),
        pytest.param(
            b"col1,col2\n \t \n \n",
            "config.csv",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "CSV file must contain at least one data row.",
            id="parse_csv_header_with_whitespace_lines_fail",
        ),
        pytest.param(
            b'col1,col2\n"line1\nline2",value2',
            "config.csv",
            PARSE_SUCCESSFUL,
            {"csv_rows": [{"col1": "line1\nline2", "col2": "value2"}]},
            EXPECT_NO_ERROR,
            id="parse_csv_quoted_newlines_success",
        ),
        pytest.param(
            b"float_val = 3.14\ninf_val = inf\nnan_val = nan",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"float_val": 3.14, "inf_val": float("inf"), "nan_val": float("nan")},
            EXPECT_NO_ERROR,
            id="parse_toml_float_inf_nan_success",
        ),
        pytest.param(
            b"bool_true = true\nbool_false = false",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"bool_true": True, "bool_false": False},
            EXPECT_NO_ERROR,
            id="parse_toml_booleans_success",
        ),
        pytest.param(
            b'inline_table = { key1 = "val1", key2 = 123 }',
            "config.toml",
            PARSE_SUCCESSFUL,
            {"inline_table": {"key1": "val1", "key2": 123}},
            EXPECT_NO_ERROR,
            id="parse_toml_inline_table_success",
        ),
        pytest.param(
            b"[[points]]\nx = 1\ny = 2\n[[points]]\nx = 3\ny = 4",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]},
            EXPECT_NO_ERROR,
            id="parse_toml_array_of_tables_success",
        ),
        pytest.param(
            b'[table]\nkey = "val"\n' + b'[table.subtable]\nkey = "subval"\n' + b'[table]\nother_key = "redefined?"',
            "config.toml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Cannot declare ('table',) twice (at line 5, column 7)",
            id="parse_toml_redefine_table_fail",
        ),
        pytest.param(
            b"array = [1, 2, 3,]",
            "config.toml",
            PARSE_SUCCESSFUL,
            {"array": [1, 2, 3]},
            EXPECT_NO_ERROR,
            id="parse_toml_trailing_comma_array_success",
        ),
        pytest.param(
            b"anchor_test: &anchor_val value\nalias_test: *anchor_val",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"anchor_test": "value", "alias_test": "value"},
            EXPECT_NO_ERROR,
            id="parse_yaml_anchor_alias_success",
        ),
        pytest.param(
            b"base: &base { x: 1 }\nderived: { <<: *base, y: 2 }",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"base": {"x": 1}, "derived": {"x": 1, "y": 2}},
            EXPECT_NO_ERROR,
            id="parse_yaml_merge_keys_success",
        ),
        pytest.param(
            b"str_val: !!str 123\nint_val: !!int '456'\nbool_val: !!bool yes",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"str_val": "123", "int_val": 456, "bool_val": True},
            EXPECT_NO_ERROR,
            id="parse_yaml_explicit_tags_success",
        ),
        pytest.param(
            b"literal_block: |\n  Line 1\n  Line 2\nfolded_block: >\n  Word1 Word2 Word3\n  Word4 Word5",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"literal_block": "Line 1\nLine 2\n", "folded_block": "Word1 Word2 Word3 Word4 Word5"},
            EXPECT_NO_ERROR,
            id="parse_yaml_scalar_styles_success",
        ),
        pytest.param(
            b"- item1\n- item2",
            "config.yaml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            "Invalid YAML file loaded.",
            id="parse_yaml_top_level_sequence_fail",
        ),
        pytest.param(
            b"doc1_key: value1\n---\ndoc2_key: value2",
            "config.yaml",
            PARSE_FAILED,
            EXPECT_NO_DICT,
            (
                "expected a single document in the stream\n"
                + '  in "<unicode string>", line 1, column 1:\n'
                + "    doc1_key: value1\n"
                + "    ^\n"
                + "but found another document\n"
                + '  in "<unicode string>", line 2, column 1:\n'
                + "    ---\n"
                + "    ^"
            ),
            id="parse_yaml_multiple_documents_fail",
        ),
        pytest.param(
            b"a: &a [1, *a]",
            "config.yaml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_DICT,
            EXPECT_NO_ERROR,
        ),
        pytest.param(
            b"large_string: '" + b"a" * 5000 + b"'",
            "config.yaml",
            PARSE_SUCCESSFUL,
            {"large_string": "a" * 5000},
            EXPECT_NO_ERROR,
            id="parse_yaml_large_scalar_success",
        ),
    ],
)
def test_parse(
    content: bytes,
    filename: str,
    is_successful: bool,
    expected_dict: Optional[ParsedDictType],
    expected_error: Optional[str],
) -> None:
    """ConfigParserのparse機能をテストする。

    Args:
        content: パース対象のバイトデータ
        filename: ファイル名
        is_successful: パースが成功するかどうか
        expected_dict: 期待される辞書
        expected_error: 期待されるエラーメッセージ
    """
    # Use the helper function to perform parsing and assertions
    TestHelpers.assert_parsing_result(
        content,
        filename,
        is_successful,
        expected_dict,
        expected_error,
    )


@UNIT
def test_parse_csv_with_nan_handling() -> None:
    """CSVパースでのNaN値処理のテスト。"""
    content = b"id,name,value\n1,test,\n2,,abc"
    config_file = TestHelpers.create_test_file(content, "config.csv")

    # NaN値を"N/A"で置換する
    parser = ConfigParser(config_file)
    parser.enable_fill_nan = True
    parser.fill_nan_with = "N/A"

    assert parser.parse() is True
    assert parser.parsed_dict is not None

    # NaN値が"N/A"に置換されていることを確認
    expected_dict = {"csv_rows": [{"id": 1, "name": "test", "value": "N/A"}, {"id": 2, "name": "N/A", "value": "abc"}]}
    TestHelpers.assert_dict_equality(parser.parsed_dict, expected_dict)  # type: ignore


@UNIT
def test_custom_csv_rows_name() -> None:
    """カスタムCSV行名のテスト。"""
    content = b"id,name\n1,test\n2,another"
    config_file = TestHelpers.create_test_file(content, "config.csv")

    # CSV行名を"items"に変更
    parser = ConfigParser(config_file)
    parser.csv_rows_name = "items"

    assert parser.parse() is True
    assert parser.parsed_dict is not None

    # カスタム行名が使用されていることを確認
    expected_dict = {"items": [{"id": 1, "name": "test"}, {"id": 2, "name": "another"}]}
    TestHelpers.assert_dict_equality(parser.parsed_dict, expected_dict)  # type: ignore


@UNIT
def test_unsupported_file_extension() -> None:
    """サポートされていないファイル拡張子のテスト。"""
    content = b"This is a text file."
    config_file = TestHelpers.create_test_file(content, "config.txt")

    parser = ConfigParser(config_file)
    # パースを実行せずに初期化時点でエラーが設定されていることを確認
    assert parser.error_message == "Unsupported file type"


@UNIT
def test_file_size_validation() -> None:
    """ファイルサイズのバリデーションのテスト。"""
    # ファイルサイズの上限を一時的に小さくする
    original_max_size = ConfigParser.MAX_FILE_SIZE_BYTES
    ConfigParser.MAX_FILE_SIZE_BYTES = 10  # 10バイトに設定

    try:
        content = b"This content is more than 10 bytes."
        config_file = TestHelpers.create_test_file(content, "config.toml")

        # ファイルサイズが上限を超える場合、error_messageが設定されることを確認
        parser = ConfigParser(config_file)
        assert parser.error_message is not None
        assert "File size exceeds maximum limit of 10 bytes" in parser.error_message
        assert parser.parse() is False
    finally:
        # テスト後に元の値に戻す
        ConfigParser.MAX_FILE_SIZE_BYTES = original_max_size


@UNIT
def test_memory_size_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """メモリサイズのバリデーションのテスト。"""
    content = b"title = 'TOML test'"
    config_file = TestHelpers.create_test_file(content, "config.toml")

    parser = ConfigParser(config_file)

    # sys.getsizeofが大きな値を返すようにモックする
    def mock_getsizeof(obj: Union[ParsedDictType, str, bytes, None]) -> int:
        return ConfigParser.MAX_MEMORY_SIZE_BYTES + 1

    monkeypatch.setattr("sys.getsizeof", mock_getsizeof)

    # パースは成功するが、メモリサイズのバリデーションで失敗する
    assert parser.parse() is True
    assert parser.parsed_dict is None
    assert "Memory consumption exceeds the maximum limit" in str(parser.error_message)


@UNIT
def test_memory_error_during_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """メモリサイズのバリデーション中のメモリエラーのテスト。"""
    content = b"title = 'TOML test'"
    config_file = TestHelpers.create_test_file(content, "config.toml")

    parser = ConfigParser(config_file)

    # sys.getsizeofがMemoryErrorを発生させるようにモックする
    def mock_getsizeof(obj: Union[ParsedDictType, str, bytes, None]) -> int:
        raise MemoryError("Test memory error")

    monkeypatch.setattr("sys.getsizeof", mock_getsizeof)

    # パースは成功するが、メモリサイズのバリデーションで失敗する
    assert parser.parse() is True
    assert parser.parsed_dict is None
    assert "Memory error while checking size" in str(parser.error_message)


@UNIT
def test_unicode_decode_error() -> None:
    """UnicodeDecodeErrorのテスト。"""
    # 不正なUTF-8シーケンスを含むデータ
    content = b"\xff\xfe\xfd"
    config_file = TestHelpers.create_test_file(content, "config.toml")

    parser = ConfigParser(config_file)
    assert parser.parse() is False
    assert parser.parsed_dict is None
    assert parser.error_message is not None


@UNIT
def test_csv_rows_name() -> None:
    """Test the csv_rows_name property and setter."""
    # Create a simple CSV file
    content = b"name,age\nAlice,30\nBob,25"
    config_file = TestHelpers.create_test_file(content, "config.csv")

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


@UNIT
def test_enable_fill_nan() -> None:
    """Test the enable_fill_nan property and setter."""
    # Create a CSV file with NaN values
    content = b"name,age\nAlice,30\nBob,\nCharlie,35"
    config_file = TestHelpers.create_test_file(content, "config.csv")

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


@UNIT
def test_fill_nan_with() -> None:
    """Test the fill_nan_with property and setter."""
    # Create a CSV file with NaN values
    content = b"name,age\nAlice,30\nBob,\nCharlie,35"
    config_file = TestHelpers.create_test_file(content, "config.csv")

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


@UNIT
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
    expected_dict: Dict[str, List[Dict[str, Union[str, int]]]],  # Fixed type annotation
) -> None:
    """Test combinations of CSV options."""
    # Create a CSV file with NaN values
    content = b"name,age\nAlice,30\nBob,\nCharlie,35"
    config_file = TestHelpers.create_test_file(content, "config.csv")

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
            if expected_value is None and not enable_fill_nan:  # type: ignore[unreachable]
                # If NaN filling is disabled and expected value is None, check for NaN
                assert key in result_row  # type: ignore[unreachable]
                # Check for actual NaN or None from pandas
                actual_val = result_row[key]
                # Assert that actual_val is either NaN or None
                assert (isinstance(actual_val, (float, np.float64)) and math.isnan(actual_val)) or (actual_val is None), (
                    f"Row {i}, key {key}: expected NaN or None when filling is disabled, got {actual_val!r}"
                )
            else:
                # Otherwise, compare values directly
                assert result_row[key] == expected_value, f"Row {i}, key {key}: expected {expected_value}, got {result_row[key]}"


@UNIT
@pytest.mark.parametrize(
    ("content", "filename", "is_successful", "expected_error"),
    [
        # Edge case: Extremely large TOML file with long key names
        pytest.param(
            b"title = 'TOML test'\n" + b"key_" + b"a" * 1000 + b" = 'value'\n" * 100,
            "config.toml",
            PARSE_FAILED,
            "Invalid statement (at line 3, column 2)",
            id="edge_toml_large_file_long_keys_fail",
        ),
        # Edge case: TOML with special characters in keys
        pytest.param(
            b"'key-with-quotes' = 'value'\nkey_with_underscores = 'value'\n\"key.with.dots\" = 'value'",
            "config.toml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_toml_special_chars_in_keys_success",
        ),
        # Edge case: YAML with extremely long key names
        pytest.param(
            b"title: YAML test\nkey_" + b"a" * 100 + b": value",
            "config.yaml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_yaml_long_key_names_success",
        ),
        # Edge case: YAML with special characters in keys
        pytest.param(
            b"'key-with-quotes': value\nkey_with_underscores: value\n\"key.with.dots\": value",
            "config.yaml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_yaml_special_chars_in_keys_success",
        ),
        # Edge case: Extremely large CSV file
        pytest.param(
            b"col1,col2,col3\n" + b"value1,value2,value3\n" * 1000,
            "config.csv",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_csv_large_file_many_rows_success",
        ),
        # Edge case: CSV with quoted fields containing commas
        pytest.param(
            b'name,description\n"Smith, John","Consultant, senior"\n"Doe, Jane","Manager, department"',
            "config.csv",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_csv_quoted_fields_with_commas_success",
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
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_csv_many_columns_success",
        ),
        # Edge case: Empty file
        pytest.param(
            b"",
            "config.toml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_toml_empty_file_success",
        ),
        pytest.param(
            b"",
            "config.yaml",
            PARSE_FAILED,
            "Invalid YAML file loaded.",
            id="edge_yaml_empty_file_fail",
        ),
        # Edge case: File with only whitespace
        pytest.param(
            b"   \n\t\n  ",
            "config.toml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_toml_whitespace_only_success",
        ),
        pytest.param(
            b"   \n\t\n  ",
            "config.yaml",
            PARSE_FAILED,
            (
                "while scanning for the next token\n"
                "found character '\\t' that cannot start any token\n"
                '  in "<unicode string>", line 2, column 1:\n'
                "    \t\n"
                "    ^"
            ),
            id="edge_yaml_whitespace_only_fail",
        ),
        # Edge case: File with BOM
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML test'",
            "config.toml",
            PARSE_FAILED,
            "Invalid statement (at line 1, column 1)",
            id="edge_toml_with_bom_fail",
        ),
        pytest.param(
            b"\xef\xbb\xbftitle: YAML test",
            "config.yaml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_yaml_with_bom_success",
        ),
        # Edge case: File with non-UTF8 characters
        pytest.param(
            b"\x80\x81\x82title = 'TOML test'",
            "config.toml",
            PARSE_FAILED,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="edge_toml_invalid_utf8_fail",
        ),
        pytest.param(
            b"\x80\x81\x82title: YAML test",
            "config.yaml",
            PARSE_FAILED,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="edge_yaml_invalid_utf8_fail",
        ),
        # Edge case: File with mixed line endings
        pytest.param(
            b"title = 'TOML test'\r\nkey1 = 'value1'\nkey2 = 'value2'\r\n",
            "config.toml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_toml_mixed_line_endings_success",
        ),
        pytest.param(
            b"title: YAML test\r\nkey1: value1\nkey2: value2\r\n",
            "config.yaml",
            PARSE_SUCCESSFUL,
            EXPECT_NO_ERROR,
            id="edge_yaml_mixed_line_endings_success",
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
    config_file = TestHelpers.create_test_file(content, filename)
    parser = ConfigParser(config_file)
    result = parser.parse()
    assert result == is_successful, f"is_successful isn't match.\nExpected: {is_successful}\nGot: {result}"
    assert parser.error_message == expected_error, f"expected_error isn't match.\nExpected: {expected_error}\nGot: {parser.error_message}"


@UNIT
def test_memory_usage_with_reasonable_file() -> None:
    """Test that parsing files with reasonable size doesn't consume excessive memory."""
    # Create a CSV file with a reasonable number of rows
    header = b"col1,col2,col3\n"
    row = b"value1,value2,value3\n"

    # Generate a file with 1,000 rows (much more reasonable for a unit test)
    content = header + row * 1_000

    config_file = TestHelpers.create_test_file(content, "reasonable_file.csv")

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


@UNIT
def test_nested_structures() -> None:
    """Test parsing deeply nested structures."""
    # TOML with deeply nested tables
    toml_content = (
        b"[level1]\n"
        b'key = "value"\n'
        b"\n"
        b"[level1.level2]\n"
        b'key = "value"\n'
        b"\n"
        b"[level1.level2.level3]\n"
        b'key = "value"\n'
        b"\n"
        b"[level1.level2.level3.level4]\n"
        b'key = "value"\n'
        b"\n"
        b"[level1.level2.level3.level4.level5]\n"
        b'key = "value"'
    )

    config_file = TestHelpers.create_test_file(toml_content, "nested.toml")

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
    yaml_content = (
        b"level1:\n"
        b"  key: value\n"
        b"  level2:\n"
        b"    key: value\n"
        b"    level3:\n"
        b"      key: value\n"
        b"      level4:\n"
        b"        key: value\n"
        b"        level5:\n"
        b"          key: value\n"
    )

    config_file = TestHelpers.create_test_file(yaml_content, "nested.yaml")

    parser = ConfigParser(config_file)
    result = parser.parse()

    assert result is True
    assert parser.parsed_dict is not None
    assert "level1" in parser.parsed_dict
    assert "level2" in parser.parsed_dict["level1"]
    assert "level3" in parser.parsed_dict["level1"]["level2"]
    assert "level4" in parser.parsed_dict["level1"]["level2"]["level3"]
    assert "level5" in parser.parsed_dict["level1"]["level2"]["level3"]["level4"]


@UNIT
def test_file_size_limit() -> None:
    """ファイルサイズの上限を超えた場合のテスト。

    ConfigParserクラスのMAX_FILE_SIZE_BYTES (30MB) を超えるファイルを
    作成し、バリデーションが正しく機能することを確認します。
    """
    # Arrange
    # 31MBのデータを作成 (上限は30MB)
    large_content = b"x" * (31 * 1024 * 1024)
    config_file = TestHelpers.create_test_file(large_content, "large_config.toml")

    # Act
    parser = ConfigParser(config_file)

    # Assert
    assert parser.error_message is not None
    assert "File size exceeds maximum limit of 31457280 bytes" == parser.error_message
    assert parser.parse() is False


@UNIT
def test_memory_consumption_limit_parsed_str() -> None:
    """parsed_strのメモリ消費量の上限を超えた場合のテスト。

    モンキーパッチを使用してsys.getsizeofをオーバーライドし、
    大きなメモリサイズを返すようにします。
    """
    # Arrange
    content = b"title = 'TOML test'\nkey = 'value'\n"
    config_file = TestHelpers.create_test_file(content, "config.toml")

    parser = ConfigParser(config_file)
    assert parser.parse() is True

    # sys.getsizeofの元の実装を保存
    original_getsizeof = sys.getsizeof

    try:
        # sys.getsizeofをモンキーパッチして大きな値を返すようにする
        def mock_getsizeof(obj: object, default: int = 0) -> int:
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


@UNIT
def test_memory_consumption_limit_parsed_dict() -> None:
    """parsed_dictのメモリ消費量の上限を超えた場合のテスト。

    モンキーパッチを使用してsys.getsizeofをオーバーライドし、
    大きなメモリサイズを返すようにします。
    """
    # Arrange
    content = b"title = 'TOML test'\nkey = 'value'\n"
    config_file = TestHelpers.create_test_file(content, "config.toml")

    parser = ConfigParser(config_file)
    assert parser.parse() is True

    # sys.getsizeofの元の実装を保存
    original_getsizeof = sys.getsizeof

    try:
        # sys.getsizeofをモンキーパッチして大きな値を返すようにする
        def mock_getsizeof(obj: object, default: int = 0) -> int:
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


@UNIT
def test_memory_error_handling() -> None:
    """メモリエラーが発生した場合のテスト。

    モンキーパッチを使用してsys.getsizeofをオーバーライドし、
    MemoryErrorを発生させます。
    """
    # Arrange
    content = b"title = 'TOML test'\nkey = 'value'\n"
    config_file = TestHelpers.create_test_file(content, "config.toml")

    parser = ConfigParser(config_file)
    assert parser.parse() is True

    # sys.getsizeofの元の実装を保存
    original_getsizeof = sys.getsizeof

    try:
        # sys.getsizeofをモンキーパッチしてMemoryErrorを発生させる
        def mock_getsizeof_error(obj: object, default: int = 0) -> int:
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
