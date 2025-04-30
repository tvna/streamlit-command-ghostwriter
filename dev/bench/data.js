window.BENCHMARK_DATA = {
  "lastUpdate": 1746049572315,
  "repoUrl": "https://github.com/tvna/command-ghostwriter",
  "entries": {
    "Python E2E Benchmark": [
      {
        "commit": {
          "author": {
            "email": "31282861+tvna@users.noreply.github.com",
            "name": "Tsubasa Nagano",
            "username": "tvna"
          },
          "committer": {
            "email": "31282861+tvna@users.noreply.github.com",
            "name": "Tsubasa Nagano",
            "username": "tvna"
          },
          "distinct": true,
          "id": "4eb08bf3898c1d119bfb8e0b1a09262ef60353f6",
          "message": "ci(E2E Tests): shell設定漏れの追加、上位ワークフローのパーミッション変更",
          "timestamp": "2025-05-01T06:13:26+09:00",
          "tree_id": "e63653568e6756285c08434a4127cb6357ad3d55",
          "url": "https://github.com/tvna/command-ghostwriter/commit/4eb08bf3898c1d119bfb8e0b1a09262ef60353f6"
        },
        "date": 1746048825734,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/e2e/test_e2e.py::test_ui_input_field[chromium]",
            "value": 220.991268119306,
            "unit": "iter/sec",
            "range": "stddev: 0.0005462553433159995",
            "extra": "mean: 4.525065666667573 msec\nrounds: 144"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_wget_config_to_markdown]",
            "value": 0.1364140345274524,
            "unit": "iter/sec",
            "range": "stddev: 0.04802446438500077",
            "extra": "mean: 7.3306240333999995 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_parametrized_in_tab1[chromium-e2e_upload_toml_config]",
            "value": 0.31996645473736296,
            "unit": "iter/sec",
            "range": "stddev: 0.05454250704475541",
            "extra": "mean: 3.125327624800002 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_jinja_template_upload_in_tab1[chromium]",
            "value": 0.9006941334984419,
            "unit": "iter/sec",
            "range": "stddev: 0.027282891830611333",
            "extra": "mean: 1.1102548165999906 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_cisco_config_debug_to_toml]",
            "value": 0.12146355580490938,
            "unit": "iter/sec",
            "range": "stddev: 0.05536674542619899",
            "extra": "mean: 8.232922158199994 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_dns_dig_config_debug_csv_to_yaml]",
            "value": 0.12167482389331627,
            "unit": "iter/sec",
            "range": "stddev: 0.07038942337602636",
            "extra": "mean: 8.21862705860001 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_success_config_debug_yaml_to_toml]",
            "value": 0.12170500287331455,
            "unit": "iter/sec",
            "range": "stddev: 0.0608126290756138",
            "extra": "mean: 8.216589099799966 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_parametrized_in_tab1[chromium-e2e_upload_jinja_template]",
            "value": 0.32147530760982534,
            "unit": "iter/sec",
            "range": "stddev: 0.03967900825907991",
            "extra": "mean: 3.110658816800014 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_cisco_config_debug_to_visual]",
            "value": 0.12160277146561353,
            "unit": "iter/sec",
            "range": "stddev: 0.059640542386578725",
            "extra": "mean: 8.223496783400014 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_cisco_config_to_file]",
            "value": 0.13706738016130096,
            "unit": "iter/sec",
            "range": "stddev: 0.07608685447959229",
            "extra": "mean: 7.295681867000008 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_dns_dig_config_to_markdown]",
            "value": 0.13557350060620948,
            "unit": "iter/sec",
            "range": "stddev: 0.0879545358853472",
            "extra": "mean: 7.376072724599976 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_ui_app_title[chromium]",
            "value": 241.17001219677428,
            "unit": "iter/sec",
            "range": "stddev: 0.0011303791628043038",
            "extra": "mean: 4.146452500006862 msec\nrounds: 22"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_in_tab1[chromium]",
            "value": 0.921152882877324,
            "unit": "iter/sec",
            "range": "stddev: 0.016345249062487188",
            "extra": "mean: 1.0855961248000312 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_parametrized_in_tab1[chromium-e2e_upload_csv_config]",
            "value": 0.31986956570730535,
            "unit": "iter/sec",
            "range": "stddev: 0.03755521322449675",
            "extra": "mean: 3.126274291800064 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_dns_dig_config_to_file]",
            "value": 0.13614677698118047,
            "unit": "iter/sec",
            "range": "stddev: 0.1045256236953643",
            "extra": "mean: 7.345014125000034 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_success_config_debug_yaml_to_visual]",
            "value": 0.12184226948913972,
            "unit": "iter/sec",
            "range": "stddev: 0.07746263555980032",
            "extra": "mean: 8.207332350199977 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_dns_dig_config_debug_csv_to_toml]",
            "value": 0.12220033645045084,
            "unit": "iter/sec",
            "range": "stddev: 0.059010754268661696",
            "extra": "mean: 8.183283524800071 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_cisco_config_debug_to_yaml]",
            "value": 0.12157785564923973,
            "unit": "iter/sec",
            "range": "stddev: 0.04631614599331444",
            "extra": "mean: 8.225182083199979 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_cisco_config_to_markdown]",
            "value": 0.13660962309745167,
            "unit": "iter/sec",
            "range": "stddev: 0.09641675907922054",
            "extra": "mean: 7.320128533600018 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_dns_dig_config_debug_csv_to_visual]",
            "value": 0.12049454878895761,
            "unit": "iter/sec",
            "range": "stddev: 0.019817856984363474",
            "extra": "mean: 8.299130625000043 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_success_config_debug_yaml_to_yaml]",
            "value": 0.1218804362122241,
            "unit": "iter/sec",
            "range": "stddev: 0.04565197834762841",
            "extra": "mean: 8.204762233200018 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_wget_config_to_file]",
            "value": 0.13541459945588588,
            "unit": "iter/sec",
            "range": "stddev: 0.08002165766055373",
            "extra": "mean: 7.384728116599945 sec\nrounds: 5"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "31282861+tvna@users.noreply.github.com",
            "name": "Tsubasa Nagano",
            "username": "tvna"
          },
          "committer": {
            "email": "31282861+tvna@users.noreply.github.com",
            "name": "Tsubasa Nagano",
            "username": "tvna"
          },
          "distinct": true,
          "id": "999761fadb5bb339a1bf9a194e98d6b6e05b8e79",
          "message": "ci(E2E Tests): gh-pagesのpush方法の見直し",
          "timestamp": "2025-05-01T06:25:51+09:00",
          "tree_id": "f71ebe0d40f7134fe26f5fcc3a9ee9a22f9ea889",
          "url": "https://github.com/tvna/command-ghostwriter/commit/999761fadb5bb339a1bf9a194e98d6b6e05b8e79"
        },
        "date": 1746049570825,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_success_config_debug_yaml_to_yaml]",
            "value": 0.12165362901626386,
            "unit": "iter/sec",
            "range": "stddev: 0.01740552211540405",
            "extra": "mean: 8.2200589336 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_parametrized_in_tab1[chromium-e2e_upload_toml_config]",
            "value": 0.3179662935287414,
            "unit": "iter/sec",
            "range": "stddev: 0.034390597259201565",
            "extra": "mean: 3.1449874416000285 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_cisco_config_debug_to_yaml]",
            "value": 0.12065397943949185,
            "unit": "iter/sec",
            "range": "stddev: 0.09459628062243707",
            "extra": "mean: 8.28816425820005 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_dns_dig_config_debug_csv_to_toml]",
            "value": 0.12086015434503773,
            "unit": "iter/sec",
            "range": "stddev: 0.08661229578941412",
            "extra": "mean: 8.274025508399973 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_success_config_debug_yaml_to_toml]",
            "value": 0.12159507396433253,
            "unit": "iter/sec",
            "range": "stddev: 0.06921032995215326",
            "extra": "mean: 8.22401736679999 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_dns_dig_config_to_file]",
            "value": 0.13668419372638924,
            "unit": "iter/sec",
            "range": "stddev: 0.06058398546412964",
            "extra": "mean: 7.31613490000002 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_cisco_config_debug_to_visual]",
            "value": 0.12129397970206192,
            "unit": "iter/sec",
            "range": "stddev: 0.09565534526709586",
            "extra": "mean: 8.244432266599961 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_jinja_template_upload_in_tab1[chromium]",
            "value": 0.9052452695087873,
            "unit": "iter/sec",
            "range": "stddev: 0.03799570167987447",
            "extra": "mean: 1.1046729915999776 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_ui_input_field[chromium]",
            "value": 132.9080559535072,
            "unit": "iter/sec",
            "range": "stddev: 0.0010897766097404257",
            "extra": "mean: 7.52399839743207 msec\nrounds: 78"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_cisco_config_to_markdown]",
            "value": 0.13650492221066451,
            "unit": "iter/sec",
            "range": "stddev: 0.04407086528792821",
            "extra": "mean: 7.325743158599994 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_wget_config_to_markdown]",
            "value": 0.13726469689340956,
            "unit": "iter/sec",
            "range": "stddev: 0.06221701753105686",
            "extra": "mean: 7.285194391800042 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_cisco_config_debug_to_toml]",
            "value": 0.12153640797049768,
            "unit": "iter/sec",
            "range": "stddev: 0.06095333968668579",
            "extra": "mean: 8.22798712499998 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_dns_dig_config_debug_csv_to_visual]",
            "value": 0.12101507505268246,
            "unit": "iter/sec",
            "range": "stddev: 0.06349011636575007",
            "extra": "mean: 8.263433291799902 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_dns_dig_config_to_markdown]",
            "value": 0.1359720772637122,
            "unit": "iter/sec",
            "range": "stddev: 0.09885343499717705",
            "extra": "mean: 7.354451150000022 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_parametrized_in_tab1[chromium-e2e_upload_csv_config]",
            "value": 0.3213983089288275,
            "unit": "iter/sec",
            "range": "stddev: 0.04458281594579898",
            "extra": "mean: 3.1114040497999214 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_wget_config_to_file]",
            "value": 0.13610690564334144,
            "unit": "iter/sec",
            "range": "stddev: 0.04047068558748607",
            "extra": "mean: 7.34716578320008 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_in_tab1[chromium]",
            "value": 0.8797359208712455,
            "unit": "iter/sec",
            "range": "stddev: 0.03485918563938682",
            "extra": "mean: 1.1367047500000353 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_success_config_debug_yaml_to_visual]",
            "value": 0.12183922672554884,
            "unit": "iter/sec",
            "range": "stddev: 0.038619935304309704",
            "extra": "mean: 8.207537316800018 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_ui_app_title[chromium]",
            "value": 228.56289773346688,
            "unit": "iter/sec",
            "range": "stddev: 0.0014099266789865679",
            "extra": "mean: 4.3751632916648004 msec\nrounds: 24"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_file_upload_parametrized_in_tab1[chromium-e2e_upload_jinja_template]",
            "value": 0.3191762452700506,
            "unit": "iter/sec",
            "range": "stddev: 0.028760726280501386",
            "extra": "mean: 3.1330652416000246 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_command_generation_parametrized_in_tab1[chromium-e2e_command_gen_with_cisco_config_to_file]",
            "value": 0.13533913327384414,
            "unit": "iter/sec",
            "range": "stddev: 0.026608835938818777",
            "extra": "mean: 7.388845900000024 sec\nrounds: 5"
          },
          {
            "name": "tests/e2e/test_e2e.py::test_config_debug_parametrized_in_tab2[chromium-e2e_dns_dig_config_debug_csv_to_yaml]",
            "value": 0.12110389213165006,
            "unit": "iter/sec",
            "range": "stddev: 0.05208632296283956",
            "extra": "mean: 8.257372924999936 sec\nrounds: 5"
          }
        ]
      }
    ]
  }
}