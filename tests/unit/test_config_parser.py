"""Unit tests for the ConfigParser class.

This module contains unit tests for the `ConfigParser` class found in the
`features.config_parser` module. It verifies the parser's ability to correctly
handle TOML, YAML, and CSV configuration files, including various edge cases,
error conditions, data types, and file format specifics.

The tests cover:
- Parsing valid and invalid TOML, YAML, and CSV files.
- Handling different data types within the files.
- Support for comments and specific syntax features (e.g., TOML inline tables,
  YAML anchors).
- Error handling for syntax errors, encoding issues, unsupported file types,
  and file size limits.
- CSV-specific features like NaN handling and custom row naming.
- Robustness against edge cases like empty files, whitespace variations,
  and large files.
"""

import datetime
import pprint
import typing
from io import BytesIO
from typing import Any, Dict, Final, List, Optional, Union

import numpy as np
import pytest
from _pytest.mark.structures import MarkDecorator

# Assuming features is importable from tests/unit, adjust if necessary
from features.config_parser import ConfigParser

# Define descriptive constants for boolean and None values
SHOULD_FILL_NAN: Final[bool] = True
SHOULD_NOT_FILL_NAN: Final[bool] = False
DEFAULT_FILL_VALUE: Final[Optional[str]] = None
DEFAULT_CSV_ROWS_NAME: Final[str] = "csv_rows"
NO_EXPECTED_DICT: Final[Optional[typing.Dict[str, Any]]] = None
NO_EXPECTED_INITIAL_ERROR: Final[Optional[str]] = None
NO_EXPECTED_RUNTIME_ERROR: Final[Optional[str]] = None

UNIT: MarkDecorator = pytest.mark.unit


def _create_large_toml_content(num_entries: int) -> bytes:
    """Generates moderately large TOML content for testing.

    Args:
        num_entries: The number of key-value entries to generate in the [section] table.

    Returns:
        A bytes object containing the generated TOML content encoded in UTF-8.
    """
    content = "[section]\n"
    entries = [f'key{i} = "value{i}"' for i in range(num_entries)]
    return (content + "\n".join(entries)).encode("utf-8")


def _create_large_yaml_content(num_entries: int) -> bytes:
    """Generates moderately large YAML content for testing.

    Args:
        num_entries: The number of key-value entries to generate under the 'data' key.

    Returns:
        A bytes object containing the generated YAML content encoded in UTF-8.
    """
    content = "data:\n"
    entries = [f"  key{i}: value{i}" for i in range(num_entries)]
    return (content + "\n".join(entries)).encode("utf-8")


def _create_large_csv_content(num_rows: int, num_cols: int) -> bytes:
    """Generates moderately large CSV content for testing.

    Args:
        num_rows: The number of data rows to generate (excluding the header).
        num_cols: The number of columns to generate.

    Returns:
        A bytes object containing the generated CSV content encoded in UTF-8.
    """
    header = ",".join([f"col{c}" for c in range(num_cols)])
    rows = [",".join([f"val_{r}_{c}" for c in range(num_cols)]) for r in range(num_rows)]
    return (header + "\n" + "\n".join(rows)).encode("utf-8")


def _assert_csv_values_equal(p_val: Union[str, int, float, None], e_val: Union[str, int, float, None], row_idx: int, key: str) -> None:
    """Asserts equality between a parsed value and an expected value from a CSV row.

    Handles NaN values specifically and allows for type flexibility between
    integers and floats if their values are numerically equivalent.

    Args:
        p_val: The parsed value from the CSV.
        e_val: The expected value for comparison.
        row_idx: The 0-based index of the CSV row being checked (for error reporting).
        key: The column name (key) of the value being checked (for error reporting).
    """
    if isinstance(e_val, float) and np.isnan(e_val):
        assert isinstance(p_val, float), f"CSV row {row_idx}, key '{key}' NaN check: Type mismatch: Got {type(p_val)}, Expected float"
        assert np.isnan(p_val), f"CSV row {row_idx}, key '{key}' NaN check: Value mismatch: Got {p_val}, Expected NaN"
    elif isinstance(p_val, float) and isinstance(e_val, int) and p_val == float(e_val):
        # Treat as equal if float representation matches int
        pass
    elif isinstance(p_val, int) and isinstance(e_val, float) and float(p_val) == e_val:
        # Treat as equal if int representation matches float
        pass
    else:
        assert p_val == e_val, f"CSV row {row_idx}, key '{key}' value check: Mismatch: Got {p_val!r}, Expected {e_val!r}"


