#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""E2Eテスト用のユーティリティモジュール.

このモジュールは、StreamlitアプリケーションのE2Eテストを支援する機能を提供します:

  - テストデータの管理
    - 各種設定ファイルのサンプルデータ
    - 一時ファイルの自動生成
    - ファイル種別ごとのテンプレート

  - UI操作の支援
    - ファイルアップロード
    - タブ切り替え
    - ボタンクリック
    - 結果の検証

  - 表示形式の制御
    - Visual (JSON)
    - TOML
    - YAML

Typical usage example:

  helper = StreamlitTestHelper(page)
  helper.select_tab("設定")
  helper.upload_config_and_template("config.toml", "template.j2")
  helper.click_button("生成")
  result = helper.check_result_displayed(["expected content"])
"""

import os
import sys
import tempfile
from typing import Dict, Final, List, Optional

from box import Box
from playwright.sync_api import FileChooser, Locator, Page, expect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from i18n import LANGUAGES

# 言語リソースの設定
DEFAULT_LANGUAGE: Final[str] = "日本語"
texts: Final[Box] = Box(LANGUAGES[DEFAULT_LANGUAGE])


class TestData:
    """テストデータを管理するクラス.

    このクラスは、E2Eテストで使用する各種サンプルデータを提供します。
    サポートされるファイル形式:
      - テキストファイル (.txt)
      - DNS設定ファイル (.csv)
      - DNSテンプレート (.j2)
      - WGET設定ファイル (.yaml)
      - WGETテンプレート (.j2)
      - Cisco設定ファイル (.toml)
      - Ciscoテンプレート (.jinja2)

    Attributes:
        SAMPLE_TXT: サンプルテキストファイルの内容
        DNS_DIG_CONFIG_CSV: DNS設定ファイルの内容
        DNS_DIG_TMPL_J2: DNSテンプレートファイルの内容
        WGET_CONFIG_YAML: WGET設定ファイルの内容
        WGET_TEMPLATE_J2: WGETテンプレートファイルの内容
        CISCO_CONFIG_TOML: Cisco設定ファイルの内容
        CISCO_TEMPLATE_JINJA2: Ciscoテンプレートファイルの内容

    Example:
        test_file_path = TestData.get_test_file_path("config.toml")
        with open(test_file_path) as f:
            content = f.read()
    """

    # サンプルテキストファイル
    SAMPLE_TXT: Final[str] = """This is a sample text file for testing file uploads in the Streamlit application.

It contains multiple lines of text to simulate a real file.

You can use this file to test the file upload functionality in your E2E tests."""

    # DNS設定ファイル (CSV)
    DNS_DIG_CONFIG_CSV: Final[str] = """resolver,fqdn,type
1.1.1.1,www.yahoo.co.jp,a
1.1.1.1,yahoo.co.jp,mx
1.1.1.1,yahoo.co.jp,txt
8.8.8.8,gmail.com,mx
8.8.8.8,gmail.com,txt
8.8.8.8,_dmarc.gmail.com,txt
8.8.8.8,selector1._domainkey.live.com,txt
,selector2._domainkey.live.com,txt"""

    # DNSテンプレートファイル (Jinja2)
    DNS_DIG_TMPL_J2: Final[str] = """
{% for row in csv_rows %}
dig @{{ row["resolver"] }} {{ row["fqdn"] }} {{ row["type"] }} +short
{% endfor %}"""

    # 成功設定ファイル (YAML)
    WGET_CONFIG_YAML: Final[str] = """url: "https://example.com/samplefile.txt"
date: 2024-04-01

users:
  test:
    first_name: "太郎"
    last_name: "テスト"
"""

    # 成功テンプレートファイル (Jinja2)
    WGET_TEMPLATE_J2: Final[str] = """# wget operation

```bash
wget {{ url }}
```

{% for key, val in users.items() %}
{{ key }}: こんにちわ、{{ val["last_name"] }} {{ val["first_name"] }}
{% endfor %}

```mermaid
flowchart LR
  start --> wget
  wget --> close
```"""

    # Cisco設定ファイル (TOML)
    CISCO_CONFIG_TOML: Final[str] = """[global]
hostname = "SAMPLE-ROUTER-001"
vlans = [10, 20, 30, 99]

[global.password]
enable = "P@ssw0rd"

[interfaces."GigabitEthernet0/1"]
mode = "access"
access_vlan = 10
description = "admin office"
cdp_enable = false

[interfaces."GigabitEthernet0/2"]
mode = "access"
access_vlan = 20
description = "accounting office"
cdp_enable = false

[interfaces."GigabitEthernet0/3"]
mode = "access"
access_vlan = 30
description = "engineering office"
cdp_enable = false

