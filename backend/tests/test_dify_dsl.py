from pathlib import Path

import yaml


DSL_PATH = Path(__file__).resolve().parents[2] / "dify" / "nearby-go-chatflow.yml"


def test_dify_dsl_uses_current_canvas_shape():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]

    assert dsl["version"] == "0.7.0"
    assert dsl["app"]["mode"] == "advanced-chat"
    assert dsl["workflow"]["rag_pipeline_variables"] == []

    features = dsl["workflow"]["features"]
    assert "NearbyGo" in features["opening_statement"]
    assert len(features["suggested_questions"]) >= 4
    assert features["suggested_questions_after_answer"]["enabled"] is True
    file_upload_config = features["file_upload"]["fileUploadConfig"]
    assert file_upload_config["attachment_image_file_size_limit"] == 2
    assert file_upload_config["workflow_file_upload_limit"] == 10

    dependency = dsl["dependencies"][0]["value"][
        "marketplace_plugin_unique_identifier"
    ]
    assert dependency.startswith("langgenius/openai_api_compatible:")

    environment_variables = {
        variable["name"]: variable
        for variable in dsl["workflow"]["environment_variables"]
    }
    assert environment_variables["BACKEND_BASE_URL"]["value"] == (
        "https://nearby-go.onrender.com"
    )
    assert environment_variables["INTERNAL_API_TOKEN"]["value"] == ""
    assert environment_variables["INTERNAL_API_TOKEN"]["value_type"] == "secret"

    for edge in graph["edges"]:
        assert "isInIteration" in edge["data"]
        assert "isInLoop" in edge["data"]
        assert "zIndex" in edge

    for node in graph["nodes"]:
        assert "selected" in node
        assert node["data"]["title"]
        assert node["data"]["type"]

    model_nodes = [
        node["data"]["model"]
        for node in graph["nodes"]
        if "model" in node["data"]
    ]
    assert model_nodes
    assert all(
        model["provider"]
        == "langgenius/openai_api_compatible/openai_api_compatible"
        for model in model_nodes
    )
    assert all(model["name"] == "DeepSeek-V4-Flash-0731" for model in model_nodes)

    code_node = next(node for node in graph["nodes"] if node["data"]["type"] == "code")
    for variable in code_node["data"]["variables"]:
        assert variable["value_selector"]
        assert "value" not in variable

    assert [(edge["source"], edge["target"]) for edge in graph["edges"]] == [
        ("start", "extract"),
        ("extract", "normalize"),
        ("normalize", "recommend"),
        ("recommend", "validate"),
        ("validate", "explain"),
        ("explain", "answer"),
    ]

    extractor = next(node for node in graph["nodes"] if node["id"] == "extract")
    parameter_names = {item["name"] for item in extractor["data"]["parameters"]}
    assert {
        "avoid_terms",
        "companion_profile",
        "dietary_needs",
        "accessibility_needs",
        "ambience",
        "decision_priority",
        "plan_mode",
    }.issubset(parameter_names)


def test_normalizer_preserves_meal_and_activity_intent_and_duration():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]
    code_node = next(node for node in graph["nodes"] if node["id"] == "normalize")
    namespace = {}
    exec(code_node["data"]["code"], namespace)

    output = namespace["main"](
        query="帮我安排一个吃饭加游玩的三小时路线",
        longitude="116.326",
        latitude="40.003",
        coordinate_system="gps",
        categories=["美食"],
        keywords=[],
        preferences=[],
        budget_per_person=None,
        radius_meters=None,
        transport="walking",
        duration_minutes=None,
        duration_days=None,
    )
    import json

    body = json.loads(output["request_body"])
    assert "美食" in body["categories"]
    assert {"景点", "娱乐", "公园"}.intersection(body["categories"])
    assert body["duration_minutes"] == 180
    assert body["duration_days"] == 1
    assert body["result_count"] == 3


