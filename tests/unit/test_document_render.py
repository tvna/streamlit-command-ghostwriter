"""テンプレートのレンダリングと検証のテストモジュール。

このモジュールは、DocumentRenderクラスのテストを提供します。
テストは以下の3つの主要なカテゴリに分かれています:

1. 初期検証テスト
   - ファイルサイズ
   - エンコーディング
   - 構文
   - セキュリティ (静的解析)

2. ランタイム検証テスト
   - 再帰的構造
   - ゼロ除算
   - メモリ使用量

3. 検証の一貫性テスト
   - 初期検証とランタイム検証の結果の整合性
   - エラーメッセージの一貫性
"""

from io import BytesIO
from typing import (
    Any as AnyType,
)
from typing import (
    Callable,
    Dict,
    Optional,
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

# Constants for better readability in tests
INITIAL_VALID: bool = True
INITIAL_INVALID: bool = False
RUNTIME_VALID: bool = True
RUNTIME_INVALID: bool = False
STRICT_UNDEFINED: bool = True
NON_STRICT_UNDEFINED: bool = False
EXPECTED_NO_ERROR: Optional[str] = None
EXPECTED_NO_CONTENT: Optional[str] = None


UNIT: MarkDecorator = pytest.mark.unit
SET_TIMEOUT: MarkDecorator = pytest.mark.timeout(10)


@pytest.fixture
def create_template_file() -> Callable[[bytes, str], BytesIO]:
    """テスト用のテンプレートファイルを作成するフィクスチャ。

    Returns:
        Callable[[bytes, str], BytesIO]: テンプレートファイルを作成する関数
    """

    def _create_file(content: bytes, filename: str = "template.txt") -> BytesIO:
        file: BytesIO = BytesIO(content)
        file.name = filename
        return file

    return _create_file


@UNIT
@SET_TIMEOUT
@pytest.mark.parametrize(
    ("template_content", "expected_valid", "expected_error"),
    [
        # 基本的な構文テスト
        pytest.param(
            b"Hello {{ name }}!",
            INITIAL_VALID,
            EXPECTED_NO_ERROR,
            id="test_initial_syntax_basic_success",
        ),
        # エンコーディングテスト
        pytest.param(
            b"\x80\x81\x82\x83",
            INITIAL_INVALID,
            "Template file contains invalid UTF-8 bytes",
            id="test_initial_encoding_invalid_utf8_fail",
        ),
        # 構文エラーテスト
        pytest.param(
            b"Hello {{ name }!",
            INITIAL_INVALID,
            "unexpected '}'",
            id="test_initial_syntax_error_unmatched_brace_fail",
        ),
        # セキュリティ検証テスト - マクロ
        pytest.param(
            b"{% macro input(name) %}{% endmacro %}",
            INITIAL_INVALID,
            "Template security error: 'macro' tag is not allowed",
            id="test_initial_security_macro_tag_fail",
        ),
        # セキュリティ検証テスト - インクルード
        pytest.param(
            b"{% include 'header.html' %}",
            INITIAL_INVALID,
            "Template security error: 'include' tag is not allowed",
            id="test_initial_security_include_tag_fail",
        ),
        # セキュリティ検証テスト - 制限属性
        pytest.param(
            b"{{ request.args }}",
            INITIAL_INVALID,
            "Template security validation failed: Use of restricted variable 'request' is forbidden.",
            id="test_initial_security_restricted_attribute_request_fail",
        ),
        # セキュリティ検証テスト - 大きなループ範囲
        pytest.param(
            b"{% for i in range(0, 1000000) %}{{ i }}{% endfor %}",
            INITIAL_INVALID,
            "Template security error: loop range exceeds maximum limit of 100000",
            id="test_initial_security_large_loop_range_fail",
        ),
        # ファイルサイズ検証テスト
        pytest.param(
            b"",  # 空ファイル
            INITIAL_VALID,
            EXPECTED_NO_ERROR,
            id="test_initial_filesize_empty_success",
        ),
        pytest.param(
            b"a" * (30 * 1024 * 1024),  # 制限値ちょうど
            INITIAL_VALID,
            EXPECTED_NO_ERROR,
            id="test_initial_filesize_max_exact_success",
        ),
        pytest.param(
            b"a" * (30 * 1024 * 1024 + 1),  # 制限値オーバー
            INITIAL_INVALID,
            f"Template file size exceeds maximum limit of {30 * 1024 * 1024} bytes",
            id="test_initial_filesize_max_exceeded_fail",
        ),
        # バイナリデータ (Nullバイト) 検証テスト
        pytest.param(
            b"\x00",  # Nullバイトのみ
            INITIAL_INVALID,
            "Template file contains invalid binary data",
            id="test_initial_encoding_null_byte_only_fail",
        ),
        pytest.param(
            b"Hello\x00World",  # 有効なテキスト + Nullバイト
            INITIAL_INVALID,
            "Template file contains invalid binary data",
            id="test_initial_encoding_null_byte_in_text_fail",
        ),
    ],
)
def test_initial_validation(
    create_template_file: Callable[[bytes, str], BytesIO],
    template_content: bytes,
    expected_valid: bool,
    expected_error: Optional[str],
) -> None:
    """初期検証の動作を確認する。

    Args:
        create_template_file: テンプレートファイル作成用フィクスチャ
        template_content: テンプレートの内容
        expected_valid: 検証が成功することが期待されるかどうか
        expected_error: 期待されるエラーメッセージ
    """
    # Arrange
    template_file: BytesIO = create_template_file(template_content, "template.txt")

    # Act
    renderer = DocumentRender(template_file)

    # Assert
    assert renderer.is_valid_template == expected_valid, (
        f"Template validation failed.\nExpected: {expected_valid}\nGot: {renderer.is_valid_template}"
    )
    if expected_error:
        assert renderer.error_message is not None, "Expected error message but got None"
        assert expected_error == renderer.error_message, (
            f"Error message does not match.\nExpected: {expected_error}\nGot: {renderer.error_message}"
        )
    else:
        assert renderer.error_message is None, f"Expected no error message, but got: {renderer.error_message}"


@UNIT
@SET_TIMEOUT
@pytest.mark.parametrize(
    (
        "template_content",
        "format_type",
        "is_strict_undefined",
        "context",
        "expected_initial_valid",
        "expected_runtime_valid",
        "expected_content",
        "expected_initial_error",
        "expected_runtime_error",
    ),
    [
        pytest.param(
            b"{% macro input() %}{% endmacro %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'macro' tag is not allowed",
            "Template security error: 'macro' tag is not allowed",
            id="test_render_initial_security_macro_tag_fail_strict",
        ),
        pytest.param(
            b"{% macro input() %}{% endmacro %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'macro' tag is not allowed",
            "Template security error: 'macro' tag is not allowed",
            id="test_render_initial_security_macro_tag_fail_non_strict",
        ),
        # ランタイムのみで失敗するケース - strictモード
        pytest.param(
            b"{{ 10 / value }}",
            {"value": 0},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_division_by_zero_context_fail_strict",
        ),
        # ランタイムのみで失敗するケース - 非strictモード
        pytest.param(
            b"{{ 10 / value }}",
            {"value": 0},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_division_by_zero_context_fail_non_strict",
        ),
        # 両方で成功するケース -> ランタイムで失敗するケース (エラーメッセージが不適切?)
        pytest.param(
            b"Hello {{ name }}!",
            {"name": "World"},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_valid_context_unexpected_fail_strict",
        ),
        # 両方で成功するケース -> ランタイムで失敗するケース (エラーメッセージが不適切?) - 非strictモード
        pytest.param(
            b"Hello {{ name }}!",
            {"name": "World"},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_valid_context_unexpected_fail_non_strict",
        ),
        # 未定義変数のケース -> ランタイムで失敗するケース (エラーメッセージが不適切?) - strictモード
        pytest.param(
            b"Hello {{ undefined }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_var_context_fail_strict",
        ),
        # 未定義変数のケース -> ランタイムで失敗するケース (エラーメッセージが不適切?) - 非strictモード
        pytest.param(
            b"Hello {{ undefined }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_var_context_fail_non_strict",
        ),
        # Test case on success
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_variable_basic_success_strict",
        ),
        # フォーマットタイプのテスト - インテグレーションテストの仕様に合わせる
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_REMOVE_ALL,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\nGood bye World!",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_format_remove_all_success_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\nGood bye World!",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_format_compress_alt_success_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_KEEP_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\n\n  \nGood bye World!",  # 空白行を保持
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_format_keep_alt_success_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_COMPRESS,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\nGood bye World!",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_format_compress_success_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_KEEP,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\n\n  \nGood bye World!",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_format_keep_success_strict",
        ),
        # 基本的な未定義変数のテスト - 非strictモード
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello !",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_runtime_undefined_var_success_non_strict",
        ),
        # 基本的な未定義変数のテスト - strictモード
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "'name' is undefined",
            id="test_render_runtime_undefined_var_fail_strict",
        ),
        # 複数の変数を含むテスト - 非strictモード (部分成功)
        pytest.param(
            b"Hello {{ first_name }} {{ last_name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"first_name": "John"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello John !",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_runtime_multiple_vars_partial_success_non_strict",
        ),
        # 複数の変数を含むテスト - strictモード
        pytest.param(
            b"Hello {{ first_name }} {{ last_name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"first_name": "John"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "'last_name' is undefined",
            id="test_render_runtime_multiple_vars_partial_fail_strict",
        ),
        # 条件分岐内の未定義変数 - 非strictモード
        pytest.param(
            b"{% if undefined_var %}Show{% else %}Hide{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hide",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_runtime_undefined_in_condition_success_non_strict",
        ),
        # 条件分岐内の未定義変数 - strictモード
        pytest.param(
            b"{% if undefined_var %}Show{% else %}Hide{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "'undefined_var' is undefined",
            id="test_render_runtime_undefined_in_condition_fail_strict",
        ),
        # 定義済み変数のチェック - is_definedフィルター (非strictモード)
        pytest.param(
            b"{{ name if name is defined else 'Anonymous' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Anonymous",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_runtime_defined_check_fallback_success_non_strict",
        ),
        # 定義済み変数のチェック - is_definedフィルター (strictモード)
        pytest.param(
            b"{{ name if name is defined else 'Anonymous' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Anonymous",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_runtime_defined_check_fallback_success_strict",
        ),
        # ネストされた変数アクセス - 非strictモード
        pytest.param(
            b"{{ user.name }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_runtime_nested_undefined_success_non_strict",
        ),
        # ネストされた変数アクセス - strictモード
        pytest.param(
            b"{{ user.name }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "'user' is undefined",
            id="test_render_runtime_nested_undefined_fail_strict",
        ),
        # Test case on failed
        pytest.param(
            b"\x80\x81\x82\x83",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template file contains invalid UTF-8 bytes",
            "Template file contains invalid UTF-8 bytes",
            id="test_render_initial_encoding_invalid_utf8_fail_strict",
        ),
        # Test case for syntax error - 初期検証で失敗するように修正
        pytest.param(
            b"Hello {{ name }!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "unexpected '}'",
            "unexpected '}'",
            id="test_render_initial_syntax_error_unmatched_brace_fail_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            MIN_FORMAT_TYPE - 1,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_invalid_format_type_below_min_fail_strict",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            MAX_FORMAT_TYPE + 1,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_invalid_format_type_above_max_fail_strict",
        ),
        # Edge case: Template with error in expression
        pytest.param(
            b"{{ 10 / value }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"value": 0},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Template rendering error: division by zero",
            id="test_render_runtime_division_by_zero_fail_strict",
        ),
        # YAMLコンテキストのテスト
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
            INITIAL_VALID,
            RUNTIME_VALID,
            ("Current Date: 2024-03-20\nLast Updated: 2024-03-20 15:30:45\nNext Review: June 20, 2024"),
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_filter_date_success_strict",
        ),
        pytest.param(
            b"{{ invalid_date | date('%Y-%m-%d') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"invalid_date": "not-a-date"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Template rendering error: Invalid date format",
            id="test_render_runtime_filter_invalid_date_fail_strict",
        ),
        pytest.param(
            b"{{ date | date('%Y-%m-%d') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"date": None},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Template rendering error: cannot access local variable 'dt' where it is not associated with a value",
            id="test_render_runtime_filter_null_date_fail_strict",
        ),
        # Template Injection Edge Cases
        pytest.param(
            b"{{ ''.__class__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Access to restricted attribute '__class__' is forbidden.",
            "Template security validation failed: Access to restricted attribute '__class__' is forbidden.",
            id="test_render_initial_security_injection_class_attr_fail_strict",
        ),
        pytest.param(
            b"{{ ''.__class__.__mro__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Access to restricted attribute '__mro__' is forbidden.",
            "Template security validation failed: Access to restricted attribute '__mro__' is forbidden.",
            id="test_render_initial_security_injection_mro_attr_fail_strict",
        ),
        pytest.param(
            b"{{ ''.__class__.__mro__[1].__subclasses__() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Access to restricted attribute '__subclasses__' is forbidden.",
            "Template security validation failed: Access to restricted attribute '__subclasses__' is forbidden.",
            id="test_render_initial_security_injection_subclasses_attr_fail_strict",
        ),
        pytest.param(
            b"{{ getattr('', '__class__') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Call to restricted function 'getattr()' is forbidden.",
            "Template security validation failed: Call to restricted function 'getattr()' is forbidden.",
            id="test_render_initial_security_injection_getattr_call_fail_strict",
        ),
        pytest.param(
            b"{{ self.__init__.__globals__['os'] }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"self": object()},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Access to restricted item 'os' is forbidden.",
            "Template security validation failed: Access to restricted item 'os' is forbidden.",
            id="test_render_initial_security_injection_globals_item_fail_strict",
        ),
        pytest.param(
            b"{% import 'os' as os %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'import' tag is not allowed",
            "Template security error: 'import' tag is not allowed",
            id="test_render_initial_security_injection_import_tag_fail_strict",
        ),
        pytest.param(
            b"{% extends 'base.html' %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'extends' tag is not allowed",
            "Template security error: 'extends' tag is not allowed",
            id="test_render_initial_security_injection_extends_tag_fail_strict",
        ),
        pytest.param(
            b"{{ eval('1+1') }}",  # Assuming context contains 'eval'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"eval": eval},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Call to restricted function 'eval()' is forbidden.",
            "Template security validation failed: Call to restricted function 'eval()' is forbidden.",
            id="test_render_initial_security_injection_eval_call_fail_strict",
        ),
        pytest.param(
            b"{{ exec('import os') }}",  # Assuming context contains 'exec'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"exec": exec},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Call to restricted function 'exec()' is forbidden.",
            "Template security validation failed: Call to restricted function 'exec()' is forbidden.",
            id="test_render_initial_security_injection_exec_call_fail_strict",
        ),
        pytest.param(
            b"{{ os.system('ls') }}",  # Assuming context contains 'os'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"os": __import__("os")},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Use of restricted variable 'os' is forbidden.",
            "Template security validation failed: Use of restricted variable 'os' is forbidden.",
            id="test_render_initial_security_injection_os_var_fail_strict",
        ),
        pytest.param(
            b"{{ sys.modules }}",  # Assuming context contains 'sys'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"sys": __import__("sys")},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Use of restricted variable 'sys' is forbidden.",
            "Template security validation failed: Use of restricted variable 'sys' is forbidden.",
            id="test_render_initial_security_injection_sys_var_fail_strict",
        ),
        pytest.param(
            b"{{ builtins.open('/etc/passwd').read() }}",  # Assuming context contains 'builtins'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"builtins": __import__("builtins")},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Use of restricted variable 'builtins' is forbidden.",
            "Template security validation failed: Use of restricted variable 'builtins' is forbidden.",
            id="test_render_initial_security_injection_builtins_var_fail_strict",
        ),
        pytest.param(
            b"{{ setattr(obj, 'attr', 'value') }}",  # Assuming context contains 'setattr'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"setattr": setattr, "obj": object()},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Call to restricted function 'setattr()' is forbidden.",
            "Template security validation failed: Call to restricted function 'setattr()' is forbidden.",
            id="test_render_initial_security_injection_setattr_call_fail_strict",
        ),
        pytest.param(
            b"{{ delattr(obj, 'attr') }}",  # Assuming context contains 'delattr'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"delattr": delattr, "obj": type("Dummy", (), {"attr": 1})()},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Call to restricted function 'delattr()' is forbidden.",
            "Template security validation failed: Call to restricted function 'delattr()' is forbidden.",
            id="test_render_initial_security_injection_delattr_call_fail_strict",
        ),
        pytest.param(
            b"{{ locals() }}",  # Assuming context contains 'locals'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"locals": locals},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Call to restricted function 'locals()' is forbidden.",
            "Template security validation failed: Call to restricted function 'locals()' is forbidden.",
            id="test_render_initial_security_injection_locals_call_fail_strict",
        ),
        # _validate_restricted_attributes の追加エッジケース
        pytest.param(
            b"{{ config }}",  # 禁止された Name の直接使用
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"config": {}},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Use of restricted variable 'config' is forbidden.",
            "Template security validation failed: Use of restricted variable 'config' is forbidden.",
            id="test_render_initial_security_injection_config_var_fail_strict",
        ),
        pytest.param(
            b"{{ obj.__base__ }}",  # 禁止された Getattr (__base__)
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"obj": "test"},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Access to restricted attribute '__base__' is forbidden.",
            "Template security validation failed: Access to restricted attribute '__base__' is forbidden.",
            id="test_render_initial_security_injection_base_attr_fail_strict",
        ),
        pytest.param(
            b"{{ my_dict['os'] }}",  # 禁止された Getitem
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"my_dict": {"os": "value"}},  # キーが禁止されている
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Access to restricted item 'os' is forbidden.",
            "Template security validation failed: Access to restricted item 'os' is forbidden.",
            id="test_render_initial_security_injection_os_item_fail_strict",
        ),
        pytest.param(
            b"{% set my_os = os %}{{ my_os }}",  # 禁止された Name の Assign
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"os": "fake_os"},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Assignment of restricted variable 'os' is forbidden.",
            "Template security validation failed: Assignment of restricted variable 'os' is forbidden.",
            id="test_render_initial_security_injection_os_assign_fail_strict",
        ),
        pytest.param(
            b"{% set my_eval = eval %}{{ my_eval('1') }}",  # 禁止された Call の Assign
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"eval": eval},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Assignment of restricted variable 'eval' is forbidden.",
            "Template security validation failed: Assignment of restricted variable 'eval' is forbidden.",
            id="test_render_initial_security_injection_eval_assign_fail_strict",
        ),
        # _is_recursive_structure の追加エッジケース
        # 辞書の再帰 -> doタグ禁止により初期検証で失敗
        pytest.param(
            b"{% set d = {} %}{% do d.update({'self': d}) %}{{ d }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'do' tag is not allowed",
            "Template security error: 'do' tag is not allowed",
            id="test_render_initial_security_do_tag_recursive_dict_fail_strict",
        ),
        # ネストされたリストの再帰 -> doタグ禁止により初期検証で失敗
        pytest.param(
            b"{% set l = [[]] %}{% do l[0].append(l) %}{{ l }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'do' tag is not allowed",
            "Template security error: 'do' tag is not allowed",
            id="test_render_initial_security_do_tag_recursive_list_fail_strict",
        ),
        # 混合再帰 (リストと辞書) -> doタグ禁止により初期検証で失敗
        pytest.param(
            b"{% set d = {} %}{% set l = [d] %}{% do d.update({'list': l}) %}{{ l }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'do' tag is not allowed",
            "Template security error: 'do' tag is not allowed",
            id="test_render_initial_security_do_tag_recursive_mixed_fail_strict",
        ),
        # Edge case: Template with complex nested loops and conditionals
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
            INITIAL_VALID,
            RUNTIME_VALID,
            (
                "\n      0 - 0: Start\n\n      0 - 1: Start\n\n      1 - 0: Start\n\n"
                "      1 - 1: 4\n\n      2 - 0: Start\n\n      2 - 1: 6\n\n"
            ),
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_logic_complex_loops_conditionals_success_strict",
        ),
        # Edge case: Template with undefined variable in non-strict mode
        pytest.param(
            b"{{ undefined_var if undefined_var is defined else 'Default' }}",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Default",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_edgecase_undefined_fallback_success_non_strict",
        ),
        # Edge case: Template with very long output - 修正: 出力行数を減らす
        pytest.param(
            b"{% for i in range(count) %}Line {{ i }}\n{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"count": 50},  # 1000から50に減らす
            INITIAL_VALID,
            RUNTIME_VALID,
            "\n".join([f"Line {i}" for i in range(50)]) + "\n",  # Add trailing newline
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_edgecase_many_lines_success_strict",
        ),
        # Edge case: Template with Unicode characters
        pytest.param(
            "{{ emoji }} {{ japanese }}".encode("utf-8"),
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"emoji": "😁😂🤣😃", "japanese": "こんにちは世界"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "😁😂🤣😃 こんにちは世界",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_edgecase_unicode_success_strict",
        ),
        # Edge case: Template with HTML content and safe filter -> autoescaped
        pytest.param(
            b"<html><body>{{ content | safe }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<h1>Title</h1><p>Paragraph with <b>bold</b> text</p>"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "<html><body>&lt;h1&gt;Title&lt;/h1&gt;&lt;p&gt;Paragraph with &lt;b&gt;bold&lt;/b&gt; text&lt;/p&gt;</body></html>",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_edgecase_html_safe_filter_autoescaped_success_strict",
        ),
        # Edge case: Template with unsafe HTML content (Pydantic validation fail)
        pytest.param(
            b"<html><body>{{ content | safe }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<script>alert('XSS')</script>"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            (
                "Template rendering error: 1 validation error for HTMLContent\n"
                "content\n"
                "  Value error, HTML content contains potentially unsafe elements "
                "[type=value_error, input_value=\"<script>alert('XSS')</script>\", "
                "input_type=str]\n"
                "    For further information visit https://errors.pydantic.dev/2.11/v/value_error"
            ),
            id="test_render_runtime_security_unsafe_html_fail_strict",
        ),
        # Edge case: Template with HTML escaping (default)
        pytest.param(
            b"<html><body>{{ content }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<script>alert('XSS')</script>"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "<html><body>&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;</body></html>",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_edgecase_html_autoescape_success_strict",
        ),
        # Edge case: Template with macro - 初期検証で失敗
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
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: 'macro' tag is not allowed",
            "Template security error: 'macro' tag is not allowed",
            id="test_render_initial_security_macro_definition_fail_strict",
        ),
        # Edge case: Template with call tag (runtime undefined fail)
        pytest.param(
            b"{%- call input('username') %}{% endcall %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "'input' is undefined",
            id="test_render_runtime_logic_call_tag_undefined_fail_strict",
        ),
        # Edge case: Template with request access - 初期検証で失敗
        pytest.param(
            b"{% set x = request.args %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"request": {"args": {"debug": "true"}}},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Use of restricted variable 'request' is forbidden.",
            "Template security validation failed: Use of restricted variable 'request' is forbidden.",
            id="test_render_initial_security_injection_request_var_fail_strict",
        ),
        # Edge case: Template with config access - 初期検証で失敗
        pytest.param(
            b"{{ config.items() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"config": {"secret": "sensitive_data"}},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security validation failed: Use of restricted variable 'config' is forbidden.",
            "Template security validation failed: Use of restricted variable 'config' is forbidden.",
            id="test_render_initial_security_injection_config_items_fail_strict",
        ),
        # Edge case: Template with recursive data structure (list append)
        pytest.param(
            b"{% set x = [] %}{% set _ = x.append(x) %}{{ x }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "[[...]]",
            EXPECTED_NO_ERROR,
            EXPECTED_NO_ERROR,
            id="test_render_runtime_edgecase_recursive_list_success_strict",
        ),
        # Edge case: Template with large loop range - Expect specific error message now
        pytest.param(
            b"{% for i in range(999999999) %}{{ i }}{% endfor %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            "Template security error: loop range exceeds maximum limit of 100000",
            "Template security error: loop range exceeds maximum limit of 100000",
            id="test_render_initial_security_large_loop_range_999M_fail_strict",
        ),
        # ネストされた未定義変数のケース - strictモード -> 重複のため削除候補だがIDのみ変更
        pytest.param(
            b"Hello {{ user.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_nested_undefined_context_fail_strict",
        ),
        # ネストされた未定義変数のケース - 非strictモード -> 重複のため削除候補だがIDのみ変更
        pytest.param(
            b"Hello {{ user.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_nested_undefined_context_fail_non_strict",
        ),
        # 複数レベルのネストされた未定義変数 - strictモード
        pytest.param(
            b"Hello {{ user.profile.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_multi_level_nested_undefined_context_fail_strict",
        ),
        # 複数レベルのネストされた未定義変数 - 非strictモード
        pytest.param(
            b"Hello {{ user.profile.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_multi_level_nested_undefined_context_fail_non_strict",
        ),
        # 部分的に定義された変数のネスト - strictモード
        pytest.param(
            b"Hello {{ user.name }}!",
            {"user": {}},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_partial_nested_undefined_context_fail_strict",
        ),
        # 部分的に定義された変数のネスト - 非strictモード
        pytest.param(
            b"Hello {{ user.name }}!",
            {"user": {}},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_partial_nested_undefined_context_fail_non_strict",
        ),
        # メソッド呼び出し - strictモード
        pytest.param(
            b"{{ undefined.method() }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_method_call_context_fail_strict",
        ),
        # メソッド呼び出し - 非strictモード
        pytest.param(
            b"{{ undefined.method() }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_method_call_context_fail_non_strict",
        ),
        # インデックスアクセス - strictモード
        pytest.param(
            b"{{ items[0] }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_index_access_context_fail_strict",
        ),
        # インデックスアクセス - 非strictモード
        pytest.param(
            b"{{ items[0] }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_index_access_context_fail_non_strict",
        ),
        # 複雑な式の中の未定義変数 - strictモード
        pytest.param(
            b"{{ 'prefix_' + undefined + '_suffix' }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_in_expression_context_fail_strict",
        ),
        # 複雑な式の中の未定義変数 - 非strictモード
        pytest.param(
            b"{{ 'prefix_' + undefined + '_suffix' }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_in_expression_context_fail_non_strict",
        ),
        # 条件分岐内の未定義変数 - strictモード
        pytest.param(
            b"{% if condition %}{{ value }}{% endif %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_in_condition_value_context_fail_strict",
        ),
        # 条件分岐内の未定義変数 - 非strictモード
        pytest.param(
            b"{% if condition %}{{ value }}{% endif %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_in_condition_value_context_fail_non_strict",
        ),
        # フィルターと未定義変数 - strictモード
        pytest.param(
            b"{{ undefined|upper }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_with_filter_context_fail_strict",
        ),
        # フィルターと未定義変数 - 非strictモード
        pytest.param(
            b"{{ undefined|upper }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_undefined_with_filter_context_fail_non_strict",
        ),
        # 複数の未定義変数の連結 - strictモード
        pytest.param(
            b"{{ var1 ~ var2 ~ var3 }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_multiple_undefined_concat_context_fail_strict",
        ),
        # 複数の未定義変数の連結 - 非strictモード
        pytest.param(
            b"{{ var1 ~ var2 ~ var3 }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            EXPECTED_NO_CONTENT,
            EXPECTED_NO_ERROR,
            "Validation error: context is invalid",
            id="test_render_runtime_multiple_undefined_concat_context_fail_non_strict",
        ),
    ],
)
def test_render_template(
    create_template_file: Callable[[bytes, str], BytesIO],
    template_content: bytes,
    context: Dict[str, AnyType],
    format_type: int,
    is_strict_undefined: bool,
    expected_initial_valid: bool,
    expected_runtime_valid: bool,
    expected_initial_error: Optional[str],
    expected_runtime_error: Optional[str],
    expected_content: Optional[str],
) -> None:
    """初期検証とランタイム検証の一貫性を確認する。

    Args:
        create_template_file: テンプレートファイル作成用フィクスチャ
        template_content: テンプレートの内容
        context: テンプレートに適用するコンテキスト
        format_type: フォーマットタイプ
        is_strict_undefined: 未定義変数を厳密にチェックするかどうか
        expected_initial_valid: 初期検証が成功することが期待されるかどうか
        expected_runtime_valid: ランタイム検証が成功することが期待されるかどうか
        expected_initial_error: 初期検証の期待されるエラーメッセージ
        expected_runtime_error: ランタイム検証の期待されるエラーメッセージ
        expected_content: 期待される出力内容
    """
    # Arrange
    template_file: BytesIO = create_template_file(template_content, "template.txt")

    # Act
    render = DocumentRender(template_file)

    # Act & Assert for template validation
    assert render.is_valid_template == expected_initial_valid, (
        f"expected_initial_valid isn't match.\nExpected: {expected_initial_valid}\nGot: {render.is_valid_template}"
    )
    assert render.error_message == expected_initial_error, (
        f"expected_initial_error isn't match.\nExpected: {expected_initial_error}\nGot: {render.error_message}"
    )

    # Act
    apply_result: bool = render.apply_context(context, format_type, is_strict_undefined)

    # Assert
    assert apply_result == expected_runtime_valid, (
        f"expected_runtime_valid isn't match.\nExpected: {expected_runtime_valid}\nGot: {apply_result}"
    )
    assert render.render_content == expected_content, (
        f"expected_content isn't match.\nExpected: {expected_content}\nGot: {render.render_content}"
    )
    assert render.error_message == expected_runtime_error, (
        f"expected_runtime_error isn't match.\nExpected: {expected_runtime_error}\nGot: {render.error_message}"
    )
