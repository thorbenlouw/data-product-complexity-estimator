from dataclasses import dataclass
from enum import Enum
import abc


class QuestionType(str, Enum):
    DROPDOWN = "DropDown"
    CHECKBOX = "CheckBox"
    SHORT_ANSWER = "ShortAnswer"


@dataclass(frozen=True)
class Option:
    option_text: str
    score: float

    @staticmethod
    def from_dict(d):
        return Option(option_text=d["optionText"], score=d["score"])


@dataclass(frozen=True)
class Question:
    question_id: str
    question_text: str
    description: str
    weight: float
    options: list[Option]
    question_type: QuestionType

    @staticmethod
    def from_dict(d: dict, question_id: str):
        return Question(
            question_id = question_id, 
            question_text=d["question"],
            description=d["description"],
            question_type=QuestionType(d["questionType"]),
            weight=d.get("weight", 1.0),
            options=[Option.from_dict(_) for _ in d.get("options", [])],
        )


@dataclass(frozen=True)
class Section:
    title: str
    questions: list[Question]
    section_id: str

    @staticmethod
    def from_dict(d: dict, section_id: str):
        return Section(
            section_id = section_id,
            title=d["section"],
            questions=[Question.from_dict(q, question_id=f"{section_id}.{i}") for i,q in enumerate(d["questions"], start=1)],
        )


@dataclass(frozen=True)
class DataProductComplexityAssessment:
    title: str
    data_product_info: Section
    scorable_sections: list[Section]

    @staticmethod
    def from_dict(d):
        return DataProductComplexityAssessment(
            title=d["formTitle"],
            data_product_info=Section.from_dict(d["sections"][0], section_id="0"),
            scorable_sections=[Section.from_dict(s, section_id=section_num) for section_num, s in enumerate(d["sections"][1:], start=1)],
        )


class Backend(abc.ABC):
    @abc.abstractmethod
    def render(self, data: DataProductComplexityAssessment, output_path: str) -> None:
        pass
