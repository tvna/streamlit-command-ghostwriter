from io import BytesIO
from typing import Optional

import chardet
from pydantic import BaseModel, PrivateAttr


class TextTranscoder(BaseModel):
    __import_file: BytesIO = PrivateAttr()
    __filename: Optional[str] = PrivateAttr(default=None)

    def __init__(self: "TextTranscoder", import_file: BytesIO) -> None:
        super().__init__()

        self.__import_file = import_file

        if hasattr(import_file, "name"):
            self.__filename = import_file.name

    def detect_binary(self: "TextTranscoder") -> bool:
        import_file = self.__import_file
        current_position = import_file.tell()
        import_file.seek(0)
        chunk = import_file.read(1024)
        import_file.seek(current_position)

        return b"\0" in chunk

    def detect_encoding(self: "TextTranscoder") -> Optional[str]:
        if self.detect_binary() is True:
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

        if current_encode is None:
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

    def convert(self: "TextTranscoder", new_encode: str = "utf-8", is_allow_fallback: bool = True) -> Optional[BytesIO]:
        result = self.__convert_to_new_encode(new_encode)

        if is_allow_fallback is True:
            return result if isinstance(result, BytesIO) else self.__import_file
        else:
            return result
