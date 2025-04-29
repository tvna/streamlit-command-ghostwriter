from typing import Any, Dict, Final, Mapping, Union, cast

import pytest
from _pytest.mark.structures import MarkDecorator

from i18n import LANGUAGES

UNIT: MarkDecorator = pytest.mark.unit


@UNIT
def test_i18n_japanese() -> None:
    """日本語の言語辞書の構造をテストする。

    日本語の言語辞書が正しい構造を持っていることを確認します。
    すべてのキーと値が適切な型であることを検証します。
    """
    # Arrange
    japanese_key: Final[str] = "日本語"

    # Act & Assert
    assert isinstance(LANGUAGES, dict), "LANGUAGES should be a dictionary"
    assert japanese_key in LANGUAGES.keys(), f"Japanese key '{japanese_key}' not found in LANGUAGES"

    for nest1_key, nest1_val in LANGUAGES[japanese_key].items():
        assert isinstance(nest1_key, str), f"First level key '{nest1_key}' should be a string"
        assert isinstance(nest1_val, dict), f"First level value for key '{nest1_key}' should be a dictionary"
        for nest2_key, nest2_val in nest1_val.items():
            assert isinstance(nest2_key, str), f"Second level key '{nest2_key}' should be a string"
            assert isinstance(nest2_val, (str, dict)), f"Second level value for key '{nest2_key}' should be a string or dictionary"
            if isinstance(nest2_val, dict):
                for nest3_key, nest3_val in nest2_val.items():
                    assert isinstance(nest3_key, int), f"Third level key '{nest3_key}' should be an integer"
                    assert isinstance(nest3_val, str), f"Third level value for key '{nest3_key}' should be a string"


@UNIT
def test_i18n_structure_consistency() -> None:
    """すべての言語辞書が同じ構造を持っていることをテストする。

    すべての言語辞書が同じトップレベルのキー、セクションキー、
    およびネストされた辞書構造を持っていることを確認します。
    """
    # Arrange
    lang_name: str
    lang_dict: Dict[str, Any]
    section_key: str
    key: str
    value: Union[str, Dict[str, Any]]

    reference_lang: Final[Mapping[str, Any]] = next(iter(LANGUAGES.values()))

    # Act & Assert
    for lang_name, lang_dict in LANGUAGES.items():
        assert set(lang_dict.keys()) == set(reference_lang.keys()), f"Language {lang_name} has different top-level keys"

        # Check that all second-level dictionaries have the same keys
        for section_key, section_dict in lang_dict.items():
            assert isinstance(section_dict, dict), f"Value for {section_key} in {lang_name} is not a dict"
            ref_section = reference_lang[section_key]
            assert isinstance(ref_section, dict), f"Reference section {section_key} is not a dict, inconsistency detected."
            assert set(section_dict.keys()) == set(ref_section.keys()), f"Section {section_key} in {lang_name} has different keys"

            # Check nested dictionaries (like format_type_items)
            for key, value in section_dict.items():
                if isinstance(value, dict):
                    assert isinstance(ref_section[key], dict), f"Ref value for {key} in {section_key} is not a dict"
                    ref_nested_dict = cast("Dict[int, str]", ref_section[key])
                    assert set(value.keys()) == set(ref_nested_dict.keys()), (
                        f"Nested dict {key} in {section_key}.{lang_name} has different keys"
                    )


@UNIT
def test_i18n_no_empty_strings() -> None:
    """言語辞書に空の文字列がないことをテストする。

    すべての言語辞書のすべての文字列値が空でないことを確認します。
    これには、ネストされた辞書内の文字列も含まれます。
    """
    # Arrange & Act & Assert
    lang_name: str
    lang_dict: Dict[str, Any]
    section_key: str
    key: str
    value: Union[str, Dict[str, Any]]

    for lang_name, lang_dict in LANGUAGES.items():
        for section_key, section_dict in lang_dict.items():
            assert isinstance(section_dict, dict), f"Value for {section_key} in {lang_name} is not a dict"
            for key, value in section_dict.items():
                if isinstance(value, str):
                    assert value.strip() != "", f"Empty string found at {lang_name}.{section_key}.{key}"
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        assert str(subvalue).strip() != "", f"Empty string found at {lang_name}.{section_key}.{key}.{subkey}"


@UNIT
@pytest.mark.parametrize(
    ("unsafe_pattern"),
    [
        pytest.param("{0}", id="i18n_validate_format_index_0"),
        pytest.param("{1}", id="i18n_validate_format_index_1"),
        pytest.param("%s", id="i18n_validate_c_style_string"),
        pytest.param("%d", id="i18n_validate_c_style_integer"),
    ],
)
def test_i18n_string_interpolation_safety(unsafe_pattern: str) -> None:
    """文字列に安全でない補間パターンが含まれていないことをテストする。

    すべての言語辞書の文字列に、安全でない補間パターン({0}、{1}、%s、%dなど)
    が含まれていないことを確認します。
    """

    lang_name: str
    lang_dict: Dict[str, Any]
    section_key: str
    key: str
    value: Union[str, Dict[str, Any]]
    subkey: str
    subvalue: Union[str, Dict[str, Any]]

    # Arrange & Act & Assert
    for lang_name, lang_dict in LANGUAGES.items():
        for section_key, section_dict in lang_dict.items():
            assert isinstance(section_dict, dict), f"Value for {section_key} in {lang_name} is not a dict"
            for key, value in section_dict.items():
                if isinstance(value, str):
                    assert unsafe_pattern not in value, f"Unsafe pattern {unsafe_pattern} found in {lang_name}.{section_key}.{key}"
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, str):
                            assert unsafe_pattern not in subvalue, (
                                f"Unsafe pattern {unsafe_pattern} found in {lang_name}.{section_key}.{key}.{subkey}"
                            )
