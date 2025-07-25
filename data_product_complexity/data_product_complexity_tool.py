
import yaml
import argparse
from .excel_backend import ExcelBackend
from .google_form_backend import write_google_form_from_yaml
from .validate_input import validate_yaml
import sys

from .data_product_complexity import DataProductComplexityAssessment

def load_questionnaire(yaml_path) -> DataProductComplexityAssessment:
    with open(yaml_path, "r", encoding="utf-8") as f:
        d =  yaml.safe_load(f)
        assessment = DataProductComplexityAssessment.from_dict(d["data_product_complexity"])
        return assessment
    
def main():
    parser = argparse.ArgumentParser(
        description="Generate an Excel workbook from a data product complexity YAML specification."
    )
    parser.add_argument("yaml_path", help="Path to the YAML input file.")
    
    parser.add_argument("-f", "--format", default="excel",
                        help="What to generate (default excel).")
    parser.add_argument("-o", "--output", default="data_product_complexity_tool.xlsx",
                        help="Path to the output Excel or Google form app script file.")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate the YAML, do not generate Excel or Google form app script.")

    args = parser.parse_args()

    valid, errors = validate_yaml(args.yaml_path)

    if not valid:
        print("❌ YAML validation failed:")
        for err in errors:
            print("-", err)
        sys.exit(1)
    else:
        print("✅ YAML is valid.")

    if args.validate_only:
        print("⚠️  --validate-only flag set. Skipping Excel generation.")
        return
    
    questionnaire = load_questionnaire(args.yaml_path)

    if args.format == 'excel':
        ExcelBackend().render(questionnaire, args.output)
        print(f"✅ Excel workbook created at: {args.output}")
    
    if args.format == 'google-form':
        write_google_form_from_yaml(questionnaire, args.output)
        print(f"✅ Google form created at: {args.output}")

if __name__ == "__main__":
    main()