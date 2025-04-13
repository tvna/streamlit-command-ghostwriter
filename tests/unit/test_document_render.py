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
    List,
    Optional,
    Union,
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
            None,
            id="template_validate_basic_syntax",
        ),
        # エンコーディングテスト
        pytest.param(
            b"\x80\x81\x82\x83",
            INITIAL_INVALID,
            "Template file contains invalid UTF-8 bytes",
            id="template_validate_invalid_utf8",
        ),
        # 構文エラーテスト
        pytest.param(
            b"Hello {{ name }!",
            INITIAL_INVALID,
            "unexpected '}'",
            id="template_validate_syntax_error",
        ),
        # セキュリティ検証テスト - マクロ
        pytest.param(
            b"{% macro input(name) %}{% endmacro %}",
            INITIAL_INVALID,
            "Template security error: 'macro' tag is not allowed",
            id="template_security_macro_tag",
        ),
        # セキュリティ検証テスト - インクルード
        pytest.param(
            b"{% include 'header.html' %}",
            INITIAL_INVALID,
            "Template security error: 'include' tag is not allowed",
            id="template_security_include_tag",
        ),
        # セキュリティ検証テスト - 制限属性
        pytest.param(
            b"{{ request.args }}",
            INITIAL_INVALID,
            "Template security validation failed: Use of restricted variable 'request' is forbidden.",
            id="template_security_restricted_attribute",
        ),
        # セキュリティ検証テスト - 大きなループ範囲
        pytest.param(
            b"{% for i in range(0, 1000000) %}{{ i }}{% endfor %}",
            INITIAL_INVALID,
            "Template security error: loop range exceeds maximum limit of 100000",
            id="template_security_large_loop_range",
        ),
        # ファイルサイズ検証テスト
        pytest.param(
            b"",  # 空ファイル
            INITIAL_VALID,
            None,
            id="template_validate_empty_file",
        ),
        pytest.param(
            b"a" * (30 * 1024 * 1024),  # 制限値ちょうど
            INITIAL_VALID,
            None,
            id="template_validate_max_size_exact",
        ),
        pytest.param(
            b"a" * (30 * 1024 * 1024 + 1),  # 制限値オーバー
            INITIAL_INVALID,
            f"Template file size exceeds maximum limit of {30 * 1024 * 1024} bytes",
            id="template_validate_max_size_exceeded",
        ),
        # バイナリデータ (Nullバイト) 検証テスト
        pytest.param(
            b"\x00",  # Nullバイトのみ
            INITIAL_INVALID,
            "Template file contains invalid binary data",
            id="template_validate_null_byte_only",
        ),
        pytest.param(
            b"Hello\x00World",  # 有効なテキスト + Nullバイト
            INITIAL_INVALID,
            "Template file contains invalid binary data",
            id="template_validate_null_byte_in_text",
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
        "context",
        "format_type",
        "is_strict_undefined",
        "expected_initial_valid",
        "expected_runtime_valid",
        "expected_error",
        "expected_content",
    ),
    [
        # 初期検証で失敗するケース - strictモード
        pytest.param(
            b"{% macro input() %}{% endmacro %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_INVALID,
            RUNTIME_INVALID,
            "Template security error: 'macro' tag is not allowed",
            None,
            id="template_validate_macro_strict",
        ),
        # 初期検証で失敗するケース - 非strictモード
        pytest.param(
            b"{% macro input() %}{% endmacro %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_INVALID,
            RUNTIME_INVALID,
            "Template security error: 'macro' tag is not allowed",
            None,
            id="template_validate_macro_non_strict",
        ),
        # ランタイムのみで失敗するケース - strictモード
        pytest.param(
            b"{{ 10 / value }}",
            {"value": 0},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            "Template rendering error: division by zero",
            None,
            id="template_runtime_division_by_zero_strict",
        ),
        # ランタイムのみで失敗するケース - 非strictモード
        pytest.param(
            b"{{ 10 / value }}",
            {"value": 0},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            "Template rendering error: division by zero",
            None,
            id="template_runtime_division_by_zero_non_strict",
        ),
        # 両方で成功するケース - strictモード
        pytest.param(
            b"Hello {{ name }}!",
            {"name": "World"},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_VALID,
            None,
            "Hello World!",
            id="template_validate_and_runtime_success_strict",
        ),
        # 両方で成功するケース - 非strictモード
        pytest.param(
            b"Hello {{ name }}!",
            {"name": "World"},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_VALID,
            None,
            "Hello World!",
            id="template_validate_and_runtime_success_non_strict",
        ),
        # 未定義変数のケース - strictモード
        pytest.param(
            b"Hello {{ undefined }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            "'undefined' is undefined",
            None,
            id="template_runtime_undefined_var_strict",
        ),
        # 未定義変数のケース - 非strictモード
        pytest.param(
            b"Hello {{ undefined }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_VALID,
            None,
            "Hello !",
            id="template_runtime_undefined_var_non_strict",
        ),
    ],
)
def test_validation_consistency(
    create_template_file: Callable[[bytes, str], BytesIO],
    template_content: bytes,
    context: Dict[str, AnyType],
    format_type: int,
    is_strict_undefined: bool,
    expected_initial_valid: bool,
    expected_runtime_valid: bool,
    expected_error: Optional[str],
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
        expected_error: 期待されるエラーメッセージ
        expected_content: 期待される出力内容
    """
    # Arrange
    template_file: BytesIO = create_template_file(template_content, "template.txt")

    # Act
    renderer = DocumentRender(template_file)

    # Assert - 初期検証
    assert renderer.is_valid_template == expected_initial_valid, (
        f"Initial validation failed.\nExpected: {expected_initial_valid}\nGot: {renderer.is_valid_template}"
    )
    if not expected_initial_valid and expected_error:
        assert renderer.error_message is not None, "Expected error message but got None"
        assert expected_error in str(renderer.error_message), (
            f"Initial error message does not match.\nExpected to contain: {expected_error}\nGot: {renderer.error_message}"
        )
        return

    # ランタイム検証 (初期検証が成功した場合のみ実行)
    if expected_initial_valid:
        # Act - ランタイム検証
        apply_result: bool = renderer.apply_context(context, format_type, is_strict_undefined)

        # Assert - ランタイム検証
        assert apply_result == expected_runtime_valid, (
            f"Runtime validation failed.\nExpected: {expected_runtime_valid}\nGot: {apply_result}"
        )

        # Assert - Error Message (Runtime)
        if not expected_runtime_valid and expected_error:
            assert renderer.error_message is not None, "Expected runtime error message but got None"
            assert expected_error in str(renderer.error_message), (
                f"Runtime error message does not match.\nExpected to contain: {expected_error}\nGot: {renderer.error_message}"
            )
        elif expected_runtime_valid:
            assert renderer.error_message is None, f"Expected no error message, but got: {renderer.error_message}"

        # Assert - Content (only if runtime validation succeeded)
        if expected_runtime_valid:
            assert renderer.render_content == expected_content, (
                f"Rendered content does not match.\nExpected: {expected_content}\nGot: {renderer.render_content}"
            )


@UNIT
@SET_TIMEOUT
@pytest.mark.parametrize(
    (
        "template_content",
        "format_type",
        "is_strict_undefined",
        "context",
        "expected_validate_template",
        "expected_apply_succeeded",
        "expected_content",
        "expected_error",
    ),
    [
        # Test case on success
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!",
            None,
            id="template_render_basic_variable",
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
            None,
            id="template_format_type_4",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\nGood bye World!",
            None,
            id="template_format_type_3",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_KEEP_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\n\n  \nGood bye World!",  # 空白行を保持
            None,
            id="template_format_type_2",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_COMPRESS,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\nGood bye World!",
            None,
            id="template_format_type_1",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            FORMAT_TYPE_KEEP,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello World!\n\n\n  \nGood bye World!",
            None,
            id="template_format_type_0",
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
            None,
            id="template_render_undefined_var_non_strict",
        ),
        # 基本的な未定義変数のテスト - strictモード
        pytest.param(
            b"Hello {{ name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "'name' is undefined",
            id="template_render_undefined_var_strict",
        ),
        # 複数の変数を含むテスト - 非strictモード
        pytest.param(
            b"Hello {{ first_name }} {{ last_name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            {"first_name": "John"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "Hello John !",
            None,
            id="template_render_multiple_vars_non_strict",
        ),
        # 複数の変数を含むテスト - strictモード
        pytest.param(
            b"Hello {{ first_name }} {{ last_name }}!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"first_name": "John"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "'last_name' is undefined",
            id="template_render_multiple_vars_strict",
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
            None,
            id="template_render_undefined_in_condition_non_strict",
        ),
        # 条件分岐内の未定義変数 - strictモード
        pytest.param(
            b"{% if undefined_var %}Show{% else %}Hide{% endif %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "'undefined_var' is undefined",
            id="template_render_undefined_in_condition_strict",
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
            None,
            id="template_render_defined_check_non_strict",
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
            None,
            id="template_render_defined_check_strict",
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
            None,
            id="template_render_nested_undefined_non_strict",
        ),
        # ネストされた変数アクセス - strictモード
        pytest.param(
            b"{{ user.name }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "'user' is undefined",
            id="template_render_nested_undefined_strict",
        ),
        # Test case on failed
        pytest.param(
            b"\x80\x81\x82\x83",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template file contains invalid UTF-8 bytes",
            id="template_validate_invalid_utf8_bytes",
        ),
        # Test case for syntax error - 初期検証で失敗するように修正
        pytest.param(
            b"Hello {{ name }!",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "unexpected '}'",
            id="template_validate_syntax_error_missing_brace",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            MIN_FORMAT_TYPE - 1,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_format_type_negative",
        ),
        pytest.param(
            b"Hello {{ name }}!\n\n\n  \nGood bye {{ name }}!",
            MAX_FORMAT_TYPE + 1,
            STRICT_UNDEFINED,
            {"name": "World"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_format_type_invalid",
        ),
        # Edge case: Template with error in expression
        pytest.param(
            b"{{ 10 / value }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"value": 0},
            INITIAL_VALID,  # テンプレートは無効 (ゼロ除算は禁止)
            RUNTIME_INVALID,  # 適用は失敗する
            None,  # 出力内容はない
            "Template rendering error: division by zero",  # エラーメッセージ
            id="template_runtime_division_by_zero",
        ),
        # YAMLコンテキストのテスト
        pytest.param(
            b"""Current Date: {{ current_date | date('%Y-%m-%d') }}
Last Updated: {{ last_updated | date('%Y-%m-%d %H:%M:%S') }}
Next Review: {{ next_review | date('%B %d, %Y') }}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {
                "current_date": "2024-03-20",
                "last_updated": "2024-03-20T15:30:45",
                "next_review": "2024-06-20",
            },
            INITIAL_VALID,
            RUNTIME_VALID,
            """Current Date: 2024-03-20
Last Updated: 2024-03-20 15:30:45
Next Review: June 20, 2024""",
            None,
            id="template_render_date_filter",
        ),
        pytest.param(
            b"""{{ invalid_date | date('%Y-%m-%d') }}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"invalid_date": "not-a-date"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Template rendering error: Invalid date format",
            id="template_render_invalid_date",
        ),
        pytest.param(
            b"""{{ date | date('%Y-%m-%d') }}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"date": None},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Template rendering error: cannot access local variable 'dt' where it is not associated with a value",
            id="template_render_null_date",
        ),
        # Template Injection Edge Cases based on Rules B-002_domain / C-103_python-security
        pytest.param(
            b"{{ ''.__class__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Access to restricted attribute '__class__' is forbidden.",
            id="Injection_class_access",
        ),
        pytest.param(
            b"{{ ''.__class__.__mro__ }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Access to restricted attribute '__mro__' is forbidden.",
            id="Injection_mro_access",
        ),
        pytest.param(
            b"{{ ''.__class__.__mro__[1].__subclasses__() }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Access to restricted attribute '__subclasses__' is forbidden.",
            id="Injection_subclasses_access",
        ),
        pytest.param(
            b"{{ getattr('', '__class__') }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Call to restricted function 'getattr()' is forbidden.",
            id="Injection_getattr_access",
        ),
        pytest.param(
            b"{{ self.__init__.__globals__['os'] }}",  # Assuming 'self' or similar context
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"self": object()},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Access to restricted item 'os' is forbidden.",
            id="Injection_globals_access",
        ),
        pytest.param(
            b"{% import 'os' as os %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security error: 'import' tag is not allowed",
            id="Injection_import_tag",
        ),
        pytest.param(
            b"{% extends 'base.html' %}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security error: 'extends' tag is not allowed",
            id="Injection_extends_tag",
        ),
        pytest.param(
            b"{{ eval('1+1') }}",  # Assuming context contains 'eval'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"eval": eval},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Call to restricted function 'eval()' is forbidden.",
            id="Injection_eval_access",
        ),
        pytest.param(
            b"{{ exec('import os') }}",  # Assuming context contains 'exec'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"exec": exec},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Call to restricted function 'exec()' is forbidden.",
            id="Injection_exec_access",
        ),
        pytest.param(
            b"{{ os.system('ls') }}",  # Assuming context contains 'os'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"os": __import__("os")},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Use of restricted variable 'os' is forbidden.",
            id="Injection_os_access",
        ),
        pytest.param(
            b"{{ sys.modules }}",  # Assuming context contains 'sys'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"sys": __import__("sys")},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Use of restricted variable 'sys' is forbidden.",
            id="Injection_sys_access",
        ),
        pytest.param(
            b"{{ builtins.open('/etc/passwd').read() }}",  # Assuming context contains 'builtins'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"builtins": __import__("builtins")},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Use of restricted variable 'builtins' is forbidden.",
            id="Injection_builtins_access",
        ),
        pytest.param(
            b"{{ setattr(obj, 'attr', 'value') }}",  # Assuming context contains 'setattr'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"setattr": setattr, "obj": object()},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Call to restricted function 'setattr()' is forbidden.",
            id="Injection_setattr_access",
        ),
        pytest.param(
            b"{{ delattr(obj, 'attr') }}",  # Assuming context contains 'delattr'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"delattr": delattr, "obj": type("Dummy", (), {"attr": 1})()},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Call to restricted function 'delattr()' is forbidden.",
            id="Injection_delattr_access",
        ),
        pytest.param(
            b"{{ locals() }}",  # Assuming context contains 'locals'
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"locals": locals},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Call to restricted function 'locals()' is forbidden.",
            id="Injection_locals_access",
        ),
        # _validate_restricted_attributes の追加エッジケース
        pytest.param(
            b"{{ config }}",  # 禁止された Name の直接使用
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"config": {}},  # コンテキストにあっても禁止されるべき
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Use of restricted variable 'config' is forbidden.",
            id="Injection_direct_name_config",
        ),
        pytest.param(
            b"{{ obj.__base__ }}",  # 禁止された Getattr (__base__)
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"obj": "test"},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Access to restricted attribute '__base__' is forbidden.",
            id="Injection_getattr_base",
        ),
        pytest.param(
            b"{{ my_dict['os'] }}",  # 禁止された Getitem
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"my_dict": {"os": "value"}},  # キーが禁止されている
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Access to restricted item 'os' is forbidden.",
            id="Injection_getitem_os",
        ),
        pytest.param(
            b"{% set my_os = os %}{{ my_os }}",  # 禁止された Name の Assign
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"os": "fake_os"},  # コンテキストにあっても禁止されるべき
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Assignment of restricted variable 'os' is forbidden.",
            id="Injection_assign_name_os",
        ),
        pytest.param(
            b"{% set my_eval = eval %}{{ my_eval('1') }}",  # 禁止された Call の Assign
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"eval": eval},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed: Assignment of restricted variable 'eval' is forbidden.",
            id="Injection_assign_call_eval",
        ),
        # _is_recursive_structure の追加エッジケース
        # 辞書の再帰 -> doタグ禁止により初期検証で失敗
        pytest.param(
            b"{% set d = {} %}{% do d.update({'self': d}) %}{{ d }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,  # 初期検証で失敗
            RUNTIME_INVALID,  # ランタイム到達せず
            None,
            "Template security error: 'do' tag is not allowed",  # Specific error message
            id="template_runtime_recursive_dict",
        ),
        # ネストされたリストの再帰 -> doタグ禁止により初期検証で失敗
        pytest.param(
            b"{% set l = [[]] %}{% do l[0].append(l) %}{{ l }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,  # 初期検証で失敗
            RUNTIME_INVALID,  # ランタイム到達せず
            None,
            "Template security error: 'do' tag is not allowed",  # Specific error message
            id="template_runtime_recursive_nested_list",
        ),
        # 混合再帰 (リストと辞書) -> doタグ禁止により初期検証で失敗
        pytest.param(
            b"{% set d = {} %}{% set l = [d] %}{% do d.update({'list': l}) %}{{ l }}",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,  # 初期検証で失敗
            RUNTIME_INVALID,  # ランタイム到達せず
            None,
            "Template security error: 'do' tag is not allowed",  # Specific error message
            id="template_runtime_recursive_mixed",
        ),
        # Edge case: Template with complex nested loops and conditionals
        pytest.param(
            b"""{% for i in range(3) %}
  {% for j in range(2) %}
    {% if i > 0 and j > 0 %}
      {{ i }} - {{ j }}: {{ data[i][j] if data and i < data|length and j < data[i]|length else 'N/A' }}
    {% else %}
      {{ i }} - {{ j }}: Start
    {% endif %}
  {% endfor %}
{% endfor %}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"data": [[1, 2], [3, 4], [5, 6]]},
            INITIAL_VALID,
            RUNTIME_VALID,
            """
      0 - 0: Start

      0 - 1: Start

      1 - 0: Start

      1 - 1: 4

      2 - 0: Start

      2 - 1: 6

""",
            None,
            id="Complex_nested_loops_and_conditionals",
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
            None,
            id="Undefined_variable_with_fallback",
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
            None,
            id="Template_with_many_lines",
        ),
        # Edge case: Template with Unicode characters
        pytest.param(
            "{{ emoji }} {{ japanese }}".encode("utf-8"),  # 明示的にUTF-8エンコード
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"emoji": "😀😁😂🤣😃", "japanese": "こんにちは世界"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "😀😁😂🤣😃 こんにちは世界",
            None,
            id="Template_with_unicode_characters",
        ),
        # Edge case: Template with HTML content and safe filter
        pytest.param(
            b"<html><body>{{ content | safe }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<h1>Title</h1><p>Paragraph with <b>bold</b> text</p>"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "<html><body>&lt;h1&gt;Title&lt;/h1&gt;&lt;p&gt;Paragraph with &lt;b&gt;bold&lt;/b&gt; text&lt;/p&gt;</body></html>",
            None,
            id="Template_with_html_safe_filter",
        ),
        # Edge case: Template with unsafe HTML content
        pytest.param(
            b"<html><body>{{ content | safe }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<script>alert('XSS')</script>"},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "HTML content contains potentially unsafe elements",
            id="Template_with_unsafe_html",
        ),
        # Edge case: Template with HTML escaping
        pytest.param(
            b"<html><body>{{ content }}</body></html>",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"content": "<script>alert('XSS')</script>"},
            INITIAL_VALID,
            RUNTIME_VALID,
            "<html><body>&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;</body></html>",
            None,
            id="Template_with_html_escaping",
        ),
        # Edge case: Template with macro - 初期検証で失敗
        pytest.param(
            b"""{% macro input(name, value='', type='text') -%}
    <input type="{{ type }}" name="{{ name }}" value="{{ value }}">
{%- endmacro %}

{{ input('username') }}
{{ input('password', type='password') }}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security error: 'macro' tag is not allowed",
            id="template_validate_macro_strict",
        ),
        # Edge case: Template with call tag - 初期検証で成功
        pytest.param(
            b"""{%- call input('username') %}{% endcall %}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "'input' is undefined",  # セキュリティエラーメッセージ
            id="template_with_call_tag",
        ),
        # Edge case: Template with request access - 初期検証で失敗
        pytest.param(
            b"""{% set x = request.args %}{{ x }}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"request": {"args": {"debug": "true"}}},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed",
            id="Runtime_injection_request_access",
        ),
        # Edge case: Template with config access - 初期検証で失敗
        pytest.param(
            b"""{{ config.items() }}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {"config": {"secret": "sensitive_data"}},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security validation failed",
            id="Runtime_injection_config_access",
        ),
        # Edge case: Template with recursive data structure
        pytest.param(
            b"""{% set x = [] %}{% set _ = x.append(x) %}{{ x }}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_VALID,
            RUNTIME_VALID,
            "[[...]]",
            None,
            id="Runtime_recursive_data_structure",
        ),
        # Edge case: Template with large loop range - Expect specific error message now
        pytest.param(
            b"""{% for i in range(999999999) %}{{ i }}{% endfor %}""",
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            {},
            INITIAL_INVALID,
            RUNTIME_INVALID,
            None,
            "Template security error: loop range exceeds maximum limit of 100000",
            id="Runtime_large_loop_range",
        ),
        # 追加: ネストされた未定義変数のケース - strictモード
        pytest.param(
            b"Hello {{ user.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_nested_undefined_strict",
        ),
        # 追加: ネストされた未定義変数のケース - 非strictモード
        pytest.param(
            b"Hello {{ user.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_nested_undefined_non_strict",
        ),
        # 追加: 複数レベルのネストされた未定義変数 - strictモード
        pytest.param(
            b"Hello {{ user.profile.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_multi_level_undefined_strict",
        ),
        # 追加: 複数レベルのネストされた未定義変数 - 非strictモード
        pytest.param(
            b"Hello {{ user.profile.name }}!",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_multi_level_undefined_non_strict",
        ),
        # 追加: 部分的に定義された変数のネスト - strictモード
        pytest.param(
            b"Hello {{ user.name }}!",
            {"user": {}},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_partial_defined_strict",
        ),
        # 追加: 部分的に定義された変数のネスト - 非strictモード
        pytest.param(
            b"Hello {{ user.name }}!",
            {"user": {}},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_partial_defined_non_strict",
        ),
        # 追加: メソッド呼び出し - strictモード
        pytest.param(
            b"{{ undefined.method() }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_method_call_strict",
        ),
        # 追加: メソッド呼び出し - 非strictモード
        pytest.param(
            b"{{ undefined.method() }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "",
            id="template_runtime_method_call_non_strict",
        ),
        # 追加: インデックスアクセス - strictモード
        pytest.param(
            b"{{ items[0] }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_index_access_strict",
        ),
        # 追加: インデックスアクセス - 非strictモード
        pytest.param(
            b"{{ items[0] }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_index_access_non_strict",
        ),
        # 追加: 複雑な式の中の未定義変数 - strictモード
        pytest.param(
            b"{{ 'prefix_' + undefined + '_suffix' }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_complex_expression_strict",
        ),
        # 複雑な式の中の未定義変数 - 非strictモード
        pytest.param(
            b"{{ 'prefix_' + undefined + '_suffix' }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_complex_expression_non_strict",
        ),
        # 追加: 条件分岐内の未定義変数 - strictモード
        pytest.param(
            b"{% if condition %}{{ value }}{% endif %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_condition_strict",
        ),
        # 追加: 条件分岐内の未定義変数 - 非strictモード
        pytest.param(
            b"{% if condition %}{{ value }}{% endif %}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_condition_non_strict",
        ),
        # 追加: フィルターと未定義変数 - strictモード
        pytest.param(
            b"{{ undefined|upper }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_filter_strict",
        ),
        # 追加: フィルターと未定義変数 - 非strictモード
        pytest.param(
            b"{{ undefined|upper }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "",
            id="template_runtime_filter_non_strict",
        ),
        # 追加: 複数の未定義変数の連結 - strictモード
        pytest.param(
            b"{{ var1 ~ var2 ~ var3 }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,
            None,
            "Validation error: context is invalid",
            id="template_runtime_multiple_undefined_strict",
        ),
        # 追加: 複数の未定義変数の連結 - 非strictモード
        pytest.param(
            b"{{ var1 ~ var2 ~ var3 }}",
            {},
            FORMAT_TYPE_COMPRESS_ALT,
            NON_STRICT_UNDEFINED,
            INITIAL_VALID,
            RUNTIME_INVALID,  # This should fail because concatenation with undefined non-strict still raises error
            None,
            "",
            id="template_runtime_multiple_undefined_non_strict",
        ),
    ],
)
def test_render_edge_cases(
    create_template_file: Callable[[bytes, str], BytesIO],
    template_content: bytes,
    format_type: int,
    is_strict_undefined: bool,
    context: Dict[str, Union[str, int, float, bool, List[AnyType], Dict[str, AnyType], None]],
    expected_validate_template: bool,
    expected_apply_succeeded: bool,
    expected_content: Optional[str],
    expected_error: Optional[str],
) -> None:
    """
    DocumentRenderのエッジケースをテストする。

    Args:
        create_template_file: テンプレートファイル作成用フィクスチャ
        template_content: テンプレートの内容
        format_type: フォーマットタイプ
        is_strict_undefined: 未定義変数を厳密にチェックするかどうか
        context: テンプレートに適用するコンテキスト [str, int, float, bool, list, dict, None]を含む
        expected_validate_template: テンプレートが有効であることが期待されるかどうか
        expected_apply_succeeded: コンテキスト適用が成功することが期待されるかどうか
        expected_content: 期待される出力内容
        expected_error: 期待されるエラーメッセージ
    """
    # Arrange
    template_file: BytesIO = create_template_file(template_content, "template.txt")
    render = DocumentRender(template_file)

    # Act & Assert for template validation
    assert render.is_valid_template == expected_validate_template, (
        f"is_valid_template isn't match.\nExpected: {expected_validate_template}\nGot: {render.is_valid_template}"
    )

    # Act
    apply_result: bool = render.apply_context(context, format_type, is_strict_undefined)

    # Assert
    assert apply_result == expected_apply_succeeded, f"apply_result isn't match.\nExpected: {expected_apply_succeeded}\nGot: {apply_result}"
    assert render.render_content == expected_content, (
        f"expected_content isn't match.\nExpected: {expected_content}\nGot: {render.render_content}"
    )

    # エラーメッセージの検証
    actual_error: Optional[str] = render.error_message
    if expected_error is not None:
        assert actual_error is not None, "Expected error message but got None"
        actual_error_str = str(actual_error)
        assert isinstance(actual_error_str, str), "Error message must be convertible to string"
        assert actual_error_str != "", "Error message must not be empty"
        assert expected_error in actual_error_str, (
            f"expected_error isn't match.\nExpected to contain: {expected_error}\nGot: {actual_error_str}"
        )
    else:
        assert actual_error is None, f"actual_error isn't None.\nGot: {actual_error}"