def test_normalizer_builds_active_time_budget_and_stop_count_for_multi_day_trip():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]
    code_node = next(node for node in graph["nodes"] if node["id"] == "normalize")
    namespace = {}
    exec(code_node["data"]["code"], namespace)

    output = namespace["main"](
        query="安排一个三天两夜的游玩攻略",
        longitude="116.326",
        latitude="40.003",
        coordinate_system="gps",
        categories=["景点"],
        keywords=[],
        preferences=[],
        budget_per_person=None,
        radius_meters=None,
        transport="walking",
        duration_minutes=None,
        duration_days=None,
    )
    import json

    body = json.loads(output["request_body"])
    assert body["duration_days"] == 3
    assert body["duration_minutes"] == 3 * 480
    assert body["result_count"] == 12
    assert "美食" in body["categories"]
    assert "景点" in body["categories"]

    weekend = namespace["main"](
        query="两天一夜的附近吃喝游玩攻略，每天约8小时",
        longitude="116.326",
        latitude="40.003",
        coordinate_system="gps",
        categories=["美食", "景点"],
        keywords=[],
        preferences=[],
        budget_per_person=None,
        radius_meters=None,
        transport="walking",
        duration_minutes=None,
        duration_days=None,
    )
    weekend_body = json.loads(weekend["request_body"])
    assert weekend_body["duration_days"] == 2
    assert weekend_body["duration_minutes"] == 2 * 480
    assert weekend_body["result_count"] == 8


def test_explanation_prompt_requires_valid_markdown_and_honest_route_fallback():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]
    explain = next(node for node in graph["nodes"] if node["id"] == "explain")
    system_prompt = explain["data"]["prompt_template"][0]["text"]

    assert "完整、规范的 Markdown" in system_prompt
    assert "straight_line_only" in system_prompt
    assert "total_planned_minutes" in system_prompt
    assert "itinerary_days" in system_prompt
    assert "像实用旅行攻略" in system_prompt
    assert "不能自行增删" in system_prompt
    assert "不得输出思考过程" in system_prompt
    assert "constraint_conflicts" in system_prompt
    assert "quick_pick" in system_prompt
    assert "compare" in system_prompt
    assert "Plan B" in system_prompt


def test_normalizer_builds_personalized_context_and_safe_location_fallback():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]
    code_node = next(node for node in graph["nodes"] if node["id"] == "normalize")
    namespace = {}
    exec(code_node["data"]["code"], namespace)

    output = namespace["main"](
        query="带老人步行10分钟内找安静的晚餐，不要太辣",
        longitude="",
        latitude="",
        coordinate_system="gps",
        categories=["美食"],
        keywords=[],
        preferences=["安静"],
        budget_per_person=80,
        radius_meters=None,
        transport="walking",
        duration_minutes=None,
        duration_days=1,
        avoid_terms=["太辣"],
        companion_profile=["老人"],
        accessibility_needs=["少走路"],
        ambience=["安静"],
        decision_priority="nearest",
        plan_mode="quick_pick",
        fallback_location_name="清华大学",
    )

    import json

    body = json.loads(output["request_body"])
    context = json.loads(output["request_context"])
    assert body["longitude"] == 116.326
    assert body["latitude"] == 40.003
    assert body["radius_meters"] == 800
    assert body["duration_minutes"] is None
    assert {"安静", "老人", "少走路"}.issubset(body["preferences"])
    assert context["location_source"] == "fallback"
    assert context["avoid_terms"] == ["太辣"]
    assert context["decision_priority"] == "nearest"


def test_result_auditor_handles_service_errors_and_constraint_conflicts():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]
    code_node = next(node for node in graph["nodes"] if node["id"] == "validate")
    namespace = {}
    exec(code_node["data"]["code"], namespace)

    import json

    failed = namespace["main"]("not-json", 503, "{}")
    assert failed["response_state"] == "service_error"

    audited = namespace["main"](
        json.dumps(
            {
                "places": [
                    {
                        "name": "热辣火锅",
                        "category": "餐饮服务",
                        "address": "示例路",
                        "tags": ["辣"],
                    }
                ],
                "itinerary_days": [],
                "warnings": [],
            },
            ensure_ascii=False,
        ),
        200,
        json.dumps({"avoid_terms": ["辣"], "plan_mode": "quick_pick"}, ensure_ascii=False),
    )
    result = json.loads(audited["validated_result"])
    assert audited["response_state"] == "needs_caution"
    assert result["constraint_conflicts"][0]["place_name"] == "热辣火锅"
