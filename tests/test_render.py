from io import BytesIO
from features.command_render import GhostwriterRender


def test_render_template_success():
    template_content = b"Hello {{ name }}!"
    template_file = BytesIO(template_content)
    context = {"name": "World"}
    render = GhostwriterRender(template_file, context)
    result = render.render_content
    assert result == "Hello World!"


def test_render_template_not_strict_undefined_success():
    template_content = b"Hello {{ name }}!"
    template_file = BytesIO(template_content)
    render = GhostwriterRender(template_file, {}, False)
    result = render.render_content
    assert result == "Hello !"


def test_render_template_with_undefined_error():
    template_content = b"Hello {{ user }}!"
    template_file = BytesIO(template_content)
    context = {"name": "World"}  # 'user' is not defined in the context
    render = GhostwriterRender(template_file, context)
    result = render.render_content
    assert result is None
    assert "undefined" in str(render.error_message).lower()


def test_render_template_with_unicode_decode_error():
    template_content = b"\x80\x81\x82\x83"
    template_file = BytesIO(template_content)
    context = {"name": "World"}
    render = GhostwriterRender(template_file, context)
    result = render.render_content
    assert result is None
    assert "'utf-8' codec can't decode byte 0x80 in position 0" in str(render.error_message)


def test_render_template_with_not_binary_error():
    template_file = "Hello {{ user }}!"
    context = {"name": "World"}
    render = GhostwriterRender(template_file, context)  # type: ignore
    result = render.render_content
    assert result is None
    assert "'str' object has no attribute 'read'" in str(render.error_message)


def test_render_template_with_syntax_error():
    template_content = b"Hello {{ name }!"
    template_file = BytesIO(template_content)
    render = GhostwriterRender(template_file, {}, False)
    result = render.render_content
    assert result is None
    assert "unexpected '}'" in str(render.error_message)
