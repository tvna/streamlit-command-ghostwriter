import pytest

from i18n import LANGUAGES


@pytest.mark.unit()
def test_i11n_japanese() -> None:
    assert isinstance(LANGUAGES, dict)
    assert "日本語" in LANGUAGES.keys()

    for nest1_key, nest1_val in LANGUAGES["日本語"].items():
        assert isinstance(nest1_key, str)
        assert isinstance(nest1_val, dict)
        for nest2_key, nest2_val in nest1_val.items():
            assert isinstance(nest2_key, str)
            assert isinstance(nest2_val, str)
