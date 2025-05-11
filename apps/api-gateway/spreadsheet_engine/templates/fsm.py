from .loader import insert_template

def build_fsm(wb, sheet_name: str, **kw):
    """
    Insert a pre-built Financial Statement Model (FSM) into the workbook.
    
    Args:
        wb: Target workbook to insert into
        sheet_name: Prefix for the sheet names
    
    Returns:
        Status dictionary with list of inserted sheets
    """
    return insert_template(wb, "cf0.ai.FSM", prefix=sheet_name) 