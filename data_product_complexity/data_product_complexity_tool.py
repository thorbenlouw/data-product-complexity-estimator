
import yaml
import argparse
from excel_backend import write_excel_from_yaml
from validate_input import validate_yaml
import sys

def load_questionnaire(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(
        description="Generate an Excel workbook from a data product complexity YAML specification."
    )
    parser.add_argument("yaml_path", help="Path to the YAML input file.")
    
    parser.add_argument("-f", "--format", default="excel",
                        help="What to generate (default excel).")
    parser.add_argument("-o", "--output", default="data_product_complexity_tool.xlsx",
                        help="Path to the output Excel file.")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate the YAML, do not generate Excel.")

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
        write_excel_from_yaml(questionnaire, args.output)
        print(f"✅ Excel workbook created at: {args.output}")

if __name__ == "__main__":
    main()