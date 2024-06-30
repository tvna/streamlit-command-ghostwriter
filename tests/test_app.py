import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.unit()
def test_main_layout() -> None:
    """Test streamlit app layout"""

    at = AppTest.from_file("app.py").run()

    # startup
    assert at.title.len == 1
    assert len(at.tabs) == 4
    assert len(at.columns) == 12
    assert at.subheader.len == 6
    assert len(at.sidebar) == 2
    assert at.markdown.len == 2
    assert at.button.len == 3
    assert at.button[0].value is False
    assert at.button[1].value is False
    assert at.button[2].value is False
    assert at.error.len == 0
    assert at.warning.len == 0
    assert at.success.len == 0
    assert at.radio.len == 1
    assert at.toggle.len == 3
    assert at.selectbox.len == 2
    assert at.text_input.len == 2
    assert at.text_area.len == 6

    # click "generate_text_button" without uploaded files
    at.button[0].click().run()
    assert at.button[0].value is True
    assert at.button[1].value is False
    assert at.button[2].value is False
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0

    # click "generate_markdown_button" without uploaded files
    at.button[1].click().run()
    assert at.button[0].value is False
    assert at.button[1].value is True
    assert at.button[2].value is False
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0

    # click "generate_debug_config" without uploaded file
    at.button[2].click().run()
    assert at.button[0].value is False
    assert at.button[1].value is False
    assert at.button[2].value is True
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0
