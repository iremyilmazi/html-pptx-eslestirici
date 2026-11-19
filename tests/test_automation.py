import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from pptx import Presentation
from pptx.util import Inches

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import main


class AutomationTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.pptx = self.directory / 'example.pptx'
        self.html = self.directory / 'html'
        self.html.mkdir()
        self.output = self.directory / 'output'

        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        for index, text in enumerate(
            ['Solar panel performance', 'General information', 'General information']
        ):
            shape = slide.shapes.add_textbox(
                Inches(1), Inches(index + 1), Inches(8), Inches(.5)
            )
            shape.text = text
        table = slide.shapes.add_table(1, 2, Inches(1), Inches(4), Inches(8), Inches(.5)).table
        table.cell(0, 0).text = 'Battery storage capacity'
        table.cell(0, 1).text = 'Annual power generation'
        presentation.save(self.pptx)
        self.original_sha = hashlib.sha256(self.pptx.read_bytes()).digest()

        (self.html / '01.html').write_text(
            '<p>Güneş paneli performansı</p><p>Genel bilgiler</p>'
            '<table><tr><td>Batarya depolama kapasitesi</td>'
            '<td>Yıllık elektrik üretimi</td></tr></table>',
            encoding='utf-8',
        )

    def prepare_args(self, command):
        return [
            command, '--pptx', str(self.pptx), '--html-dir', str(self.html),
            '--output', str(self.output),
        ]

    @staticmethod
    def fake_embeddings(texts, model_dir):
        concepts = (
            ('Solar panel performance', 'Güneş paneli performansı'),
            ('General information', 'Genel bilgiler'),
            ('Battery storage capacity', 'Batarya depolama kapasitesi'),
            ('Annual power generation', 'Yıllık elektrik üretimi'),
        )
        vector_ids = {text: index for index, pair in enumerate(concepts) for text in pair}
        vectors = np.eye(len(concepts), dtype=np.float32)
        return vectors[[vector_ids[text] for text in texts]]

    def test_automatic_applies_unique_matches_and_leaves_ambiguous_for_review(self):
        with patch.object(main, 'encode_texts', side_effect=self.fake_embeddings):
            self.assertEqual(main.main(self.prepare_args('otomatik')), 0)

        result = Presentation(self.output / 'cevrilmis.pptx')
        shapes = result.slides[0].shapes
        self.assertEqual(shapes[0].text, 'Güneş paneli performansı')
        self.assertEqual(shapes[1].text, 'General information')
        self.assertEqual(shapes[2].text, 'General information')
        self.assertEqual(shapes[3].table.cell(0, 0).text, 'Batarya depolama kapasitesi')
        self.assertEqual(shapes[3].table.cell(0, 1).text, 'Yıllık elektrik üretimi')
        self.assertEqual(hashlib.sha256(self.pptx.read_bytes()).digest(), self.original_sha)

        review = main.read_csv(self.output / 'kontrol_gerekenler.csv')
        self.assertEqual([row['translation'] for row in review], ['Genel bilgiler'])
        self.assertEqual(review[0]['apply'], '')
        mapping = main.read_csv(self.output / 'eslestirme_sablonu.csv')
        self.assertEqual(len(mapping), 4)
        self.assertEqual(sum(row['apply'] == 'EVET' for row in mapping), 3)
        self.assertTrue((self.output / 'pptx_envanter.csv').is_file())

    def test_manual_prepare_and_apply_remain_available_without_model(self):
        self.assertIn(main.main(self.prepare_args('hazirla')), (None, 0))
        mapping = self.output / 'eslestirme_sablonu.csv'
        rows = main.read_csv(mapping)
        self.assertTrue(all(row['apply'] == '' for row in rows))
        target_id = Presentation(self.pptx).slides[0].shapes[2].shape_id
        rows[1].update(
            apply='EVET', target_slide='1', target_shape_id=str(target_id),
            target_row='', target_col='',
        )
        main.write_csv(mapping, main.FIELDS, rows)

        manual_output = self.output / 'manual.pptx'
        self.assertEqual(main.main([
            'uygula', '--pptx', str(self.pptx), '--mapping', str(mapping),
            '--output', str(manual_output),
        ]), 0)
        shapes = Presentation(manual_output).slides[0].shapes
        self.assertEqual(shapes[0].text, 'Solar panel performance')
        self.assertEqual(shapes[1].text, 'General information')
        self.assertEqual(shapes[2].text, 'Genel bilgiler')
        self.assertEqual(hashlib.sha256(self.pptx.read_bytes()).digest(), self.original_sha)

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        existing = self.output / 'eslestirme_sablonu.csv'
        existing.write_text('Önceki eşleştirmeler', encoding='utf-8')
        with patch.object(main, 'encode_texts') as encode:
            self.assertEqual(main.main(self.prepare_args('otomatik')), 1)
        encode.assert_not_called()
        self.assertEqual(existing.read_text(encoding='utf-8'), 'Önceki eşleştirmeler')

    def test_no_accepted_matches_writes_only_review(self):
        def empty_evidence(texts, model_dir):
            return np.zeros((len(texts), 4), dtype=np.float32)

        with patch.object(main, 'encode_texts', side_effect=empty_evidence):
            self.assertEqual(main.main(self.prepare_args('otomatik')), 0)

        self.assertFalse((self.output / 'cevrilmis.pptx').exists())
        review = main.read_csv(self.output / 'kontrol_gerekenler.csv')
        self.assertEqual(len(review), 4)
        self.assertTrue(all(row['apply'] == '' for row in review))


if __name__ == '__main__':
    unittest.main()
