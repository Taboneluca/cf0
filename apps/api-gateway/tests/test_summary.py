import json
import tiktoken
import pytest
from spreadsheet_engine.model import Spreadsheet
from spreadsheet_engine.summary import sheet_summary

def count_tokens(text, model="gpt-4o"):
    """Count tokens in a string using tiktoken"""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except (KeyError, AttributeError):
        encoding = tiktoken.get_encoding("cl100k_base")
    
    return len(encoding.encode(text))

def test_summary_token_reduction():
    """Test that sheet_summary reduces token count significantly"""
    # Create a large test sheet (100x100)
    rows = 100
    cols = 100
    sheet = Spreadsheet(rows=rows, cols=cols, name="TestSheet")
    
    # Fill with some sample data
    for r in range(0, min(rows, 40)):
        for c in range(0, min(cols, 20)):
            cell_val = f"Sample {r*c}" if (r+c) % 5 == 0 else r*c
            sheet.cells[r][c] = cell_val
    
    # Original serialization (full sheet)
    full_sheet = sheet.to_dict()
    full_json = json.dumps(full_sheet)
    full_tokens = count_tokens(full_json)
    
    # New summary serialization
    summary = sheet_summary(sheet)
    summary_json = json.dumps(summary)
    summary_tokens = count_tokens(summary_json)
    
    # Calculate reduction
    reduction_pct = 100 * (1 - summary_tokens / full_tokens)
    
    # Check actual token counts
    print(f"Full sheet tokens: {full_tokens}")
    print(f"Summary tokens: {summary_tokens}")
    print(f"Reduction: {reduction_pct:.1f}%")
    
    # Assert that we meet the requirement of 80-90% reduction
    assert reduction_pct >= 80, f"Token reduction only {reduction_pct:.1f}%, expected at least 80%"
    
    # Verify the summary contains the expected fields
    assert "name" in summary
    assert "n_rows" in summary and summary["n_rows"] == rows
    assert "n_cols" in summary and summary["n_cols"] == cols
    assert "headers" in summary
    assert "sample" in summary
    assert "hash" in summary and len(summary["hash"]) == 12 