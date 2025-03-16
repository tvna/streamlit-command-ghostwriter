from io import BytesIO
from typing import Optional

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
            "Invalid statement",
            id="Edge case: Extremely large TOML file with long key names",
        ),
        # Edge case: TOML with special characters in keys
        pytest.param(
            b"'key-with-quotes' = 'value'\nkey_with_underscores = 'value'\n\"key.with.dots\" = 'value'",
            "config.toml",
            True,
            None,
            id="Edge case: TOML with special characters in keys",
        ),
        # Edge case: YAML with extremely long key names
        pytest.param(
            b"title: YAML test\nkey_" + b"a" * 100 + b": value",
            "config.yaml",
            True,
            None,
            id="Edge case: YAML with extremely long key names",
        ),
        # Edge case: YAML with special characters in keys
        pytest.param(
            b"'key-with-quotes': value\nkey_with_underscores: value\n\"key.with.dots\": value",
            "config.yaml",
            True,
            None,
            id="Edge case: YAML with special characters in keys",
        ),
        # Edge case: Extremely large CSV file
        pytest.param(
            b"col1,col2,col3\n" + b"value1,value2,value3\n" * 1000,
            "config.csv",
            True,
            None,
            id="Edge case: Extremely large CSV file",
        ),
        # Edge case: CSV with quoted fields containing commas
        pytest.param(
            b'name,description\n"Smith, John","Consultant, senior"\n"Doe, Jane","Manager, department"',
            "config.csv",
            True,
            None,
            id="Edge case: CSV with quoted fields containing commas",
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
            id="Edge case: CSV with many columns",
        ),
        # Edge case: Empty file
        pytest.param(
            b"",
            "config.toml",
            True,
            None,
            id="Edge case: Empty TOML file",
        ),
        pytest.param(
            b"",
            "config.yaml",
            False,
            "Invalid YAML file loaded",
            id="Edge case: Empty YAML file",
        ),
        # Edge case: File with only whitespace
        pytest.param(
            b"   \n\t\n  ",
            "config.toml",
            True,
            None,
            id="Edge case: TOML file with only whitespace",
        ),
        pytest.param(
            b"   \n\t\n  ",
            "config.yaml",
            False,
            "while scanning for the next token",
            id="Edge case: YAML file with only whitespace",
        ),
        # Edge case: File with BOM
        pytest.param(
            b"\xef\xbb\xbftitle = 'TOML test'",
            "config.toml",
            False,
            "Invalid statement",
            id="Edge case: TOML file with BOM",
        ),
        pytest.param(
            b"\xef\xbb\xbftitle: YAML test",
            "config.yaml",
            True,
            None,
            id="Edge case: YAML file with BOM",
        ),
        # Edge case: File with non-UTF8 characters
        pytest.param(
            b"\x80\x81\x82title = 'TOML test'",
            "config.toml",
            False,
            "codec can't decode",
            id="Edge case: TOML file with non-UTF8 characters",
        ),
        pytest.param(
            b"\x80\x81\x82title: YAML test",
            "config.yaml",
            False,
            "invalid start byte",
            id="Edge case: YAML file with non-UTF8 characters",
        ),
        # Edge case: File with mixed line endings
        pytest.param(
            b"title = 'TOML test'\r\nkey1 = 'value1'\nkey2 = 'value2'\r\n",
            "config.toml",
            True,
            None,
            id="Edge case: TOML file with mixed line endings",
        ),
        pytest.param(
            b"title: YAML test\r\nkey1: value1\nkey2: value2\r\n",
            "config.yaml",
            True,
            None,
            id="Edge case: YAML file with mixed line endings",
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
        assert expected_error in str(parser.error_message)
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

    # Record memory usage before parsing
    import resource

    before_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Parse the file
    parser = ConfigParser(config_file)
    result = parser.parse()

    # Record memory usage after parsing
    after_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Verify parsing succeeded
    assert result is True

    # Check that memory usage didn't increase too dramatically
    # This is a rough check - the exact threshold depends on the system
    memory_increase_mb = (after_mem - before_mem) / 1024  # Convert KB to MB

    # Log the memory increase for debugging
    print(f"Memory increase: {memory_increase_mb:.2f} MB")

    # Adjust threshold based on observed memory usage
    # The actual memory usage can vary significantly between systems and Python implementations
    assert memory_increase_mb < 200, f"Memory usage increased by {memory_increase_mb:.2f} MB"


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