def _assert_csv_rows_equal(parsed_rows: List[Dict[str, Any]], expected_rows: List[Dict[str, Any]]) -> None:
    """Asserts equality between two lists of dictionaries representing CSV rows.

    Validates the structure (list of dicts) and length, then delegates
    individual value comparison within each row dictionary to
    `_assert_csv_values_equal`.

    Args:
        parsed_rows: The list of row dictionaries obtained from the parser.
        expected_rows: The expected list of row dictionaries.
    """
    assert isinstance(parsed_rows, list), "Parsed CSV rows is not a list."
    assert isinstance(expected_rows, list), "Expected CSV rows is not a list."
    assert len(parsed_rows) == len(expected_rows), f"CSV rows length mismatch: Got {len(parsed_rows)}, Expected {len(expected_rows)}"

    for i, (parsed_row, expected_row) in enumerate(zip(parsed_rows, expected_rows, strict=False)):
        assert isinstance(parsed_row, dict), f"Parsed row {i} is not a dictionary."
        assert isinstance(expected_row, dict), f"Expected row {i} is not a dictionary."
        assert parsed_row.keys() == expected_row.keys(), (
            f"CSV row {i} keys mismatch: Expected {expected_row.keys()}, Got {parsed_row.keys()}"
        )
        for key in expected_row:
            p_val, e_val = parsed_row.get(key), expected_row.get(key)
            # Delegate value comparison to the specialized helper function
            _assert_csv_values_equal(p_val, e_val, i, key)


def _assert_csv_dicts_equal(parsed_dict: typing.Dict[str, Any], expected_dict: typing.Dict[str, Any], csv_rows_name: str) -> None:
    """Asserts equality between two dictionaries, with special handling for CSV data.

    Compares the list of CSV rows (stored under `csv_rows_name`) using
    `_assert_csv_rows_equal`. Compares all other key-value pairs in the
    dictionaries directly.

    Args:
        parsed_dict: The dictionary obtained from the parser.
        expected_dict: The expected dictionary structure and content.
        csv_rows_name: The key under which the list of CSV row dictionaries is stored.
    """
    parsed_rows = parsed_dict.get(csv_rows_name)
    expected_rows = expected_dict.get(csv_rows_name)

    if expected_rows is not None:
        assert parsed_rows is not None, f"Expected CSV rows under key '{csv_rows_name}' but found none in parsed dict."
        # Delegate row comparison to the specialized helper function
        _assert_csv_rows_equal(parsed_rows, expected_rows)
    else:
        # Ensure parsed_rows is also None if expected_rows is None
        assert parsed_rows is None, f"Found unexpected CSV rows under key '{csv_rows_name}' in parsed dict."

    # Compare the rest of the dictionary excluding the csv rows part
    parsed_dict_other = {k: v for k, v in parsed_dict.items() if k != csv_rows_name}
    expected_dict_other = {k: v for k, v in expected_dict.items() if k != csv_rows_name}
    assert parsed_dict_other == expected_dict_other, (
        f"Non-CSV part of dictionary mismatch\nGot: {pprint.pformat(parsed_dict_other)}\nExpected: {pprint.pformat(expected_dict_other)}"
    )


