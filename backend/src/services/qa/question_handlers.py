from __future__ import annotations

from .mcq_handler import QuestionType


class BaseQuestionHandler:
    question_type: QuestionType = QuestionType.OPEN

    def system_addon(self) -> str:
        return ""

    def user_suffix(self) -> str:
        return ""


class MCQHandler(BaseQuestionHandler):
    question_type = QuestionType.MULTIPLE_CHOICE

    def system_addon(self) -> str:
        return "请从给定选项中选出唯一正确答案，先写出选项字母（如 A），再用一句话说明理由。"

    def user_suffix(self) -> str:
        return "\n请作答：（先给出选项字母，再简要说明依据）"


class MultiSelectHandler(BaseQuestionHandler):
    question_type = QuestionType.MULTIPLE_SELECT

    def system_addon(self) -> str:
        return "请从给定选项中选出所有正确答案，列出全部正确选项字母（如 A,C），再逐条说明理由。"

    def user_suffix(self) -> str:
        return "\n请作答：（列出所有正确选项字母，用逗号分隔，并简要说明）"


class TrueFalseHandler(BaseQuestionHandler):
    question_type = QuestionType.TRUE_FALSE

    def system_addon(self) -> str:
        return "请判断下列说法是否正确，直接回答【正确】或【错误】，再引用规范依据说明原因。"

    def user_suffix(self) -> str:
        return "\n请作答：（【正确】/ 【错误】，并说明规范依据）"


class FillBlankHandler(BaseQuestionHandler):
    question_type = QuestionType.FILL_BLANK

    def system_addon(self) -> str:
        return "请根据规范内容填写空白处，直接给出填入的词或短语，不需要其他说明。"

    def user_suffix(self) -> str:
        return "\n请填写："


class ShortAnswerHandler(BaseQuestionHandler):
    question_type = QuestionType.SHORT_ANSWER

    def system_addon(self) -> str:
        return "请简要回答，100字以内，列出核心要点即可。"


class OpenQAHandler(BaseQuestionHandler):
    question_type = QuestionType.OPEN


_HANDLER_MAP: dict[QuestionType, BaseQuestionHandler] = {
    QuestionType.MULTIPLE_CHOICE: MCQHandler(),
    QuestionType.MULTIPLE_SELECT: MultiSelectHandler(),
    QuestionType.TRUE_FALSE: TrueFalseHandler(),
    QuestionType.FILL_BLANK: FillBlankHandler(),
    QuestionType.SHORT_ANSWER: ShortAnswerHandler(),
    QuestionType.OPEN: OpenQAHandler(),
}


def get_question_handler(qt: QuestionType) -> BaseQuestionHandler:
    return _HANDLER_MAP.get(qt, OpenQAHandler())
