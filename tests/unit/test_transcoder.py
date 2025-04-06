from io import BytesIO
from typing import Callable, Final, Optional

import pytest
from _pytest.mark.structures import MarkDecorator

from features.transcoder import TextTranscoder

UNIT: MarkDecorator = pytest.mark.unit


@pytest.fixture
def create_text_file() -> Callable[[str, str, str], BytesIO]:
    """テスト用のテキストファイルを作成するフィクスチャ。

    Returns:
        Callable[[str, str, str], BytesIO]: テキストファイルを作成する関数
    """

    def _create_file(content: str, encoding: str, filename: str = "example.txt") -> BytesIO:
        file: Final[BytesIO] = BytesIO(content.encode(encoding))
        file.name = filename
        return file

    return _create_file


@pytest.fixture
def create_binary_file() -> Callable[[bytes, str], BytesIO]:
    """テスト用のバイナリファイルを作成するフィクスチャ。

    Returns:
        Callable[[bytes, str], BytesIO]: バイナリファイルを作成する関数
    """

    def _create_file(content: bytes, filename: str = "example.bin") -> BytesIO:
        file: Final[BytesIO] = BytesIO(content)
        file.name = filename
        return file

    return _create_file


@UNIT
@pytest.mark.parametrize(
    ("input_str", "input_encoding", "expected_encoding", "expected_result"),
    [
        pytest.param("ABCDEF", "Shift_JIS", "ASCII", "ABCDEF", id="encoding_convert_ascii_from_shift_jis"),
        pytest.param("ABCDEF", "Shift-JIS", "ASCII", "ABCDEF", id="encoding_convert_ascii_from_shift_jis_hyphen"),
        pytest.param("ABCDEF", "EUC-JP", "ASCII", "ABCDEF", id="encoding_convert_ascii_from_euc_jp"),
        pytest.param("ABCDEF", "EUC_JP", "ASCII", "ABCDEF", id="encoding_convert_ascii_from_euc_jp_underscore"),
        pytest.param("ABCDEF", "utf-8", "ASCII", "ABCDEF", id="encoding_convert_ascii_from_utf8"),
        pytest.param("ABCDEF", "utf_8", "ASCII", "ABCDEF", id="encoding_convert_ascii_from_utf8_underscore"),
        pytest.param("", "Shift_JIS", "ASCII", "", id="encoding_convert_empty_from_shift_jis"),
        pytest.param("", "Shift-JIS", "ASCII", "", id="encoding_convert_empty_from_shift_jis_hyphen"),
        pytest.param("", "EUC_JP", "ASCII", "", id="encoding_convert_empty_from_euc_jp"),
        pytest.param("", "EUC-JP", "ASCII", "", id="encoding_convert_empty_from_euc_jp_hyphen"),
        pytest.param("", "utf-8", "ASCII", "", id="encoding_convert_empty_from_utf8"),
        pytest.param("", "utf_8", "ASCII", "", id="encoding_convert_empty_from_utf8_underscore"),
        pytest.param("あいうえお", "Shift_JIS", "Shift_JIS", "あいうえお", id="encoding_convert_hiragana_from_shift_jis"),
        pytest.param("あいうえお", "Shift-JIS", "Shift_JIS", "あいうえお", id="encoding_convert_hiragana_from_shift_jis_hyphen"),
        pytest.param("あいうえお", "EUC-JP", "EUC-JP", "あいうえお", id="encoding_convert_hiragana_from_euc_jp"),
        pytest.param("あいうえお", "EUC_JP", "EUC-JP", "あいうえお", id="encoding_convert_hiragana_from_euc_jp_underscore"),
        pytest.param("あいうえお", "utf-8", "utf-8", "あいうえお", id="encoding_convert_hiragana_from_utf8"),
        pytest.param("あいうえお", "utf_8", "utf-8", "あいうえお", id="encoding_convert_hiragana_from_utf8_underscore"),
        pytest.param("漢字による試験", "Shift_JIS", "Shift_JIS", "漢字による試験", id="encoding_convert_kanji_from_shift_jis"),
        pytest.param("漢字による試験", "Shift-JIS", "Shift_JIS", "漢字による試験", id="encoding_convert_kanji_from_shift_jis_hyphen"),
        pytest.param("漢字による試験", "EUC-JP", "EUC-JP", "漢字による試験", id="encoding_convert_kanji_from_euc_jp"),
        pytest.param("漢字による試験", "EUC_JP", "EUC-JP", "漢字による試験", id="encoding_convert_kanji_from_euc_jp_underscore"),
        pytest.param("漢字による試験", "utf-8", "utf-8", "漢字による試験", id="encoding_convert_kanji_from_utf8"),
        pytest.param("漢字による試験", "utf_8", "utf-8", "漢字による試験", id="encoding_convert_kanji_from_utf8_underscore"),
    ],
)
def test_transcoder_basic_functionality(
    create_text_file: Callable[[str, str, str], BytesIO], input_str: str, input_encoding: str, expected_encoding: str, expected_result: str
) -> None:
    """TextTranscoderの基本機能をテストする。

    Args:
        create_text_file: テキストファイル作成用フィクスチャ
        input_str: 入力文字列
        input_encoding: 入力エンコーディング
        expected_encoding: 期待されるエンコーディング
        expected_result: 期待される結果
    """
    # Arrange
    import_file: Final[BytesIO] = create_text_file(input_str, input_encoding, "example.csv")

    # Act
    transcoder: Final[TextTranscoder] = TextTranscoder(import_file)
    detected_encoding: Final[Optional[str]] = transcoder.detect_encoding()
    export_file_deny_fallback: Final[Optional[BytesIO]] = transcoder.convert(is_allow_fallback=False)
    export_file_allow_fallback: Final[Optional[BytesIO]] = transcoder.convert(is_allow_fallback=True)

    # Assert
    assert detected_encoding == expected_encoding, f"Encoding detection mismatch.\nExpected: {expected_encoding}\nGot: {detected_encoding}"

    assert isinstance(export_file_deny_fallback, BytesIO), "Export file with deny fallback should be BytesIO instance"
    if isinstance(export_file_deny_fallback, BytesIO):
        assert export_file_deny_fallback.read().decode("utf-8") == expected_result, (
            f"Content mismatch with deny fallback. Expected: {expected_result}, Got: {export_file_deny_fallback.read().decode('utf-8')}"
        )
        assert export_file_deny_fallback.name == import_file.name, (
            f"Filename mismatch with deny fallback. Expected: {import_file.name}, Got: {export_file_deny_fallback.name}"
        )

    assert isinstance(export_file_allow_fallback, BytesIO), "Export file with allow fallback should be BytesIO instance"
    if isinstance(export_file_allow_fallback, BytesIO):
        decoded_content: Final[str] = export_file_allow_fallback.getvalue().decode("utf-8")
        assert decoded_content == expected_result, (
            f"Content mismatch with allow fallback.\nExpected: {expected_result}\nGot: {decoded_content}"
        )
        assert export_file_allow_fallback.name == import_file.name, (
            f"Filename mismatch with allow fallback.\nExpected: {import_file.name}\nGot: {export_file_allow_fallback.name}"
        )


