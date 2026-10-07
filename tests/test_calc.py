import os, tempfile
from libreoffice_mcp.tools import documents as d, calc as c


def test_calc_all():
    did = d.create_document("calc")["doc_id"]
    c.calc_set_range(did, "A1", [["Region", "Sales", "Cost"], ["N", 10, 4], ["S", 20, 9], ["E", 15, 5], ["Tot", "=SUM(B2:B4)", "=SUM(C2:C4)"]])
    r = c.calc_get_range(did, "A1:C5")["data"]
    assert r[4][1] == 45.0, r
    assert c.calc_get_range(did, "B5", formulas=True)["data"][0][0] == "=SUM(B2:B4)"
    c.calc_sheet_edit(did, "add", "Second")
    c.calc_set_cell(did, "Second.A1", "hi")
    assert c.calc_get_range(did, "Second.A1")["data"][0][0] == "hi"
    c.calc_format_range(did, "A1:C1", bold=True, color_bg="#DDDDDD", align="center", borders=True)
    c.calc_format_range(did, "B2:C5", number_format="#,##0.00")
    c.calc_merge(did, "E1:F1")
    c.calc_sort(did, "A2:C4", column=1, ascending=False, has_header=False)
    assert c.calc_get_range(did, "A2:A2")["data"][0][0] == "S"
    c.calc_col_row_size(did, "col", 0, optimal=True)
    c.calc_freeze(did, 0, 1)
    c.calc_named_range(did, "add", "Sales", "A1:C4")
    assert c.calc_named_range(did, "list")[0]["name"] == "Sales"
    c.calc_autofilter(did, "A1:C4")
    c.calc_validation(did, "H1:H5", "list", ["a", "b"])
    c.calc_validation(did, "I1:I5", "whole", minimum=1, maximum=10)
    c.calc_conditional_format(did, "B2:B4", "greater", 12)
    c.calc_chart(did, "A1:B4", "column", title="Sales")
    c.calc_pivot(did, "A1:C4", "K1", rows=["Region"], data=["Sales"])
    assert c.calc_find_replace(did, "Tot", "Total")["count"] >= 1
    c.calc_hyperlink(did, "M1", "https://example.com", "ex")
    c.calc_insert_delete(did, "insert_rows", 0)
    c.calc_recalculate(did, True)
    assert len(c.calc_sheets(did)) == 2
    out = os.path.join(tempfile.mkdtemp(), "c.xlsx")
    d.save_document_as(did, out)
    assert os.path.getsize(out) > 3000
    d.close_document(did)


def test_autofilter_per_sheet():
    did = d.create_document("calc")["doc_id"]
    c.calc_sheet_edit(did, "add", "S2")
    for sh in ("Sheet1", "S2"):
        c.calc_set_range(did, "A1", [["h", "v"], ["a", 1]], sheet=sh)
        c.calc_autofilter(did, "A1:B2", sheet=sh)
    names = list(d.b.doc(did).DatabaseRanges.ElementNames)
    assert len([n for n in names if n.startswith("mcp_filter_")]) == 2, names
    d.close_document(did)
