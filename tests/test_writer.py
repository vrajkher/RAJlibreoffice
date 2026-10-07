import os, tempfile
from libreoffice_mcp.tools import documents as d, writer as w


def test_writer_all():
    did = d.create_document("writer")["doc_id"]
    w.writer_append(did, "Title", "Heading 1")
    w.writer_append(did, "Hello world body text.\nSecond paragraph.", "Text Body")
    assert w.writer_get_text(did)["paragraph_count"] == 3
    w.writer_insert_paragraph(did, "Inserted", 1, "Heading 2")
    assert w.writer_list_paragraphs(did)[1]["text"] == "Inserted"
    assert w.writer_find_replace(did, "world", "MCP")["replaced"] == 1
    w.writer_format_range(did, search="MCP", bold=True, color_fg="red", size=14)
    w.writer_format_range(did, paragraph=0, align="center")
    t = w.writer_insert_table(did, data=[["a", "b"], [1, 2], ["=sum(<A2:B2>)", ""]], name="T1")
    assert w.writer_get_table(did, "T1")["data"][1] == [1.0, 2.0]
    w.writer_set_table_cell(did, "T1", "B1", "x", bg="#ffff00", bold=True)
    w.writer_table_edit(did, "T1", "insert_rows", 1)
    w.writer_insert_list(did, ["one", "two"], ordered=True)
    w.writer_page_setup(did, landscape=True, margin_left_mm=20)
    w.writer_header_footer(did, header="HDR", footer="FTR", page_numbers="footer")
    w.writer_page_break(did)
    w.writer_append(did, "Last page")
    w.writer_toc(did)
    w.writer_bookmark(did, "add", "bm1", search="Last page")
    assert "bm1" in w.writer_bookmark(did, "list")
    w.writer_comment(did, "check", search="Inserted")
    assert w.writer_list_comments(did)[0]["content"] == "check"
    w.writer_footnote(did, "a note", search="Last page")
    w.writer_track_changes(did, "on"); w.writer_track_changes(did, "off")
    w.writer_insert_field(did, "page")
    w.writer_create_style(did, "MyStyle", "ParagraphStyles", "Standard", {"CharHeight": 18.0})
    assert "MyStyle" in w.writer_list_styles(did)
    assert w.writer_outline(did)
    w.writer_update_indexes(did)
    w.writer_delete_paragraph(did, 1)
    out = os.path.join(tempfile.mkdtemp(), "w.docx")
    d.save_document_as(did, out)
    assert os.path.getsize(out) > 3000
    d.close_document(did)
