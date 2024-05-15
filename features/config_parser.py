#! /usr/bin/env python
import pprint
import tomllib
from io import BytesIO
from typing import Any, Dict, Optional

import yaml


class GhostwriterParser:
    def __init__(self, config_file: BytesIO) -> None:
        """
        TOMLファイルをパースするためのクラスを初期化する。
        """

        self.__parsed_dict: Optional[Dict[str, Any]] = None
        self.__error_message: str = "Not failed"

        try:
            file_extension: str = config_file.name.split(".")[-1]
            config_data = config_file.read().decode("utf-8")
        except AttributeError:
            self.__error_message = "バイナリが引数に指定されていません。"
            return None
        except UnicodeDecodeError as e:
            self.__error_message = str(e)
            return None

        if file_extension == "toml":
            self.__parsed_dict = self.__parse_toml(config_data)  # type: ignore
        elif file_extension in ["yaml", "yml"]:
            self.__parsed_dict = self.__parse_yaml(config_data)  # type: ignore
        else:
            self.__error_message = "Unsupported file type"

    def __parse_toml(self, source_content: str) -> Optional[Dict[str, Any]]:
        """TOMLファイルをパースして辞書を返す。エラーが発生した場合はNoneを返す。"""
        try:
            toml_dict = tomllib.loads(source_content)
            return toml_dict
        except (tomllib.TOMLDecodeError, TypeError) as e:
            self.__error_message = str(e)
            return None

    def __parse_yaml(self, source_content) -> Optional[Dict[str, Any]]:
        """YAMLファイルをパースして辞書を返す。エラーが発生した場合はNoneを返す。"""
        try:
            yaml_dict = yaml.safe_load(source_content)
            return yaml_dict
        except (yaml.YAMLError, ValueError) as e:
            self.__error_message = str(e)
            return None

    @property
    def parsed_dict(self) -> Optional[Dict[str, Any]]:
        """
        コンフィグファイルをパースして辞書を返す。エラーが発生した場合はNoneを返す。
        """
        return self.__parsed_dict

    @property
    def parsed_str(self) -> str:
        """
        コンフィグファイルをパースして文字列を返す。エラーが発生した場合は"None"を返す。
        """
        return pprint.pformat(self.__parsed_dict)

    @property
    def error_message(self) -> str:
        """エラーメッセージを返す。"""
        return self.__error_message