@UNIT
@pytest.mark.parametrize(
    ("input_bytes", "expected_encoding", "expected_result"),
    [
        pytest.param(b"\x00\x01\x02\x03\x04", None, b"\x00\x01\x02\x03\x04", id="binary_detect_control_chars"),
        pytest.param(b"\x80\x81\x82\x83", None, b"\x80\x81\x82\x83", id="binary_detect_high_ascii"),
        pytest.param(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01",
            None,
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01",
            id="binary_detect_png_header",
        ),
    ],
)
def test_transcoder_non_string_data(
    create_binary_file: Callable[[bytes, str], BytesIO], input_bytes: bytes, expected_encoding: Optional[str], expected_result: bytes
) -> None:
    """非文字列データに対するTextTranscoderの動作をテストする。

    Args:
        create_binary_file: バイナリファイル作成用フィクスチャ
        input_bytes: 入力バイトデータ
        expected_encoding: 期待されるエンコーディング
        expected_result: 期待される結果
    """
    # Arrange
    import_file: Final[BytesIO] = create_binary_file(input_bytes, "example.csv")

    # Act
    transcoder: Final[TextTranscoder] = TextTranscoder(import_file)
    detected_encoding: Final[Optional[str]] = transcoder.detect_encoding()
    export_file_deny_fallback: Final[Optional[BytesIO]] = transcoder.convert(is_allow_fallback=False)
    export_file_allow_fallback: Final[Optional[BytesIO]] = transcoder.convert(is_allow_fallback=True)

    # Assert
    assert detected_encoding == expected_encoding, f"Encoding detection mismatch.\nExpected: {expected_encoding}\nGot: {detected_encoding}"
    assert export_file_deny_fallback is None, "Export file with deny fallback should be None for binary data"

    assert isinstance(export_file_allow_fallback, BytesIO), "Export file with allow fallback should be BytesIO instance"
    if isinstance(export_file_allow_fallback, BytesIO):
        assert export_file_allow_fallback.getvalue() == expected_result, (
            f"Binary content mismatch with allow fallback.\nExpected: {expected_result}\nGot: {export_file_allow_fallback.getvalue()}"
        )
        assert export_file_allow_fallback.name == import_file.name, (
            f"Filename mismatch with allow fallback.\nExpected: {import_file.name}\nGot: {export_file_allow_fallback.name}"
        )


