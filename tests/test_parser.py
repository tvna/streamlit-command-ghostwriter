from io import BytesIO

from features.config_parser import GhostwriterParser


def test_parse_toml_success():
    toml_content = b"title = 'TOML Example'"
    configure_file = BytesIO(toml_content)
    configure_file.name = "config.toml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict == {"title": "TOML Example"}
    assert "{'title': 'TOML Example'}" in parser.parsed_str
    assert parser.error_message == "Not failed"


def test_parse_yaml_success():
    yaml_content = b"title: YAML Example"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yaml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict == {"title": "YAML Example"}
    assert parser.parsed_str == "{'title': 'YAML Example'}"
    assert parser.error_message == "Not failed"


def test_parse_yml_success():
    yaml_content = b"title: YAML Example"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict == {"title": "YAML Example"}
    assert parser.parsed_str == "{'title': 'YAML Example'}"
    assert parser.error_message == "Not failed"


def test_parse_toml_with_toml_decode_error():
    toml_content = b"title 'TOML Example'"
    configure_file = BytesIO(toml_content)
    configure_file.name = "config.toml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert "Expected '=' after a key in a key/value pair" in str(parser.error_message)


def test_parse_yaml_with_yaml_decode_error():
    yaml_content = b"name: name: YAML"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yaml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "mapping values are not allowed here" in str(parser.error_message)


def test_parse_yml_with_yaml_decode_error():
    yaml_content = b"name: name: YAML"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "mapping values are not allowed here" in str(parser.error_message)


def test_parse_toml_with_date_value_error():
    toml_content = b"title = 2024-04-00"
    configure_file = BytesIO(toml_content)
    configure_file.name = "config.toml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "Expected newline or end of document after a statement " in str(parser.error_message)


def test_parse_yaml_with_date_value_error():
    yaml_content = b"date: 2024-04-00"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yaml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "day is out of range for month" in str(parser.error_message)


def test_parse_yml_with_date_value_error():
    yaml_content = b"date: 2024-04-00"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "day is out of range for month" in str(parser.error_message)


def test_unsupported_file_type():
    content = b"unsupported content"
    configure_file = BytesIO(content)
    configure_file.name = "config.txt"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert "Unsupported file type" in str(parser.error_message)


def test_non_binary_config():
    parser = GhostwriterParser("title = 'TOML Example'")  # type: ignore
    assert parser.parsed_dict is None
    assert "バイナリが引数に指定されていません。" in str(parser.error_message)


def test_parsed_toml_with_decode_error_return_str_none():
    toml_content = b"title 'TOML Example'"
    configure_file = BytesIO(toml_content)
    configure_file.name = "config.toml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_str == "None"


def test_parsed_yaml_with_decode_error_return_str_none():
    # parsed_strがNoneを返すケース
    yaml_content = b"name: name: YAML"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yaml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_str == "None"


def test_parsed_yml_with_decode_error_return_str_none():
    # parsed_strがNoneを返すケース
    yaml_content = b"name: name: YAML"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_str == "None"


def test_parse_toml_with_unicode_decode_error():
    yaml_content = b"\x80\x81\x82\x83"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.toml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "invalid start byte" in str(parser.error_message)


def test_parse_yaml_with_unicode_decode_error():
    yaml_content = b"\x80\x81\x82\x83"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yaml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "invalid start byte" in str(parser.error_message)


def test_parse_yml_with_unicode_decode_error():
    yaml_content = b"\x80\x81\x82\x83"
    configure_file = BytesIO(yaml_content)
    configure_file.name = "config.yml"
    parser = GhostwriterParser(configure_file)
    assert parser.parsed_dict is None
    assert parser.parsed_str == "None"
    assert "invalid start byte" in str(parser.error_message)
