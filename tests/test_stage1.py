import os
import tempfile


from libreoffice_mcp.tools import documents as d, generic as g, guide


def test_guide():
    assert "OPEN" in guide.lo_guide()


def test_lifecycle_and_generic():
    r = d.create_document("writer")
    did = r["doc_id"]
    root = g.uno_root(did, "text")
    g.uno_call(root["handle"], "setString", ["Hello MCP"])
    out = os.path.join(tempfile.mkdtemp(), "t.docx")
    d.save_document_as(did, out)
    assert os.path.getsize(out) > 1000
    pdf = os.path.join(os.path.dirname(out), "t.pdf")
    d.export_pdf(did, pdf)
    assert open(pdf, "rb").read(4) == b"%PDF"
    assert g.run_python("result = doc.getText().getString()", did)["result"] == "Hello MCP"
    assert g.uno_get(root["handle"], "String") == "Hello MCP"
    g.dispatch_command(did, ".uno:SelectAll")
    d.close_document(did)
    d2 = d.open_document(out)
    assert d.document_info(d2["doc_id"])["kind"] == "writer"
    d.close_document(d2["doc_id"])
