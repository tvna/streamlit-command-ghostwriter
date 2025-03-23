"""アップロードされたファイルの検証を行うモジュール。

このモジュールは、アップロードされたファイルの検証機能を提供します。
主な機能:
- ファイルサイズの検証
- ファイルポインタの位置を保持したままの検証

典型的な使用方法:
```python
from io import BytesIO
from features.validate_uploaded_file import FileValidator

MAX_SIZE = 1024 * 1024  # 1MB
validator = FileValidator(max_size_bytes=MAX_SIZE)

with open('large_file.txt', 'rb') as f:
    file = BytesIO(f.read())
    try:
        validator.validate_size(file)
        # ファイルサイズが制限内の場合の処理
    except ValueError as e:
        # ファイルサイズが制限を超えている場合の処理
```
"""

from io import BytesIO
from typing import Optional


class FileValidator:
    """ファイルの検証を行うクラス。

    このクラスは、アップロードされたファイルの検証機能を提供します。
    現在は主にファイルサイズの検証に焦点を当てていますが、
    将来的に他の検証機能（ファイル形式、コンテンツタイプなど）を追加することを想定しています。

    Attributes:
        max_size_bytes: 許可される最大ファイルサイズ（バイト）
    """

    def __init__(self, max_size_bytes: int) -> None:
        """FileValidatorインスタンスを初期化する。

        Args:
            max_size_bytes: 許可される最大ファイルサイズ（バイト）

        Raises:
            ValueError: max_size_bytesが0以下の場合
        """
        if max_size_bytes <= 0:
            raise ValueError("Maximum file size must be greater than 0")
        self._max_size_bytes = max_size_bytes

    @property
    def max_size_bytes(self) -> int:
        """許可される最大ファイルサイズを返す。

        Returns:
            int: 最大ファイルサイズ（バイト）
        """
        return self._max_size_bytes

    def validate_size(self, file: BytesIO) -> bool:
        """ファイルサイズを検証する。

        ファイルポインタの位置を保持したまま、ファイルサイズが制限値を超えていないかチェックします。

        Args:
            file: 検証対象のファイル

        Returns:
            bool: ファイルサイズが制限内の場合はTrue

        Raises:
            ValueError: ファイルサイズが制限を超えている場合
            IOError: ファイルの読み取りに失敗した場合
        """
        try:
            file_size = self.get_file_size(file)
            if file_size is None:
                raise IOError("Failed to get file size")

            if file_size > self._max_size_bytes:
                raise ValueError(f"File size exceeds maximum limit of {self._max_size_bytes} bytes")
            return True

        except IOError as e:
            raise IOError(f"Failed to read file: {e!s}") from e

    def get_file_size(self, file: BytesIO) -> Optional[int]:
        """ファイルサイズを取得する。

        ファイルポインタの位置を保持したまま、ファイルサイズを取得します。

        Args:
            file: サイズを取得するファイル

        Returns:
            Optional[int]: ファイルサイズ（バイト）、取得に失敗した場合はNone

        Note:
            このメソッドは例外を発生させません。
            ファイルサイズの取得に失敗した場合はNoneを返します。
        """
        try:
            current_pos = file.tell()
            file.seek(0, 2)  # ファイルの末尾に移動
            file_size = file.tell()
            file.seek(current_pos)  # 元の位置に戻す
            return file_size
        except IOError:
            return None