[interfaces."GigabitEthernet0/19"]
mode = "trunk"
native_vlan = 99
description = "access point #2"
cdp_enable = true

[interfaces."GigabitEthernet0/20"]
mode = "trunk"
native_vlan = 99
description = "access point #1"
cdp_enable = true

[interfaces."GigabitEthernet0/23"]
mode = "trunk"
description = "uplink #2"
cdp_enable = true

[interfaces."GigabitEthernet0/24"]
mode = "trunk"
description = "uplink #1"
cdp_enable = true"""

    # Ciscoテンプレートファイル (Jinja2)
    CISCO_TEMPLATE_JINJA2: Final[str] = """enable
{{ global.password.enable }}

ter len 0

# show commands
show running-config
show startup-config
show int status
show int trunk

# change config commands
conf t

hostname {{ global.hostname }}

{% for vlan in global.vlans %}
vlan {{ vlan }}
  name ##_VLAN-{{ vlan }}_##
exit
{% endfor %}

no ip domain-lookup
vtp mode transparent

{% for name, intf in interfaces.items() %}
interface {{ name }}
  switchport mode {{ intf["mode"] }}
  {% if intf["mode"] == "access" %}
  switchport access vlan {{ intf["access_vlan"] }}
{% else %}
{% if intf["trunk_vlan"] is defined %}
  switchport trunk vlan {{ intf["trunk_vlan"] }}
    {% endif %}
    {% if intf["native_vlan"] is defined %}
  switchport trunk native vlan {{ intf["native_vlan"] }}
    {% endif %}
  {% endif %}
  switchport nonegotiate
  {% if intf["description"] is defined %}
  description {{ intf["description"] }}
  {% endif %}
  {% if intf["cdp_enable"] == true %}
  cdp enable
  {% else %}
  no cdp enable
  {% endif %}
exit
{% endfor %}


