#!/usr/bin/env python

import os
import re
import sys
from pathlib import Path

def update_imports(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Update import paths
    replacements = [
        # Agents imports
        (r'from agents\.', r'from core.agents.'),
        (r'import agents\.', r'import core.agents.'),
        # LLM imports
        (r'from llm\.', r'from core.llm.'),
        (r'import llm\.', r'import core.llm.'),
        # Spreadsheet engine imports
        (r'from spreadsheet_engine\.', r'from core.sheets.'),
        (r'import spreadsheet_engine\.', r'import core.sheets.'),
        # DB imports
        (r'from db\.', r'from infrastructure.'),
        (r'import db\.', r'import infrastructure.'),
        # Chat imports
        (r'from chat\.', r'from api.'),
        (r'import chat\.', r'import api.'),
    ]
    
    updated_content = content
    for pattern, replacement in replacements:
        updated_content = re.sub(pattern, replacement, updated_content)
    
    if updated_content != content:
        with open(file_path, 'w') as f:
            f.write(updated_content)
        return True
    return False

def process_directory(directory):
    modified_files = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if update_imports(file_path):
                    print(f"Updated imports in {file_path}")
                    modified_files += 1
    return modified_files

if __name__ == '__main__':
    api_gateway_dir = Path(__file__).parent.parent
    dirs_to_process = [
        api_gateway_dir / 'core',
        api_gateway_dir / 'api',
        api_gateway_dir / 'infrastructure',
        api_gateway_dir / 'main.py',
        api_gateway_dir / 'run.py',
    ]
    
    total_modified = 0
    for path in dirs_to_process:
        if path.is_file():
            if update_imports(path):
                print(f"Updated imports in {path}")
                total_modified += 1
        else:
            total_modified += process_directory(path)
    
    print(f"Total files modified: {total_modified}") 