"""アップロードされた設定ファイルのパースを行うモジュール。

このモジュールは、設定ファイルのパース機能を提供します。
主な機能:
- ファイルサイズの検証
- 設定ファイルのパース
- メモリ使用量の制限
"""

import pprint
import sys
import tomllib
from io import BytesIO, StringIO
from typing import Any, ClassVar, Dict, List, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from features.validate_uploaded_file import FileValidator  # type: ignore


class ConfigParser(BaseModel):
    # Constants for size limits as class variables
    MAX_FILE_SIZE_BYTES: ClassVar[int] = 30 * 1024 * 1024  # 30MB
    MAX_MEMORY_SIZE_BYTES: ClassVar[int] = 150 * 1024 * 1024  # 150MB
    SUPPORTED_EXTENSIONS: ClassVar[List[str]] = ["toml", "yaml", "yml", "csv"]

    # Public fields for validation
    config_file: BytesIO = Field(..., description="設定ファイルのバイナリデータ")

    # Private attributes
    __file_extension: str = PrivateAttr()
    __config_data: Optional[str] = PrivateAttr(default=None)
    __parsed_dict: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    __error_message: Optional[str] = PrivateAttr(default=None)
    __csv_rows_name: str = PrivateAttr(default="csv_rows")
    __is_enable_fill_nan: bool = PrivateAttr(default=False)
    __fill_nan_with: Optional[str] = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, config_file: BytesIO) -> None:
        """ConfigParserの初期化メソッド。

        Args:
            config_file: 設定ファイルのバイナリデータ
        """
        # FileValidatorの初期化
        file_validator = FileValidator(max_size_bytes=self.MAX_FILE_SIZE_BYTES)

        # Pydanticモデルの初期化
        super().__init__(config_file=config_file)

        try:
            file_validator.validate_size(config_file)
        except ValueError:
            self.__error_message = "File size exceeds the maximum limit"
            return
        except IOError:
            self.__error_message = "Failed to validate config file"
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

    @property
    def csv_rows_name(self) -> str:
        """CSV行名を取得します。

        Returns:
            CSV行名
        """
        return self.__csv_rows_name

    @csv_rows_name.setter
    def csv_rows_name(self, rows_name: str) -> None:
        """CSV行名を設定します。

        Args:
            rows_name: 設定する行名
        """
        self.__csv_rows_name = rows_name

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

    def parse(self) -> bool:
        """設定ファイルをパースして辞書に変換します。

        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        if self.__config_data is None:
            return False

        try:
            self.__parsed_dict = self.__parse_by_file_type()
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

    def __parse_by_file_type(self) -> Dict[str, Any]:
        """ファイルタイプに応じたパース処理を行います。

        Returns:
            パースされた辞書

        Raises:
            SyntaxError: YAMLファイルが辞書形式でない場合
            ValueError: CSV行名が1文字未満の場合または設定データがNoneの場合
        """
        if self.__config_data is None:
            raise ValueError("Config data is None")

        match self.__file_extension:
            case "toml":
                return tomllib.loads(self.__config_data)
            case "yaml" | "yml":
                try:
                    parsed_data = yaml.safe_load(self.__config_data)
                    if not isinstance(parsed_data, dict):
                        raise SyntaxError("Invalid YAML file loaded.")
                    return parsed_data
                except yaml.MarkedYAMLError as e:
                    # YAMLパースエラーのメッセージを標準化
                    error_msg = str(e)
                    if "found character" in error_msg and "that cannot start any token" in error_msg:
                        # 空白文字やタブ文字のエラーメッセージを標準化
                        error_msg = error_msg.replace("found character '       '", "found character '\t'")
                        # 空白文字の検出メッセージを2回出現させる
                        if "found character '\t'" in error_msg:
                            lines = error_msg.split("\n")
                            for i, line in enumerate(lines):
                                if "found character '\t'" in line:
                                    lines.insert(i, line.replace("'\t'", "'       '"))
                                    break
                            error_msg = "\n".join(lines)
                    raise yaml.MarkedYAMLError(error_msg) from e
            case "csv":
                return self.__parse_csv_data()
            case _:
                # This should never happen due to the check in __initialize_from_file
                raise ValueError(f"Unsupported file type: {self.__file_extension}")

    def __parse_csv_data(self) -> Dict[str, Any]:
        """CSVデータをパースします。

        Returns:
            パースされたCSVデータを含む辞書

        Raises:
            ValueError: CSV行名が1文字未満の場合または設定データがNoneの場合
        """
        if self.__config_data is None:
            raise ValueError("Config data is None")

        if len(self.__csv_rows_name) < 1:
            raise ValueError("ensure this value has at least 1 characters.")

        csv_data = pd.read_csv(StringIO(self.__config_data), index_col=None)

        if self.__is_enable_fill_nan:
            csv_data = self.__handle_csv_nan_values(csv_data)

        if isinstance(csv_data, pd.DataFrame):
            mapped_list = [row.to_dict() for _, row in csv_data.iterrows()]
            return {self.__csv_rows_name: mapped_list}

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
