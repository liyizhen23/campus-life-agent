from app.dify import _StreamingAnswerFilter, strip_reasoning


def test_strip_reasoning_keeps_only_final_answer() -> None:
    response = (
        "<think>\n<!--dify-deepseek-reasoning-->内部分析"
        "<!--/dify-deepseek-reasoning-->\n</think>最终推荐"
    )

    assert strip_reasoning(response) == "最终推荐"


def test_streaming_filter_waits_for_reasoning_to_finish() -> None:
    answer_filter = _StreamingAnswerFilter()

    assert answer_filter.add("<thi") == ""
    assert answer_filter.add("nk>内部分析") == ""
    assert answer_filter.add("</think>最终") == "最终"
    assert answer_filter.add("推荐") == "推荐"


def test_strip_reasoning_leaves_plain_answer_unchanged() -> None:
    assert strip_reasoning("最终推荐") == "最终推荐"
