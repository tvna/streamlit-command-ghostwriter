#! /usr/bin/env python
import pprint
import sys
import tomllib
from io import BytesIO, StringIO
from typing import Any, ClassVar, Dict, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, Field, PrivateAttr, field_validator


class ConfigParser(BaseModel):
    # Constants for size limits as class variables
    MAX_FILE_SIZE_BYTES: ClassVar[int] = 30 * 1024 * 1024  # 30MB
    MAX_MEMORY_SIZE_BYTES: ClassVar[int] = 150 * 1024 * 1024  # 150MB

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

    class Config:
        arbitrary_types_allowed = True

    @field_validator("config_file")
    def _validate_file_size(cls, v: BytesIO) -> BytesIO:  # noqa: N805
        """ファイルサイズのバリデーションを行います。

        Args:
            v: 検証するファイルオブジェクト

        Returns:
            検証済みのファイルオブジェクト

        Raises:
            ValueError: ファイルサイズが上限を超えている場合
        """
        # Check file size
        v.seek(0, 2)  # Move to the end of the file
        file_size = v.tell()  # Get current position (file size)
        v.seek(0)  # Reset position to the beginning

        if file_size > cls.MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size exceeds the maximum limit of 30MB (actual: {file_size / (1024 * 1024):.2f}MB)")
        return v

    def __init__(self, config_file: BytesIO) -> None:
        """ConfigParserの初期化メソッド。

        Args:
            config_file: 設定ファイルのバイナリデータ
        """
        # Pydanticモデルの初期化
        super().__init__(config_file=config_file)

        try:
            self.__file_extension = self.config_file.name.split(".")[-1]
            if self.__file_extension not in ["toml", "yaml", "yml", "csv"]:
                self.__error_message = "Unsupported file type"
                return

            try:
                self.__config_data = self.config_file.read().decode("utf-8")
            except UnicodeDecodeError as e:
                self.__error_message = str(e)
        except Exception as e:
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
            match self.__file_extension:
                case "toml":
                    self.__parsed_dict = tomllib.loads(self.__config_data)
                case "yaml" | "yml":
                    self.__parsed_dict = yaml.safe_load(self.__config_data)

                    if not isinstance(self.__parsed_dict, dict):
                        raise SyntaxError("Invalid YAML file loaded.")
                case "csv":
                    if len(self.__csv_rows_name) < 1:
                        raise ValueError("ensure this value has at least 1 characters.")

                    csv_data = pd.read_csv(StringIO(self.__config_data), index_col=None)

                    if self.__is_enable_fill_nan is True:
                        csv_data.fillna(value=self.__fill_nan_with, inplace=True)

                    if isinstance(csv_data, pd.DataFrame):
                        mapped_list = [row.to_dict() for _, row in csv_data.iterrows()]
                        self.__parsed_dict = {self.__csv_rows_name: mapped_list}

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

        return True

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
