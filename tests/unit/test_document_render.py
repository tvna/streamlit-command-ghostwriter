"""Template rendering and validation test module.

This module provides tests for the DocumentRender class, which is responsible for
template rendering and validation. The tests are divided into three main categories:

1. Initial Validation Tests
   - File size limits
   - Encoding validation
   - Syntax checking
   - Security (static analysis)

2. Runtime Validation Tests
   - Recursive structures
   - Division by zero
   - Memory usage monitoring

3. Validation Consistency Tests
   - Consistency between initial and runtime validation results
   - Error message consistency
   - Handling of various edge cases

4. Date and Time Formatting Tests
   - ISO 8601 date format handling (e.g. "2024-03-20T15:30:45")
   - Multilingual date format support (English and Japanese)
   - Various date/time pattern validations

These tests ensure the template engine operates securely and predictably under
various conditions, including malformed templates, security attacks, and edge cases.
"""

import typing
from io import BytesIO
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
)
from typing import (
    Any as AnyType,
)

import pytest
from _pytest.mark.structures import MarkDecorator

from features.document_render import (
    FORMAT_TYPE_COMPRESS,
    FORMAT_TYPE_COMPRESS_ALT,
    FORMAT_TYPE_KEEP,
    FORMAT_TYPE_KEEP_ALT,
    FORMAT_TYPE_REMOVE_ALL,
    MAX_FORMAT_TYPE,
    MIN_FORMAT_TYPE,
    DocumentRender,
)

STRICT_UNDEFINED: bool = True
NON_STRICT_UNDEFINED: bool = False
EXPECTED_INITIAL_NO_ERROR: Optional[str] = None
EXPECTED_RUNTIME_NO_ERROR: Optional[str] = None
EXPECTED_NO_CONTENT: Optional[str] = None


UNIT: MarkDecorator = pytest.mark.unit
SET_TIMEOUT: MarkDecorator = pytest.mark.timeout(10)


# --- Helper functions for deeply nested data ---
def _create_deeply_nested_list(depth: int) -> List[Any]:
    """Creates a nested list with the specified depth."""
    root: List[Any] = []
    current: List[Any] = root
    for _ in range(depth):
        new_list: List[Any] = []
        current.append(new_list)
        current = new_list
    return root


def _create_deeply_nested_dict(depth: int) -> Dict[str, Any]:
    """Creates a nested dictionary with the specified depth."""
    root: Dict[str, Any] = {}
    current: Dict[str, Any] = root
    for _ in range(depth):
        new_dict: Dict[str, Any] = {}
        current["next"] = new_dict
        current = new_dict
    return root


# --- Helper functions for circular data ---
def _create_circular_list() -> Dict[str, List[Any]]:
    """Creates a dictionary containing a list that references itself."""
    data = [1, 2]
    data.append(data)  # type: ignore[arg-type] # Intentionally creating circular ref
    return {"data": data}


def _create_circular_dict() -> Dict[str, Dict[Any, Any]]:
    """Creates a dictionary containing a dictionary that references itself."""
    data: Dict[str, Any] = {"a": 1}
    data["self"] = data  # Intentionally creating circular ref
    return {"data": data}


def _create_list_with_circular_dict() -> Dict[str, List[Any]]:
    """Creates a dictionary containing a list with a dictionary that references itself."""
    d: Dict[str, Any] = {}
    d["rec"] = d
    data = [1, d, 3]
    return {"data": data}


def _create_indirect_circular_list() -> Dict[str, List[Any]]:
    """Creates a dictionary containing an indirectly circular list."""
    l1: List[Any] = []
    l2: List[Any] = [l1]
    l1.append(l2)
    return {"data": l1}


def _create_indirect_circular_dict() -> Dict[str, Dict[str, Any]]:
    """Creates a dictionary containing an indirectly circular dictionary."""
    d1: Dict[str, Any] = {}
    d2: Dict[str, Any] = {"d1": d1}
    d1["d2"] = d2
    return {"data": d1}


@pytest.fixture
def create_template_file() -> Callable[[bytes, str], BytesIO]:
    """Fixture for creating template files for testing.

    Returns:
        Callable[[bytes, str], BytesIO]: A function that creates a template file
    """

    def _create_file(content: bytes, filename: str = "template.txt") -> BytesIO:
        file: BytesIO = BytesIO(content)
        file.name = filename
        return file

    return _create_file