@UNIT
@pytest.mark.parametrize(
    ("input_str", "input_encoding", "expected_encoding", "expected_result"),
    [
        pytest.param("A" * 100, "utf-8", "ASCII", "A" * 100, id="encoding_convert_long_ascii_string"),
        pytest.param("Hello, 世界! こんにちは!", "utf-8", "utf-8", "Hello, 世界! こんにちは!", id="encoding_convert_mixed_ascii_non_ascii"),
        pytest.param("   \t\n\r   ", "utf-8", "ASCII", "   \t\n\r   ", id="encoding_convert_whitespace_only"),
        pytest.param(
            "\x00\x01\x02\x03\x04\x05Hello", "utf-8", None, "\x00\x01\x02\x03\x04\x05Hello", id="encoding_detect_control_chars_with_text"
        ),
        pytest.param("😀😁😂🤣😃😄😅", "utf-8", "utf-8", "😀😁😂🤣😃😄😅", id="encoding_convert_emoji_only"),
        pytest.param("Hello 😀 World 🌍", "utf-8", "utf-8", "Hello 😀 World 🌍", id="encoding_convert_mixed_emoji_text"),
        pytest.param("", "utf-8", "ASCII", "", id="encoding_convert_empty_string"),
        pytest.param("a", "utf-8", "ASCII", "a", id="encoding_convert_single_char"),
        pytest.param("あ" * 1000, "utf-8", "utf-8", "あ" * 1000, id="encoding_convert_long_non_ascii"),
        pytest.param("\u0300\u0301\u0302", "utf-8", "utf-8", "\u0300\u0301\u0302", id="encoding_convert_combining_marks"),
        pytest.param("\u200b\u200c\u200d", "utf-8", "utf-8", "\u200b\u200c\u200d", id="encoding_convert_zero_width_chars"),
        pytest.param("\u0009\u000a\u000d\u0020", "utf-8", "ASCII", "\u0009\u000a\u000d\u0020", id="encoding_convert_whitespace_chars"),
        pytest.param("Hello\u0000World", "utf-8", None, "Hello\u0000World", id="encoding_detect_null_char"),
        pytest.param("\ufeff Hello World", "utf-8", "utf-8", "\ufeff Hello World", id="encoding_convert_with_bom"),
        pytest.param("表\u309a", "utf-8", "utf-8", "表\u309a", id="encoding_convert_combining_sound_marks"),
    ],
)
def test_transcoder_edge_cases(
    create_text_file: Callable[[str, str, str], BytesIO],
    input_str: str,
    input_encoding: str,
    expected_encoding: Optional[str],
    expected_result: str,
) -> None:
    """エッジケースでのTextTranscoderの動作をテストする。

    Args:
        create_text_file: テキストファイル作成用フィクスチャ
        input_str: 入力文字列
        input_encoding: 入力エンコーディング
        expected_encoding: 期待されるエンコーディング
        expected_result: 期待される結果
    """
    # Arrange
    import_file: Final[BytesIO] = create_text_file(input_str, input_encoding, "example.txt")

    # Act
    transcoder: Final[TextTranscoder] = TextTranscoder(import_file)
    detected_encoding: Final[Optional[str]] = transcoder.detect_encoding()

    # Assert
    assert detected_encoding == expected_encoding, f"Encoding detection mismatch.\nExpected: {expected_encoding}\nGot: {detected_encoding}"

    # 期待されるエンコーディングがNoneの場合は、変換結果のチェックをスキップ
    if expected_encoding is not None:
        # Act
        export_file: Final[Optional[BytesIO]] = transcoder.convert(is_allow_fallback=True)

        # Assert
        assert isinstance(export_file, BytesIO), "Export file should be BytesIO instance"
        if isinstance(export_file, BytesIO):
            assert export_file.getvalue().decode("utf-8") == expected_result, (
                f"Content mismatch.\nExpected: {expected_result}\nGot: {export_file.getvalue().decode('utf-8')}"
            )
            assert export_file.name == import_file.name, f"Filename mismatch.\nExpected: {import_file.name}\nGot: {export_file.name}"


