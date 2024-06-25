import pytest

from i18n import LANGUAGES


@pytest.mark.unit()
def test_i11n_japanese() -> None:
    assert isinstance(LANGUAGES, dict)
    assert "日本語" in LANGUAGES.keys()

    for k, v in LANGUAGES["日本語"].items():
        assert isinstance(k, str)
        assert isinstance(v, str)
