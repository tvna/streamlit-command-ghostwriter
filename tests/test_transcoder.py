from io import BytesIO
from typing import Optional

import pytest

from features.transcoder import TextTranscoder


@pytest.mark.unit()
@pytest.mark.parametrize(
    ("input_str", "input_encoding", "expected_encoding", "expected_result"),
    [
        pytest.param("ABCDEF", "Shift_JIS", "ASCII", "ABCDEF"),
        pytest.param("ABCDEF", "Shift-JIS", "ASCII", "ABCDEF"),
        pytest.param("ABCDEF", "EUC-JP", "ASCII", "ABCDEF"),
        pytest.param("ABCDEF", "EUC_JP", "ASCII", "ABCDEF"),
        pytest.param("ABCDEF", "utf-8", "ASCII", "ABCDEF"),
        pytest.param("ABCDEF", "utf_8", "ASCII", "ABCDEF"),
        pytest.param("", "Shift_JIS", "ASCII", ""),
        pytest.param("", "Shift-JIS", "ASCII", ""),
        pytest.param("", "EUC_JP", "ASCII", ""),
        pytest.param("", "EUC-JP", "ASCII", ""),
        pytest.param("", "utf-8", "ASCII", ""),
        pytest.param("", "utf_8", "ASCII", ""),
        pytest.param("あいうえお", "Shift_JIS", "Shift_JIS", "あいうえお"),
        pytest.param("あいうえお", "Shift-JIS", "Shift_JIS", "あいうえお"),
        pytest.param("あいうえお", "EUC-JP", "EUC-JP", "あいうえお"),
        pytest.param("あいうえお", "EUC_JP", "EUC-JP", "あいうえお"),
        pytest.param("あいうえお", "utf-8", "utf-8", "あいうえお"),
        pytest.param("あいうえお", "utf_8", "utf-8", "あいうえお"),
        pytest.param("漢字による試験", "Shift_JIS", "Shift_JIS", "漢字による試験"),
        pytest.param("漢字による試験", "Shift-JIS", "Shift_JIS", "漢字による試験"),
        pytest.param("漢字による試験", "EUC-JP", "EUC-JP", "漢字による試験"),
        pytest.param("漢字による試験", "EUC_JP", "EUC-JP", "漢字による試験"),
        pytest.param("漢字による試験", "utf-8", "utf-8", "漢字による試験"),
        pytest.param("漢字による試験", "utf_8", "utf-8", "漢字による試験"),
    ],
)
def test_transcoder(input_str: str, input_encoding: str, expected_encoding: str, expected_result: str) -> None:
    import_file = BytesIO(input_str.encode(input_encoding))
    import_file.name = "example.csv"

    trans = TextTranscoder(import_file)
    assert trans.detect_encoding() == expected_encoding

    export_file_deny_fallback = trans.convert(is_allow_fallback=False)
    assert export_file_deny_fallback.read().decode("utf-8") == expected_result  # type: ignore
    assert export_file_deny_fallback.name == import_file.name  # type: ignore

    export_file_allow_fallback = trans.convert(is_allow_fallback=True)
    assert export_file_allow_fallback.getvalue().decode("utf-8") == expected_result  # type: ignore
    assert export_file_allow_fallback.name == import_file.name  # type: ignore


@pytest.mark.unit()
@pytest.mark.parametrize(
    ("input_bytes", "expected_encoding", "expected_result"),
    [
        pytest.param(b"\x00\x01\x02\x03\x04", None, b"\x00\x01\x02\x03\x04"),
        pytest.param(b"\x80\x81\x82\x83", None, b"\x80\x81\x82\x83"),
        pytest.param(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01", None, b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"),
    ],
)
def test_transcoder_non_string(input_bytes: bytes, expected_encoding: Optional[str], expected_result: Optional[bytes]) -> None:
    import_file = BytesIO(input_bytes)
    import_file.name = "example.csv"

    trans = TextTranscoder(import_file)
    assert trans.detect_encoding() == expected_encoding

    export_file_deny_fallback = trans.convert(is_allow_fallback=False)
    assert export_file_deny_fallback is None  # type: ignore

    export_file_allow_fallback = trans.convert(is_allow_fallback=True)
    assert export_file_allow_fallback.getvalue() == expected_result  # type: ignore
    assert export_file_allow_fallback.name == import_file.name  # type: ignore


@pytest.mark.unit()
def test_transcoder_missing_encode() -> None:
    trans = TextTranscoder(BytesIO(b"ABCDEF"))
    assert trans.detect_encoding() == "ASCII"
    assert trans.convert("utf-9", False) is None
    assert trans.convert("utf-9", True).getvalue() == b"ABCDEF"  # type: ignore