# show commands
show int status
show int trunk
show running-config
show startup-config"""

    @classmethod
    def get_test_file_path(cls, file_name: str) -> str:
        """テストファイルを一時ファイルとして作成.

        指定されたファイル名に対応するテストデータを一時ファイルとして作成し、
        そのパスを返します。一時ファイルはテスト終了時に自動的に削除されます。

        Args:
            file_name: 作成するファイルの名前
                サポートされる名前:
                - sample.txt
                - dns_dig_config.csv
                - dns_dig_tmpl.j2
                - wget_config.yaml
                - wget_template.j2
                - cisco_config.toml
                - cisco_template.jinja2

        Returns:
            str: 作成された一時ファイルの絶対パス

        Example:
            test_file_path = TestData.get_test_file_path("config.toml")
            helper.upload_file(selector, test_file_path)
        """
        content: Final[str] = cls._get_file_content(file_name)

        fd: int
        path: str
        fd, path = tempfile.mkstemp(suffix=f"_{file_name}")
        with os.fdopen(fd, "w") as f:
            f.write(content)

        return path

    @classmethod
    def _get_file_content(cls, file_name: str) -> str:
        """ファイル名に対応するテストデータを取得.

        Args:
            file_name: 取得するファイルの名前

        Returns:
            str: ファイルの内容
                対応するファイルが存在しない場合は空文字列
        """
        file_content_map: Final[Dict[str, str]] = {
            "sample.txt": cls.SAMPLE_TXT,
            "dns_dig_config.csv": cls.DNS_DIG_CONFIG_CSV,
            "dns_dig_tmpl.j2": cls.DNS_DIG_TMPL_J2,
            "wget_config.yaml": cls.WGET_CONFIG_YAML,
            "wget_template.j2": cls.WGET_TEMPLATE_J2,
            "cisco_config.toml": cls.CISCO_CONFIG_TOML,
            "cisco_template.jinja2": cls.CISCO_TEMPLATE_JINJA2,
        }

        return file_content_map.get(file_name, "")


class StreamlitTestHelper:
    """StreamlitアプリケーションのE2Eテストを支援するクラス.

    このクラスは、StreamlitアプリケーションのE2Eテストにおいて、
    一般的なUI操作と検証を簡単に行うためのメソッドを提供します。

    主な機能:
      - ファイルアップロード操作
      - タブ切り替え操作
      - ボタンクリック操作
      - 結果表示の検証
      - 表示形式の制御

    Attributes:
        page: Playwrightのページオブジェクト
        default_wait_time: UI操作後の待機時間 [ミリ秒]

    Example:
        helper = StreamlitTestHelper(page)
        helper.select_tab("設定")
        helper.upload_file(selector, "config.toml")
        helper.click_button("生成")
        result = helper.check_result_displayed()
    """

    def __init__(self, page: Page) -> None:
        """初期化.

        Args:
            page: Playwrightのページオブジェクト
        """
        self.page = page
        self.default_wait_time = 1000  # ミリ秒

    def wait_for_ui_stabilization(self) -> None:
        """UI要素の安定化を待機.

        Note:
            - ネットワークリクエストの完了を待機
            - デフォルトの待機時間を追加
        """
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(self.default_wait_time)

    def upload_file(self, upload_container_selector: str, file_name: str) -> None:
        """ファイルをアップロード.

        Args:
            upload_container_selector: アップロード要素のセレクタ
            file_name: アップロードするファイル名

        Note:
            - アップロード要素の表示を確認
            - ファイル選択ダイアログを処理
            - アップロード完了を待機
        """
        upload_container: Final[Locator] = self.page.locator(upload_container_selector).first
        expect(upload_container).to_be_visible()

        upload_button: Final[Locator] = upload_container.locator("button:has-text('Browse files')").first
        expect(upload_button).to_be_visible()

        test_file_path: str = TestData.get_test_file_path(file_name)
        with self.page.expect_file_chooser() as fc_info:
            upload_button.click()
        file_chooser: Final[FileChooser] = fc_info.value
        file_chooser.set_files(test_file_path)

        self.wait_for_ui_stabilization()

    def select_tab(self, tab_name: str) -> None:
        """タブを選択.

        Args:
            tab_name: 選択するタブの名前

        Note:
            - タブボタンの表示を確認
            - タブパネルの表示を確認
            - 切り替え完了を待機
        """
        tab_button: Final[Locator] = self.page.locator(f"button[role='tab']:has-text('{tab_name}')").first
        expect(tab_button).to_be_visible()
        tab_button.click()

        self.page.wait_for_timeout(self.default_wait_time)
        self.page.wait_for_load_state("networkidle")

        tab_panel: Final[Locator] = self.page.locator("div[role='tabpanel']:visible").first
        expect(tab_panel).to_be_visible()

    def click_button(self, button_text: str) -> None:
        """ボタンをクリック.

        Args:
            button_text: クリックするボタンのテキスト

        Note:
            - ボタンの表示を確認
            - クリック完了を待機
        """
        button: Final[Locator] = self.page.locator(f"button:has-text('{button_text}')").first
        expect(button).to_be_visible()
        button.click()

        self.wait_for_ui_stabilization()

    def check_result_displayed(self, expected_contents: Optional[List[str]] = None) -> str:
        """結果の表示を検証.

        Args:
            expected_contents: 結果に含まれるべき内容のリスト
                指定された場合、各内容が結果に含まれることを検証

        Returns:
            str: 表示されている結果のテキスト

        Raises:
            AssertionError: 結果が表示されていない場合
            AssertionError: 期待される内容が含まれていない場合

        Example:
            result = helper.check_result_displayed(["設定", "完了"])
            assert "エラー" not in result
        """
        result_area: Final[Locator] = self.page.locator("div.element-container").filter(has=self.page.locator("div.stMarkdown")).first
        expect(result_area).to_be_visible()

        result_text: Final[str] = result_area.inner_text()

        assert len(result_text) > 0, "No result content is displayed"

        if expected_contents:
            for content in expected_contents:
                assert content in result_text, f"Expected content not found in result.\nExpected: {content}\nActual content: {result_text}"

        return result_text

    def upload_config_and_template(self, config_file: str, template_file: str) -> None:
        """設定ファイルとテンプレートファイルをアップロード.

        Args:
            config_file: 設定ファイル名
            template_file: テンプレートファイル名

        Raises:
            AssertionError: アップロード要素が不足している場合
            AssertionError: ファイル名が表示されない場合

        Note:
            - 2つのアップロード要素の存在を確認
            - 各ファイルのアップロードを実行
            - アップロード後のファイル名表示を確認
        """
        upload_containers: Final[List[Locator]] = self.page.locator("div[data-testid='stFileUploader']").all()
        assert len(upload_containers) > 1, "Not enough file uploaders found (expected at least 2)"

        config_upload_container: Final[Locator] = upload_containers[0]
        config_upload_button: Final[Locator] = config_upload_container.locator("button:has-text('Browse files')").first
        expect(config_upload_button).to_be_visible()

        config_file_path: str = TestData.get_test_file_path(config_file)
        with self.page.expect_file_chooser() as fc_info:
            config_upload_button.click()
        config_file_chooser: Final[FileChooser] = fc_info.value
        config_file_chooser.set_files(config_file_path)

        self.wait_for_ui_stabilization()

        jinja_upload_container: Final[Locator] = upload_containers[1]
        jinja_upload_button: Final[Locator] = jinja_upload_container.locator("button:has-text('Browse files')").first
        expect(jinja_upload_button).to_be_visible()

        jinja_file_path: str = TestData.get_test_file_path(template_file)
        with self.page.expect_file_chooser() as fc_info:
            jinja_upload_button.click()
        template_file_chooser: Final[FileChooser] = fc_info.value
        template_file_chooser.set_files(jinja_file_path)

        self.wait_for_ui_stabilization()

        config_text: Final[str] = config_upload_container.inner_text()
        assert config_file in config_text, f"Config file name not displayed.\nExpected: {config_file}\nActual text: {config_text}"

        jinja_text = jinja_upload_container.inner_text()
        assert template_file in jinja_text, f"Template file name not displayed.\nExpected: {template_file}\nActual text: {jinja_text}"

    def get_display_button(self, display_format: str) -> Locator:
        """表示形式に応じたボタンを取得.

        Args:
            display_format: 表示形式
                - "visual": JSON形式の可視化表示
                - "toml": TOML形式のテキスト表示
                - "yaml": YAML形式のテキスト表示

        Returns:
            Locator: ボタンのLocatorオブジェクト
        """
        format_button_map: Final[Dict[str, str]] = {
            "visual": texts.tab2.generate_visual_button,
            "toml": texts.tab2.generate_toml_button,
            "yaml": texts.tab2.generate_yaml_button,
        }
        button_text: Final[str] = format_button_map[display_format]
        display_button: Final[Locator] = self.page.locator(f"button:has-text('{button_text}')").first
        return display_button

    def get_result_text(self, tab_panel: Locator, display_format: str) -> str:
        """表示形式に応じた結果テキストを取得.

        Args:
            tab_panel: タブパネルのLocatorオブジェクト
            display_format: 表示形式
                - "visual": JSON形式の可視化表示
                - "toml": TOML形式のテキスト表示
                - "yaml": YAML形式のテキスト表示

        Returns:
            str: 解析結果のテキスト

        Note:
            - JSON形式: stJsonコンポーネントから取得
            - TOML/YAML形式: テキストエリアから取得
            - 上記で取得できない場合: マークダウン要素から取得
        """
        result_text: str = ""
        area_text: str = ""

        if display_format == "visual":
            json_container: Final[Locator] = tab_panel.locator("div[data-testid='stJson']").first
            if json_container.count() > 0:
                return json_container.inner_text()

        text_areas: Final[List[Locator]] = tab_panel.locator("textarea").all()
        for text_area in text_areas:
            area_text = text_area.input_value()
            if area_text:
                result_text += area_text + "\n"

        if not result_text:
            markdown_areas: Final[List[Locator]] = tab_panel.locator("div.stMarkdown").all()
            for area in markdown_areas:
                area_text = area.inner_text()
                if area_text and not area_text.startswith(texts.tab2.upload_debug_config):
                    result_text += area_text + "\n"

        return result_text

    def verify_result_content(self, result_text: str, expected_content: List[str], display_format: str) -> None:
        """解析結果の内容を検証.

        Args:
            result_text: 解析結果のテキスト
            expected_content: 期待される内容のリスト
            display_format: 表示形式
                - "visual": JSON形式の可視化表示
                - "toml": TOML形式のテキスト表示
                - "yaml": YAML形式のテキスト表示

        Raises:
            AssertionError: 結果が空の場合
            AssertionError: 期待される内容が含まれていない場合
        """
        assert len(result_text.strip()) > 0, f"解析結果が表示されていません({display_format}形式)"

        for content in expected_content:
            assert content.lower() in result_text.lower(), f"期待される内容 '{content}' が解析結果に含まれていません"

    def upload_debug_config_file(self, file_name: str) -> None:
        """デバッグ用の設定ファイルをアップロード.

        Args:
            file_name: アップロードするファイル名

        Note:
            - 現在表示中のタブパネルにあるアップロード要素を使用
            - アップロード完了を待機
        """
        tab_panel: Final[Locator] = self.page.locator("div[role='tabpanel']:visible").first

        upload_container: Final[Locator] = tab_panel.locator("div[data-testid='stFileUploader']").first
        expect(upload_container).to_be_visible()

        upload_button: Final[Locator] = upload_container.locator("button:has-text('Browse files')").first
        expect(upload_button).to_be_visible()

        test_file_path: str = TestData.get_test_file_path(file_name)
        with self.page.expect_file_chooser() as fc_info:
            upload_button.click()
        file_chooser: Final[FileChooser] = fc_info.value
        file_chooser.set_files(test_file_path)

        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(1000)
