from io import BytesIO
from typing import Final, Optional

import nkf


class TextTranscoder:
    def __init__(self: "TextTranscoder", input_data: BytesIO) -> None:
        self.__input_data: Final[BytesIO] = input_data
        self.__filename: Final[str] = input_data.name

    def detect_encoding(self: "TextTranscoder") -> Optional[str]:
        raw_data = self.__input_data.getvalue()
        result = nkf.guess(raw_data)  # type: ignore
        return result

    def to_utf8(self: "TextTranscoder") -> Optional[BytesIO]:
        encoding = self.detect_encoding()

        if not encoding:
            return None

        try:
            self.__input_data.seek(0)
            content = self.__input_data.read().decode(encoding)
        except UnicodeDecodeError:
            return None

        output_data = BytesIO(content.encode("utf-8"))
        output_data.name = self.__filename

        return output_data

    def challenge_to_utf8(self: "TextTranscoder") -> BytesIO:
        result = self.to_utf8()

        return result if isinstance(result, BytesIO) else self.__input_data
