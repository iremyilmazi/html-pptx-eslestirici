import tempfile
import unittest
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from main import parse_html

class ParseTest(unittest.TestCase):
    def test_br_and_table(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'01.html'
            p.write_text('<p><strong>Bir</strong><br>İki</p><p> </p><div class="table-scroll"><table><tr><td>A</td><td>B</td></tr></table></div><h3>Üç</h3>',encoding='utf-8')
            b=parse_html([p]);self.assertEqual(len(b),4)
            self.assertEqual(b[0]['translation'],'Bir\nİki')
            self.assertEqual(b[1]['html_type'],'table_cell')
            self.assertEqual(b[3]['translation'],'Üç')
if __name__=='__main__': unittest.main()
