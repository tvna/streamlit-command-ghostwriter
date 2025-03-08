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
    assert at.button.len == 5
    assert at.button(key="tab1_execute_text").value is False
    assert at.button(key="tab1_execute_markdown").value is False
    assert at.button(key="tab2_execute_visual").value is False
    assert at.button(key="tab2_execute_toml").value is False
    assert at.button(key="tab2_execute_yaml").value is False
    assert at.error.len == 0
    assert at.warning.len == 0
    assert at.success.len == 0
    assert at.radio.len == 1
    assert at.toggle.len == 4
    assert at.selectbox.len == 2
    assert at.text_input.len == 3
    assert at.text_area.len == 6

    at.button(key="tab1_execute_text").click().run()
    assert at.button(key="tab1_execute_text").value is True
    assert at.button(key="tab1_execute_markdown").value is False
    assert at.button(key="tab2_execute_visual").value is False
    assert at.button(key="tab2_execute_toml").value is False
    assert at.button(key="tab2_execute_yaml").value is False
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0

    at.button(key="tab1_execute_markdown").click().run()
    assert at.button(key="tab1_execute_text").value is False
    assert at.button(key="tab1_execute_markdown").value is True
    assert at.button(key="tab2_execute_visual").value is False
    assert at.button(key="tab2_execute_toml").value is False
    assert at.button(key="tab2_execute_yaml").value is False
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0

    at.button(key="tab2_execute_visual").click().run()
    assert at.button(key="tab1_execute_text").value is False
    assert at.button(key="tab1_execute_markdown").value is False
    assert at.button(key="tab2_execute_visual").value is True
    assert at.button(key="tab2_execute_toml").value is False
    assert at.button(key="tab2_execute_yaml").value is False
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0

    at.button(key="tab2_execute_toml").click().run()
    assert at.button(key="tab1_execute_text").value is False
    assert at.button(key="tab1_execute_markdown").value is False
    assert at.button(key="tab2_execute_visual").value is False
    assert at.button(key="tab2_execute_toml").value is True
    assert at.button(key="tab2_execute_yaml").value is False
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0

    at.button(key="tab2_execute_yaml").click().run()
    assert at.button(key="tab1_execute_text").value is False
    assert at.button(key="tab1_execute_markdown").value is False
    assert at.button(key="tab2_execute_visual").value is False
    assert at.button(key="tab2_execute_toml").value is False
    assert at.button(key="tab2_execute_yaml").value is True
    assert at.error.len == 0
    assert at.warning.len == 1
    assert at.success.len == 0
