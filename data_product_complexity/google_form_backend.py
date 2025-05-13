#!/usr/bin/env python3
"""
generate_form_script.py

Usage:
    python generate_form_script.py \
        --input questionnaire.yaml \
        --output build_form.gs
"""

import argparse
import json
import yaml
import textwrap
from typing import Dict, Any


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

def generate_script(config):
    """
    Returns the full Apps Script source as a string, injecting the JSON-ified config.
    """
    js_config = to_js(config)

    # Use a template for the rest of the code
    template = f"""
    /**
     * Auto-generated on {{timestamp}}
     * Creates a Google Form + linked Sheet based on the provided questionnaire config.
     */
    function createDataProductComplexityForm() {{
      const config = {js_config};

      // create form and sheet
      const form = FormApp.create(config.formTitle);
      const sheet = SpreadsheetApp.create(config.formTitle + ' Responses');
      form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

      // build sections and questions
      config.sections.forEach(section => {{
        form.addPageBreakItem()
            .setTitle(section.section);

        section.questions.forEach(q => {{
          const helpText = q.description || '';
          switch (q.questionType) {{
            case 'ShortAnswer':
              form.addTextItem()
                  .setTitle(q.question)
                  .setHelpText(helpText);
              break;
            case 'DropDown':
              form.addListItem()
                  .setTitle(q.question)
                  .setHelpText(helpText)
                  .setChoiceValues(q.options);
              break;
            case 'CheckBox':
              form.addCheckboxItem()
                  .setTitle(q.question)
                  .setHelpText(helpText)
                  .setChoiceValues(q.options);
              break;
            default:
              throw new Error('Unknown questionType: ' + q.questionType);
          }}
        }});
      }});

      Logger.log('Form URL: ' + form.getEditUrl());
      Logger.log('Sheet URL: ' + sheet.getUrl());
    }}
    """
    # Dedent and strip leading/trailing blank lines
    return textwrap.dedent(template).strip()


def write_google_form_from_yaml(questionair_yaml: Dict[str, Any], output_path: str):

    script = generate_script(questionair_yaml)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(script + '\n')
