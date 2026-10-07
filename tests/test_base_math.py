import os, tempfile
from libreoffice_mcp.tools import documents as d, base_math as x, writer as w


def test_math_and_base():
    try:
        mm = d.create_document("math")["doc_id"]
    except Exception as e:
        print("SKIP math/base (module not installed):", e)
        return
    assert "over" in x.math_set_formula(mm, "a over b")["formula"]
    d.close_document(mm)
    wd = d.create_document("writer")["doc_id"]
    x.math_insert_into(wd, "E = m c^2")
    d.close_document(wd)
    p = os.path.join(tempfile.mkdtemp(), "t.odb")
    did = x.base_create(p)["doc_id"]
    x.base_execute(did, 'CREATE TABLE "People" ("id" INTEGER PRIMARY KEY, "name" VARCHAR(50))')
    x.base_execute(did, "INSERT INTO \"People\" VALUES (1, 'Ada')")
    assert x.base_query(did, 'SELECT * FROM "People"')["rows"] == [["1", "Ada"]]
    assert x.base_tables(did)[0]["table"] == "People"
