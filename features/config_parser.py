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

    def __init__(self: "ConfigParser", config_file: BytesIO) -> None:
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
        return self.__csv_rows_name

    @csv_rows_name.setter
    def csv_rows_name(self: "ConfigParser", rows_name: str) -> None:
        """Set list variable name when CSV rows are converted to arrays."""

        self.__csv_rows_name = rows_name

    def parse(self: "ConfigParser") -> bool:
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
                    mapped_list = [row._asdict() for row in csv_data.itertuples(index=False)]  # type: ignore

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
        """コンフィグファイルをパースして辞書を返す。エラーが発生した場合はNoneを返す。"""
        return self.__parsed_dict

    @property
    def parsed_str(self: "ConfigParser") -> str:
        """コンフィグファイルをパースして文字列を返す。エラーが発生した場合は"None"を返す。"""
        return pprint.pformat(self.__parsed_dict)

    @property
    def error_message(self: "ConfigParser") -> Optional[str]:
        """エラーメッセージを返す。"""
        return self.__error_message
