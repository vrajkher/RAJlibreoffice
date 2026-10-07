import os, tempfile
from libreoffice_mcp.tools import documents as d, impress as i


def test_impress_all():
    did = d.create_document("impress")["doc_id"]
    n0 = len(i.impress_list_slides(did))
    i.impress_add_slide(did, "title_content", "Quarterly Review", "Revenue up\nCosts down")
    sl = i.impress_list_slides(did)
    assert len(sl) == n0 + 1 and sl[-1]["title"] == "Quarterly Review", sl
    k = n0
    i.impress_add_shape(did, k, "rectangle", 10, 100, 50, 20, fill="#336699", text="Box", text_color="white")
    i.impress_add_shape(did, k, "star", 70, 100, 30, 30, fill="yellow")
    i.impress_add_text(did, k, "note", 10, 130)
    i.impress_add_table(did, k, [["a", "b"], [1, 2]])
    assert len(i.impress_list_shapes(did, k)) >= 6
    i.impress_edit_shape(did, k, 2, x_mm=15, fill="#ff0000")
    i.impress_arrange(did, k, 2, "front")
    i.impress_notes(did, k, "speaker notes")
    assert i.impress_notes(did, k)["notes"] == "speaker notes"
    i.impress_transition(did, k, "DISSOLVE")
    i.impress_background(did, k, "#eeeeee")
    i.impress_set_layout(did, k, "title_only")
    i.impress_duplicate_slide(did, k)
    i.impress_move_slide(did, k + 1, 0)
    i.impress_delete_shape(did, k, 2)
    assert i.impress_master(did)
    out = tempfile.mkdtemp()
    i.impress_export_slide(did, k, os.path.join(out, "s.png"))
    assert os.path.getsize(os.path.join(out, "s.png")) > 1000
    d.save_document_as(did, os.path.join(out, "p.pptx"))
    d.close_document(did)
    dr = d.create_document("draw")["doc_id"]
    i.impress_add_shape(dr, 0, "ellipse", 10, 10, 40, 40, fill="green")
    assert i.impress_list_shapes(dr, 0)
    d.close_document(dr)
