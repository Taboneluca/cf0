from spreadsheet_engine import operations as ops
from spreadsheet_engine.summary import sheet_summary

TOOL_CATALOG = [
    {
        "name": "get_cell",
        "description": "Return value in a single cell (A1 notation).",
        "parameters": {
            "type": "object",
            "properties": {"cell": {"type": "string"}},
            "required": ["cell"],
        },
        "func": ops.get_cell,
        "read_only": True,
    },
    {
        "name": "get_range",
        "description": "Return values in a range of cells (A1:B2 notation).",
        "parameters": {
            "type": "object",
            "properties": {"range_ref": {"type": "string"}},
            "required": ["range_ref"],
        },
        "func": ops.get_range,
        "read_only": True,
    },
    {
        "name": "summarize_sheet",
        "description": "Get summary information about the spreadsheet (rows, columns, headers).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "func": ops.summarize_sheet,
        "read_only": True,
    },
    {
        "name": "calculate",
        "description": "Evaluate a simple formula on the spreadsheet data, such as SUM(A1:A10) or AVERAGE(B2:B5).",
        "parameters": {
            "type": "object",
            "properties": {"formula": {"type": "string"}},
            "required": ["formula"],
        },
        "func": ops.calculate,
        "read_only": True,
    },
    {
        "name": "set_cell",
        "description": "Set the value of a specific cell (A1 notation).",
        "parameters": {
            "type": "object",
            "properties": {
                "cell_ref": {"type": "string"},
                "value": {"type": ["string", "number", "boolean", "null"]},
            },
            "required": ["cell_ref", "value"],
        },
        "func": ops.set_cell,
        "read_only": False,
    },
    {
        "name": "add_row",
        "description": "Add a new row to the spreadsheet with optional values.",
        "parameters": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": ["string", "number", "boolean", "null"]}},
            },
            "required": [],
        },
        "func": ops.add_row,
        "read_only": False,
    },
    {
        "name": "add_column",
        "description": "Add a new column to the spreadsheet with optional name and values.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "values": {"type": "array", "items": {"type": ["string", "number", "boolean", "null"]}},
            },
            "required": [],
        },
        "func": ops.add_column,
        "read_only": False,
    },
    {
        "name": "delete_row",
        "description": "Delete a row from the spreadsheet by index (0-based).",
        "parameters": {
            "type": "object",
            "properties": {"row_index": {"type": "integer"}},
            "required": ["row_index"],
        },
        "func": ops.delete_row,
        "read_only": False,
    },
    {
        "name": "delete_column",
        "description": "Delete a column from the spreadsheet by index or letter.",
        "parameters": {
            "type": "object",
            "properties": {
                "column_index_or_letter": {"type": ["string", "integer"]},
            },
            "required": ["column_index_or_letter"],
        },
        "func": ops.delete_column,
        "read_only": False,
    },
    {
        "name": "sort_range",
        "description": "Sort a range of cells by a specific column.",
        "parameters": {
            "type": "object",
            "properties": {
                "range_ref": {"type": "string"},
                "key_col": {"type": ["string", "integer"]},
                "order": {"type": "string", "enum": ["asc", "desc"]},
            },
            "required": ["range_ref", "key_col"],
        },
        "func": ops.sort_range,
        "read_only": False,
    },
    {
        "name": "find_replace",
        "description": "Find and replace text in the spreadsheet.",
        "parameters": {
            "type": "object",
            "properties": {
                "find_text": {"type": "string"},
                "replace_text": {"type": "string"},
            },
            "required": ["find_text", "replace_text"],
        },
        "func": ops.find_replace,
        "read_only": False,
    },
    {
        "name": "create_new_sheet",
        "description": "Create a new spreadsheet, replacing the current one.",
        "parameters": {
            "type": "object",
            "properties": {
                "rows": {"type": "integer"},
                "cols": {"type": "integer"},
                "name": {"type": "string"},
            },
            "required": [],
        },
        "func": ops.create_new_sheet,
        "read_only": False,
    },
    {
        "name": "get_row_by_header",
        "description": "Return refs & values for the row whose first cell equals header.",
        "parameters": {
            "type": "object",
            "properties": {"header": {"type": "string"}},
            "required": ["header"],
        },
        "func": ops.get_row_by_header,
        "read_only": True,
    },
    {
        "name": "apply_scalar_to_row",
        "description": "Multiply every numeric cell in row `header` by `factor`.",
        "parameters": {
            "type": "object",
            "properties": {
                "header": {"type": "string"},
                "factor": {"type": "number"},
            },
            "required": ["header", "factor"],
        },
        "func": ops.apply_scalar_to_row,
        "read_only": False,
    },
    {
        "name": "set_cells",
        "description": "Apply many cell updates at once",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cell": {"type": "string"},
                            "value": {}
                        },
                        "required": ["cell", "value"]
                    }
                }
            },
            "required": ["updates"],
        },
        "func": ops.set_cells,
        "read_only": False,
    },
    {
        "name": "apply_updates_and_reply",
        "description": "Apply many cell updates **and** provide the final human-readable reply in ONE call.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cell":  {"type": "string"},
                            "value": {}
                        },
                        "required": ["cell", "value"]
                    }
                },
                "reply": { "type": "string" }
            },
            "required": ["updates", "reply"]
        },
        "func": lambda updates, reply="", **kw: {**ops.set_cells(updates, **kw), "reply": reply},
        "read_only": False,
    },
    {
        "name": "list_sheets",
        "description": "Return all sheet names in the current workbook.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "func": ops.list_sheets,
        "read_only": True,
    },
    {
        "name": "get_sheet_summary",
        "description": "Return rows, columns, headers & non-empty-cell count for a given sheet.",
        "parameters": {
            "type": "object",
            "properties": {"sid": {"type": "string"}},
            "required": ["sid"],
        },
        "func": ops.get_sheet_summary,
        "read_only": True,
    },
    {
        "name": "sheet_summary",
        "description": "Get a compact summary of the sheet including dimensions, headers, and sample rows.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "func": sheet_summary,
        "read_only": True,
    }
]

READ_ONLY_TOOLS = [t for t in TOOL_CATALOG if t["read_only"]]
ALL_TOOLS = TOOL_CATALOG