@UNIT
@SET_TIMEOUT
@pytest.mark.parametrize(
    (
        "template_content",
        "format_type",
        "is_strict_undefined",
        "context",
        "expected_content",
        "expected_initial_error",
        "expected_runtime_error",
    ),
    [
        pytest.param(
            b"",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_filesize_empty_success_strict",
        ),
        pytest.param(
            b"a" * (30 * 1024 * 1024),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "a" * (30 * 1024 * 1024),
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_filesize_max_exact_strict",
        ),
        pytest.param(
            b"a" * (30 * 1024 * 1024 + 1),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            f"Template file size exceeds maximum limit of {30 * 1024 * 1024} bytes",
            f"Template file size exceeds maximum limit of {30 * 1024 * 1024} bytes",
            id="test_render_failure_filesize_max_exceeded_strict",
        ),
        pytest.param(
            b"\x80\x81\x82\x83",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template file contains invalid UTF-8 bytes",
            "Template file contains invalid UTF-8 bytes",
            id="test_render_failure_encoding_invalid_utf8_strict",
        ),
        pytest.param(
            b"\x00",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template file contains invalid binary data",
            "Template file contains invalid binary data",
            id="test_render_failure_encoding_null_byte_only_strict",
        ),
        pytest.param(
            b"Hello\x00World",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template file contains invalid binary data",
            "Template file contains invalid binary data",
            id="test_render_failure_encoding_null_byte_in_text_strict",
        ),
        pytest.param(
            b"Hello {{ name }!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            EXPECTED_NO_CONTENT,
            "Template syntax error: unexpected '}'",
            "Template syntax error: unexpected '}'",
            id="test_render_failure_syntax_error_unmatched_brace_strict",
        ),
        pytest.param(
            b"{% macro input() %}{% endmacro %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'macro' tag is not allowed",
            "Template security error: 'macro' tag is not allowed",
            id="test_render_failure_security_macro_tag_strict",
        ),
        pytest.param(
            b"{{ 10 / value }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"value": 0},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: division by zero",
            id="test_render_failure_division_by_zero_context_strict",
        ),
        pytest.param(
            b"{{ 10 / value }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"value": 0},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: division by zero",
            id="test_render_failure_division_by_zero_context_non_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_valid_context_unexpected_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_valid_context_unexpected_non_strict",
        ),
        pytest.param(
            b"Hello {{ undefined }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undefined' is undefined",
            id="test_render_failure_undefined_var_context_strict",
        ),
        pytest.param(
            b"Hello {{ undefined }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "Hello !",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_var_context_non_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_variable_basic_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_REMOVE_ALL,
            STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!\nGood bye World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_format_remove_all_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!\n\nGood bye World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_format_compress_alt_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_KEEP_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!\n\n\n  \nGood bye World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_format_keep_alt_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_COMPRESS,
            STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!\n\nGood bye World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_format_compress_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_KEEP,
            STRICT_UNDEFINED,
            {"name": "World"},
            "Hello World!\n\n\n  \nGood bye World!",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_format_keep_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "Hello !",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_var_non_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'name' is undefined",
            id="test_render_failure_undefined_var_strict",
        ),
        pytest.param(
            b"Hello {{ first_name }} {{ last_name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"first_name": "John"},
            "Hello John !",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_multiple_vars_partial_non_strict",
        ),
        pytest.param(
            b"Hello {{ first_name }} {{ last_name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"first_name": "John"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'last_name' is undefined",
            id="test_render_failure_multiple_vars_partial_strict",
        ),
        pytest.param(
            b"{% if undefined_var %}Show{% else %}Hide{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "Hide",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_in_condition_non_strict",
        ),
        pytest.param(
            b"{% if undefined_var %}Show{% else %}Hide{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undefined_var' is undefined",
            id="test_render_failure_undefined_in_condition_strict",
        ),
        pytest.param(
            b"{{ name if name is defined else 'Anonymous' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "Anonymous",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_defined_check_fallback_non_strict",
        ),
        pytest.param(
            b"{{ name if name is defined else 'Anonymous' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "Anonymous",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_defined_check_fallback_strict",
        ),
        pytest.param(
            b"{{ user.name }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_nested_undefined_non_strict",
        ),
        pytest.param(
            b"{{ user.name }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'user' is undefined",
            id="test_render_failure_nested_undefined_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            MIN_FORMAT_TYPE - 1,
            STRICT_UNDEFINED,
            {"name": "World"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Validation error: Input should be greater than or equal to 0 at 'format_type'",
            id="test_render_failure_invalid_format_type_below_min_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            MAX_FORMAT_TYPE + 1,
            STRICT_UNDEFINED,
            {"name": "World"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Validation error: Input should be less than or equal to 4 at 'format_type'",
            id="test_render_failure_invalid_format_type_above_max_strict",
        ),
        pytest.param(
            b"{{ 10 / value }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"value": 0},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: division by zero",
            id="test_render_failure_division_by_zero_strict",
        ),
        pytest.param(
            (
                b"Current Date: {{ current_date | date('%Y-%m-%d') }}\n"
                b"Last Updated: {{ last_updated | date('%Y-%m-%d %H:%M:%S') }}\n"
                b"Next Review: {{ next_review | date('%B %d, %Y') }}"
            ),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {
                "current_date": "2024-03-20",
                "last_updated": "2024-03-20T15:30:45",
                "next_review": "2024-06-20",
            },
            ("Current Date: 2024-03-20\nLast Updated: 2024-03-20 15:30:45\nNext Review: June 20, 2024"),
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_filter_date_strict",
        ),
        pytest.param(
            (
                b"Unix Timestamp: {{ unix_timestamp | date('%Y-%m-%d %H:%M:%S') }}\n"
                b"Millisecond Timestamp: {{ ms_timestamp | date('%Y-%m-%d %H:%M:%S.%f') }}\n"
                b"Formatted Time: {{ unix_timestamp | date('%H:%M') }}"
            ),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {
                "unix_timestamp": "2024-03-20T15:30:45",  # ISO 8601 format
                "ms_timestamp": "2024-03-20T15:30:45.123",  # ISO 8601 format with milliseconds
            },
            "Unix Timestamp: 2024-03-20 15:30:45\nMillisecond Timestamp: 2024-03-20 15:30:45.123000\nFormatted Time: 15:30",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_filter_timestamp_strict",
        ),
        pytest.param(
            b"Historic Date: {{ historic_date | date('%Y-%m-%d %H:%M:%S') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {
                "historic_date": "1969-01-01T00:00:00",  # ISO 8601形式
            },
            "Historic Date: 1969-01-01 00:00:00",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_filter_historic_date_strict",
        ),
        pytest.param(
            (
                b"ISO String: {{ iso_date | date('%d %b %Y') }}\n"
                b"ISO with TZ: {{ iso_with_tz | date('%Y-%m-%d %H:%M %Z') }}\n"
                b"Future Date: {{ future_date | date('%A, %B %d, %Y') }}"
            ),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {
                "iso_date": "2024-12-31T23:59:59",
                "iso_with_tz": "2024-06-15T12:30:45+09:00",
                "future_date": "2025-01-01T00:00:00",
            },
            "ISO String: 31 Dec 2024\nISO with TZ: 2024-06-15 12:30 UTC+09:00\nFuture Date: Wednesday, January 01, 2025",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_filter_iso_date_formats_strict",
        ),
        pytest.param(
            b"{{ invalid_date | date('%Y-%m-%d') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"invalid_date": "not-a-date"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: Invalid date format",
            id="test_render_failure_filter_invalid_date_strict",
        ),
        pytest.param(
            b"{{ date | date('%Y-%m-%d') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"date": None},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'NoneType' object has no attribute 'replace'",
            id="test_render_failure_filter_null_date_strict",
        ),
        pytest.param(
            b"{{ ''.__class__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted attribute '__class__' is forbidden.",
            "Template security error: Access to restricted attribute '__class__' is forbidden.",
            id="test_render_failure_security_injection_class_attr_strict",
        ),
        pytest.param(
            b"{{ ''.__class__.__mro__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted attribute '__mro__' is forbidden.",
            "Template security error: Access to restricted attribute '__mro__' is forbidden.",
            id="test_render_failure_security_injection_mro_attr_strict",
        ),
        pytest.param(
            b"{{ ''.__class__.__mro__[1].__subclasses__() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted attribute '__subclasses__' is forbidden.",
            "Template security error: Access to restricted attribute '__subclasses__' is forbidden.",
            id="test_render_failure_security_injection_subclasses_attr_strict",
        ),
        pytest.param(
            b"{{ getattr('', '__class__') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: Call to restricted function 'getattr()' is forbidden.",
            "Template security error: Call to restricted function 'getattr()' is forbidden.",
            id="test_render_failure_security_injection_getattr_call_strict",
        ),
        pytest.param(
            b"{{ self.__init__.__globals__['os'] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"self": object()},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted item 'os' is forbidden.",
            "Template security error: Access to restricted item 'os' is forbidden.",
            id="test_render_failure_security_injection_globals_item_strict",
        ),
        pytest.param(
            b"{% import 'os' as os %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'import' tag is not allowed",
            "Template security error: 'import' tag is not allowed",
            id="test_render_failure_security_injection_import_tag_strict",
        ),
        pytest.param(
            b"{% extends 'base.html' %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'extends' tag is not allowed",
            "Template security error: 'extends' tag is not allowed",
            id="test_render_failure_security_injection_extends_tag_strict",
        ),
        pytest.param(
            b"{{ eval('1+1') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"eval": eval},
            EXPECTED_NO_CONTENT,
            "Template security error: Call to restricted function 'eval()' is forbidden.",
            "Template security error: Call to restricted function 'eval()' is forbidden.",
            id="test_render_failure_security_injection_eval_call_strict",
        ),
        pytest.param(
            b"{{ exec('import os') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"exec": exec},
            EXPECTED_NO_CONTENT,
            "Template security error: Call to restricted function 'exec()' is forbidden.",
            "Template security error: Call to restricted function 'exec()' is forbidden.",
            id="test_render_failure_security_injection_exec_call_strict",
        ),
        pytest.param(
            b"{{ os.system('ls') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"os": __import__("os")},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'os' is forbidden.",
            "Template security error: Use of restricted variable 'os' is forbidden.",
            id="test_render_failure_security_injection_os_var_strict",
        ),
        pytest.param(
            b"{{ sys.modules }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"sys": __import__("sys")},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'sys' is forbidden.",
            "Template security error: Use of restricted variable 'sys' is forbidden.",
            id="test_render_failure_security_injection_sys_var_strict",
        ),
        pytest.param(
            b"{{ builtins.open('/etc/passwd').read() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"builtins": __import__("builtins")},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'builtins' is forbidden.",
            "Template security error: Use of restricted variable 'builtins' is forbidden.",
            id="test_render_failure_security_injection_builtins_var_strict",
        ),
        pytest.param(
            b"{{ setattr(obj, 'attr', 'value') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"setattr": setattr, "obj": object()},
            EXPECTED_NO_CONTENT,
            "Template security error: Call to restricted function 'setattr()' is forbidden.",
            "Template security error: Call to restricted function 'setattr()' is forbidden.",
            id="test_render_failure_security_injection_setattr_call_strict",
        ),
        pytest.param(
            b"{{ delattr(obj, 'attr') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"delattr": delattr, "obj": type("Dummy", (), {"attr": 1})()},
            EXPECTED_NO_CONTENT,
            "Template security error: Call to restricted function 'delattr()' is forbidden.",
            "Template security error: Call to restricted function 'delattr()' is forbidden.",
            id="test_render_failure_security_injection_delattr_call_strict",
        ),
        pytest.param(
            b"{{ locals() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"locals": locals},
            EXPECTED_NO_CONTENT,
            "Template security error: Call to restricted function 'locals()' is forbidden.",
            "Template security error: Call to restricted function 'locals()' is forbidden.",
            id="test_render_failure_security_injection_locals_call_strict",
        ),
        pytest.param(
            b"{{ config }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"config": {}},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'config' is forbidden.",
            "Template security error: Use of restricted variable 'config' is forbidden.",
            id="test_render_failure_security_injection_config_var_strict",
        ),
        pytest.param(
            b"{{ obj.__base__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"obj": "test"},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted attribute '__base__' is forbidden.",
            "Template security error: Access to restricted attribute '__base__' is forbidden.",
            id="test_render_failure_security_injection_base_attr_strict",
        ),
        pytest.param(
            b"{{ my_dict['os'] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"my_dict": {"os": "value"}},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted item 'os' is forbidden.",
            "Template security error: Access to restricted item 'os' is forbidden.",
            id="test_render_failure_security_injection_os_item_strict",
        ),
        pytest.param(
            b"{% set my_os = os %}{{ my_os }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"os": "fake_os"},
            EXPECTED_NO_CONTENT,
            "Template security error: Assignment of restricted variable 'os' is forbidden.",
            "Template security error: Assignment of restricted variable 'os' is forbidden.",
            id="test_render_failure_security_injection_os_assign_strict",
        ),
        pytest.param(
            b"{% set my_eval = eval %}{{ my_eval('1') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"eval": eval},
            EXPECTED_NO_CONTENT,
            "Template security error: Assignment of restricted variable 'eval' is forbidden.",
            "Template security error: Assignment of restricted variable 'eval' is forbidden.",
            id="test_render_failure_security_injection_eval_assign_strict",
        ),
        pytest.param(
            b"{% set d = {} %}{% do d.update({'self': d}) %}{{ d }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'do' tag is not allowed",
            "Template security error: 'do' tag is not allowed",
            id="test_render_failure_security_do_tag_recursive_dict_strict",
        ),
        pytest.param(
            b"{% set l = [[]] %}{% do l[0].append(l) %}{{ l }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'do' tag is not allowed",
            "Template security error: 'do' tag is not allowed",
            id="test_render_failure_security_do_tag_recursive_list_strict",
        ),
        pytest.param(
            b"{% set d = {} %}{% set l = [d] %}{% do d.update({'list': l}) %}{{ l }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'do' tag is not allowed",
            "Template security error: 'do' tag is not allowed",
            id="test_render_failure_security_do_tag_recursive_mixed_strict",
        ),
        pytest.param(
            (
                b"{% for i in range(3) %}\n"
                b"  {% for j in range(2) %}\n"
                b"    {% if i > 0 and j > 0 %}\n"
                b"      {{ i }} - {{ j }}: {{ data[i][j] if data and i < data|length and j < data[i]|length else 'N/A' }}\n"
                b"    {% else %}\n"
                b"      {{ i }} - {{ j }}: Start\n"
                b"    {% endif %}\n"
                b"  {% endfor %}\n"
                b"{% endfor %}"
            ),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"data": [[1, 2], [3, 4], [5, 6]]},
            (
                "\n      0 - 0: Start\n\n      0 - 1: Start\n\n      1 - 0: Start\n\n"
                "      1 - 1: 4\n\n      2 - 0: Start\n\n      2 - 1: 6\n\n"
            ),
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_logic_complex_loops_conditionals_strict",
        ),
        pytest.param(
            b"{{ undefined_var if undefined_var is defined else 'Default' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "Default",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_fallback_non_strict",
        ),
        pytest.param(
            b"{% for i in range(count) %}Line {{ i }}\n{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"count": 50},  # 1000から50に減らす
            "\n".join([f"Line {i}" for i in range(50)]) + "\n",  # Add trailing newline
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_many_lines_strict",
        ),
        pytest.param(
            "{{ emoji }} {{ japanese }}".encode("utf-8"),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"emoji": "😁😂🤣😃", "japanese": "こんにちは世界"},
            "😁😂🤣😃 こんにちは世界",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_unicode_strict",
        ),
        pytest.param(
            b"<html><body>{{ content | safe }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<h1>Title</h1><p>Paragraph with <b>bold</b> text</p>"},
            "<html><body>&lt;h1&gt;Title&lt;/h1&gt;&lt;p&gt;Paragraph with &lt;b&gt;bold&lt;/b&gt; text&lt;/p&gt;</body></html>",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_html_safe_filter_autoescaped_strict",
        ),
        pytest.param(
            b"<html><body>{{ content | safe }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<script>alert('XSS')</script>"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            (
                "Template runtime error: 1 validation error for HTMLContent\n"
                "content\n"
                "  Value error, HTML content contains potentially unsafe elements "
                "[type=value_error, input_value=\"<script>alert('XSS')</script>\", "
                "input_type=str]\n"
                "    For further information visit https://errors.pydantic.dev/2.11/v/value_error"
            ),
            id="test_render_failure_unsafe_html_strict",
        ),
        pytest.param(
            b"<html><body>{{ content }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<script>alert('XSS')</script>"},
            "<html><body>&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;</body></html>",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_html_autoescape_strict",
        ),
        pytest.param(
            (
                b"{% macro input(name, value='', type='text') -%}\n"
                b'    <input type="{{ type }}" name="{{ name }}" value="{{ value }}">\n'
                b"{%- endmacro %}\n\n"
                b"{{ input('username') }}\n"
                b"{{ input('password', type='password') }}"
            ),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'macro' tag is not allowed",
            "Template security error: 'macro' tag is not allowed",
            id="test_render_failure_security_macro_definition_strict",
        ),
        pytest.param(
            (
                b"{% macro input(name, value='', type='text') -%}\n"
                b'    <input type="{{ type }}" name="{{ name }}" value="{{ value }}">\n'
                b"{%- endmacro %}\n\n"
                b"{{ input('username') }}\n"
                b"{{ input('password', type='password') }}"
            ),
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'macro' tag is not allowed",
            "Template security error: 'macro' tag is not allowed",
            id="test_render_failure_security_macro_definition_non_strict",
        ),
        pytest.param(
            b"{%- call input('username') %}{% endcall %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'input' is undefined",
            id="test_render_failure_logic_call_tag_undefined_strict",
        ),
        pytest.param(
            b"{%- call input('username') %}{% endcall %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: sequence item 0: expected str instance, CustomUndefined found",
            id="test_render_failure_logic_call_tag_undefined_non_strict",
        ),
        pytest.param(
            b"{% set x = request.args %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"request": {"args": {"debug": "true"}}},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'request' is forbidden.",
            "Template security error: Use of restricted variable 'request' is forbidden.",
            id="test_render_failure_security_injection_request_var_strict",
        ),
        pytest.param(
            b"{% set x = request.args %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"request": {"args": {"debug": "true"}}},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'request' is forbidden.",
            "Template security error: Use of restricted variable 'request' is forbidden.",
            id="test_render_failure_security_injection_request_var_non_strict",
        ),
        pytest.param(
            b"{{ config.items() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"config": {"secret": "sensitive_data"}},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'config' is forbidden.",
            "Template security error: Use of restricted variable 'config' is forbidden.",
            id="test_render_failure_security_injection_config_items_strict",
        ),
        pytest.param(
            b"{{ config.items() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"config": {"secret": "sensitive_data"}},
            EXPECTED_NO_CONTENT,
            "Template security error: Use of restricted variable 'config' is forbidden.",
            "Template security error: Use of restricted variable 'config' is forbidden.",
            id="test_render_failure_security_injection_config_items_non_strict",
        ),
        pytest.param(
            b"{% set x = [] %}{% set _ = x.append(x) %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "[[...]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_list_strict",
        ),
        pytest.param(
            b"{% set x = [] %}{% set _ = x.append(x) %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "[[...]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_list_non_strict",
        ),
        pytest.param(
            b"{% for i in range(999999999) %}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: loop range exceeds maximum limit of 100000",
            "Template security error: loop range exceeds maximum limit of 100000",
            id="test_render_failure_large_loop_range_999M_strict",
        ),
        pytest.param(
            b"{% for i in range(999999999) %}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: loop range exceeds maximum limit of 100000",
            "Template security error: loop range exceeds maximum limit of 100000",
            id="test_render_failure_large_loop_range_999M_non_strict",
        ),
        pytest.param(
            b"Hello {{ user.name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'user' is undefined",
            id="test_render_failure_nested_undefined_context_strict",
        ),
        pytest.param(
            b"Hello {{ user.name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "Hello !",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_nested_undefined_context_success_non_strict",
        ),
        pytest.param(
            b"Hello {{ user.profile.name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'user' is undefined",
            id="test_render_failure_multi_level_nested_undefined_context_strict",
        ),
        pytest.param(
            b"Hello {{ user.profile.name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "Hello !",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_multi_level_nested_undefined_context_success_non_strict",
        ),
        pytest.param(
            b"Hello {{ user.name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"user": {}},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'dict object' has no attribute 'name'",
            id="test_render_failure_partial_nested_undefined_context_strict",
        ),
        pytest.param(
            b"{{ undefined.method() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undefined' is undefined",
            id="test_render_failure_undefined_method_call_context_strict",
        ),
        pytest.param(
            b"{{ items[0] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'items' is undefined",
            id="test_render_failure_undefined_index_access_context_strict",
        ),
        pytest.param(
            b"{{ 'prefix_' + undefined + '_suffix' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undefined' is undefined",
            id="test_render_failure_undefined_in_expression_context_strict",
        ),
        pytest.param(
            b"{{ 'prefix_' + undefined + '_suffix' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "_suffix",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_in_expression_context_non_strict",
        ),
        pytest.param(
            b"{% if condition %}{{ value }}{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'condition' is undefined",
            id="test_render_failure_undefined_in_condition_value_context_strict",
        ),
        pytest.param(
            b"{{ undefined|upper }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undefined' is undefined",
            id="test_render_failure_undefined_with_filter_context_strict",
        ),
        pytest.param(
            b"{{ var1 ~ var2 ~ var3 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'var1' is undefined",
            id="test_render_failure_multiple_undefined_concat_context_strict",
        ),
        pytest.param(
            b"Hello {{ user.name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"user": {}},
            "Hello !",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_partial_nested_undefined_context_non_strict",
        ),
        pytest.param(
            b"{{ undefined.method() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_method_call_context_non_strict",
        ),
        pytest.param(
            b"{{ items[0] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'items' is undefined",
            id="test_render_failure_undefined_index_access_context_non_strict",
        ),
        pytest.param(
            b"{% if condition %}{{ value }}{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_in_condition_value_context_non_strict",
        ),
        pytest.param(
            b"{{ undefined|upper }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_undefined_with_filter_context_non_strict",
        ),
        pytest.param(
            b"{{ var1 ~ var2 ~ var3 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_multiple_undefined_concat_context_non_strict",
        ),
        pytest.param(
            b"{{ large_data }}",
            FORMAT_TYPE_KEEP,
            STRICT_UNDEFINED,
            {"large_data": "a" * (DocumentRender.MAX_MEMORY_SIZE_BYTES + 10)},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            f"Memory consumption exceeds maximum limit of {DocumentRender.MAX_MEMORY_SIZE_BYTES} bytes",
            id="test_render_failure_memory_limit_exceeded_by_context_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_circular_list(),  # Use helper function
            "[1, 2, [...]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_list_from_context_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_circular_dict(),  # Use helper function
            "{&#39;a&#39;: 1, &#39;self&#39;: {...}}",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_dict_from_context_strict",
        ),
        pytest.param(
            b"{% set l = [] %}{% set _ = l.append(l) %}{{ l }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "[[...]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_list_created_in_template_strict",
        ),
        pytest.param(
            b"{% set d = {} %}{% set _ = d.update({'self': d}) %}{{ d }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "{&#39;self&#39;: {...}}",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_dict_created_in_template_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_indirect_circular_list(),  # Use helper function
            "[[[...]]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_indirect_recursive_list_from_context_strict",
        ),
        pytest.param(
            b"{% set l1 = [] %}{% set l2 = [l1] %}{% set _ = l1.append(l2) %}{{ l1 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "[[[...]]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_indirect_recursive_list_created_in_template_strict",
        ),
        pytest.param(
            b"{% for i in range(limit) %}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"limit": 1000000},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_dynamic_loop_range_over_limit_strict",
        ),
        pytest.param(
            b"{% for i in range(limit) %}{% for j in range(limit) %}{% endfor %}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"limit": 1000},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_nested_dynamic_loop_range_over_limit_strict",
        ),
        pytest.param(
            b"{% for i in range(1, 5, 0) %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            (
                "Template security error: 1 validation error for RangeConfig\n"
                "step\n"
                "  Input should be greater than 0 [type=greater_than, input_value=0, input_type=int]\n"
                "    For further information visit https://errors.pydantic.dev/2.11/v/greater_than"
            ),
            (
                "Template security error: 1 validation error for RangeConfig\n"
                "step\n"
                "  Input should be greater than 0 [type=greater_than, input_value=0, input_type=int]\n"
                "    For further information visit https://errors.pydantic.dev/2.11/v/greater_than"
            ),
            id="test_render_failure_invalid_range_step_zero_strict",
        ),
        pytest.param(
            b"{% for i in range(1, 5, step_var) %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"step_var": 0},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: range() arg 3 must not be zero",
            id="test_render_failure_dynamic_range_step_zero_strict",
        ),
        pytest.param(
            b"{% for i in range(1, 5.5) %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'float' object cannot be interpreted as an integer",
            id="test_render_failure_invalid_range_float_literal_strict",
        ),
        pytest.param(
            b"{% for i in range(1, stop_var) %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"stop_var": 5.5},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'float' object cannot be interpreted as an integer",
            id="test_render_failure_dynamic_range_float_arg_strict",
        ),
        pytest.param(
            b"{% for i in range(1, stop_var) %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"stop_var": "5"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'str' object cannot be interpreted as an integer",
            id="test_render_failure_dynamic_range_string_arg_strict",
        ),
        pytest.param(
            b"{% for i in range() %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: invalid number of arguments for range()",
            "Template security error: invalid number of arguments for range()",
            id="test_render_failure_invalid_range_zero_args_strict",
        ),
        pytest.param(
            b"{% for i in range(1, 2, 3, 4) %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: range expected at most 3 arguments, got 4",
            id="test_render_failure_invalid_range_four_args_strict",
        ),
        pytest.param(
            b"{{ 1 + 'a' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: unsupported operand type(s) for +: 'int' and 'str'",
            id="test_render_failure_binop_add_int_str_strict",
        ),
        pytest.param(
            b"{{ 'a' - 1 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: unsupported operand type(s) for -: 'str' and 'int'",
            id="test_render_failure_binop_sub_str_int_strict",
        ),
        pytest.param(
            b"{{ 1 + none_var }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"none_var": None},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: unsupported operand type(s) for +: 'int' and 'NoneType'",
            id="test_render_failure_binop_add_int_none_strict",
        ),
        pytest.param(
            b"{{ 1 + undef }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_binop_add_int_undef_strict",
        ),
        pytest.param(
            b"{{ 'hello' + undef }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_binop_add_str_undef_non_strict",
        ),
        pytest.param(
            b"{{ 'hello' ~ undef }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "hello",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_binop_concat_str_undef_non_strict",
        ),
        pytest.param(
            b"{{ 1 / none_var }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"none_var": None},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: unsupported operand type(s) for /: 'int' and 'NoneType'",
            id="test_render_failure_binop_div_int_none_strict",
        ),
        pytest.param(
            b"{{ 1 / undef }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_binop_div_int_undef_strict",
        ),
        pytest.param(
            b"{{ 1 / undef }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_binop_div_int_undef_non_strict",
        ),
        pytest.param(
            b"{% set l = [] %}{{ l.append(l) }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "None",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_call_list_append_self_strict",
        ),
        pytest.param(
            b"{% set d = {} %}{{ d.update({'self': d}) }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "None",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_recursive_call_dict_update_self_strict",
        ),
        pytest.param(
            b"{% macro recursive(n) %}{% if n > 0 %}{{ recursive(n-1) }}{% endif %}{% endmacro %}{{ recursive(5) }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            "Template security error: 'macro' tag is not allowed",
            "Template security error: 'macro' tag is not allowed",
            id="test_render_failure_recursive_macro_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_circular_list(),  # Use helper function
            "[1, 2, [...]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_context_recursive_list_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_circular_dict(),  # Use helper function
            "{&#39;a&#39;: 1, &#39;self&#39;: {...}}",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_context_recursive_dict_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_indirect_circular_list(),  # Use helper function
            "[[[...]]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_context_indirect_recursive_list_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_indirect_circular_dict(),  # Use helper function
            "{&#39;d2&#39;: {&#39;d1&#39;: {...}}}",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_context_indirect_recursive_dict_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"data": _create_deeply_nested_list(10)},
            "[[[[[[[[[[[]]]]]]]]]]]",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_context_deeply_nested_list_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"data": _create_deeply_nested_list(50000)},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: maximum recursion depth exceeded while getting the repr of an object",
            id="test_render_failure_context_deeply_nested_list_strict",
        ),
        pytest.param(
            b"{{ data }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"data": _create_deeply_nested_dict(50000)},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: maximum recursion depth exceeded while getting the repr of an object",
            id="test_render_failure_context_deeply_nested_dict_strict",
        ),
        pytest.param(
            b"{{ 1 / 0 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template security error: division by zero is not allowed",
            id="test_render_failure_div_literal_zero_strict",
        ),
        pytest.param(
            b"{{ 1 // 0 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: integer division or modulo by zero",
            id="test_render_failure_floordiv_literal_zero_strict",
        ),
        pytest.param(
            b"{{ 1 % 0 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: integer modulo by zero",
            id="test_render_failure_mod_literal_zero_strict",
        ),
        pytest.param(
            b"{{ 1 // zero_var }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"zero_var": 0},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: integer division or modulo by zero",
            id="test_render_failure_floordiv_context_zero_strict",
        ),
        pytest.param(
            b"{{ 1 % zero_var }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"zero_var": 0},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: integer modulo by zero",
            id="test_render_failure_mod_context_zero_strict",
        ),
        pytest.param(
            b"{{ 1 / 'a' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: unsupported operand type(s) for /: 'int' and 'str'",
            id="test_render_failure_div_by_string_strict",
        ),
        pytest.param(
            b"{{ 1 // 'a' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: unsupported operand type(s) for //: 'int' and 'str'",
            id="test_render_failure_floordiv_by_string_strict",
        ),
        pytest.param(
            b"{{ 1 % 'a' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: unsupported operand type(s) for %: 'int' and 'str'",
            id="test_render_failure_mod_by_string_strict",
        ),
        # --- String Operation Edge Cases ---
        pytest.param(
            b"{{ 'a' + 1 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            'Template runtime error: can only concatenate str (not "int") to str',
            id="test_render_failure_string_add_int_strict",
        ),
        pytest.param(
            b"{{ 'a' ~ 1 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            "a1",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_string_concat_int_strict",
        ),
        pytest.param(
            b"{{ 'a' ~ none_var }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"none_var": None},
            "aNone",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_string_concat_none_strict",
        ),
        pytest.param(
            b"{{ 'a' * 2.5 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: can't multiply sequence by non-int of type 'float'",
            id="test_render_failure_string_mul_float_strict",
        ),
        pytest.param(
            b"{{ 'a' * 'b' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: can't multiply sequence by non-int of type 'str'",
            id="test_render_failure_string_mul_string_strict",
        ),
        pytest.param(
            b"{{ '%d' % 'a' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: %d format: a real number is required, not str",
            id="test_render_failure_string_format_wrong_type_strict",
        ),
        pytest.param(
            b"{{ '%s %s' % 'a' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: not enough arguments for format string",
            id="test_render_failure_string_format_insufficient_args_strict",
        ),
        pytest.param(
            b"{{ '%s' % undef }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_string_format_undefined_strict",
        ),
        pytest.param(
            b"{{ '%s' % undef }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_string_format_undefined_non_strict",
        ),
        pytest.param(
            b"{% set my_conf = config %}{{ my_conf }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"config": {"key": "value"}},
            EXPECTED_NO_CONTENT,
            "Template security error: Assignment of restricted variable 'config' is forbidden.",
            "Template security error: Assignment of restricted variable 'config' is forbidden.",
            id="test_render_failure_assign_restricted_var_strict",
        ),
        pytest.param(
            b"{% set cls = getattr(obj, '__class__') %}{{ cls }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"getattr": getattr, "obj": object()},
            EXPECTED_NO_CONTENT,
            "Template security error: Assignment involving restricted function 'getattr()' is forbidden.",
            "Template security error: Assignment involving restricted function 'getattr()' is forbidden.",
            id="test_render_failure_assign_restricted_call_strict",
        ),
        pytest.param(
            b"{% set x = 1 / 0 %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: Assign cannot evaluate expression",
            id="test_render_failure_assign_div_zero_strict",
        ),
        pytest.param(
            b"{% set x = 1 + undef %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: Assign cannot evaluate expression",
            id="test_render_failure_assign_op_undefined_strict",
        ),
        pytest.param(
            b"{{ obj.__class__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"obj": object()},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted attribute '__class__' is forbidden.",
            "Template security error: Access to restricted attribute '__class__' is forbidden.",
            id="test_render_failure_getattr_restricted_class_strict",
        ),
        pytest.param(
            b"{{ my_dict['os'] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"my_dict": {"os": "value"}},
            EXPECTED_NO_CONTENT,
            "Template security error: Access to restricted item 'os' is forbidden.",
            "Template security error: Access to restricted item 'os' is forbidden.",
            id="test_render_failure_getitem_restricted_os_strict",
        ),
        pytest.param(
            b"{{ none_var.attribute }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"none_var": None},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'None' has no attribute 'attribute'",
            id="test_render_failure_getattr_on_none_strict",
        ),
        pytest.param(
            b"{{ undef.attribute }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_getattr_on_undef_strict",
        ),
        pytest.param(
            b"{{ undef.attribute }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_getattr_on_undef_non_strict",
        ),
        pytest.param(
            b"{{ undef.attr1.attr2 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_getattr_nested_undef_strict",
        ),
        pytest.param(
            b"{{ undef.attr1.attr2 }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_getattr_nested_undef_non_strict",
        ),
        pytest.param(
            b"{{ data[123] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {123: "value"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Validation error: Input should be a valid string at 'context.123.[key]'",
            id="test_render_failure_context_int_key_strict",
        ),
        pytest.param(
            b"{{ data[(1, 2)] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {(1, 2): "value"},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Validation error: Input should be a valid string at 'context.(1, 2).[key]'",
            id="test_render_failure_context_tuple_key_strict",
        ),
        pytest.param(
            b"{% if 1 > 'a' %}TRUE{% else %}FALSE{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: '>' not supported between instances of 'int' and 'str'",
            id="test_render_failure_if_compare_int_str_strict",
        ),
        pytest.param(
            b"{% if 1 > none_var %}TRUE{% else %}FALSE{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"none_var": None},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: '>' not supported between instances of 'int' and 'NoneType'",
            id="test_render_failure_if_compare_int_none_strict",
        ),
        pytest.param(
            b"{% if 1 > undef %}TRUE{% else %}FALSE{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_if_compare_int_undef_strict",
        ),
        pytest.param(
            b"{% if 1 > undef %}TRUE{% else %}FALSE{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_if_compare_int_undef_non_strict",
        ),
        pytest.param(
            b"{% if True and undef %}TRUE{% else %}FALSE{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            EXPECTED_NO_CONTENT,
            EXPECTED_INITIAL_NO_ERROR,
            "Template runtime error: 'undef' is undefined",
            id="test_render_failure_if_and_undef_strict",
        ),
        pytest.param(
            b"{% if True and undef %}TRUE{% else %}FALSE{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "FALSE",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_if_and_undef_non_strict",
        ),
        pytest.param(
            b"{% if False or undef %}TRUE{% else %}FALSE{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            "FALSE",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_if_or_undef_non_strict",
        ),
        pytest.param(
            b"{% for item in data %}{{ item }},{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_circular_list(),
            "1,2,[1, 2, [...]],",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_for_over_recursive_list_strict",
        ),
        pytest.param(
            b"{% for k, v in data.items() %}{{ k }}:{{ v }},{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_circular_dict(),
            "a:1,self:{&#39;a&#39;: 1, &#39;self&#39;: {...}},",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_for_over_recursive_dict_strict",
        ),
        pytest.param(
            b"{% for item in data %}{{ item }},{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            _create_list_with_circular_dict(),
            "1,{&#39;rec&#39;: {...}},3,",
            EXPECTED_INITIAL_NO_ERROR,
            EXPECTED_RUNTIME_NO_ERROR,
            id="test_render_success_for_over_list_with_recursive_dict_strict",
        ),
    ],
)
def test_render_template(
    create_template_file: Callable[[bytes, str], BytesIO],
    template_content: bytes,
    format_type: int,
    is_strict_undefined: bool,
    context: typing.Dict[str, AnyType],
    expected_content: Optional[str],
    expected_initial_error: Optional[str],
    expected_runtime_error: Optional[str],
) -> None:
    """Tests template rendering with various inputs and configurations.

    This comprehensive test checks template rendering behavior with different:
    - Template content
    - Format types
    - Strict/non-strict undefined variable handling
    - Context data
    - Expected output content
    - Initial errors (parsing/syntax)
    - Runtime errors (during template execution)

    Args:
        create_template_file: Fixture to create template files for testing
        template_content: Raw template content bytes
        format_type: Formatting option to apply to the rendered template
        is_strict_undefined: Whether undefined variables raise errors
        context: Dictionary of variables to use during rendering
        expected_content: Expected rendered output or None if error expected
        expected_initial_error: Expected error during template parsing/initialization
        expected_runtime_error: Expected error during template rendering
    """
    # Arrange
    template_file: BytesIO = create_template_file(template_content, "template.txt")
    expected_initial_valid: bool = True if expected_initial_error is EXPECTED_INITIAL_NO_ERROR else False

    # Act
    render = DocumentRender(template_file)

    # Act & Assert for template validation
    assert render.is_valid_template == expected_initial_valid, (
        f"expected_initial_valid isn't match.\nGot: {render.is_valid_template}\nExpected: {expected_initial_valid}"
    )
    assert render.error_message == expected_initial_error, (
        f"expected_initial_error isn't match.\nGot: {render.error_message}\nExpected: {expected_initial_error}"
    )

    # Act
    apply_result: bool = render.apply_context(context, format_type, is_strict_undefined)
    expected_runtime_valid: bool = True if expected_runtime_error is EXPECTED_RUNTIME_NO_ERROR else False

    # Assert
    assert apply_result == expected_runtime_valid, (
        f"expected_runtime_valid isn't match.\nGot: {apply_result}\nExpected: {expected_runtime_valid}"
    )
    assert render.render_content == expected_content, (
        f"expected_content isn't match.\nGot: {render.render_content}\nExpected: {expected_content}"
    )
    assert render.error_message == expected_runtime_error, (
        f"expected_runtime_error isn't match.\nGot: {render.error_message}\nExpected: {expected_runtime_error}"
    )
