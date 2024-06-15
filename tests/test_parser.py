from datetime import date
from io import BytesIO
from typing import Any, Dict, Optional

import pytest

from features.config_parser import GhostwriterParser


@pytest.mark.unit()
@pytest.mark.parametrize(
    ("content", "filename", "is_successful", "expected_dict", "expected_str", "expected_error"),
    [
        # Test case for tomllib module on success
        pytest.param(b"title = 'TOML test'", "config.toml", True, {"title": "TOML test"}, "{'title': 'TOML test'}", None),
        pytest.param(b"date = 2024-04-01", "config.toml", True, {"date": date(2024, 4, 1)}, "{'date': datetime.date(2024, 4, 1)}", None),
        pytest.param(
            b"fruits = ['apple', 'orange', 'apple']",
            "config.toml",
            True,
            {"fruits": ["apple", "orange", "apple"]},
            "{'fruits': ['apple', 'orange', 'apple']}",
            None,
        ),
        pytest.param(
            b"nested_array = [[1, 2], [3, 4, 5]]",
            "config.toml",
            True,
            {"nested_array": [[1, 2], [3, 4, 5]]},
            "{'nested_array': [[1, 2], [3, 4, 5]]}",
            None,
        ),
        # Test case for pyyaml module on success
        pytest.param(b"title: YAML test", "config.yaml", True, {"title": "YAML test"}, "{'title': 'YAML test'}", None),
        pytest.param(
            b"title: YAML test # comment",
            "config.yaml",
            True,
            {"title": "YAML test"},
            "{'title': 'YAML test'}",
            None,
        ),
        pytest.param(
            b"date: 2024-04-01",
            "config.yaml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
        ),
        pytest.param(b"title: YAML test", "config.yml", True, {"title": "YAML test"}, "{'title': 'YAML test'}", None),
        pytest.param(
            b"date: 2024-04-01",
            "config.yml",
            True,
            {"date": date(2024, 4, 1)},
            "{'date': datetime.date(2024, 4, 1)}",
            None,
        ),
        # Test cases for load_config_file function on failed
        pytest.param(b"unsupported content", "config.txt", False, None, "None", "Unsupported file type"),
        pytest.param(b"unsupported content", "config", False, None, "None", "Unsupported file type"),
        # Test case for tomllib module on failed
        pytest.param(b"\x00\x01\x02\x03\x04", "config.toml", False, None, "None", "Invalid statement"),
        pytest.param(b"\x80\x81\x82\x83", "config.toml", False, None, "None", "invalid start byte"),
        pytest.param(b"title 'TOML test'", "config.toml", False, None, "None", "after a key in a key/value pair (at line 1, column 7)"),
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
        ),
        pytest.param(b"date = 2024-04-00", "config.toml", False, None, "None", "Expected newline or end of document after a statement "),
        # Test case for pyyaml module　 on failed
        pytest.param(
            b"\x00\x01\x02\x03\x04", "config.yaml", False, None, "None", "unacceptable character #x0000: special characters are not allowed"
        ),
        pytest.param(b"\x80\x81\x82\x83", "config.yaml", False, None, "None", "invalid start byte"),
        pytest.param(b"\x80\x81\x82\x83", "config.yml", False, None, "None", "invalid start byte"),
        pytest.param(b"title = 'YAML test'", "config.yaml", False, None, "None", "Invalid YAML file loaded."),
        pytest.param(b"title: title: YAML test", "config.yaml", False, None, "None", "mapping values are not allowed here"),
        pytest.param(b"title: title: YAML test", "config.yml", False, None, "None", "mapping values are not allowed here"),
        pytest.param(b"date: 2024-04-00", "config.yaml", False, None, "None", "day is out of range for month"),
        pytest.param(b"date: 2024-04-00", "config.yml", False, None, "None", "day is out of range for month"),
        pytest.param(
            b"key: @unexpected_character",
            "config.yaml",
            False,
            None,
            "None",
            "while scanning for the next token\nfound character",
        ),
        pytest.param(
            b"key: @unexpected_character",
            "config.yml",
            False,
            None,
            "None",
            "while scanning for the next token\nfound character",
        ),
        pytest.param(
            b'key1: !!binary "not a valid base64 string"',
            "config.yaml",
            False,
            None,
            "None",
            "failed to decode base64 data: Invalid base64-encoded",
        ),
        pytest.param(
            b'key1: !!binary "not a valid base64 string"',
            "config.yml",
            False,
            None,
            "None",
            "failed to decode base64 data: Invalid base64-encoded",
        ),
        pytest.param(b"!!invalidTag key1: value1", "config.yaml", False, None, "None", "could not determine a constructor for the tag"),
        pytest.param(b"title: [", "config.yaml", False, None, "None", "while parsing a flow node\nexpected the node content"),
    ],
)
def test_parse(
    content: bytes,
    filename: str,
    is_successful: bool,
    expected_dict: Optional[Dict[str, Any]],
    expected_str: str,
    expected_error: Optional[str],
) -> None:
    """Test parser."""

    config_file = BytesIO(content)
    config_file.name = filename

    parser = GhostwriterParser()
    assert parser.load_config_file(config_file).parse() == is_successful
    assert parser.parsed_dict == expected_dict
    assert parser.parsed_str == expected_str
    if expected_error is None:
        assert parser.error_message is None
    else:
        assert expected_error in str(parser.error_message)
