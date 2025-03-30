"""アップロードされた設定ファイルのパースを行うモジュール。

このモジュールは、設定ファイルのパース機能を提供します。
主な機能:
- 設定ファイルの検証とパース
- メモリ使用量の制限
- CSVデータの特殊処理

クラス階層:
- ConfigParser: メインのパースクラス (Pydanticモデル)
  - FileValidator: ファイルサイズの検証
  - pandas: CSVデータの処理

検証プロセス:
1. 入力検証
   - Pydanticモデルによるバリデーション
   - ファイルサイズの制限チェック
   - サポートされているファイル形式の確認

2. ファイル処理
   - エンコーディングの検証 (UTF-8)
   - ファイル拡張子の抽出
   - ファイル内容の読み込み

3. パース処理
   - ファイル形式に応じたパース (TOML/YAML/CSV)
   - CSVデータの特殊処理 (NaN値の処理)
   - パース結果の辞書変換

4. メモリ管理
   - パース結果のメモリ使用量チェック
   - 文字列変換時のメモリ制限
   - エラー時のメモリ解放

対応ファイル形式:
- TOML (.toml)
  - tomllibによるパース
  - 厳密な構文チェック
- YAML (.yaml, .yml)
  - PyYAMLによる安全なパース
  - 辞書形式の検証
- CSV (.csv)
  - pandasによるパース
  - NaN値の柔軟な処理
  - カスタム行名の設定

エラー処理:
- ValidationError: Pydanticによる検証エラー
- ValueError: ファイルサイズ、形式、構文エラー
- UnicodeError: エンコーディングエラー
- MemoryError: メモリ制限超過
- YAMLError: YAML構文エラー
- TOMLDecodeError: TOML構文エラー
- pandas.errors: CSVパースエラー

メモリ管理:
- ファイルサイズ制限: 30MB
- メモリ使用量制限: 150MB
- 大きなファイルの安全な処理
- メモリリークの防止

典型的な使用方法:
```python
with open('config.toml', 'rb') as f:
    config_file = BytesIO(f.read())
    parser = ConfigParser(config_file)
    if parser.parse():
        config_dict = parser.parsed_dict
        config_str = parser.parsed_str
```

CSVファイルの特殊処理:
```python
with open('data.csv', 'rb') as f:
    config_file = BytesIO(f.read())
    parser = ConfigParser(config_file)
    parser.csv_rows_name = 'items'      # カスタム行名の設定
    parser.enable_fill_nan = True       # NaN値の処理を有効化
    parser.fill_nan_with = ''          # NaN値を空文字列で置換
    if parser.parse():
        csv_data = parser.parsed_dict
```
"""

import pprint
import sys
import tomllib
from io import BytesIO, StringIO
from typing import Any, ClassVar, Dict, List, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from features.validate_uploaded_file import FileSizeConfig, FileValidator  # type: ignore


