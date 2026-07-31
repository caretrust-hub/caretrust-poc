from __future__ import annotations
import json

from docx import Document

from scripts.build_smart40_data_output_logs import DISCLOSURE, DOCX, MD, build, load

def test_smart40_log_has_all_frozen_cycles_hash_and_disclosure():
    frozen,rows=load(); build(); text=MD.read_text(encoding='utf-8')
    assert len(rows)==40 and [row['ordinal'] for row in rows]==list(range(1,41))
    assert frozen['freeze_sha256'] in text and DISCLOSURE in text
    assert '"status": "error"' in text
    for row in rows: assert row['case_id'] in text


def test_smart40_docx_reproduces_each_ordered_json_record_exactly():
    _, rows = load()
    build()
    paragraphs = [paragraph.text for paragraph in Document(DOCX).paragraphs]
    cycle_headings = [
        (index, text)
        for index, text in enumerate(paragraphs)
        if text.startswith("Cycle ")
    ]
    assert len(cycle_headings) == 40
    for expected, (index, heading) in zip(rows, cycle_headings, strict=True):
        assert heading == (
            f'Cycle {expected["ordinal"]}: {expected["case_id"]} '
            f'({expected["group"]})'
        )
        assert json.loads(paragraphs[index + 1]) == expected
