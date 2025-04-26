"""アップロードされたファイルの検証を行うモジュール。

このモジュールは、アップロードされたファイルの検証機能を提供します。
主な機能:
- ファイルサイズの検証 (Pydanticモデル)
- ファイルポインタの位置を保持したままの検証
- エラー状態の管理

クラス階層:
- ValidationModels
  - FileSizeConfig: ファイルサイズの設定
  - ValidationState: 検証状態の管理
- FileValidator: メインの検証クラス

検証プロセス:
1. 入力検証
   - Pydanticモデルによるバリデーション
   - サイズ制限値の検証
   - ファイルオブジェクトの検証

2. ファイル処理
   - ファイルポインタの位置保持
   - サイズ計算の安全な実行
   - エラー状態の管理

エラー処理:
- ValidationError: Pydanticによる検証エラー
- ValueError: サイズ制限値の検証エラー
- IOError: ファイル読み取りエラー
- TypeError: 無効なファイルオブジェクト

典型的な使用方法:
```python
from io import BytesIO
from features.validate_uploaded_file import FileValidator, FileSizeConfig

config = FileSizeConfig(max_size_bytes=1024 * 1024)  # 1MB
validator = FileValidator(config)

with open('large_file.txt', 'rb') as f:
    file = BytesIO(f.read())
    if validator.validate_size(file):
        # ファイルサイズが制限内の場合の処理
        print(f"File size: {validator.get_file_size(file)} bytes")
    else:
        # エラーの場合の処理
        print(validator.error_message)
```
"""

from io import BytesIO
from typing import Annotated, ClassVar, Final, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator


class FileSizeConfig(BaseModel):
    """ファイルサイズの設定を管理するモデル。

    Attributes:
        max_size_bytes: 許可される最大ファイルサイズ (バイト)
            1以上の整数である必要があります
    """

    model_config = ConfigDict(strict=True)

    max_size_bytes: Annotated[int, Field(gt=0, description="許可される最大ファイルサイズ (バイト)")]

    @field_validator("max_size_bytes")
    def validate_max_size(cls, v: int) -> int:  # noqa: N805 (Keep cls for Pydantic validator)
        """最大サイズの値を検証する。

        Args:
            v: 検証する値

        Returns:
            検証済みの値

        Raises:
            ValueError: 値が1未満の場合
        """
        if v <= 0:
            raise ValueError("Maximum file size must be greater than 0")
        return v


class ValidationState(BaseModel):
    """検証状態を管理するモデル。

    Attributes:
        is_valid: 検証が成功したかどうか
        error_message: エラーメッセージ (エラーがない場合はNone)
    """

    model_config = ConfigDict(strict=True)

    is_valid: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None)

    def set_error(self, message: str) -> None:
        """エラー状態を設定する。

        Args:
            message: エラーメッセージ
        """
        self.is_valid = False
        self.error_message = message

    def reset(self) -> None:
        """状態をリセットする。"""
        self.is_valid = True
        self.error_message = None


class FileValidator(BaseModel):
    """ファイルの検証を行うクラス。

    このクラスは、アップロードされたファイルの検証機能を提供します。
    Pydanticモデルによる厳密な入力検証とエラー管理を提供します。

    主な機能:
    1. サイズ検証
       - 最大サイズの制限
       - ファイルポインタの位置保持
       - エラー状態の管理

    2. エラー処理
       - 検証状態の管理
       - 詳細なエラーメッセージ
       - IOエラーの安全な処理

    Attributes:
        DEFAULT_MAX_SIZE: デフォルトの最大ファイルサイズ [バイト]
            30MB

    Properties:
        max_size_bytes: 設定された最大ファイルサイズ
        error_message: 現在のエラーメッセージ (エラーがない場合はNone)
        is_valid: 最後の検証が成功したかどうか
    """

    # Constants
    DEFAULT_MAX_SIZE: ClassVar[int] = 30 * 1024 * 1024  # 30MB

    # Configuration
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Required fields
    size_config: FileSizeConfig = Field(default_factory=lambda: FileSizeConfig(max_size_bytes=FileValidator.DEFAULT_MAX_SIZE))

    # Private attributes
    _validation_state: ValidationState = PrivateAttr(default_factory=ValidationState)

    @property
    def max_size_bytes(self) -> int:
        """許可される最大ファイルサイズを返す。

        Returns:
            int: 最大ファイルサイズ (バイト)
        """
        return self.size_config.max_size_bytes

    @property
    def error_message(self) -> Optional[str]:
        """現在のエラーメッセージを返す。

        Returns:
            Optional[str]: エラーメッセージ (エラーがない場合はNone)
        """
        return self._validation_state.error_message

    @property
    def is_valid(self) -> bool:
        """最後の検証が成功したかどうかを返す。

        Returns:
            bool: 検証が成功した場合はTrue
        """
        return self._validation_state.is_valid

    def validate_size(self, file: BytesIO) -> bool:
        """ファイルサイズを検証する。

        ファイルポインタの位置を保持したまま、ファイルサイズが制限値を超えていないかチェックします。

        Args:
            file: 検証対象のファイル

        Returns:
            bool: ファイルサイズが制限内の場合はTrue

        Note:
            エラーが発生した場合、validation_stateにエラー情報が設定されます。
            エラーメッセージはerror_messageプロパティで取得できます。
        """
        self._validation_state.reset()

        try:
            file_size: Final[Optional[int]] = self.get_file_size(file)
            if file_size is None:
                self._validation_state.set_error("Failed to get file size")
                return False

            if file_size > self.max_size_bytes:
                self._validation_state.set_error(f"File size exceeds maximum limit of {self.max_size_bytes} bytes")
                return False

            return True

        except IOError as e:
            self._validation_state.set_error(f"Failed to read file: {e!s}")
            return False

    def get_file_size(self, file: BytesIO) -> Optional[int]:
        """ファイルサイズを取得する。

        ファイルポインタの位置を保持したまま、ファイルサイズを取得します。

        Args:
            file: サイズを取得するファイル

        Returns:
            Optional[int]: ファイルサイズ (バイト)、取得に失敗した場合はNone

        Note:
            このメソッドは例外を発生させません。
            ファイルサイズの取得に失敗した場合はNoneを返します。
        """
        try:
            current_pos: Final[int] = file.tell()
            file.seek(0, 2)  # ファイルの末尾に移動
            file_size: Final[int] = file.tell()
            file.seek(current_pos)  # 元の位置に戻す
            return file_size
        except IOError:
            return None
