import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import (column_index_from_string, get_column_letter,
                            range_boundaries)
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.layout import Layout, ManualLayout

import re



def sanitize_sheet_name(name):
    """Convert to lowercase and keep only _0-9a-zA-Z"""
    base = "_data_" + re.sub(r"[^0-9a-zA-Z_]", "", name.replace(" ", "_").lower())
    return base[:31]  # Excel sheet name limit


def populate_score_sheet(wb, question_formulas):
    ws_score: Worksheet = wb.create_sheet("Score")
    wb._sheets.remove(ws_score)
    wb._sheets.insert(2, ws_score)
    row = 2  # Start from row 2 to leave space for headers

    # Headers
    ws_score.cell(row=1, column=1, value="Section")
    ws_score.cell(row=1, column=2, value="Final Score (1–5)")
    ws_score.cell(row=1, column=1).font = Font(bold=True)
    ws_score.cell(row=1, column=2).font = Font(bold=True)

    for category in question_formulas.keys():
        if category == "Data Product Information":
            pass
        else:
            ws_score.cell(row=row, column=1, value=category)
            for qidx, question in enumerate(question_formulas[category]):
                tmp_cell = ws_score.cell(row=row, column=3 + qidx)
                tmp_cell.value = question_formulas[category][qidx]
                # print(question_formulas[category][qidx])
            avg_formula = f"=INT(AVERAGE(C{row}:{get_column_letter(len(question_formulas[category])+3)}{row}) * 5) + 1"
            ws_score.cell(row=row, column=2).value = avg_formula
            row += 1

    # Apply heatmap conditional formatting to column B
    heatmap = ColorScaleRule(
        start_type="num",
        start_value=1,
        start_color="92D050",
        mid_type="num",
        mid_value=3,
        mid_color="FFFF00",
        end_type="num",
        end_value=5,
        end_color="FF0000",
    )
    ws_score.conditional_formatting.add(f"B2:B{row - 1}", heatmap)

    fit_col_width(worksheet=ws_score, col="A")
    fit_col_width(worksheet=ws_score, col="B")

    for col_letter in [get_column_letter(x) for x in range(3, 30)]:
        ws_score.column_dimensions[col_letter].hidden = True


    chart = BarChart()
    chart.type = "bar"
    chart.style = 10  # Excel predefined chart style
    chart.title = "Data Product Complexity Scores"
    chart.y_axis.title = "Sections"
    chart.x_axis.title = "Score"
    chart.y_axis.majorGridlines = None  # Optional: remove vertical gridlines
    chart.x_axis.majorGridlines = chart.x_axis.majorGridlines  # Ensures horizontal gridlines are visible

    # Reference data
    data_ref = Reference(ws_score, min_col=2, min_row=1, max_row=8)
    categories_ref = Reference(ws_score, min_col=1, min_row=2, max_row=8)

    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(categories_ref)

    # Layout to roughly center chart (H1 is a good anchor)
    chart.layout = Layout(
        manualLayout=ManualLayout(
            x=0.25, y=0.1, h=0.6, w=0.5,  # Adjust for position and size
            xMode="factor", yMode="factor",
            hMode="factor", wMode="factor"
        )
    )

    # === Step 3: Insert Chart into Sheet ===
    ws_score.add_chart(chart, "H1")  # Center-ish position


def apply_font_to_range(wb, range_str, bold=False, italic=False):
    """
    Applies bold and/or italic font to all cells in the specified range.

    Parameters:
        wb        : openpyxl Workbook object
        range_str : string like "Sheet1!A5:B11"
        bold      : apply bold font if True
        italic    : apply italic font if True
    """
    # Parse sheet name and range
    if "!" not in range_str:
        raise ValueError("Range must be in 'Sheet!A1:B2' format")

    sheet_name, cell_range = range_str.split("!")
    ws = wb[sheet_name]

    # Get boundaries
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)

    # Apply font to each cell
    for row in ws.iter_rows(
        min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col
    ):
        for cell in row:
            cell.font = Font(bold=bold, italic=italic)


