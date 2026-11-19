import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from auto_match import suggest

class AutoTests(unittest.TestCase):
    def test_order_and_table_kind(self):
        blocks=[{'translation':'Toplam büyüme 2026 %15','html_type':'p'}, {'translation':'2026 12','html_type':'table_cell'}]
        slots=[{'text':'Total growth 2026 15%','kind':'text','slide':1,'shape_id':2,'row':'','col':''},
               {'text':'2026 12','kind':'table_cell','slide':2,'shape_id':3,'row':1,'col':1}]
        result=suggest(blocks,slots)
        self.assertEqual(result[0][0]['shape_id'],2)
        self.assertEqual(result[1][0]['shape_id'],3)
    def test_empty(self):
        self.assertEqual(suggest([],[]),{})
if __name__=='__main__':unittest.main()
