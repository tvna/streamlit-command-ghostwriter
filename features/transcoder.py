from io import BytesIO
from typing import Final, Optional

import chardet


class TextTranscoder:
    def __init__(self: "TextTranscoder", input_data: BytesIO) -> None:
        self.__input_data: Final[BytesIO] = input_data

        if hasattr(input_data, "name"):
            self.__filename: Final[str] = input_data.name

    def detect_binary(self: "TextTranscoder", input_data: BytesIO) -> bool:
        current_position = input_data.tell()
        input_data.seek(0)
        chunk = input_data.read(1024)
        input_data.seek(current_position)

        return b"\0" in chunk

    def detect_encoding(self: "TextTranscoder", input_data: BytesIO) -> Optional[str]:
        if self.detect_binary(input_data):
            return None

        input_data.seek(0)
        raw_data = input_data.getvalue()
        result = chardet.detect(raw_data)
        encoding = result["encoding"]
        known_encode = ["ASCII", "Shift_JIS", "EUC-JP", "ISO-2022-JP", "utf-8"]

        # 日本語に関連するエンコーディングを優先する
        if encoding in known_encode:
            return encoding
        else:
            # 他のエンコーディングを試す
            for enc in known_encode:
                try:
                    raw_data.decode(enc)
                    return enc
                except (UnicodeDecodeError, LookupError):
                    continue
            return encoding

    def convert(self: "TextTranscoder", encode: str = "utf-8") -> Optional[BytesIO]:
        encoding = self.detect_encoding(self.__input_data)
        output_data = None

        if not encoding:
            return None

        try:
            self.__input_data.seek(0)
            content = self.__input_data.read().decode(encoding)
        except UnicodeDecodeError:
            return None

        try:
            output_data = BytesIO(content.encode(encode))
            output_data.name = self.__filename
        except (AttributeError, LookupError):
            pass

        return output_data

    def challenge_to_utf8(self: "TextTranscoder") -> BytesIO:
        result = self.convert()

        return result if isinstance(result, BytesIO) else self.__input_data
