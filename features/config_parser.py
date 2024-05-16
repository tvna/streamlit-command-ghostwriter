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
            self.__config_data = config_file.read().decode("utf-8")
            if self.__file_extension not in ["toml", "yaml", "yml"]:
                self.__error_message = "Unsupported file type"
        except AttributeError:
            self.__error_message = "バイナリが引数に指定されていません。"
        except UnicodeDecodeError as e:
            self.__error_message = str(e)

        return self

    def parse(self: "GhostwriterParser") -> bool:

        if self.__config_data is None:
            return False

        match self.__file_extension:
            case "toml":
                self.__parsed_dict = self.__parse_toml(self.__config_data)

            case "yaml":
                self.__parsed_dict = self.__parse_yaml(self.__config_data)

            case "yml":
                self.__parsed_dict = self.__parse_yaml(self.__config_data)

            case _:
                return False

        return True

    def __parse_toml(self: "GhostwriterParser", source_content: str) -> Optional[Dict[str, Any]]:
        """TOMLファイルをパースして辞書を返す。エラーが発生した場合はNoneを返す。"""
        try:
            toml_dict = tomllib.loads(source_content)
            return toml_dict
        except (tomllib.TOMLDecodeError, TypeError) as e:
            self.__error_message = str(e)
            return None

    def __parse_yaml(self: "GhostwriterParser", source_content: str) -> Optional[Dict[str, Any]]:
        """YAMLファイルをパースして辞書を返す。エラーが発生した場合はNoneを返す。"""
        try:
            yaml_dict = yaml.safe_load(source_content)
            return yaml_dict
        except (yaml.YAMLError, ValueError) as e:
            self.__error_message = str(e)
            return None

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
