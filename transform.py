# transform_questions.py

import yaml

def transform(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Traverse each section and question
    for section in data.get('data_product_complexity', {}).get('sections', []):
        for question in section.get('questions', []):
            # Add default weight
            question['weight'] = 1

            # Transform options if present
            if 'options' in question and isinstance(question['options'], list):
                options = question['options']
                # Identify non-Not sure options for scoring
                non_ns = [opt for opt in options if opt.lower() != 'not sure']
                total = len(non_ns)

                transformed = []
                for opt in options:
                    if opt.lower() == 'not sure':
                        score = 0.5
                    else:
                        idx = non_ns.index(opt)
                        score = round((idx + 1) / total, 3) if total > 0 else 0
                    transformed.append({
                        'optionText': opt,
                        'score': score
                    })

                question['options'] = transformed

    # Print the transformed YAML
    print(yaml.dump(data, sort_keys=False, allow_unicode=True))


if __name__ == '__main__':
    transform('full_data_product_complexity_questionnaire.yaml')
