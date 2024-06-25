#! /usr/bin/env python
import pprint
import tomllib
from io import BytesIO, StringIO
from typing import Any, Dict, Optional

import pandas as pd
import yaml


class GhostwriterParser:
    def __init__(self: "GhostwriterParser") -> None:
        """
        TOMLファイルをパースするためのクラスを初期化する。
        """

        self.__file_extension: Optional[str] = None
        self.__config_data: Optional[str] = None
        self.__parsed_dict: Optional[Dict[str, Any]] = None
        self.__error_message: Optional[str] = None
        self.__csv_rows_name: str = "csv_rows"

    def load_config_file(self: "GhostwriterParser", config_file: BytesIO) -> "GhostwriterParser":
        try:
            self.__file_extension = config_file.name.split(".")[-1]
            if self.__file_extension not in ["toml", "yaml", "yml", "csv"]:
                self.__error_message = "Unsupported file type"
                return self

            self.__config_data = config_file.read().decode("utf-8")

        except UnicodeDecodeError as e:
            self.__error_message = str(e)

        return self

    def set_csv_rows_name(self: "GhostwriterParser", rows_name: str) -> "GhostwriterParser":
        """Set list variable name when CSV rows are converted to arrays."""

        self.__csv_rows_name = rows_name

        return self

    def parse(self: "GhostwriterParser") -> bool:
        if self.__config_data is None:
            return False

        try:
            match self.__file_extension:
                case "toml":
                    self.__parsed_dict = tomllib.loads(self.__config_data)
                case "yaml" | "yml":
                    self.__parsed_dict = yaml.safe_load(self.__config_data)
                case "csv":
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
            TypeError,
            ValueError,
        ) as e:
            self.__error_message = str(e)

        if self.__parsed_dict is None:
            print(self.__error_message)
            return False

        if self.__file_extension in {"yaml", "yml"} and not isinstance(self.__parsed_dict, dict):
            self.__error_message = "Invalid YAML file loaded."
            self.__parsed_dict = None
            return False

        return True

    @property
    def parsed_dict(self: "GhostwriterParser") -> Optional[Dict[str, Any]]:
        """
        コンフィグファイルをパースして辞書を返す。エラーが発生した場合はNoneを返す。
        """
        return self.__parsed_dict

    @property
    def parsed_str(self: "GhostwriterParser") -> str:
        """
        コンフィグファイルをパースして文字列を返す。エラーが発生した場合は"None"を返す。
        """
        return pprint.pformat(self.__parsed_dict)

    @property
    def error_message(self: "GhostwriterParser") -> Optional[str]:
        """エラーメッセージを返す。"""
        return self.__error_message