@UNIT
@pytest.mark.parametrize(
    ("input_bytes", "expected_encoding", "expected_result"),
    [
        pytest.param(b"%PDF-1.5\n%\xd0\xd0\xd0\xd0\n", "Shift_JIS", b"%PDF-1.5\n%\xd0\xd0\xd0\xd0\n", id="binary_detect_pdf_header"),
        pytest.param(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00", None, b"\xff\xd8\xff\xe0\x00\x10JFIF\x00", id="binary_detect_jpeg_header"),
        pytest.param(b"GIF89a\x01\x00\x01\x00\x80\x00\x00", None, b"GIF89a\x01\x00\x01\x00\x80\x00\x00", id="binary_detect_gif_header"),
        pytest.param(b"PK\x03\x04\x14\x00\x00\x00\x08\x00", None, b"PK\x03\x04\x14\x00\x00\x00\x08\x00", id="binary_detect_zip_header"),
        pytest.param(bytes([i % 256 for i in range(100)]), None, bytes([i % 256 for i in range(100)]), id="binary_detect_random_bytes"),
        pytest.param(b"", "ASCII", b"", id="binary_detect_empty_data"),
        pytest.param(b"\x00", None, b"\x00", id="binary_detect_single_null"),
        pytest.param(b"\xff" * 1000, "ISO-8859-1", b"\xff" * 1000, id="binary_detect_large_binary"),
        pytest.param(b"\xef\xbb\xbfHello", "utf-8", b"\xef\xbb\xbfHello", id="binary_detect_utf8_bom"),
        pytest.param(b"\xff\xfeH\x00e\x00l\x00l\x00o\x00", None, b"\xff\xfeH\x00e\x00l\x00l\x00o\x00", id="binary_detect_utf16_le_bom"),
        pytest.param(b"\xfe\xff\x00H\x00e\x00l\x00l\x00o", None, b"\xfe\xff\x00H\x00e\x00l\x00l\x00o", id="binary_detect_utf16_be_bom"),
        pytest.param(
            b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x00", None, b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x00", id="binary_detect_gzip_header"
        ),
        pytest.param(b"\x7f\x45\x4c\x46\x02\x01\x01\x00", None, b"\x7f\x45\x4c\x46\x02\x01\x01\x00", id="binary_detect_elf_header"),
    ],
)
def test_transcoder_binary_edge_cases(
    create_binary_file: Callable[[bytes, str], BytesIO], input_bytes: bytes, expected_encoding: Optional[str], expected_result: bytes
) -> None:
    """バイナリデータのエッジケースでのTextTranscoderの動作をテストする。

    Args:
        create_binary_file: バイナリファイル作成用フィクスチャ
        input_bytes: 入力バイトデータ
        expected_encoding: 期待されるエンコーディング
        expected_result: 期待される結果
    """
    # Arrange
    import_file: Final[BytesIO] = create_binary_file(input_bytes, "example.bin")

    # Act
    transcoder: Final[TextTranscoder] = TextTranscoder(import_file)
    detected_encoding: Final[Optional[str]] = transcoder.detect_encoding()

    # Assert
    assert detected_encoding == expected_encoding, f"Encoding detection mismatch.\nExpected: {expected_encoding}\nGot: {detected_encoding}"

    # Act
    result: Final[Optional[BytesIO]] = transcoder.convert()

    # Assert
    if expected_encoding is None:
        # エンコーディングが検出されない場合は、バイナリデータとして扱われる
        assert isinstance(result, BytesIO), "Result should be BytesIO instance for binary data"
        assert result.getvalue() == expected_result, f"Binary content mismatch.\nExpected: {expected_result}\nGot: {result.getvalue()}"
    else:
        # エンコーディングが検出された場合は、テキストデータとして扱われる
        assert result is not None, "Result should not be None for text data"


@UNIT
@pytest.mark.parametrize(
    ("input_str", "target_encoding", "is_allow_fallback", "expected_result", "expected_error"),
    [
        pytest.param(
            "Hello, 世界!",
            "ascii",
            True,
            None,
            "'ascii' codec can't encode characters in position 7-8: ordinal not in range(128)",
            id="encoding_convert_to_ascii_with_fallback",
        ),
        pytest.param(
            "Hello, 世界!",
            "ascii",
            False,
            None,
            "'ascii' codec can't encode characters in position 7-8: ordinal not in range(128)",
            id="encoding_convert_to_ascii_without_fallback",
        ),
        pytest.param(
            "こんにちは世界",
            "shift_jis",
            True,
            b"\x82\xb1\x82\xf1\x82\xc9\x82\xbf\x82\xcd\x90\xa2\x8aE",
            None,
            id="encoding_convert_to_shift_jis",
        ),
        pytest.param(
            "こんにちは世界",
            "euc_jp",
            True,
            b"\xa4\xb3\xa4\xf3\xa4\xcb\xa4\xc1\xa4\xcf\xc0\xa4\xb3\xa6",
            None,
            id="encoding_convert_to_euc_jp",
        ),
        pytest.param("", "shift_jis", True, b"", None, id="encoding_convert_empty_to_shift_jis"),
        pytest.param("\u3000", "shift_jis", True, b"\x81\x40", None, id="encoding_convert_fullwidth_space_to_shift_jis"),
        pytest.param(
            "①②③",
            "shift_jis",
            True,
            None,
            r"'shift_jis' codec can't encode character '\u2460' in position 0: illegal multibyte sequence",
            id="encoding_convert_circled_numbers_to_shift_jis",
        ),
        pytest.param("ｱｲｳｴｵ", "shift_jis", True, b"\xb1\xb2\xb3\xb4\xb5", None, id="encoding_convert_halfwidth_katakana_to_shift_jis"),
        pytest.param(
            "㈱㈲㈹",
            "shift_jis",
            True,
            None,
            r"'shift_jis' codec can't encode character '\u3231' in position 0: illegal multibyte sequence",
            id="encoding_convert_parenthesized_ideographs_to_shift_jis",
        ),
        pytest.param("Hello♪World", "shift_jis", True, b"Hello\xe2\x99\xaaWorld", None, id="encoding_convert_music_symbol_to_shift_jis"),
        pytest.param(
            "表\u309a",
            "shift_jis",
            True,
            None,
            r"'shift_jis' codec can't encode character '\u309a' in position 1: illegal multibyte sequence",
            id="encoding_convert_combining_mark_to_shift_jis",
        ),
        pytest.param("\u301c", "shift_jis", True, b"\x81\x60", None, id="encoding_convert_wave_dash_to_shift_jis"),
        pytest.param("漢字", "shift_jis", True, b"\x8a\xbf\x8e\x9a", None, id="encoding_convert_basic_kanji_to_shift_jis"),
        pytest.param(
            "カタカナ", "shift_jis", True, b"\x83\x4a\x83\x5e\x83\x4a\x83\x69", None, id="encoding_convert_basic_katakana_to_shift_jis"
        ),
        pytest.param(
            "ひらがな", "shift_jis", True, b"\x82\xd0\x82\xe7\x82\xaa\x82\xc8", None, id="encoding_convert_basic_hiragana_to_shift_jis"
        ),
    ],
)
def test_transcoder_encoding_conversion(
    create_text_file: Callable[[str, str, str], BytesIO],
    input_str: str,
    target_encoding: str,
    is_allow_fallback: bool,
    expected_result: Optional[bytes],
    expected_error: Optional[str],
) -> None:
    """エンコーディング変換機能をテストする。

    Args:
        create_text_file: テキストファイル作成用フィクスチャ
        input_str: 入力文字列
        target_encoding: 変換先エンコーディング
        is_allow_fallback: フォールバックを許可するかどうか
        expected_result: 期待される結果
    """
    # Arrange
    import_file: Final[BytesIO] = create_text_file(input_str, "utf-8", "example.txt")

    # Act
    transcoder: Final[TextTranscoder] = TextTranscoder(import_file)

    if expected_error is None:
        result: Optional[BytesIO] = transcoder.convert(target_encoding, is_allow_fallback)
    else:
        with pytest.raises(UnicodeEncodeError) as exc_info:
            result: Optional[BytesIO] = transcoder.convert(target_encoding, is_allow_fallback)

    # Assert
    if expected_result is None:
        assert str(exc_info.value) == expected_error
    else:
        assert isinstance(result, BytesIO)
        if isinstance(result, BytesIO):
            if input_str == "":  # 空文字列の場合の特別な処理
                assert result.getvalue() == b""
            else:
                try:
                    if target_encoding.lower() == "ascii":
                        # ASCIIの場合、非ASCII文字は?に置換される
                        expected_decoded: Final[str] = input_str.encode("ascii", errors="replace").decode("ascii")
                        assert result.getvalue().decode("ascii") == expected_decoded
                    else:
                        # その他のエンコーディングの場合
                        assert result.getvalue() == expected_result
                except UnicodeDecodeError:
                    pytest.fail(f"Could not decode {result.getvalue()} with {target_encoding}")


@UNIT
@pytest.mark.parametrize(
    ("test_data", "invalid_encoding", "expected_encoding"),
    [
        pytest.param(b"ABCDEF", "utf-9", "ASCII", id="encoding_detect_ascii_with_invalid_encoding"),
    ],
)
def test_transcoder_missing_encoding(test_data: bytes, invalid_encoding: str, expected_encoding: str) -> None:
    """存在しないエンコーディングを指定した場合のTextTranscoderの動作をテストする。

    Args:
        test_data: テスト用のバイトデータ
        invalid_encoding: 無効なエンコーディング
        expected_encoding: 期待されるエンコーディング
    """
    # Arrange
    transcoder: Final[TextTranscoder] = TextTranscoder(BytesIO(test_data))

    # Act
    detected_encoding: Final[Optional[str]] = transcoder.detect_encoding()
    result_without_fallback: Final[Optional[BytesIO]] = transcoder.convert(invalid_encoding, False)
    result_with_fallback: Final[Optional[BytesIO]] = transcoder.convert(invalid_encoding, True)

    # Assert
    assert detected_encoding == expected_encoding, f"Encoding detection mismatch.\nExpected: {expected_encoding}\nGot: {detected_encoding}"
    assert result_without_fallback is None, "Result without fallback should be None for invalid encoding"

    assert isinstance(result_with_fallback, BytesIO), "Result with fallback should be BytesIO instance"
    if isinstance(result_with_fallback, BytesIO):
        assert result_with_fallback.getvalue() == test_data, (
            f"Content mismatch with fallback.\nExpected: {test_data}\nGot: {result_with_fallback.getvalue()}"
        )
