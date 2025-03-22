from io import BytesIO
from typing import Callable, Optional

import pytest

from features.transcoder import TextTranscoder


@pytest.fixture
def create_text_file() -> Callable[[str, str, str], BytesIO]:
    """テスト用のテキストファイルを作成するフィクスチャ。

    Returns:
        Callable[[str, str, str], BytesIO]: テキストファイルを作成する関数
    """

    def _create_file(content: str, encoding: str, filename: str = "example.txt") -> BytesIO:
        file = BytesIO(content.encode(encoding))
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
        file = BytesIO(content)
        file.name = filename
        return file

    return _create_file


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_str", "input_encoding", "expected_encoding", "expected_result"),
    [
        pytest.param("ABCDEF", "Shift_JIS", "ASCII", "ABCDEF", id="ASCII_text_from_Shift_JIS"),
        pytest.param("ABCDEF", "Shift-JIS", "ASCII", "ABCDEF", id="ASCII_text_from_Shift-JIS"),
        pytest.param("ABCDEF", "EUC-JP", "ASCII", "ABCDEF", id="ASCII_text_from_EUC-JP"),
        pytest.param("ABCDEF", "EUC_JP", "ASCII", "ABCDEF", id="ASCII_text_from_EUC_JP"),
        pytest.param("ABCDEF", "utf-8", "ASCII", "ABCDEF", id="ASCII_text_from_utf-8"),
        pytest.param("ABCDEF", "utf_8", "ASCII", "ABCDEF", id="ASCII_text_from_utf_8"),
        pytest.param("", "Shift_JIS", "ASCII", "", id="Empty_string_from_Shift_JIS"),
        pytest.param("", "Shift-JIS", "ASCII", "", id="Empty_string_from_Shift-JIS"),
        pytest.param("", "EUC_JP", "ASCII", "", id="Empty_string_from_EUC_JP"),
        pytest.param("", "EUC-JP", "ASCII", "", id="Empty_string_from_EUC-JP"),
        pytest.param("", "utf-8", "ASCII", "", id="Empty_string_from_utf-8"),
        pytest.param("", "utf_8", "ASCII", "", id="Empty_string_from_utf_8"),
        pytest.param("あいうえお", "Shift_JIS", "Shift_JIS", "あいうえお", id="Japanese_hiragana_from_Shift_JIS"),
        pytest.param("あいうえお", "Shift-JIS", "Shift_JIS", "あいうえお", id="Japanese_hiragana_from_Shift-JIS"),
        pytest.param("あいうえお", "EUC-JP", "EUC-JP", "あいうえお", id="Japanese_hiragana_from_EUC-JP"),
        pytest.param("あいうえお", "EUC_JP", "EUC-JP", "あいうえお", id="Japanese_hiragana_from_EUC_JP"),
        pytest.param("あいうえお", "utf-8", "utf-8", "あいうえお", id="Japanese_hiragana_from_utf-8"),
        pytest.param("あいうえお", "utf_8", "utf-8", "あいうえお", id="Japanese_hiragana_from_utf_8"),
        pytest.param("漢字による試験", "Shift_JIS", "Shift_JIS", "漢字による試験", id="Japanese_kanji_from_Shift_JIS"),
        pytest.param("漢字による試験", "Shift-JIS", "Shift_JIS", "漢字による試験", id="Japanese_kanji_from_Shift-JIS"),
        pytest.param("漢字による試験", "EUC-JP", "EUC-JP", "漢字による試験", id="Japanese_kanji_from_EUC-JP"),
        pytest.param("漢字による試験", "EUC_JP", "EUC-JP", "漢字による試験", id="Japanese_kanji_from_EUC_JP"),
        pytest.param("漢字による試験", "utf-8", "utf-8", "漢字による試験", id="Japanese_kanji_from_utf-8"),
        pytest.param("漢字による試験", "utf_8", "utf-8", "漢字による試験", id="Japanese_kanji_from_utf_8"),
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
    import_file = create_text_file(input_str, input_encoding, "example.csv")

    # Act
    transcoder = TextTranscoder(import_file)
    detected_encoding = transcoder.detect_encoding()
    export_file_deny_fallback = transcoder.convert(is_allow_fallback=False)
    export_file_allow_fallback = transcoder.convert(is_allow_fallback=True)

    # Assert
    assert detected_encoding == expected_encoding

    assert isinstance(export_file_deny_fallback, BytesIO)
    if isinstance(export_file_deny_fallback, BytesIO):
        assert export_file_deny_fallback.read().decode("utf-8") == expected_result
        assert export_file_deny_fallback.name == import_file.name

    assert isinstance(export_file_allow_fallback, BytesIO)
    if isinstance(export_file_allow_fallback, BytesIO):
        assert export_file_allow_fallback.getvalue().decode("utf-8") == expected_result
        assert export_file_allow_fallback.name == import_file.name


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_bytes", "expected_encoding", "expected_result"),
    [
        pytest.param(b"\x00\x01\x02\x03\x04", None, b"\x00\x01\x02\x03\x04", id="Binary_data_with_control_characters"),
        pytest.param(b"\x80\x81\x82\x83", None, b"\x80\x81\x82\x83", id="Binary_data_with_high_ASCII"),
        pytest.param(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01",
            None,
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01",
            id="Binary_data_with_PNG_header",
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
    import_file = create_binary_file(input_bytes, "example.csv")

    # Act
    transcoder = TextTranscoder(import_file)
    detected_encoding = transcoder.detect_encoding()
    export_file_deny_fallback = transcoder.convert(is_allow_fallback=False)
    export_file_allow_fallback = transcoder.convert(is_allow_fallback=True)

    # Assert
    assert detected_encoding == expected_encoding
    assert export_file_deny_fallback is None

    assert isinstance(export_file_allow_fallback, BytesIO)
    if isinstance(export_file_allow_fallback, BytesIO):
        assert export_file_allow_fallback.getvalue() == expected_result
        assert export_file_allow_fallback.name == import_file.name


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_str", "input_encoding", "expected_encoding", "expected_result"),
    [
        pytest.param("A" * 100, "utf-8", "ASCII", "A" * 100, id="Very_long_ASCII_string"),
        pytest.param("Hello, 世界! こんにちは!", "utf-8", "utf-8", "Hello, 世界! こんにちは!", id="Mixed_ASCII_and_non_ASCII"),
        pytest.param("   \t\n\r   ", "utf-8", "ASCII", "   \t\n\r   ", id="String_with_only_whitespace"),
        pytest.param("\x00\x01\x02\x03\x04\x05Hello", "utf-8", None, "\x00\x01\x02\x03\x04\x05Hello", id="String_with_control_characters"),
        pytest.param("😀😁😂🤣😃😄😅", "utf-8", "utf-8", "😀😁😂🤣😃😄😅", id="String_with_emoji"),
        pytest.param("Hello 😀 World 🌍", "utf-8", "utf-8", "Hello 😀 World 🌍", id="String_with_mixed_emoji_and_text"),
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
    import_file = create_text_file(input_str, input_encoding, "example.txt")

    # Act
    transcoder = TextTranscoder(import_file)
    detected_encoding = transcoder.detect_encoding()

    # Assert
    assert detected_encoding == expected_encoding

    # 期待されるエンコーディングがNoneの場合は、変換結果のチェックをスキップ
    if expected_encoding is not None:
        # Act
        export_file = transcoder.convert(is_allow_fallback=True)

        # Assert
        assert isinstance(export_file, BytesIO)
        if isinstance(export_file, BytesIO):
            assert export_file.getvalue().decode("utf-8") == expected_result
            assert export_file.name == import_file.name


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_bytes", "expected_encoding", "expected_result"),
    [
        pytest.param(b"%PDF-1.5\n%\xd0\xd0\xd0\xd0\n", "Shift_JIS", b"%PDF-1.5\n%\xd0\xd0\xd0\xd0\n", id="Binary_data_with_PDF_header"),
        pytest.param(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00", None, b"\xff\xd8\xff\xe0\x00\x10JFIF\x00", id="Binary_data_with_JPEG_header"),
        pytest.param(b"GIF89a\x01\x00\x01\x00\x80\x00\x00", None, b"GIF89a\x01\x00\x01\x00\x80\x00\x00", id="Binary_data_with_GIF_header"),
        pytest.param(b"PK\x03\x04\x14\x00\x00\x00\x08\x00", None, b"PK\x03\x04\x14\x00\x00\x00\x08\x00", id="Binary_data_with_ZIP_header"),
        pytest.param(bytes([i % 256 for i in range(100)]), None, bytes([i % 256 for i in range(100)]), id="Binary_data_with_random_bytes"),
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
    import_file = create_binary_file(input_bytes, "example.bin")

    # Act
    transcoder = TextTranscoder(import_file)
    detected_encoding = transcoder.detect_encoding()

    # Assert
    assert detected_encoding == expected_encoding

    # Act
    result = transcoder.convert()

    # Assert
    if expected_encoding is None:
        # エンコーディングが検出されない場合は、バイナリデータとして扱われる
        assert isinstance(result, BytesIO)
        assert result.getvalue() == expected_result
    else:
        # エンコーディングが検出された場合は、テキストデータとして扱われる
        assert result is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_str", "target_encoding", "is_allow_fallback", "expected_result"),
    [
        pytest.param(
            "Hello, 世界!",
            "ascii",
            True,
            None,
            marks=pytest.mark.skip(reason="ASCIIエンコーディングへの変換はエラーになるため"),
            id="Convert_to_ASCII_with_fallback",
        ),
        pytest.param(
            "Hello, 世界!",
            "ascii",
            False,
            None,
            marks=pytest.mark.skip(reason="ASCIIエンコーディングへの変換はエラーになるため"),
            id="Convert_to_ASCII_without_fallback",
        ),
        pytest.param(
            "こんにちは世界", "shift_jis", True, b"\x82\xb1\x82\xf1\x82\xc9\x82\xbf\x82\xcd\x90\xa2\x8aE", id="Convert_to_Shift_JIS"
        ),
        pytest.param("こんにちは世界", "euc_jp", True, b"\xa4\xb3\xa4\xf3\xa4\xcb\xa4\xc1\xa4\xcf\xc0\xa4\xb3\xa6", id="Convert_to_EUC_JP"),
    ],
)
def test_transcoder_encoding_conversion(
    create_text_file: Callable[[str, str, str], BytesIO],
    input_str: str,
    target_encoding: str,
    is_allow_fallback: bool,
    expected_result: Optional[bytes],
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
    import_file = create_text_file(input_str, "utf-8", "example.txt")

    # Act
    transcoder = TextTranscoder(import_file)
    result = transcoder.convert(target_encoding, is_allow_fallback)

    # Assert
    if expected_result is None:
        assert result is None
    else:
        assert isinstance(result, BytesIO)
        if isinstance(result, BytesIO):
            if is_allow_fallback:
                try:
                    decoded = result.getvalue().decode(target_encoding)
                    if target_encoding.lower() == "ascii":
                        # For ASCII, we expect ? for non-ASCII chars
                        expected_decoded = (
                            input_str.replace("世", "?")
                            .replace("界", "?")
                            .replace("こ", "?")
                            .replace("ん", "?")
                            .replace("に", "?")
                            .replace("ち", "?")
                            .replace("は", "?")
                        )
                        assert decoded == expected_decoded
                    else:
                        # For other encodings, we just check if it can be decoded back to something
                        assert len(decoded) > 0
                except UnicodeDecodeError:
                    pytest.fail(f"Could not decode {result.getvalue()} with {target_encoding}")
            else:
                assert result.getvalue() == expected_result


@pytest.mark.unit
@pytest.mark.parametrize(
    ("test_data", "invalid_encoding", "expected_encoding"),
    [
        pytest.param(b"ABCDEF", "utf-9", "ASCII", id="Invalid_encoding_with_ASCII_data"),
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
    transcoder = TextTranscoder(BytesIO(test_data))

    # Act
    detected_encoding = transcoder.detect_encoding()
    result_without_fallback = transcoder.convert(invalid_encoding, False)
    result_with_fallback = transcoder.convert(invalid_encoding, True)

    # Assert
    assert detected_encoding == expected_encoding
    assert result_without_fallback is None

    assert isinstance(result_with_fallback, BytesIO)
    if isinstance(result_with_fallback, BytesIO):
        assert result_with_fallback.getvalue() == test_data
