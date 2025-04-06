from _pytest.config import Config as PytestConfig


def pytest_configure(config: PytestConfig) -> None:
    """pytestの設定を構成.

    Args:
        config: pytestの設定オブジェクト

    Note:
        - カスタムマーカー (e2e) の登録
        - ベンチマーク設定の構成
          - 自動保存の有効化
          - 保存先ディレクトリの設定
          - 比較対象の設定
          - ヒストグラム出力の設定
    """
    # Add registrations for other markers found in pyproject.toml
    config.addinivalue_line("markers", "unit: mark a test as a unit test.")
    config.addinivalue_line("markers", "integration: mark a test as an integration test.")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "benchmark: mark a test for benchmarking")