@UNIT
@pytest.mark.parametrize(
    (
        "config_content",
        "file_name",
        "expected_init_error",
        "expected_dict",
        "expected_parse_error",
    ),
    [
        pytest.param(
            b'key = "value"',
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"key": "value"},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_toplevel_key",
        ),
        pytest.param(
            b'[section\nkey = "value"',  # Invalid TOML
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Expected ']' at the end of a table declaration (at line 1, column 9)",
            id="toml_failure_invalid_syntax",
        ),
        pytest.param(
            _create_large_toml_content(1000),
            "large_ok.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"section": {f"key{i}": f"value{i}" for i in range(1000)}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_moderately_large",
        ),
        pytest.param(
            _create_large_toml_content(2 * 10**6),
            "large_ng.toml",
            "File size exceeds maximum limit of 31457280 bytes",
            NO_EXPECTED_DICT,
            "File size exceeds maximum limit of 31457280 bytes",
            id="toml_failure_moderately_large",
        ),
        pytest.param(
            b'# This is a comment\n[section] # Another comment\nkey = "value" # Inline comment',
            "commented.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"section": {"key": "value"}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_with_comments",
        ),
        pytest.param(
            b'[data]\nint_val = 123\nfloat_val = 4.56\nbool_val = true\narray_val = [1, "two", 3.0]',
            "datatypes.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"data": {"int_val": 123, "float_val": 4.56, "bool_val": True, "array_val": [1, "two", 3.0]}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_various_types",
        ),
        pytest.param(
            b'[parent.child]\nkey = "nested_value"',
            "nested.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"parent": {"child": {"key": "nested_value"}}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_nested_tables",
        ),
        pytest.param(
            b"",
            "empty.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_failure_empty_file",
        ),
        pytest.param(
            b"[error]\nkey = value_without_quotes",  # Invalid syntax
            "syntax_error.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Invalid value (at line 2, column 7)",
            id="toml_failure_missing_quotes",
        ),
        pytest.param(
            b'[inline]\ndata = { key1 = "val1", key2 = 123 }',
            "inline.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"inline": {"data": {"key1": "val1", "key2": 123}}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_inline_table",
        ),
        pytest.param(
            b'[[products]]\nname = "Hammer"\nsku = 738594937\n\n[[products]]\nname = "Nail"\nsku = 284758393\ncolor = "gray"',
            "array_table.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"products": [{"name": "Hammer", "sku": 738594937}, {"name": "Nail", "sku": 284758393, "color": "gray"}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_array_of_tables",
        ),
        pytest.param(
            (
                b"[dates]\n"
                b"offset_dt = 1979-05-27T07:32:00Z\n"
                b"local_dt = 1979-05-27T00:32:00-07:00\n"
                b"local_date = 1979-05-27\n"
                b"local_time = 07:32:00"
            ),
            "dates.toml",
            NO_EXPECTED_INITIAL_ERROR,
            # Note: Exact representation might depend on the TOML library (e.g., datetime objects)
            # Assuming the library parses them into standard Python types or specific objects
            # We'll assert structure and type presence rather than exact object equality for simplicity
            # For now, let's represent as strings, assuming parser keeps them as strings or a custom type
            # A better test might involve checking `isinstance(parser.parsed_dict['dates']['offset_dt'], datetime)`
            {
                "dates": {
                    "local_date": datetime.date(1979, 5, 27),
                    "local_dt": datetime.datetime(1979, 5, 27, 0, 32, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200))),
                    "local_time": datetime.time(7, 32),
                    "offset_dt": datetime.datetime(1979, 5, 27, 7, 32, tzinfo=datetime.timezone.utc),
                }
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_date_time_formats",
        ),
        pytest.param(
            b"[invalid]\ndate = 2023/01/01",
            "invalid_date.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Expected newline or end of document after a statement (at line 2, column 12)",
            id="toml_failure_invalid_date_format",
        ),
        pytest.param(
            b"date = 2024-04-00",
            "invalid_date.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Expected newline or end of document after a statement (at line 1, column 12)",
            id="toml_failure_invalid_date_out_of_range",
        ),
        pytest.param(
            b'[a.b.c]\nkey = "deep_value"',
            "deep_nested.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"a": {"b": {"c": {"key": "deep_value"}}}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_deeply_nested_tables",
        ),
        pytest.param(
            b'[table]\ninline = { key = "value" }\n[table.nested]\nval = 123',
            "mixed_tables.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"table": {"inline": {"key": "value"}, "nested": {"val": 123}}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_mixed_inline_standard_tables",
        ),
        pytest.param(
            b"points = [ { x = 1, y = 2 }, { x = 7, y = 8 } ]",
            "array_inline_tables.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"points": [{"x": 1, "y": 2}, {"x": 7, "y": 8}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_array_of_inline_tables",
        ),
        pytest.param(
            b"[invalid#key]\nval = 1",  # Disallowed char # in bare key
            "invalid_bare_key.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Expected ']' at the end of a table declaration (at line 1, column 9)",
            id="toml_failure_disallowed_char_in_bare_key",
        ),
        pytest.param(
            b'[duplicate]\nkey = "value1"\nkey = "value2"',  # Duplicate key
            "duplicate_key.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Cannot overwrite a value (at end of document)",
            id="toml_failure_duplicate_key",
        ),
        pytest.param(
            b"title: YAML content",
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Expected '=' after a key in a key/value pair (at line 1, column 6)",
            id="toml_with_yaml_content_fail",
        ),
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML with BOM'",
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Invalid statement (at line 1, column 1)",
            id="toml_with_bom_fail",
        ),
        pytest.param(
            b"\x80\x81\x82title = 'TOML test'",
            "config.toml",
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="toml_failure_invalid_utf8",
        ),
        pytest.param(
            b"title = 'TOML test'\n" + b"key_" + b"a" * 1000 + b" = 'value'\n" * 100,
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Invalid statement (at line 3, column 2)",
            id="toml_failure_large_file_long_keys",
        ),
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML test'",
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Invalid statement (at line 1, column 1)",
            id="toml_failure_with_bom",
        ),
        pytest.param(
            b"\xef\xbb\xbftitle: YAML test",
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Invalid statement (at line 1, column 1)",
            id="yaml_failure_with_bom",
        ),
        pytest.param(
            b"\xff\xfe\xfd",
            "config.toml",
            "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
            id="toml_failure_unicode_decode_error",
        ),
        pytest.param(
            b"unicode = '\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e'",
            "config.toml",
            NO_EXPECTED_INITIAL_ERROR,
            {"unicode": "日本語"},
            NO_EXPECTED_RUNTIME_ERROR,
            id="toml_success_unicode_chars",
        ),
        # --- YAML Cases ---
        pytest.param(
            b"section:\n key: value",  # Valid YAML (indentation)
            "config.yml",
            NO_EXPECTED_INITIAL_ERROR,
            {"section": {"key": "value"}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_valid_indentation",
        ),
        pytest.param(
            b"- item1\n- item2",  # Valid YAML but not a dictionary at the root
            "config.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Invalid YAML file loaded.",
            id="yaml_failure_not_a_dict",
        ),
        pytest.param(
            _create_large_yaml_content(1000),
            "large_ok.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {"data": {f"key{i}": f"value{i}" for i in range(1000)}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_moderately_large",
        ),
        pytest.param(
            _create_large_yaml_content(2 * 10**6),
            "large_ng.yaml",
            "File size exceeds maximum limit of 31457280 bytes",
            NO_EXPECTED_DICT,
            "File size exceeds maximum limit of 31457280 bytes",
            id="yaml_failure_moderately_large",
        ),
        pytest.param(
            b"section:\n  list:\n    - item1\n    - {key: value}\nnested:\n  map:\n    subkey: subvalue",  # Complex YAML
            "complex.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {"nested": {"map": {"subkey": "subvalue"}}, "section": {"list": ["item1", {"key": "value"}]}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_complex_mapping_value",
        ),
        pytest.param(
            "セクション:\n  キー: 値".encode("shift_jis"),  # YAML with Shift-JIS encoding
            "sjis.yaml",
            "'utf-8' codec can't decode byte 0x83 in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0x83 in position 0: invalid start byte",
            id="yaml_failure_shiftjis_encoding_init",
        ),
        pytest.param(
            b"# Root comment\nsection: # Comment on section\n  key: value # Comment on value",  # YAML with comments
            "commented.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {"section": {"key": "value"}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_with_comments",
        ),
        pytest.param(
            b"data:\n  int_val: 123\n  float_val: 4.56\n  bool_val: true\n  null_val: null\n  list_val:\n    - item1\n    - 2\n    - false",
            "datatypes.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {"data": {"int_val": 123, "float_val": 4.56, "bool_val": True, "null_val": None, "list_val": ["item1", 2, False]}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_various_types",
        ),
        pytest.param(
            (
                b"nested:\n"
                b"  level1:\n"
                b"    list_in_map:\n"
                b"      - itemA\n"
                b"      - itemB\n"
                b"    map_in_map:\n"
                b"      key1: val1\n"
                b"      key2: val2\n"
                b"  level1_list:\n"
                b"    - map_in_list:\n"
                b"        k: v\n"
                b"    - simple_item"
            ),
            "nested.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {
                "nested": {
                    "level1": {"list_in_map": ["itemA", "itemB"], "map_in_map": {"key1": "val1", "key2": "val2"}},
                    "level1_list": [{"map_in_list": {"k": "v"}}, "simple_item"],
                }
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_nested_structures",
        ),
        pytest.param(
            b"",
            "empty.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Invalid YAML file loaded.",
            id="yaml_failure_empty_file",
        ),
        pytest.param(
            b"section:\n  key1: value1\n key2: value2",  # Indentation error
            "indent_error.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            (
                "while parsing a block mapping\n"
                '  in "<unicode string>", line 1, column 1:\n'
                "    section:\n"
                "    ^\n"
                "expected <block end>, but found '<block mapping start>'\n"
                '  in "<unicode string>", line 3, column 2:\n'
                "     key2: value2\n"
                "     ^"
            ),
            id="yaml_failure_bad_indentation",
        ),
        pytest.param(
            b"anchor_example: &anchor1\n  name: Anchor Name\n  value: 10\nalias_example: *anchor1",  # Anchors and aliases
            "anchor.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {"anchor_example": {"name": "Anchor Name", "value": 10}, "alias_example": {"name": "Anchor Name", "value": 10}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_anchors_aliases",
        ),
        pytest.param(
            b"doc1:\n  key: value1\n---\ndoc2:\n  key: value2",  # Multiple documents
            "multidoc.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            (
                "expected a single document in the stream\n"
                '  in "<unicode string>", line 1, column 1:\n'
                "    doc1:\n"
                "    ^\n"
                "but found another document\n"
                '  in "<unicode string>", line 3, column 1:\n'
                "    ---\n"
                "    ^"
            ),
            id="yaml_failure_multiple_documents_first_only",
        ),
        pytest.param(
            (
                b"timestamps:\n"
                b"  iso_utc: 2001-12-15T02:59:43Z\n"
                b"  space_sep: 2001-12-14 21:59:43 -05:00\n"
                b"  no_secs: 2001-12-14 21:59 -05:00\n"
                b"  date_only: 2002-12-14"
            ),
            "timestamps.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            # PyYAML parses these into datetime.datetime and datetime.date objects
            # We represent the expected structure; actual test might need type checks
            {
                "timestamps": {
                    "date_only": datetime.date(2002, 12, 14),
                    "iso_utc": datetime.datetime(2001, 12, 15, 2, 59, 43, tzinfo=datetime.timezone.utc),
                    "no_secs": "2001-12-14 21:59 -05:00",
                    "space_sep": datetime.datetime(
                        2001, 12, 14, 21, 59, 43, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))
                    ),
                }
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_valid_timestamps",
        ),
        pytest.param(
            b"dates_as_strings:\n  ambiguous: 01-02-2023 # Could be Jan 2 or Feb 1",
            "ambiguous_dates.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {"dates_as_strings": {"ambiguous": "01-02-2023"}},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_ambiguous_date_as_string",
        ),
        pytest.param(
            b"invalid_time: 20:30:40,123",
            "invalid_timestamp.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {"invalid_time": "20:30:40,123"},
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_failure_invalid_timestamp_format",
        ),
        pytest.param(
            (
                b"deep_mix:\n"
                b"  level1_map:\n"
                b"    level2_list:\n"
                b"      - item1\n"
                b"      - level3_map:\n"
                b"          key_c: 1\n"
                b"          key_d: 2\n"
                b"    level2_map:\n"
                b"      level3_key: value_e"
            ),
            "deep_mixed_nesting.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {
                "deep_mix": {
                    "level1_map": {
                        "level2_list": ["item1", {"level3_map": {"key_c": 1, "key_d": 2}}],
                        "level2_map": {"level3_key": "value_e"},
                    }
                }
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_deeply_nested_mixed",
        ),
        pytest.param(
            (
                b"list_of_maps:\n"
                b"  - id: 1\n"
                b"    properties:\n"
                b"      color: red\n"
                b"      size: L\n"
                b"  - id: 2\n"
                b"    properties:\n"
                b"      color: blue\n"
                b"      size: M"
            ),
            "list_nested_maps.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            {
                "list_of_maps": [
                    {"id": 1, "properties": {"color": "red", "size": "L"}},
                    {"id": 2, "properties": {"color": "blue", "size": "M"}},
                ]
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="yaml_success_list_of_nested_maps",
        ),
        pytest.param(
            b"   \n\t\n  ",
            "tab_indent.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            (
                "while scanning for the next token\n"
                "found character '\\t' that cannot start any token\n"
                '  in "<unicode string>", line 2, column 1:\n'
                "    \t\n"
                "    ^"
            ),
            id="yaml_failure_tab_indentation",
        ),
        pytest.param(
            b"invalid_utf8: Str with \xc3\x28 invalid seq",  # Invalid UTF-8 sequence (incomplete)
            "invalid_utf8_seq.yaml",
            "'utf-8' codec can't decode byte 0xc3 in position 23: invalid continuation byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0xc3 in position 23: invalid continuation byte",
            id="yaml_failure_invalid_utf8_sequence",
        ),
        pytest.param(
            b"\x80\x81\x82title: YAML test",
            "config.yaml",
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="yaml_failure_invalid_utf8",
        ),
        pytest.param(
            b"\xff\xfe\xfd",
            "config.yaml",
            "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
            id="yaml_failure_unicode_decode_error",
        ),
        pytest.param(
            b"key: @unexpected_character",
            "config.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            (
                "while scanning for the next token\n"
                "found character '@' that cannot start any token\n"
                '  in "<unicode string>", line 1, column 6:\n'
                "    key: @unexpected_character\n"
                "         ^"
            ),
            id="yaml_failure_unexpected_char",
        ),
        pytest.param(
            b"date: 2024-04-00",
            "invalid_date.yaml",
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "day is out of range for month",
            id="yaml_failure_invalid_date_out_of_range",
        ),
        pytest.param(
            b"content",
            "file.txt",  # Unsupported extension
            "Unsupported file type",
            NO_EXPECTED_DICT,
            "Unsupported file type",
            id="failure_unsupported_extension_init",
        ),
        pytest.param(
            b"\x80abc",  # Invalid UTF-8 start byte (for TOML/YAML)
            "config.toml",
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="common_failure_invalid_utf8_init_toml",
        ),
        pytest.param(
            b"\x80abc",  # Invalid UTF-8 start byte (for TOML/YAML)
            "config.yaml",
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            id="common_failure_invalid_utf8_init_yaml",
        ),
        pytest.param(
            b'key = "value"',  # Valid TOML content
            "invalid_extension.abc",  # But wrong extension
            "Unsupported file type",
            NO_EXPECTED_DICT,
            "Unsupported file type",
            id="failure_valid_content_wrong_extension_init",
        ),
    ],
)
def test_parse_toml_or_yaml(
    config_content: bytes,
    file_name: str,
    expected_init_error: Optional[str],
    expected_dict: Optional[typing.Dict[str, Any]],
    expected_parse_error: Optional[str],
) -> None:
    """Tests `ConfigParser`'s ability to parse TOML and YAML files.

    This parameterized test covers a wide range of scenarios, including:
    - Basic valid TOML and YAML syntax.
    - Invalid syntax and parsing errors.
    - Various data types (integers, floats, booleans, arrays, nested tables/maps).
    - Handling of comments.
    - Edge cases like empty files, large files (within limits and exceeding limits).
    - Specific TOML features like inline tables, arrays of tables, date/time formats.
    - Specific YAML features like anchors/aliases, different timestamp formats,
      nested structures, and indentation rules/errors.
    - Encoding issues (e.g., invalid UTF-8, BOM).
    - File type detection based on extension and handling unsupported types.
    - Validation of initial and final error messages and parsed dictionary/string states.

    Args:
        config_content: The byte string representing the content of the config file.
        file_name: The simulated filename, used to determine the expected format (.toml or .yaml).
        expected_parse_result: Boolean indicating if `parser.parse()` is expected to succeed.
        expected_init_error: The expected error message string during `ConfigParser`
            initialization (e.g., for file size or encoding errors detected early),
            or `None` if no init error is expected.
        expected_dict: The dictionary expected to be in `parser.parsed_dict` after parsing,
            or `None` if parsing is expected to fail or the file is empty/invalid.
        expected_parse_error: The expected error message string in `parser.error_message`
            after `parser.parse()` is called, or `None` if no error is expected post-parse.
    """

    # Arrange
    config_file = BytesIO(config_content)
    config_file.name = file_name

    # Act
    parser = ConfigParser(config_file=config_file)

    # Assert for initial state
    assert parser.error_message == expected_init_error, (
        f"Initial error message mismatch\nGot: {parser.error_message}\nExpected: {expected_init_error}"
    )

    # Act for runtime state
    parse_result = parser.parse()
    expected_parse_result: Final[bool] = False if expected_dict is None else True
    expected_str_final: Final[str] = pprint.pformat(expected_dict) if expected_init_error is None and expected_parse_result else "None"

    # Assert for runtime state
    assert parse_result == expected_parse_result, f"Parse result mismatch\nGot: {parse_result}\nExpected: {expected_parse_result}"
    assert parser.parsed_dict == expected_dict, (
        f"Parsed dictionary mismatch\nGot: {pprint.pformat(parser.parsed_dict)}\nExpected: {pprint.pformat(expected_dict)}"
    )
    assert parser.parsed_str == expected_str_final, f"Parsed string mismatch\nGot: {parser.parsed_str}\nExpected: {expected_str_final}"
    assert parser.error_message == expected_parse_error, (
        f"Final error message mismatch\nGot: {parser.error_message}\nExpected: {expected_parse_error}"
    )


