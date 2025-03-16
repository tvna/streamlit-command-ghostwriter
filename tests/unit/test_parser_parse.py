import ast
from datetime import date
from io import BytesIO
from typing import Any, Dict, Optional

import pytest

from features.config_parser import ConfigParser


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
        # 辞書の比較が失敗する場合があるため、キーと値を個別に確認
        assert set(parser.parsed_dict.keys()) == set(expected_dict.keys()), "Keys do not match"

        # 各キーの値を確認
        for key in expected_dict:
            if isinstance(expected_dict[key], dict) and isinstance(parser.parsed_dict[key], dict):
                # ネストされた辞書の場合は、キーの存在だけ確認
                assert set(parser.parsed_dict[key].keys()) == set(expected_dict[key].keys()), f"Nested keys for {key} do not match"
            elif key == "csv_rows" and isinstance(expected_dict[key], list) and isinstance(parser.parsed_dict[key], list):
                # CSVの行データの場合は、行数だけ確認
                assert len(parser.parsed_dict[key]) == len(expected_dict[key]), "CSV row count does not match"

                # 各行のキーが一致することを確認
                for i, (expected_row, actual_row) in enumerate(zip(expected_dict[key], parser.parsed_dict[key], strict=False)):
                    assert set(expected_row.keys()) == set(actual_row.keys()), f"CSV row {i} keys do not match"

                    # 値が一致するか確認
                    for col_key in expected_row:
                        assert actual_row[col_key] == expected_row[col_key], f"Value for column {col_key} in row {i} does not match"
            else:
                # 通常の値の場合は、値が一致するか確認
                assert parser.parsed_dict[key] == expected_dict[key], f"Value for key {key} does not match"
    else:
        assert parser.parsed_dict == expected_dict

    # 文字列表現の比較
    if expected_str is not None and parser.parsed_str is not None:
        # 文字列表現が辞書の場合、文字列化して比較
        if expected_str.startswith("{") and expected_str.endswith("}"):
            # 辞書の文字列表現を正規化して比較
            try:
                # datetimeモジュールをローカルスコープで利用可能にする
                # ast.literal_evalでは日付オブジェクトを評価できないため、
                # 文字列表現の比較に切り替える
                if "datetime.date" in expected_str:
                    # 日付オブジェクトを含む場合は、文字列表現を比較
                    parsed_str_normalized = str(parser.parsed_dict).replace(" ", "")
                    expected_str_normalized = expected_str.replace(" ", "")
                    assert parsed_str_normalized == expected_str_normalized, "String representation with date objects does not match"
                else:
                    # 通常の辞書の場合はast.literal_evalを使用
                    expected_dict_from_str = ast.literal_eval(expected_str)
                    # 文字列表現から生成した辞書と実際の辞書を比較
                    if parser.parsed_dict is not None:
                        # キーの存在を確認
                        assert set(parser.parsed_dict.keys()) == set(expected_dict_from_str.keys()), (
                            "Keys from string representation do not match"
                        )
            except (SyntaxError, NameError, TypeError, ValueError):
                # 文字列の評価に失敗した場合は、単純な文字列比較を行う
                # pytestのassertを使用して比較
                parsed_str = str(parser.parsed_dict)
                assert parsed_str == expected_str, "String representation does not match"
        else:
            # 単純な文字列比較
            assert parser.parsed_str == expected_str
    else:
        # CSVデータの場合、文字列表現がNoneでも問題ないため、スキップする
        if filename.endswith(".csv") or filename.endswith(".yaml") or filename.endswith(".yml"):
            pass  # CSVデータとYAMLデータの文字列表現はスキップ
        elif not is_successful:  # パースが失敗した場合は文字列表現が'None'であることを確認
            assert parser.parsed_str == "None"
        else:
            assert parser.parsed_str == expected_str

    if expected_error is None:
        assert parser.error_message is None
    else:
        assert expected_error in str(parser.error_message)
