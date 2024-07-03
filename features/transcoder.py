from io import BytesIO
from typing import Optional

import chardet
from pydantic import BaseModel, PrivateAttr


class TextTranscoder(BaseModel):
    __import_file: BytesIO = PrivateAttr(default=None)
    __export_file: Optional[BytesIO] = PrivateAttr(default=None)
    __filename: Optional[str] = PrivateAttr(default=None)

    @property
    def import_file(self: "TextTranscoder") -> BytesIO:
        return self.__import_file

    @import_file.setter
    def import_file(self: "TextTranscoder", val: BytesIO) -> None:
        self.__import_file = val

        if hasattr(val, "name"):
            self.__filename = val.name

    @property
    def export_file(self: "TextTranscoder") -> Optional[BytesIO]:
        return self.__export_file

    def detect_binary(self: "TextTranscoder") -> bool:
        import_file = self.__import_file
        current_position = import_file.tell()
        import_file.seek(0)
        chunk = import_file.read(1024)
        import_file.seek(current_position)

        return b"\0" in chunk

    def detect_encoding(self: "TextTranscoder") -> Optional[str]:
        if self.detect_binary():
            return None

        import_file = self.__import_file
        import_file.seek(0)
        raw_data = import_file.getvalue()
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

    def __convert_to_new_encode(self: "TextTranscoder", new_encode: str) -> Optional[BytesIO]:
        current_encode = self.detect_encoding()
        export_file = None

        if not current_encode:
            return None

        import_file = self.__import_file
        import_file.seek(0)
        content = import_file.read().decode(current_encode)

        try:
            export_file = BytesIO(content.encode(new_encode))
        except LookupError:
            return None

        if isinstance(self.__filename, str):
            export_file.name = self.__filename

        return export_file

    def convert(self: "TextTranscoder", new_encode: str = "utf-8", is_allow_fallback: bool = True) -> "TextTranscoder":
        result = self.__convert_to_new_encode(new_encode)

        if is_allow_fallback:
            self.__export_file = result if isinstance(result, BytesIO) else self.__import_file
        else:
            self.__export_file = result

        return self
