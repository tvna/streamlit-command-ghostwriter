import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.unit()
def test_main_layout() -> None:
    """Test streamlit app layout"""

    at = AppTest.from_file("app.py").run()

    # startup
    assert at.title.len == 1
    assert len(at.tabs) == 3
    assert len(at.columns) == 12
    assert len(at.sidebar) == 2
    assert len(at.markdown) == 4
    assert at.button.len == 3
    assert at.button[0].value is False
    assert at.button[1].value is False
    assert at.button[2].value is False
    assert len(at.error) == 0
    assert len(at.warning) == 0
    assert len(at.success) == 0
    assert at.radio.len == 1
    assert at.toggle.len == 2
    assert at.selectbox.len == 1
    assert at.text_input.len == 2
    assert at.text_area.len == 0

    # click "generate_text_button" without uploaded files
    at.button[0].click().run()
    assert at.button[0].value is True
    assert at.button[1].value is False
    assert at.button[2].value is False
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert len(at.success) == 0

    # click "generate_markdown_button" without uploaded files
    at.button[1].click().run()
    assert at.button[0].value is False
    assert at.button[1].value is True
    assert at.button[2].value is False
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert len(at.success) == 0

    # click "generate_debug_config" without uploaded file
    at.button[2].click().run()
    assert at.button[0].value is False
    assert at.button[1].value is False
    assert at.button[2].value is True
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert len(at.success) == 0
