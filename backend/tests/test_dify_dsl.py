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
    assert features["opening_statement"] == ""
    assert features["suggested_questions"] == []
    assert features["suggested_questions_after_answer"]["enabled"] is False
    assert "fileUploadConfig" not in features["file_upload"]

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

    code_node = next(node for node in graph["nodes"] if node["data"]["type"] == "code")
    for variable in code_node["data"]["variables"]:
        assert variable["value_selector"]
        assert "value" not in variable


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
    )
    import json

    body = json.loads(output["request_body"])
    assert "美食" in body["categories"]
    assert {"景点", "娱乐", "公园"}.intersection(body["categories"])
    assert body["duration_minutes"] == 180


def test_explanation_prompt_requires_valid_markdown_and_honest_route_fallback():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]
    explain = next(node for node in graph["nodes"] if node["id"] == "explain")
    system_prompt = explain["data"]["prompt_template"][0]["text"]

    assert "完整、规范的 Markdown" in system_prompt
    assert "straight_line_only" in system_prompt
    assert "不得输出思考过程" in system_prompt
