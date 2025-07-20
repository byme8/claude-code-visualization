#!/usr/bin/env python3
"""
Process JSONL file with Claude JSON converter and apply secret replacements
"""

import subprocess
import sys
import json
from pathlib import Path
import re

def load_secret_replacements(secrets_file_path):
    """Load secret replacement patterns from secrets.local.md file."""
    replacements = {}
    secrets_path = Path(secrets_file_path)
    
    if not secrets_path.exists():
        return replacements
    
    try:
        with open(secrets_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    secret, replacement = line.split('=', 1)
                    replacements[secret.strip()] = replacement.strip()
    except Exception as e:
        print(f"Warning: Could not load secrets file {secrets_file_path}: {e}")
    
    return replacements


def apply_secret_replacements_to_value(value, replacements):
    """Apply secret replacements to a single value (string)."""
    if not replacements or not isinstance(value, str):
        return value
    
    # Apply replacements in order of length (longest first to avoid partial matches)
    for secret in sorted(replacements.keys(), key=len, reverse=True):
        replacement = replacements[secret]
        # Case-insensitive replacement
        value = re.sub(re.escape(secret), replacement, value, flags=re.IGNORECASE)
    
    return value


def apply_secret_replacements_to_dict(obj, replacements):
    """Recursively apply secret replacements to all string values in a dictionary or list."""
    if isinstance(obj, dict):
        return {key: apply_secret_replacements_to_dict(value, replacements) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [apply_secret_replacements_to_dict(item, replacements) for item in obj]
    elif isinstance(obj, str):
        return apply_secret_replacements_to_value(obj, replacements)
    else:
        return obj


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 process_json_with_secrets.py <input.jsonl> [--no-content] [-o output.json]")
        sys.exit(1)
    
    # Run the original JSON converter first
    result = subprocess.run(['python3', 'claude_log_to_json.py'] + sys.argv[1:], 
                          capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error running claude_log_to_json.py:")
        print(result.stderr)
        sys.exit(1)
    
    print(result.stdout)
    
    # Determine output file
    input_file = sys.argv[1]
    output_file = None
    
    # Check if -o was specified
    if '-o' in sys.argv:
        idx = sys.argv.index('-o')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    if not output_file:
        output_file = Path(input_file).with_suffix('.json')
    
    output_path = Path(output_file)
    
    if not output_path.exists():
        print(f"Error: Output file {output_file} was not created")
        sys.exit(1)
    
    # Load secret replacements
    script_dir = Path(__file__).parent
    secrets_file = script_dir / 'secrets.local.md'
    replacements = load_secret_replacements(secrets_file)
    
    if not replacements:
        print("No secret replacements found - file processed without changes")
        return
    
    # Read the generated JSON file
    with open(output_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Apply secret replacements to the entire JSON structure
    original_str = json.dumps(data)
    data = apply_secret_replacements_to_dict(data, replacements)
    
    # Write back the modified JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    modified_str = json.dumps(data)
    print(f"Applied {len(replacements)} secret replacements to {output_file}")
    if len(modified_str) != len(original_str):
        print(f"Content length changed from {len(original_str)} to {len(modified_str)} characters")


if __name__ == '__main__':
    main()