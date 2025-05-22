import yaml
from cerberus import Validator
import pprint


# Load and parse the YAML file
def load_yaml_file(file_path):
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        return data, None
    except yaml.YAMLError as e:
        return None, f"YAML parsing error: {str(e)}"


# Cerberus schema definition
schema = {
    "data_product_complexity": {
        "type": "dict",
        "schema": {
            "formTitle": {"type": "string", "required": True},
            "sections": {
                "type": "list",
                "required": True,
                "schema": {
                    "type": "dict",
                    "schema": {
                        "section": {"type": "string", "required": True},
                        "questions": {
                            "type": "list",
                            "schema": {
                                "type": "dict",
                                "schema": {
                                    "question": {"type": "string", "required": True},
                                    "questionType": {
                                        "type": "string",
                                        "allowed": [
                                            "DropDown",
                                            "ShortAnswer",
                                            "CheckBox",
                                        ],
                                        "required": True,
                                    },
                                    "description": {"type": "string", "required": True},
                                    "options": {
                                        "type": "list",
                                        "schema": {
                                            "type": "dict",
                                            "schema": {
                                                "optionText": {
                                                    "type": "string",
                                                    "required": True,
                                                },
                                                "score": {
                                                    "type": "float",
                                                    "min": 0.0,
                                                    "max": 1.0,
                                                    "required": True,
                                                },
                                            },
                                            "required": False,  # Conditional logic will enforce
                                        },
                                    },
                                    "weight": {
                                        "type": "float",
                                        "min": 0.0,
                                        "max": 1.0,
                                        "required": False,
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }
}


# Custom rules beyond Cerberus
def custom_validation(data):
    errors = []

    # 1. Top-level key check
    if "data_product_complexity" not in data:
        errors.append("Missing top-level 'data_product_complexity' key.")
        return errors  # Can't continue if missing

    # 2.
    # Must have a section named "Data Product Information"
    if not any(
        s.get("section") == "Data Product Information"
        for s in data["data_product_complexity"]["sections"]
    ):
        errors.append("Missing required section: 'Data Product Information'.")

    for section in data["data_product_complexity"]["sections"]:
        for q in section.get("questions", []):
            q_type = q.get("questionType")
            options = q.get("options")

            if q_type == "ShortAnswer":
                # if "options" in q:
                #     errors.append(
                #         f"'options' should not be present for ShortAnswer in question '{q.get('question')}'."
                #     )
                pass
            elif q_type in ["DropDown", "CheckBox"]:
                if not options:
                    errors.append(
                        f"'options' must be a non-empty list for {q_type} in question '{q.get('question')}'."
                    )
                if (
                    q_type == "DropDown"
                    and options
                    and options[-1]["optionText"] != "Not sure"
                    and section["section"] != "Data Product Information"
                ):
                    errors.append(
                        f"The last option for DropDown question '{q.get('question')}' must be 'Not sure'."
                    )

    return errors


# Full validation function
def validate_yaml(file_path):
    data, parse_error = load_yaml_file(file_path)
    if parse_error:
        return False, [parse_error]

    v = Validator(schema)
    if not v.validate(data):
        pprint.pprint(v.errors)
        cerberus_errors = [f"Cerberus: {e}" for e in v.errors]
    else:
        cerberus_errors = []

    custom_errors = custom_validation(data)
    return len(cerberus_errors + custom_errors) == 0, cerberus_errors + custom_errors


# Example usage
if __name__ == "__main__":
    valid, errors = validate_yaml("your_file.yaml")
    if valid:
        print("YAML is valid ✅")
    else:
        print("YAML is invalid ❌:")
        for err in errors:
            print("-", err)