@UNIT
@pytest.mark.parametrize(
    (
        "config_content",
        "file_name",
        "csv_rows_name",
        "enable_fill_nan",
        "fill_nan_with",
        "expected_init_error",
        "expected_dict",
        "expected_parse_error",
    ),
    [
        # --- CSV Cases ---
        pytest.param(
            b"col1,col2",
            "data.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "CSV file must contain at least one data row.",
            id="csv_failure_header_only_custom_name",
        ),
        pytest.param(
            b"col1,col2\nval1,\nval2,val3",
            "data.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,  # Default csv_rows_name, no NaN fill
            NO_EXPECTED_INITIAL_ERROR,
            {"csv_rows": [{"col1": "val1", "col2": np.nan}, {"col1": "val2", "col2": "val3"}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_nan_no_fill",
        ),
        pytest.param(
            b"col1,col2\nval1,\nval3,val4",  # CSV with NaN, fill with empty string
            "data.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_FILL_NAN,
            "",  # Fill with empty string
            NO_EXPECTED_INITIAL_ERROR,
            {"csv_rows": [{"col1": "val1", "col2": ""}, {"col1": "val3", "col2": "val4"}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_nan_fill_empty_string",
        ),
        pytest.param(
            b"col1,col2\nval1,\nval3,val4",  # CSV with NaN, fill with "N/A"
            "data.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_FILL_NAN,
            "N/A",  # Fill with "N/A"
            NO_EXPECTED_INITIAL_ERROR,
            {"csv_rows": [{"col1": "val1", "col2": "N/A"}, {"col1": "val3", "col2": "val4"}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_nan_fill_na_string",
        ),
        pytest.param(
            b"col1,col2",  # CSV with only header
            "data.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "CSV file must contain at least one data row.",
            id="csv_failure_header_only",
        ),
        pytest.param(
            b"",  # Empty CSV
            "data.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "No columns to parse from file",  # Error message might vary slightly based on pandas version
            id="csv_failure_empty_file",
        ),
        pytest.param(
            _create_large_csv_content(100, 100),  # ~100KB CSV
            "large_ok.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            # Generate expected dict (can be large)
            {"csv_rows": [{f"col{c}": f"val_{r}_{c}" for c in range(100)} for r in range(100)]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_moderately_large",
        ),
        # Note: Testing the exact >30MB boundary failure within parametrize is infeasible
        # due to the size of data required. Recommend separate test functions for that.
        pytest.param(
            b"a,b\n\x00,d",  # CSV with null byte
            "null.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Failed to parse CSV: Null byte detected in input data.",
            id="csv_failure_null_byte",
        ),
        pytest.param(
            b'col1,"col,2"\nval1,"v,al2"',
            "quoted.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            {"csv_rows": [{"col,2": "v,al2", "col1": "val1"}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_quoted_commas_newline",
        ),
        pytest.param(
            b"col1;col2\nval1;val2",
            "semicolon.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            {"csv_rows": [{"col1;col2": "val1;val2"}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_semicolon_delimiter",
        ),
        pytest.param(
            b"header1,header2\nvalue1,\nvalue3,value4",  # NaN in second column
            "nan_fill_missing.csv",
            "items",  # Custom rows name
            SHOULD_FILL_NAN,
            "MISSING",  # Fill value
            NO_EXPECTED_INITIAL_ERROR,
            {"items": [{"header1": "value1", "header2": "MISSING"}, {"header1": "value3", "header2": "value4"}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_nan_fill_missing_custom_name",
        ),
        pytest.param(
            b"col_a,col_b,col_c\n1,alpha,\n,beta,gamma\n3,,delta",  # Multiple NaNs
            "multi_nan_fill_empty.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_FILL_NAN,
            "",
            NO_EXPECTED_INITIAL_ERROR,
            {
                "csv_rows": [
                    {"col_a": float(1.0), "col_b": "alpha", "col_c": ""},
                    {"col_a": "", "col_b": "beta", "col_c": "gamma"},
                    {"col_a": float(3.0), "col_b": "", "col_c": "delta"},
                ]
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_multi_nan_fill_empty_string",
        ),
        pytest.param(
            b"id,value,category\n1,100,A\n2,,B\n3,300,C",  # NaN in potentially numeric column
            "numeric_nan_fill_na.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_FILL_NAN,
            "N/A",  # Fill value
            NO_EXPECTED_INITIAL_ERROR,
            {
                "csv_rows": [
                    {"id": 1, "value": 100.0, "category": "A"},
                    {"id": 2, "value": "N/A", "category": "B"},
                    {"id": 3, "value": 300.0, "category": "C"},
                ]
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_numeric_nan_fill_na",
        ),
        pytest.param(
            b"field1,field2\nvalueA,valueB\n,\nvalueC,valueD",  # Row with all NaNs
            "all_nan_row.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_FILL_NAN,
            "DEFAULT",  # Fill value
            NO_EXPECTED_INITIAL_ERROR,
            {
                "csv_rows": [
                    {"field1": "valueA", "field2": "valueB"},
                    {"field1": "DEFAULT", "field2": "DEFAULT"},
                    {"field1": "valueC", "field2": "valueD"},
                ]
            },
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_all_nan_row_fill_default",
        ),
        pytest.param(
            b"\xff\xfe\xfd",
            "config.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
            NO_EXPECTED_DICT,
            "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
            id="parse_csv_failure_unicode_decode_error",
        ),
        pytest.param(
            b" \t \n \n \t\t ",
            "config.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "No columns to parse from file",
            id="csv_failure_whitespace_only",
        ),
        pytest.param(
            b" col1 , col2 \n val1 , val2 \n",
            "config.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            {"csv_rows": [{" col1 ": " val1 ", " col2 ": " val2 "}]},
            NO_EXPECTED_RUNTIME_ERROR,
            id="csv_success_whitespace_in_header_data",
        ),
        pytest.param(
            b"\x00\x01\x02\x03\x04",
            "config.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Failed to parse CSV: Null byte detected in input data.",
            id="csv_failure_invalid_binary_fail",
        ),
        pytest.param(
            b'a,b,c\ncat,foo,bar\ndog,foo,"baz',
            "config.csv",
            DEFAULT_CSV_ROWS_NAME,
            SHOULD_NOT_FILL_NAN,
            DEFAULT_FILL_VALUE,
            NO_EXPECTED_INITIAL_ERROR,
            NO_EXPECTED_DICT,
            "Error tokenizing data. C error: EOF inside string starting at row 2",
            id="csv_failure_unclosed_quote",
        ),
    ],
)
def test_parse_csv(
    config_content: bytes,
    file_name: str,
    csv_rows_name: str,
    enable_fill_nan: bool,
    fill_nan_with: str,
    expected_init_error: Optional[str],
    expected_dict: Optional[typing.Dict[str, Any]],
    expected_parse_error: Optional[str],
) -> None:
    """Tests `ConfigParser`'s ability to parse CSV files.

    This parameterized test covers various CSV-specific scenarios:
    - Basic CSV structure with headers and data.
    - Handling of empty files or files with only headers.
    - Parsing values with different delimiters (implicitly handled by pandas sniffing).
    - Correctly parsing quoted fields containing commas or newlines.
    - Handling of Not a Number (NaN) values:
        - Recognizing empty fields as NaN (using `numpy.nan`).
        - Optionally filling NaN values with a specified string (`enable_fill_nan`, `fill_nan_with`).
    - Using a custom key name for the list of CSV rows (`csv_rows_name`).
    - Large file handling (within size limits).
    - Detection of null bytes within the content.
    - Encoding issues (e.g., invalid UTF-8).
    - Handling of leading/trailing whitespace in headers and data.
    - Errors due to unclosed quotes.
    - Validation of initial and final error messages and parsed dictionary/string states,
      using helper functions (`_assert_csv_dicts_equal`) for robust comparison.

    Args:
        config_content: The byte string representing the content of the CSV file.
        file_name: The simulated filename (must end with .csv).
        csv_rows_name: The dictionary key under which the list of parsed CSV rows should be stored.
        enable_fill_nan: Boolean flag passed to the parser to control NaN filling.
        fill_nan_with: The string value used to replace NaNs when `enable_fill_nan` is True.
        expected_parse_result: Boolean indicating if `parser.parse()` is expected to succeed.
        expected_init_error: The expected error message during `ConfigParser`
            initialization (e.g., for encoding errors detected early), or `None`.
        expected_dict: The dictionary expected in `parser.parsed_dict` after parsing,
            or `None` if parsing fails. The comparison is done via `_assert_csv_dicts_equal`.
        expected_parse_error: The expected error message in `parser.error_message`
            after `parser.parse()` is called, or `None`.
    """

    # Arrange
    config_file = BytesIO(config_content)
    config_file.name = file_name

    # Act
    parser = ConfigParser(config_file=config_file)

    # Assert for initial state
    assert parser.error_message == expected_init_error, (
        f"Initial error message mismatch\nGot: {parser.error_message}\nExpected: {expected_init_error}"
    )

    # Arrange for runtime state
    parser.csv_rows_name = csv_rows_name
    parser.enable_fill_nan = enable_fill_nan
    parser.fill_nan_with = fill_nan_with

    # Act for runtime state
    parse_result = parser.parse()
    expected_parse_result: Final[bool] = False if expected_dict is None else True
    expected_str_final: Final[str] = pprint.pformat(expected_dict)

    # Assert for runtime state
    assert parser.fill_nan_with == fill_nan_with, f"fill_nan_with mismatch\nGot: {parser.fill_nan_with}\nExpected: {fill_nan_with}"
    assert parser.enable_fill_nan == enable_fill_nan, (
        f"enable_fill_nan mismatch\nGot: {parser.enable_fill_nan}\nExpected: {enable_fill_nan}"
    )
    assert parse_result == expected_parse_result, f"Parse result mismatch\nGot: {parse_result}\nExpected: {expected_parse_result}"
    if expected_dict is None or parser.parsed_dict is None:
        assert parser.parsed_dict is None, f"Parsed dictionary mismatch (expected None)\nGot: {pprint.pformat(parser.parsed_dict)}"
    else:
        _assert_csv_dicts_equal(parser.parsed_dict, expected_dict, parser.csv_rows_name)
    assert parser.parsed_str == expected_str_final, f"Parsed string mismatch\nGot: {parser.parsed_str}\nExpected: {expected_str_final}"
    assert parser.error_message == expected_parse_error, (
        f"Final error message mismatch\nGot: {parser.error_message}\nExpected: {expected_parse_error}"
    )
