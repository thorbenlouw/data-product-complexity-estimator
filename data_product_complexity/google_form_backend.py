#!/usr/bin/env python3
"""
generate_form_script.py

Usage:
    python generate_form_script.py \
        --input questionnaire.yaml \
        --output build_form.gs
"""

from __future__ import annotations
import argparse
import json
import yaml
import textwrap
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class Question:
    question: str
    options: List[str]

    def options_count(self)->int:
        return len(self.options)

@dataclass
class Section:
    section_name: str
    section_number: int
    questions: Dict[int, Question]

    def question_count(self)->int:
        return len(self.questions)

def column_reference(index: int) -> str:
    temp: int = 0
    ref: str = ""
    while index > 0:
        temp = (index-1) % 26
        ref = chr(65 + temp) + ref
        index = (index - temp - 1) // 26
    return ref


REFERENCE_SHEET_COL_OFFSET = 1
RESPONSE_SHEET_COL_OFFSET = 1


class QuestionsConfiguration(object):

    def __init__(self, questionaire_yaml_dict: Dict[str, Any]):
        self._questionaire_yaml_dict = questionaire_yaml_dict
        self._sections: Dict[int, Section] = {}
        for i, s in enumerate(questionaire_yaml_dict["data_product_complexity"]["sections"],1):
            questions = {j: Question(question=q["question"], options=q.get("options", [])) for j, q in enumerate(s["questions"],1)}
            self._sections[i] =  Section(section_name=s["section"], section_number=i, questions=questions)

    def sections(self) -> List[Section]:
        return self._sections

    def get_index_for(self, section: int, question: int) -> int:
        return sum([self._sections[i].question_count() for i in range(1,section)])+ question

    def get_options_range_ref(self, section: int, question: int)-> str:
        col_ref = column_reference(REFERENCE_SHEET_COL_OFFSET + self.get_index_for(section, question))
        return f"""'_reference'!${col_ref}$5:${col_ref}${5+ self._sections[section].questions[question].options_count()}"""

    def get_response_ref(self, section: int, question: int, row_no: int=2)->str:
        col_ref = column_reference(REFERENCE_SHEET_COL_OFFSET + self.get_index_for(section, question))
        return f"""'Form Responses 1'!{col_ref}{row_no}"""

    def question_score_formula(self, section_no: int, question_no: int, row_no: int = 2) -> str:
        q_response = self.get_response_ref(section_no, question_no, row_no)
        options_range = self.get_options_range_ref(section_no, question_no)
        return f"""IF({q_response}="Not sure", 0.5, MATCH({q_response}, {options_range})/{self._sections[section_no].questions[question_no].options_count()}) """

    def section_score_formula(self, section_no: int, row_no: int = 2) -> str:
        questions_formula = " + ".join([self.question_score_formula(section_no, question_no, row_no) for question_no in self._sections[section_no].questions.keys()])
        return f"""=({questions_formula})/{self._sections[section_no].question_count()}"""



def to_js(obj):
    """
    Recursively convert a Python object into a JS literal.
    """
    if isinstance(obj, str):
        # Use JSON to handle escaping
        return json.dumps(obj)
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    elif obj is None:
        return 'null'
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, list):
        inner = ', '.join(to_js(v) for v in obj)
        return f'[{inner}]'
    elif isinstance(obj, dict):
        items = []
        for k, v in obj.items():
            # assume keys are valid JS identifiers or quote them
            key = k if k.isidentifier() else json.dumps(k)
            items.append(f'{json.dumps(key)}: {to_js(v)}')
        return '{' + ', '.join(items) + '}'
    else:
        raise TypeError(f"Unsupported type: {type(obj)}")    


def generate_reference_sheet_js(config):
    """
    Generate the Apps Script code (as a string) that creates a
    'Question Options Reference' sheet from the given questionnaire config.
    """
    # 1) Flatten questions
    flat = []
    for s_idx, sec in enumerate(config["data_product_complexity"]['sections'], start=2):
        for q_idx, q in enumerate(sec['questions'], start=1):
            flat.append({
                'section': s_idx,
                'questionNum': q_idx,
                'title': q['question'],
                'options': q.get('options', [])
            })
    # 2) Determine maximum number of options
    max_opts = max(len(q['options']) for q in flat)

    # 3) Build the 2D Python list of rows
    rows = []
    rows.append(['Section Number'] + [q['section'] for q in flat])
    rows.append(['Question Number'] + [f"Question_{q['questionNum']}" for q in flat])
    rows.append(['Title']           + [q['title'] for q in flat])
    rows.append(['NumOptions']      + [len(q['options']) for q in flat])
    for i in range(max_opts):
        rows.append(
            [f'Option_{i+1}'] +
            [q['options'][i] if i < len(q['options']) else '' for q in flat]
        )

    # 4) Convert that Python list into a JS literal
    js_rows = to_js(rows)

    # 5) Emit the Apps Script snippet
    snippet = f"""
      // --- Reference sheet ---
      const refName = '_reference';
      let refSheet = sheet.getSheetByName(refName);
      if (refSheet) sheet.deleteSheet(refSheet);
      refSheet = sheet.insertSheet(refName);

      const refData = {js_rows};

      // write out the lookup table
      refSheet.getRange(1, 1, refData.length, refData[0].length)
              .setValues(refData);
    """
    return textwrap.dedent(snippet).strip()