class ConfigParser(BaseModel):
    """設定ファイルのパースを行うクラス。

    設定ファイルの検証、パース、メモリ管理を一貫して処理します。
    Pydanticモデルによる厳密な入力検証とメモリ使用量の制限を提供します。

    主な機能:
    1. ファイル処理
       - サポートされている形式の検証
       - ファイルサイズの制限
       - UTF-8エンコーディングの確認

    2. パース処理
       - TOML: tomllibによる厳密なパース
       - YAML: safe_loadによる安全なパース
       - CSV: pandasによる高度なデータ処理
         - NaN値の柔軟な処理
         - カスタム行名の設定
         - 型変換の自動処理

    3. メモリ管理
       - ファイルサイズの制限
       - パース結果のメモリ監視
       - 文字列変換時の制限

    Attributes:
        MAX_FILE_SIZE_BYTES: ファイルサイズの上限 [バイト]
            デフォルト: 30MB
        MAX_MEMORY_SIZE_BYTES: メモリ使用量の上限 [バイト]
            デフォルト: 150MB
        SUPPORTED_EXTENSIONS: サポートされているファイル拡張子
            [toml, yaml, yml, csv]

    Properties:
        parsed_dict: パース結果の辞書 (エラー時はNone)
        parsed_str: パース結果の文字列表現 (エラー時は"None")
        error_message: エラーメッセージ (エラーがない場合はNone)
        csv_rows_name: CSV行のキー名 (デフォルト: "csv_rows")
        enable_fill_nan: NaN値を置換するかどうか
        fill_nan_with: NaN値の置換値

    エラー処理:
    - ValidationError: 入力値の検証エラー
    - ValueError: ファイルサイズ、形式、構文エラー
    - UnicodeError: エンコーディングエラー
    - MemoryError: メモリ制限超過
    - YAMLError: YAML構文エラー
    - TOMLDecodeError: TOML構文エラー
    - pandas.errors: CSVパースエラー
    """

    # Constants for size limits as class variables
    MAX_FILE_SIZE_BYTES: ClassVar[int] = 30 * 1024 * 1024  # 30MB
    MAX_MEMORY_SIZE_BYTES: ClassVar[int] = 150 * 1024 * 1024  # 150MB
    SUPPORTED_EXTENSIONS: ClassVar[List[str]] = ["toml", "yaml", "yml", "csv"]

    # Public fields for validation
    config_file: BytesIO = Field(..., description="設定ファイルのバイナリデータ")
    csv_rows_name: str = Field("csv_rows", min_length=1, description="CSV行のキー名")

    # Private attributes
    __file_extension: str = PrivateAttr()
    __config_data: Optional[str] = PrivateAttr(default=None)
    __parsed_dict: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    __error_message: Optional[str] = PrivateAttr(default=None)
    __is_enable_fill_nan: bool = PrivateAttr(default=False)
    __fill_nan_with: Optional[str] = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, config_file: BytesIO) -> None:
        """ConfigParserの初期化メソッド。

        Args:
            config_file: 設定ファイルのバイナリデータ
        """
        # FileValidatorの初期化
        file_validator = FileValidator(size_config=FileSizeConfig(max_size_bytes=self.MAX_FILE_SIZE_BYTES))

        # Pydanticモデルの初期化
        super().__init__(config_file=config_file)

        # ファイルサイズの検証
        file_validator.validate_size(config_file)
        if not file_validator.is_valid:
            self.__error_message = file_validator.error_message
            return

        self.__initialize_from_file()

    def __initialize_from_file(self) -> None:
        """ファイルから初期化処理を行います。"""
        try:
            self.__file_extension = self.__extract_file_extension()
            if self.__file_extension not in self.SUPPORTED_EXTENSIONS:
                self.__error_message = "Unsupported file type"
                return

            self.__read_file_content()
        except Exception as e:
            self.__error_message = str(e)

    def __extract_file_extension(self) -> str:
        """ファイル名から拡張子を抽出します。

        Returns:
            ファイルの拡張子
        """
        return self.config_file.name.split(".")[-1]

    def __read_file_content(self) -> None:
        """ファイルの内容を読み込みます。"""
        try:
            self.__config_data = self.config_file.read().decode("utf-8")
        except UnicodeDecodeError as e:
            self.__error_message = str(e)

    def parse(self) -> bool:
        """設定ファイルをパースして辞書に変換します。

        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        if self.__config_data is None:
            return False

        try:
            self.__parsed_dict = self.__parse_by_file_type(self.__config_data)
            return True
        except (
            tomllib.TOMLDecodeError,
            yaml.MarkedYAMLError,
            yaml.reader.ReaderError,
            pd.errors.DtypeWarning,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            SyntaxError,
            TypeError,
            ValueError,
        ) as e:
            self.__error_message = str(e)
            self.__parsed_dict = None
            return False

    def _format_yaml_error_message(self, error: yaml.MarkedYAMLError) -> str:
        """Formats YAML parsing errors string for better readability.

        Specifically handles errors related to unexpected characters (like tabs vs spaces)

        Args:
            error: The original MarkedYAMLError exception.

        Returns:
            A formatted string representation of the error.
        """
        error_msg = str(error)
        # Standardize messages for errors caused by unexpected characters (e.g., tabs)
        if "found character" in error_msg and "that cannot start any token" in error_msg:
            # Replace multiple spaces representation with tab representation for clarity
            error_msg = error_msg.replace("found character '       '", "found character '\\t'")
            # If a tab was indeed found, duplicate the line showing the original space representation
            # for comparison, as sometimes the error context might involve mixed spacing.
            if "found character '\\t'" in error_msg:
                lines = error_msg.split("\n")
                for i, line in enumerate(lines):
                    if "found character '\\t'" in line:
                        # Insert the original space version before the tab version
                        lines.insert(i, line.replace("'\\t'", "'       '"))
                        break
                error_msg = "\n".join(lines)
        # Return the potentially modified error string
        return error_msg

    def __parse_by_file_type(self, config_data: str) -> Dict[str, Any]:
        """ファイルタイプに応じたパース処理を行います。

        Returns:
            パースされた辞書

        Raises:
            SyntaxError: YAMLファイルが辞書形式でない場合
            ValueError: CSV行名が1文字未満の場合または設定データがNoneの場合
        """

        match self.__file_extension:
            case "toml":
                return tomllib.loads(config_data)
            case "yaml" | "yml":
                try:
                    parsed_data = yaml.safe_load(config_data)
                    if not isinstance(parsed_data, dict):
                        raise SyntaxError("Invalid YAML file loaded.")
                    return parsed_data
                except yaml.MarkedYAMLError as e:
                    # Format the YAML error message (e.g., for logging if needed)
                    # formatted_msg = self._format_yaml_error_message(e)
                    # print(formatted_msg) # Example of logging
                    # Re-raise the original exception to preserve marks for tests
                    raise e from e
            case "csv":
                return self.__parse_csv_data(config_data)
            # The 'case _:' is used here to satisfy the type checker and catch unexpected states.
            # Validation in __initialize_from_file should prevent reaching this point.
            case _:
                raise RuntimeError(
                    f"Internal error: Reached __parse_by_file_type with unexpected extension '{self.__file_extension}'. "
                    "Validation should have caught this."
                )

    def __parse_csv_data(self, config_data: str) -> Dict[str, Any]:
        """CSVデータをパースします。

        Returns:
            パースされたCSVデータを含む辞書

        Raises:
            ValueError: CSV行名が1文字未満の場合または設定データがNoneの場合
        """

        csv_data = pd.read_csv(StringIO(config_data), index_col=None)

        if self.__is_enable_fill_nan:
            csv_data = self.__handle_csv_nan_values(csv_data)

        if isinstance(csv_data, pd.DataFrame):
            mapped_list = [row.to_dict() for _, row in csv_data.iterrows()]
            # Add check for empty data rows
            if not mapped_list:
                raise ValueError("CSV file must contain at least one data row.")
            return {self.csv_rows_name: mapped_list}

        return {}

    def __handle_csv_nan_values(self, csv_data: pd.DataFrame) -> pd.DataFrame:
        """CSVデータのNaN値を処理します。

        Args:
            csv_data: 処理するCSVデータ

        Returns:
            NaN値が処理されたCSVデータ
        """
        # 数値列に文字列を設定する場合の警告を回避するため、
        # 文字列値で置換する前に全ての列をオブジェクト型に変換
        if self.__fill_nan_with is not None and isinstance(self.__fill_nan_with, str):
            # 数値列を含む可能性のある全ての列をオブジェクト型に変換
            for col in csv_data.columns:
                if pd.api.types.is_numeric_dtype(csv_data[col]):
                    csv_data[col] = csv_data[col].astype("object")

        # NaN値を置換
        csv_data.fillna(value=self.__fill_nan_with, inplace=True)
        return csv_data

    def _validate_memory_size(self, obj: Any) -> bool:  # noqa: ANN401
        """メモリサイズのバリデーションを行います。

        Args:
            obj: 検証するオブジェクト

        Returns:
            メモリサイズが上限以内の場合はTrue、超える場合はFalse
        """
        try:
            memory_size = sys.getsizeof(obj)
            if memory_size > self.MAX_MEMORY_SIZE_BYTES:
                self.__error_message = (
                    f"Memory consumption exceeds the maximum limit of 150MB (actual: {memory_size / (1024 * 1024):.2f}MB)"
                )
                return False
            return True
        except (MemoryError, OverflowError) as e:
            self.__error_message = f"Memory error while checking size: {e!s}"
            return False

    @property
    def parsed_dict(self) -> Optional[Dict[str, Any]]:
        """パースされた辞書を返します。エラーが発生した場合やメモリ消費量が上限を超える場合はNoneを返します。

        Returns:
            パースされた辞書
        """
        if self.__parsed_dict is None:
            return None

        # メモリサイズのバリデーション
        if not self._validate_memory_size(self.__parsed_dict):
            return None

        return self.__parsed_dict

    @property
    def parsed_str(self) -> str:
        """パースされた辞書を文字列として返します。エラーが発生した場合は"None"を返します。
        メモリ消費量が上限を超える場合はエラーメッセージを設定し、"None"を返します。

        Returns:
            パースされた辞書の文字列表現
        """
        if self.__parsed_dict is None:
            return "None"

        try:
            # Format the dictionary to string
            formatted_str = pprint.pformat(self.__parsed_dict)

            # Validate memory size
            if not self._validate_memory_size(formatted_str):
                return "None"

            return formatted_str
        except (MemoryError, OverflowError) as e:
            self.__error_message = f"Memory error while formatting dictionary: {e!s}"
            return "None"

    @property
    def error_message(self) -> Optional[str]:
        """エラーメッセージを返します。

        Returns:
            エラーメッセージ
        """
        return self.__error_message

    @property
    def enable_fill_nan(self) -> bool:
        """NaNを埋めるオプションが有効かどうかを取得します。

        Returns:
            NaNを埋めるオプションが有効であればTrue、そうでなければFalse
        """
        return self.__is_enable_fill_nan

    @enable_fill_nan.setter
    def enable_fill_nan(self, is_fillna: bool) -> None:
        """NaNを埋めるオプションを設定します。

        Args:
            is_fillna: NaNを埋めるオプションを有効にするかどうか
        """
        self.__is_enable_fill_nan = is_fillna

    @property
    def fill_nan_with(self) -> Optional[str]:
        """NaNを埋める際の値を取得します。

        Returns:
            NaNを埋める際の値
        """
        return self.__fill_nan_with

    @fill_nan_with.setter
    def fill_nan_with(self, fillna_value: str) -> None:
        """NaNを埋める際の値を設定します。

        Args:
            fillna_value: NaNを埋める際の値
        """
        self.__fill_nan_with = fillna_value
