#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit アプリケーションのテスト用ユーティリティ
"""

import os
import sys
import tempfile
from typing import List, Optional

from box import Box
from playwright.sync_api import Locator, Page, expect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from i18n import LANGUAGES

# 言語リソースの設定
DEFAULT_LANGUAGE = "日本語"
texts = Box(LANGUAGES[DEFAULT_LANGUAGE])


class TestData:
    """テストデータを提供するクラス"""

    # サンプルテキストファイル
    SAMPLE_TXT = """This is a sample text file for testing file uploads in the Streamlit application.

It contains multiple lines of text to simulate a real file.

You can use this file to test the file upload functionality in your E2E tests."""

    # DNS設定ファイル (CSV)
    DNS_DIG_CONFIG_CSV = """resolver,fqdn,type
1.1.1.1,www.yahoo.co.jp,a
1.1.1.1,yahoo.co.jp,mx
1.1.1.1,yahoo.co.jp,txt
8.8.8.8,gmail.com,mx
8.8.8.8,gmail.com,txt
8.8.8.8,_dmarc.gmail.com,txt
8.8.8.8,selector1._domainkey.live.com,txt
,selector2._domainkey.live.com,txt"""

    # DNSテンプレートファイル (Jinja2)
    DNS_DIG_TMPL_J2 = """
{% for row in csv_rows %}
dig @{{ row["resolver"] }} {{ row["fqdn"] }} {{ row["type"] }} +short
{% endfor %}"""

    # 成功設定ファイル (YAML)
    WGET_CONFIG_YAML = """url: "https://example.com/samplefile.txt"
date: 2024-04-01

users:
  test:
    first_name: "太郎"
    last_name: "テスト"