def generate_section_scores_js(config):
    """
    Returns a JS snippet string that:
      - Opens "Form Responses 1"
      - Builds/clears "Section Scores" sheet
      - For each section (except the 1st), inserts an ArrayFormula which:
          * On header row, writes "<Section> Score"
          * On data rows, averages each question's normalized score
      - Uses "Question Options Reference" to look up:
          - colIndex = MATCH(questionTitle, Ref!3:3,0)
          - numOpts   = INDEX(Ref!5:5, colIndex)
          - rawRank   = MATCH(response, OFFSET(Ref!$A$5,1,colIndex-1,numOpts,1), FALSE)
          - score     = IF(response="Not sure",0.5,(rawRank-1)/numOpts)
    """
    qc = QuestionsConfiguration(config)

    rows = []
    rows.append(["Response Time"]+  [ f"{qc._sections[i].section_name} score"  for i in range(2, len(qc._sections.keys())+1) ])
    for i in range(2,6):
        rows.append([f"='Form Responses 1'!A{i}" ] + [ qc.section_score_formula(j,i)  for j in range(2, len(qc._sections.keys())+1  )])

    js_rows = to_js(rows)

    snippet = f"""
      // --- Section Scores sheet ---
      const scoreName = 'Section Scoring';
      let scoreSheet = sheet.getSheetByName(scoreName);
      if (scoreSheet) sheet.deleteSheet(scoreSheet);
      scoreSheet = sheet.insertSheet(scoreName);

      const scoreSheetData = {js_rows};

      // set cell contents for the scoring sheet
      scoreSheet.getRange(1, 1, scoreSheetData.length, scoreSheetData[0].length)
              .setValues(scoreSheetData);
    """
    return textwrap.dedent(snippet).strip()


def generate_script(config):
    """
    Returns the full Apps Script source as a string,
    injecting the JSON-ified config, marking all questions required,
    and adding a summary sheet with section score formulas.
    """
    js_config = to_js(config["data_product_complexity"])
    respSheetName  = "Form Responses 1"

    reference_sheet_js = generate_reference_sheet_js(config)
    scoring_sheet_js = generate_section_scores_js(config)


    template = f"""
    /**
     * Auto-generated on {{timestamp}}
     * Creates a Google Form + linked Sheet based on the provided questionnaire config,
     * with every question set to required, and adds a "Section Scores" sheet.
     */
    function createDataProductComplexityForm() {{
      const config = {js_config};

      // 1) Create form and response sheet
      const form = FormApp.create(config.formTitle);
      const sheet = SpreadsheetApp.create(config.formTitle + ' Responses');
      form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

      // 2) Build form sections and questions
      config.sections.forEach(section => {{
        form.addPageBreakItem().setTitle(section.section);
        section.questions.forEach(q => {{
          const helpText = q.description || '';
          let item;
          switch (q.questionType) {{
            case 'ShortAnswer':
              item = form.addTextItem()
                         .setTitle(q.question)
                         .setHelpText(helpText)
                         .setRequired(true);
              break;
            case 'DropDown':
              item = form.addListItem()
                         .setTitle(q.question)
                         .setHelpText(helpText)
                         .setChoiceValues(q.options)
                         .setRequired(true);
              break;
            case 'CheckBox':
              item = form.addCheckboxItem()
                         .setTitle(q.question)
                         .setHelpText(helpText)
                         .setChoiceValues(q.options)
                         .setRequired(true);
              break;
            default:
              throw new Error('Unknown questionType: ' + q.questionType);
          }}
        }});
      }});

      {reference_sheet_js}

      {scoring_sheet_js}

      // 4) Log URLs
      Logger.log('Form URL: ' + form.getEditUrl());
      Logger.log('Sheet URL: ' + sheet.getUrl());
    }}
    """
    return textwrap.dedent(template).strip()

def write_google_form_from_yaml(questionair_yaml: Dict[str, Any], output_path: str):

    script = generate_script(questionair_yaml)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(script + '\n')
