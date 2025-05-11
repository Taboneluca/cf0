#!/usr/bin/env python3
import json, zlib, base64
from pathlib import Path

TEMPLATES_DIR = Path("apps/api-gateway/assets/templates_compiled")

def inspect_template(filename):
    """Decode and inspect a compiled template JSON file."""
    path = TEMPLATES_DIR / filename
    
    # Read the compressed blob
    data = path.read_bytes()
    
    # Decompress and decode
    template_json = json.loads(zlib.decompress(base64.b64decode(data)))
    
    print(f"\n===== Template: {filename} =====")
    print(f"Number of sheets: {len(template_json)}")
    
    # Inspect each sheet
    for sheet_name, sheet_data in template_json.items():
        print(f"\n  Sheet: {sheet_name}")
        print(f"  Dimensions: {sheet_data['n_rows']} rows × {sheet_data['n_cols']} columns")
        
        # Count non-empty cells
        non_empty = 0
        formula_count = 0
        cells = sheet_data['cells']
        
        for row in cells:
            for cell in row:
                if cell is not None:
                    non_empty += 1
                    if isinstance(cell, str) and cell.startswith('='):
                        formula_count += 1
        
        print(f"  Non-empty cells: {non_empty}")
        print(f"  Formulas: {formula_count}")
        
        # Print sample cells (first few non-empty)
        print("\n  Sample cells:")
        samples = 0
        for r_idx, row in enumerate(cells):
            for c_idx, value in enumerate(row):
                if value is not None and samples < 5:
                    samples += 1
                    print(f"    Cell {r_idx+1},{c_idx+1}: {value}")

# Check all template files
for template_file in TEMPLATES_DIR.glob("*.json"):
    inspect_template(template_file.name) 