"""

    # 成功テンプレートファイル (Jinja2)
    WGET_TEMPLATE_J2 = """# wget operation

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
    CISCO_CONFIG_TOML = """[global]
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
    CISCO_TEMPLATE_JINJA2 = """enable
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
        """テストファイルのパスを取得する

        指定されたファイル名に対応するテストデータを一時ファイルとして作成し、
        そのパスを返します。

        Args:
            file_name: ファイル名

        Returns:
            str: テスト用の一時ファイルパス
        """
        # ファイル名に対応するデータを取得
        content = cls._get_file_content(file_name)

        # 一時ファイルを作成
        fd, path = tempfile.mkstemp(suffix=f"_{file_name}")
        with os.fdopen(fd, "w") as f:
            f.write(content)

        return path

    @classmethod
    def _get_file_content(cls, file_name: str) -> str:
        """ファイル名に対応するテストデータの内容を取得する

        Args:
            file_name: ファイル名

        Returns:
            str: テストデータの内容
        """
        file_content_map = {
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
    """Streamlitアプリケーションのテスト支援クラス"""

    def __init__(self, page: Page) -> None:
        """初期化

        Args:
            page: Playwrightのページオブジェクト
        """
        self.page = page
        self.default_wait_time = 1000  # ミリ秒

    def wait_for_ui_stabilization(self) -> None:
        """UI要素が安定するまで待機する"""
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(self.default_wait_time)

    def upload_file(self, upload_container_selector: str, file_name: str) -> None:
        """ファイルをアップロードする

        Args:
            upload_container_selector: アップロードコンテナのセレクタ
            file_name: アップロードするファイル名
        """
        # アップロードコンテナを取得
        upload_container = self.page.locator(upload_container_selector).first
        expect(upload_container).to_be_visible()

        # ファイルアップロードボタンを見つける
        upload_button = upload_container.locator("button:has-text('Browse files')").first
        expect(upload_button).to_be_visible()

        # ファイルをアップロード
        test_file_path = TestData.get_test_file_path(file_name)
        with self.page.expect_file_chooser() as fc_info:
            upload_button.click()
        file_chooser = fc_info.value
        file_chooser.set_files(test_file_path)

        # アップロード後の処理を待機
        self.wait_for_ui_stabilization()

    def select_tab(self, tab_name: str) -> None:
        """タブを選択する

        Args:
            tab_name: タブ名
        """
        tab_button = self.page.locator(f"button[role='tab']:has-text('{tab_name}')").first
        expect(tab_button).to_be_visible()
        tab_button.click()

        # タブ切り替え後の表示を待機
        self.page.wait_for_timeout(self.default_wait_time)
        self.page.wait_for_load_state("networkidle")

        # タブパネルが表示されるのを待機
        tab_panel = self.page.locator("div[role='tabpanel']:visible").first
        expect(tab_panel).to_be_visible()

    def click_button(self, button_text: str) -> None:
        """ボタンをクリックする

        Args:
            button_text: ボタンのテキスト
        """
        button = self.page.locator(f"button:has-text('{button_text}')").first
        expect(button).to_be_visible()
        button.click()

        # ボタンクリック後の処理を待機
        self.wait_for_ui_stabilization()

    def check_result_displayed(self, expected_contents: Optional[List[str]] = None) -> str:
        """結果が表示されていることを確認する

        Args:
            expected_contents: 結果に含まれるべき内容のリスト

        Returns:
            str: 表示されている結果のテキスト
        """
        # 結果が表示されるエリアが存在することを確認
        result_area = self.page.locator("div.element-container").filter(has=self.page.locator("div.stMarkdown")).first
        expect(result_area).to_be_visible()

        # 結果テキストを取得
        result_text = result_area.inner_text()

        # 何らかの結果が表示されていることを確認
        assert len(result_text) > 0, "No result content is displayed"

        # 期待される内容が含まれていることを確認
        if expected_contents:
            for content in expected_contents:
                assert content in result_text, f"Expected content not found in result.\nExpected: {content}\nActual content: {result_text}"

        return result_text

    def upload_config_and_template(self, config_file: str, template_file: str) -> None:
        """設定ファイルとテンプレートファイルをアップロードする

        Args:
            config_file: 設定ファイル名
            template_file: テンプレートファイル名
        """
        # ファイルアップロード要素を取得
        upload_containers = self.page.locator("div[data-testid='stFileUploader']").all()
        assert len(upload_containers) > 1, "Not enough file uploaders found (expected at least 2)"

        # 設定ファイルをアップロード
        config_upload_container = upload_containers[0]
        config_upload_button = config_upload_container.locator("button:has-text('Browse files')").first
        expect(config_upload_button).to_be_visible()

        config_file_path = TestData.get_test_file_path(config_file)
        with self.page.expect_file_chooser() as fc_info:
            config_upload_button.click()
        file_chooser = fc_info.value
        file_chooser.set_files(config_file_path)

        # アップロード後の処理を待機
        self.wait_for_ui_stabilization()

        # テンプレートファイルをアップロード
        jinja_upload_container = upload_containers[1]
        jinja_upload_button = jinja_upload_container.locator("button:has-text('Browse files')").first
        expect(jinja_upload_button).to_be_visible()

        jinja_file_path = TestData.get_test_file_path(template_file)
        with self.page.expect_file_chooser() as fc_info:
            jinja_upload_button.click()
        file_chooser = fc_info.value
        file_chooser.set_files(jinja_file_path)

        # アップロード後の処理を待機
        self.wait_for_ui_stabilization()

        # アップロードされたファイル名が表示されていることを確認
        config_text = config_upload_container.inner_text()
        assert config_file in config_text, f"Config file name not displayed.\nExpected: {config_file}\nActual text: {config_text}"

        jinja_text = jinja_upload_container.inner_text()
        assert template_file in jinja_text, f"Template file name not displayed.\nExpected: {template_file}\nActual text: {jinja_text}"

    def get_display_button(self, display_format: str) -> Locator:
        """表示形式に応じたボタンを取得する

        Args:
            page: Playwrightのページオブジェクト
            display_format: 表示形式[visual, toml, yaml]

        Returns:
            Locator: ボタンのLocatorオブジェクト
        """
        format_button_map = {
            "visual": texts.tab2.generate_visual_button,
            "toml": texts.tab2.generate_toml_button,
            "yaml": texts.tab2.generate_yaml_button,
        }
        button_text = format_button_map[display_format]
        display_button = self.page.locator(f"button:has-text('{button_text}')").first
        return display_button

    def get_result_text(self, tab_panel: Locator, display_format: str) -> str:
        """表示形式に応じた結果テキストを取得する

        Args:
            tab_panel: タブパネルのLocatorオブジェクト
            display_format: 表示形式[visual, toml, yaml]

        Returns:
            str: 解析結果のテキスト
        """
        result_text = ""

        # JSON表示の場合
        if display_format == "visual":
            json_container = tab_panel.locator("div[data-testid='stJson']").first
            if json_container.count() > 0:
                return json_container.inner_text()

        # テキストエリアの場合 [tomlとyaml形式]
        text_areas = tab_panel.locator("textarea").all()
        for text_area in text_areas:
            area_text = text_area.input_value()
            if area_text:
                result_text += area_text + "\n"

        # テキストエリアやJSON表示が見つからない場合、マークダウン要素を確認
        if not result_text:
            markdown_areas = tab_panel.locator("div.stMarkdown").all()
            for area in markdown_areas:
                area_text = area.inner_text()
                if area_text and not area_text.startswith(texts.tab2.upload_debug_config):
                    result_text += area_text + "\n"

        return result_text

    def verify_result_content(self, result_text: str, expected_content: List[str], display_format: str) -> None:
        """解析結果の内容を検証する

        Args:
            result_text: 解析結果のテキスト
            expected_content: 期待される内容のリスト
            display_format: 表示形式[visual, toml, yaml]

        Raises:
            AssertionError: 検証に失敗した場合
        """
        assert len(result_text.strip()) > 0, f"解析結果が表示されていません({display_format}形式)"

        for content in expected_content:
            assert content.lower() in result_text.lower(), f"期待される内容 '{content}' が解析結果に含まれていません"

    def upload_debug_config_file(self, file_name: str) -> None:
        """設定ファイルをアップロードする

        Args:
            page: Playwrightのページオブジェクト
            file_name: アップロードするファイル名
        """
        # タブパネルを取得
        tab_panel = self.page.locator("div[role='tabpanel']:visible").first

        # 設定定義ファイルのアップロード要素を見つける
        upload_container = tab_panel.locator("div[data-testid='stFileUploader']").first
        expect(upload_container).to_be_visible()

        # ファイルアップロードボタンを見つける
        upload_button = upload_container.locator("button:has-text('Browse files')").first
        expect(upload_button).to_be_visible()

        # ファイルをアップロード
        test_file_path = TestData.get_test_file_path(file_name)
        with self.page.expect_file_chooser() as fc_info:
            upload_button.click()
        file_chooser = fc_info.value
        file_chooser.set_files(test_file_path)

        # アップロード後の処理を待機
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(1000)
