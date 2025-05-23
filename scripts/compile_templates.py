import json, zlib, base64, openpyxl, sys
from pathlib import Path
import datetime

SRC  = Path("apps/api-gateway/assets/templates")
DEST = Path("apps/api-gateway/assets/templates_compiled")
DEST.mkdir(exist_ok=True, parents=True)

# Custom encoder to handle special Excel objects
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle datetime objects
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        # Convert any non-standard objects to their string representation
        if hasattr(obj, 'formula') and callable(getattr(obj, 'formula', None)):
            try:
                return f"={obj.formula()}"
            except:
                return str(obj)
        elif hasattr(obj, 'value') and callable(getattr(obj, 'value', None)):
            try:
                return obj.value()
            except:
                return str(obj)
        elif str(type(obj)).startswith("<class 'openpyxl"):
            return str(obj)
        return super().default(obj)

def dump_sheet(ws):
    rows, cols = ws.max_row or 1, ws.max_column or 1
    cells = [[None for _ in range(cols)] for _ in range(rows)]
    for cell in ws.iter_rows(values_only=False):
        for c in cell:
            if c.value is not None:
                # Explicitly convert formula type data to string with '='
                if c.data_type == 'f':
                    # Store as formula string
                    cells[c.row-1][c.column-1] = f"={c.value}"
                else:
                    cells[c.row-1][c.column-1] = c.value
    return {"name": ws.title, "cells": cells, "n_rows": rows, "n_cols": cols}

for xl in SRC.glob("*.xlsx"):
    print(f"Processing {xl.name}...")
    wb = openpyxl.load_workbook(xl, data_only=False)
    print(f"Sheets in workbook: {wb.sheetnames}")
    obj = {ws.title: dump_sheet(ws) for ws in wb.worksheets}
    # Use custom encoder for JSON serialization
    json_str = json.dumps(obj, cls=CustomEncoder)
    blob = base64.b64encode(zlib.compress(json_str.encode()))
    output_file = DEST / f"{xl.stem}.json"
    output_file.write_bytes(blob)
    print(f"✓ compiled {xl.name} to {output_file}")
print("All templates done.") 