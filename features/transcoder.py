from io import BytesIO
from typing import Optional

import chardet
from pydantic import BaseModel, PrivateAttr


class TextTranscoder(BaseModel):
    __source_data: BytesIO = PrivateAttr()
    __filename: str = PrivateAttr()

    @property
    def source_data(self: "TextTranscoder") -> BytesIO:
        return self.__source_data

    @source_data.setter
    def source_data(self: "TextTranscoder", val: BytesIO) -> None:
        self.__source_data = val

        if hasattr(val, "name"):
            self.__filename = val.name

    def detect_binary(self: "TextTranscoder") -> bool:
        input_data = self.__source_data
        current_position = input_data.tell()
        input_data.seek(0)
        chunk = input_data.read(1024)
        input_data.seek(current_position)

        return b"\0" in chunk

    def detect_encoding(self: "TextTranscoder") -> Optional[str]:
        if self.detect_binary():
            return None

        source_data = self.__source_data
        source_data.seek(0)
        raw_data = source_data.getvalue()
        result = chardet.detect(raw_data)
        encoding = result["encoding"]
        known_encode = ["ASCII", "Shift_JIS", "EUC-JP", "ISO-2022-JP", "utf-8"]

        # 日本語に関連するエンコーディングを優先する
        if encoding in known_encode:
            return encoding

        # 他のエンコーディングを試す
        for enc in known_encode:
            try:
                raw_data.decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return encoding

    def convert(self: "TextTranscoder", new_encode: str = "utf-8") -> Optional[BytesIO]:
        current_encode = self.detect_encoding()
        output_data = None

        if not current_encode:
            return None

        source_data = self.__source_data
        source_data.seek(0)
        content = source_data.read().decode(current_encode)

        try:
            output_data = BytesIO(content.encode(new_encode))
            output_data.name = self.__filename
        except (AttributeError, LookupError):
            pass

        return output_data

    def challenge_to_utf8(self: "TextTranscoder") -> BytesIO:
        result = self.convert()

        return result if isinstance(result, BytesIO) else self.__source_data
