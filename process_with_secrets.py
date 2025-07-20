#!/usr/bin/env python3
"""
Process JSONL file with Claude log converter and apply secret replacements
"""

import subprocess
import sys
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


def apply_secret_replacements(text, replacements):
    """Apply secret replacements to text content."""
    if not replacements or not text:
        return text
    
    # Apply replacements in order of length (longest first to avoid partial matches)
    for secret in sorted(replacements.keys(), key=len, reverse=True):
        replacement = replacements[secret]
        # Case-insensitive replacement
        text = re.sub(re.escape(secret), replacement, text, flags=re.IGNORECASE)
    
    return text


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 process_with_secrets.py <input.jsonl> [--presentation-mode] [-o output.md]")
        sys.exit(1)
    
    # Run the original converter first
    result = subprocess.run(['python3', 'claude_log_converter.py'] + sys.argv[1:], 
                          capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error running claude_log_converter.py:")
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
        output_file = Path(input_file).with_suffix('.md')
    
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
    
    # Read the generated markdown file
    with open(output_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Apply secret replacements
    original_length = len(content)
    content = apply_secret_replacements(content, replacements)
    
    # Write back the modified content
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Applied {len(replacements)} secret replacements to {output_file}")
    if len(content) != original_length:
        print(f"Content length changed from {original_length} to {len(content)} characters")


if __name__ == '__main__':
    main()