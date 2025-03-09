#! /usr/bin/env python
import pprint
import tomllib
from io import BytesIO, StringIO
from typing import Any, Dict, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, PrivateAttr


class ConfigParser(BaseModel):
    __file_extension: str = PrivateAttr()
    __config_data: Optional[str] = PrivateAttr(default=None)
    __parsed_dict: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    __error_message: Optional[str] = PrivateAttr(default=None)
    __csv_rows_name: str = PrivateAttr(default="csv_rows")
    __is_enable_fill_nan: bool = PrivateAttr(default=False)
    __fill_nan_with: Optional[str] = PrivateAttr(default=None)

    def __init__(self: "ConfigParser", config_file: BytesIO) -> None:
        """
        ConfigParserの初期化メソッド。

        Args:
            config_file (BytesIO): 設定ファイルのバイナリデータ。
        """
        super().__init__()

        self.__file_extension = config_file.name.split(".")[-1]
        if self.__file_extension not in ["toml", "yaml", "yml", "csv"]:
            self.__error_message = "Unsupported file type"
            return

        try:
            self.__config_data = config_file.read().decode("utf-8")

        except UnicodeDecodeError as e:
            self.__error_message = str(e)

    @property
    def csv_rows_name(self: "ConfigParser") -> str:
        """CSV行名を取得します。

        Returns:
            str: CSV行名。
        """
        return self.__csv_rows_name

    @csv_rows_name.setter
    def csv_rows_name(self: "ConfigParser", rows_name: str) -> None:
        """CSV行名を設定します。

        Args:
            rows_name (str): 設定する行名。
        """
        self.__csv_rows_name = rows_name

    @property
    def enable_fill_nan(self: "ConfigParser") -> bool:
        """NaNを埋めるオプションが有効かどうかを取得します。

        Returns:
            bool: NaNを埋めるオプションが有効であればTrue、そうでなければFalse。
        """
        return self.__is_enable_fill_nan

    @enable_fill_nan.setter
    def enable_fill_nan(self: "ConfigParser", is_fillna: bool) -> None:
        """NaNを埋めるオプションを設定します。

        Args:
            is_fillna (bool): NaNを埋めるオプションを有効にするかどうか。
        """
        self.__is_enable_fill_nan = is_fillna

    @property
    def fill_nan_with(self: "ConfigParser") -> Optional[str]:
        """NaNを埋める際の値を取得します。

        Returns:
            Optional[str]: NaNを埋める際の値。
        """
        return self.__fill_nan_with

    @fill_nan_with.setter
    def fill_nan_with(self: "ConfigParser", fillna_value: str) -> None:
        """NaNを埋める際の値を設定します。

        Args:
            fillna_value (str): NaNを埋める際の値。
        """
        self.__fill_nan_with = fillna_value

    def parse(self: "ConfigParser") -> bool:
        """設定ファイルをパースして辞書に変換します。

        Returns:
            bool: 成功した場合はTrue、失敗した場合はFalse。
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

    @property
    def parsed_dict(self: "ConfigParser") -> Optional[Dict[str, Any]]:
        """パースされた辞書を返します。エラーが発生した場合はNoneを返します。

        Returns:
            Optional[Dict[str, Any]]: パースされた辞書。
        """
        return self.__parsed_dict

    @property
    def parsed_str(self: "ConfigParser") -> str:
        """パースされた辞書を文字列として返します。エラーが発生した場合は"None"を返します。

        Returns:
            str: パースされた辞書の文字列表現。
        """
        return pprint.pformat(self.__parsed_dict)

    @property
    def error_message(self: "ConfigParser") -> Optional[str]:
        """エラーメッセージを返します。

        Returns:
            Optional[str]: エラーメッセージ。
        """
        return self.__error_message
