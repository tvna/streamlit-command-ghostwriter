from io import BytesIO
from typing import Optional

import pytest

from features.text_transcoder import TextTranscoder


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
        pytest.param("あいうえお", "utf-8", "UTF-8", "あいうえお"),
        pytest.param("あいうえお", "utf_8", "UTF-8", "あいうえお"),
        pytest.param("漢字による試験", "Shift_JIS", "Shift_JIS", "漢字による試験"),
        pytest.param("漢字による試験", "Shift-JIS", "Shift_JIS", "漢字による試験"),
        pytest.param("漢字による試験", "EUC-JP", "EUC-JP", "漢字による試験"),
        pytest.param("漢字による試験", "EUC_JP", "EUC-JP", "漢字による試験"),
        pytest.param("漢字による試験", "utf-8", "UTF-8", "漢字による試験"),
        pytest.param("漢字による試験", "utf_8", "UTF-8", "漢字による試験"),
    ],
)
def test_transcoder(input_str: str, input_encoding: str, expected_encoding: str, expected_result: str) -> None:
    input_data = BytesIO(input_str.encode(input_encoding))
    input_data.name = "example.csv"

    trans = TextTranscoder(input_data)
    print(trans.detect_encoding(input_data))
    assert trans.detect_encoding(input_data) == expected_encoding

    output_data = trans.to_utf8()
    assert output_data.read().decode("utf-8") == expected_result  # type: ignore
    assert trans.challenge_to_utf8().getvalue().decode("utf-8") == expected_result
    assert output_data.name == input_data.name  # type: ignore


@pytest.mark.unit()
@pytest.mark.parametrize(
    ("input_bytes", "expected_encoding", "expected_result"),
    [
        pytest.param(b"\x00\x01\x02\x03\x04", None, b"\x00\x01\x02\x03\x04"),
        pytest.param(b"\x80\x81\x82\x83", "EUC-JP", b"\x80\x81\x82\x83"),
        pytest.param(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01", None, b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"),
    ],
)
def test_transcoder_non_string(input_bytes: bytes, expected_encoding: Optional[str], expected_result: Optional[bytes]) -> None:
    input_data = BytesIO(input_bytes)
    input_data.name = "example.csv"

    trans = TextTranscoder(input_data)
    assert trans.detect_encoding(input_data) == expected_encoding

    output_data = trans.to_utf8()
    if isinstance(output_data, BytesIO):
        assert output_data.getvalue() == expected_result
        assert trans.challenge_to_utf8().getvalue() == expected_result
        assert output_data.name == input_data.name
    else:
        assert output_data == None
        assert trans.challenge_to_utf8().getvalue() == expected_result
