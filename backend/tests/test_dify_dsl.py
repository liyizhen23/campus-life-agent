from pathlib import Path

import yaml


DSL_PATH = Path(__file__).resolve().parents[2] / "dify" / "nearby-go-chatflow.yml"


def test_dify_dsl_uses_current_canvas_shape():
    dsl = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
    graph = dsl["workflow"]["graph"]

    assert dsl["version"] == "0.7.0"
    assert dsl["app"]["mode"] == "advanced-chat"
    assert dsl["workflow"]["rag_pipeline_variables"] == []

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