def fit_col_width(worksheet, col: str) -> None:
    col_idx = column_index_from_string(col)
    max_length = 0

    for row in worksheet.iter_rows(
        min_row=1, max_row=worksheet.max_row, min_col=col_idx, max_col=col_idx
    ):
        for cell in row:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))

    worksheet.column_dimensions[col].width = max_length + 2


def populate_data_sheets(wb, questionnaire):
    """
    For each of the categories we create a hidden _data_categoryname tab that has the questions and options laid
    out like:

    |             | Question_1 | Question_2 | .... | Question_n |
    | Title       | xxxx       | xxxx       | .... | ...        |
    | Description | ....
    | NumOptions  | ....
    | Option_1    | ...  |
    | Option_2    | ...  |
    | ...
    | Option_n.   | ...  

    After this we set up the rest of the Excel file to calculate everything from the 
    hidden data tabs (DataValidations for dropdowns, understanding how many options in each question, 
    how many questions in a section etc.) 
    """
    for section_index, section in enumerate(
        questionnaire["data_product_complexity"]["sections"], start=1
    ):
        category = section["section"]
        questions = section["questions"]
        sheet_name = sanitize_sheet_name(category)
        ws_data = wb.create_sheet(title=sheet_name)

        headers = [""] + [f"Question_{x}" for x in range(1, len(questions) + 1)]
        titles = ["Title"] + [q["question"] for q in questions]
        num_questions = len(questions)
        descriptions = ["Description"] + [q.get("description", "") for q in questions]
        max_options = max(len(q.get("options", [])) for q in questions)
        num_options_row = ["NumOptions"] + [
            len(q.get("options", [])) for q in questions
        ]
        option_rows = []

        for i in range(max_options):
            row = [f"Option_{i}"]
            for q in questions:
                opts = q.get("options", [])
                row.append(opts[i] if i < len(opts) else "")
            option_rows.append(row)

        ws_data.append(headers)
        ws_data.append(titles)
        ws_data.append(descriptions)
        ws_data.append(num_options_row)
        for row in option_rows:
            ws_data.append(row)

        apply_font_to_range(wb, f"{sheet_name}!A1:A{max_options+4}", bold=True)
        apply_font_to_range(
            wb, f"{sheet_name}!A1:{get_column_letter(num_questions+1)}1", bold=True
        )
        for col in [get_column_letter(x) for x in range(1, num_questions + 1)]:
            fit_col_width(ws_data, col)

        ws_data.sheet_state = "hidden"


def get_validation_formula1(ws, cell_address):
    """
    For a given cell, we get the DataValidation attached to it and
    extract the formula1 if it's a list DataValidation. That gives us
    the range that forms the options
    """
    for dv in ws.data_validations.dataValidation:
        for dv_range in dv.cells.ranges:
            if cell_address in dv_range:
                if dv.type == "list":
                    return dv.formula1  # e.g. "'Sheet3'!$C$4:$C$17"
    return None


def get_full_cell_address(cell):
    """
    Get the 'SheetName'!$A$6 form of a cell address 
    """
    return f"{cell.parent.title}!{cell.coordinate}"


def question_score_formula(options_cell_address, validation_formula) -> str:
    """
    validation_formula is the range given to the list DataValidation (a range of cells that form the valid options)

    Finds the index of the option (that will form the rank value of the answer) unless it's the
    last answer (always Not Sure). We have this so that if a question had options 
    A, B, C, D, E, Not sure
    Then we return 2 if the answer is C, 0 if the answer is A, and 0.5 if the answer is Not sure (take the average val)
    """
    formula = f"=IF(MATCH({options_cell_address}, {validation_formula}, 0) - 1 = COUNTA({validation_formula})-1,0.5,(MATCH({options_cell_address}, {validation_formula}, 0) - 1)/(COUNTA({validation_formula})-1))"

    return formula


