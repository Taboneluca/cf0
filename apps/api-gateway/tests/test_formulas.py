import unittest
from apps.api_gateway.spreadsheet_engine.model import Spreadsheet

class TestFormulaEvaluation(unittest.TestCase):
    def setUp(self):
        # Create a test spreadsheet
        self.sheet = Spreadsheet(rows=10, cols=10, name="TestSheet")
        
    def test_basic_arithmetic(self):
        # Set up cells with values
        self.sheet.set_cell("A1", "5")
        self.sheet.set_cell("A2", "10")
        self.sheet.set_cell("A3", "=A1+A2")  # Should be 15
        self.sheet.set_cell("A4", "=A1-A2")  # Should be -5
        self.sheet.set_cell("A5", "=A1*A2")  # Should be 50
        self.sheet.set_cell("A6", "=A2/A1")  # Should be 2
        
        # Test the results
        self.assertEqual(self.sheet.get_cell("A3"), 15)
        self.assertEqual(self.sheet.get_cell("A4"), -5)
        self.assertEqual(self.sheet.get_cell("A5"), 50)
        self.assertEqual(self.sheet.get_cell("A6"), 2)
        
    def test_cell_multiplication(self):
        # Set up specific test for the B5*0.21 case
        self.sheet.set_cell("B5", "100")
        self.sheet.set_cell("C5", "=B5*0.21")  # Should be 21
        
        # Test the result
        self.assertEqual(self.sheet.get_cell("C5"), 21)
    
    def test_string_numeric_values(self):
        # Test that strings that look like numbers are treated as numbers
        self.sheet.set_cell("D1", "42")
        self.sheet.set_cell("D2", "=D1*2")  # Should be 84
        
        # Test the result
        self.assertEqual(self.sheet.get_cell("D2"), 84)
    
    def test_functions(self):
        # Test SUM function
        self.sheet.set_cell("E1", "10")
        self.sheet.set_cell("E2", "20")
        self.sheet.set_cell("E3", "30")
        self.sheet.set_cell("E4", "=SUM(E1:E3)")  # Should be 60
        
        # Test the result
        self.assertEqual(self.sheet.get_cell("E4"), 60)
        
    def test_cross_sheet_references(self):
        # Create a second sheet
        sheet2 = Spreadsheet(rows=10, cols=10, name="SecondSheet")
        
        # Set up workbook references manually
        self.sheet.workbook = type('obj', (object,), {
            'sheet': lambda x: sheet2 if x.upper() == "SECONDSHEET" else None
        })
        sheet2.workbook = type('obj', (object,), {
            'sheet': lambda x: self.sheet if x.upper() == "TESTSHEET" else None
        })
        
        # Set values in both sheets
        self.sheet.set_cell("F1", "50")
        sheet2.set_cell("F1", "25")
        
        # Test cross-sheet reference
        self.sheet.set_cell("F2", "=SecondSheet!F1*2")  # Should be 50
        sheet2.set_cell("F2", "=TestSheet!F1*0.5")      # Should be 25
        
        # Test the results
        self.assertEqual(self.sheet.get_cell("F2"), 50)
        self.assertEqual(sheet2.get_cell("F2"), 25)
    
    def test_complex_formulas(self):
        # Test more complex formulas
        self.sheet.set_cell("G1", "10")
        self.sheet.set_cell("G2", "20")
        self.sheet.set_cell("G3", "=G1+G2*2")   # Should be 50 (order of operations)
        self.sheet.set_cell("G4", "=(G1+G2)*2") # Should be 60 (explicit grouping)
        
        # Test the results
        self.assertEqual(self.sheet.get_cell("G3"), 50)
        self.assertEqual(self.sheet.get_cell("G4"), 60)

if __name__ == '__main__':
    unittest.main() 