#! /usr/bin/env python
import pprint
import tomllib
from io import BytesIO
from typing import Any, Dict, Optional

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

    def load_config_file(self: "GhostwriterParser", config_file: BytesIO) -> "GhostwriterParser":

        try:
            self.__file_extension = config_file.name.split(".")[-1]
            if self.__file_extension not in ["toml", "yaml", "yml"]:
                self.__error_message = "Unsupported file type"
                return self

            self.__config_data = config_file.read().decode("utf-8")
        except UnicodeDecodeError as e:
            self.__error_message = str(e)

        return self

    def parse(self: "GhostwriterParser") -> bool:

        if self.__config_data is None:
            return False

        try:
            if self.__file_extension == "toml":
                self.__parsed_dict = tomllib.loads(self.__config_data)

            if self.__file_extension in {"yaml", "yml"}:
                self.__parsed_dict = yaml.load(self.__config_data, yaml.FullLoader)

        except (tomllib.TOMLDecodeError, TypeError) as e:
            self.__error_message = str(e)
            return False
        except (yaml.MarkedYAMLError, yaml.reader.ReaderError, ValueError) as e:
            self.__error_message = str(e)

        if isinstance(self.__parsed_dict, str):
            self.__error_message = "Invalid YAML file loaded."
            self.__parsed_dict = None

        if self.__parsed_dict is None:
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