def populate_questions_sheet(wb, questionnaire):
    """
    Populates the questions data from the questionnaire yaml,
    setting up the DataValidation (dropdowns) of options for each
    question as
    
    1   | Section title | 
    1.1 | Question 1 title | Cell with Options in dropdown
        | Question 1 description 
    """
    ws_questions = wb.create_sheet("Questions")
    wb._sheets.remove(ws_questions)
    wb._sheets.insert(1, ws_questions)

    question_formulas = {}

    question_row = 1

    col_indexes = {"q_num": 1, "title": 2, "description": 2, "options": 3}

    for section_index, section in enumerate(
        questionnaire["data_product_complexity"]["sections"], start=1
    ):
        category = section["section"]
        question_formulas[category] = []
        data_worksheet_name = sanitize_sheet_name(category)

        questions = section["questions"]
        ws_questions.cell(
            row=question_row, column=col_indexes["title"], value=f"{category}"
        )
        ws_questions.cell(row=question_row, column=col_indexes["title"]).font = Font(
            bold=True
        )
        q_num_cell = ws_questions.cell(
            row=question_row, column=col_indexes["q_num"], value=section_index
        )
        q_num_cell.font = Font(bold=True)

        question_row += 1

        for i, q in enumerate(questions, start=1):
            q_num = f"{section_index}.{i}"
            ws_questions.cell(
                row=question_row, column=col_indexes["q_num"], value=q_num
            )

            q_title = f"{q['question']}"
            ws_questions.cell(
                row=question_row, column=col_indexes["title"], value=q_title
            )
            question_row += 1

            title_row = 2

            d_cell = ws_questions.cell(
                row=question_row,
                column=col_indexes["description"],
                value=f"={data_worksheet_name}!{get_column_letter(i+1)}{title_row+1}",
            )
            d_cell.font = Font(italic=True)
            question_row += 1

            options = q.get("options", [])
            if options:
                data_col_index = i + 1
                col_letter = get_column_letter(data_col_index)
                start_row = 5
                end_row = start_row + len(options) - 1
                range_formula = f"'{data_worksheet_name}'!${col_letter}${start_row}:${col_letter}${end_row}"

                dv = DataValidation(
                    type="list", formula1=range_formula, showDropDown=False
                )
                dropdown_cell = ws_questions.cell(
                    row=question_row - 2, column=col_indexes["options"]
                )
                ws_questions.add_data_validation(dv)
                dv.add(dropdown_cell)

                question_formulas[category].append(
                    question_score_formula(
                        get_full_cell_address(dropdown_cell), range_formula
                    )
                )

                if "Not sure" in options:
                    dropdown_cell.value = "Not sure"

        question_row += 1

    not_sure_fill = PatternFill(
        start_color="FFFFCC", end_color="FFFFCC", fill_type="solid"
    )
    question_answer_range = f"B1:B{ws_questions.max_row}"
    ws_questions.conditional_formatting.add(
        question_answer_range,
        CellIsRule(operator="equal", formula=['"Not sure"'], fill=not_sure_fill),
    )

    fit_col_width(worksheet=ws_questions, col="A")
    fit_col_width(worksheet=ws_questions, col="B")
    fit_col_width(worksheet=ws_questions, col="C")

    return question_formulas


def write_excel_from_yaml(questionnaire, output_path):
    wb = Workbook()
    populate_data_sheets(wb, questionnaire)
    question_formulas = populate_questions_sheet(wb, questionnaire)
    populate_score_sheet(wb, question_formulas)
    del wb["Sheet"]
    wb.save("tmp_" + output_path)

    # Need to strip @s from pyopenxsl's pesky formula validation
    wb = load_workbook("tmp_" + output_path, data_only=False)

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    cell.value = cell.value.replace("@", "")

    wb.save(output_path)


