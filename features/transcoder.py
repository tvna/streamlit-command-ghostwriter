from io import BytesIO
from typing import TYPE_CHECKING, Final, List, Optional

import chardet
from pydantic import BaseModel, PrivateAttr

if TYPE_CHECKING:
    from chardet.resultdict import ResultDict


class TextTranscoder(BaseModel):
    KNOWN_ENCODES: Final[List[str]] = ["ASCII", "Shift_JIS", "EUC-JP", "ISO-2022-JP", "utf-8"]

    _filename: Optional[str] = PrivateAttr(default=None)
    _import_file: BytesIO = PrivateAttr()

    def __init__(self: "TextTranscoder", import_file: BytesIO) -> None:
        """
        TextTranscoderの初期化メソッド。

        Args:
            import_file (BytesIO): インポートするファイルのバイナリデータ。
        """
        super().__init__()

        self._import_file = import_file

        if hasattr(import_file, "name"):
            self._filename = import_file.name

    def detect_binary(self: "TextTranscoder") -> bool:
        """
        インポートファイルがバイナリデータかどうかを検出します。

        Returns:
            bool: バイナリデータであればTrue、そうでなければFalse。
        """
        import_file: Final[BytesIO] = self._import_file
        current_position: Final[int] = import_file.tell()
        import_file.seek(0)
        chunk: Final[bytes] = import_file.read(1024)
        import_file.seek(current_position)

        return b"\0" in chunk

    def detect_encoding(self: "TextTranscoder") -> Optional[str]:
        """
        インポートファイルのエンコーディングを検出します。

        Returns:
            Optional[str]: 検出されたエンコーディング名、またはバイナリデータの場合はNone。
        """
        if self.detect_binary() is True:
            return None

        import_file: Final[BytesIO] = self._import_file
        import_file.seek(0)
        raw_data: Final[bytes] = import_file.getvalue()
        result: ResultDict = chardet.detect(raw_data)
        encoding: Final[Optional[str]] = result["encoding"]

        # 日本語に関連するエンコーディングを優先する
        if encoding in self.KNOWN_ENCODES:
            return encoding

        # 他のエンコーディングを試す
        for enc in self.KNOWN_ENCODES:
            try:
                raw_data.decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return encoding

    def __convert_to_new_encode(self: "TextTranscoder", new_encode: str) -> Optional[BytesIO]:
        """
        現在のエンコーディングから新しいエンコーディングに変換します。

        Args:
            new_encode (str): 変換先のエンコーディング名。

        Returns:
            Optional[BytesIO]: 変換されたファイルのバイナリデータ、またはエンコーディングが不明な場合はNone。
        """

        current_encode: Final[Optional[str]] = self.detect_encoding()
        export_file: Optional[BytesIO] = None

        if current_encode is None:
            return None

        import_file: Final[BytesIO] = self._import_file
        import_file.seek(0)
        content: Final[str] = import_file.read().decode(current_encode)

        try:
            export_file = BytesIO(content.encode(new_encode))
        except LookupError:
            return None

        if isinstance(self._filename, str):
            export_file.name = self._filename

        return export_file

    def convert(self: "TextTranscoder", new_encode: str = "utf-8", is_allow_fallback: bool = True) -> Optional[BytesIO]:
        """
        指定されたエンコーディングにファイルを変換します。

        Args:
            new_encode (str): 変換先のエンコーディング名(デフォルトは'utf-8')
            is_allow_fallback (bool): 変換に失敗した場合に元のファイルを返すかどうか。

        Returns:
            Optional[BytesIO]: 変換されたファイルのバイナリデータ、または元のファイル。
        """

        result: Optional[BytesIO] = self.__convert_to_new_encode(new_encode)

        if is_allow_fallback is True:
            return result if isinstance(result, BytesIO) else self._import_file
        else:
            return result
