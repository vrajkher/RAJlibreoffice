"""Real UNO tests for the convenience workflows added in 0.2."""
import os
from pathlib import Path
import tempfile
import unittest

from raj_libreoffice.bridge import Bridge
from raj_libreoffice.config import Config
from test_integration import pyuno_available


@unittest.skipUnless(pyuno_available(), "requires LibreOffice/PyUNO")
class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bridge = Bridge(Config(self.root, uno_python=os.getenv("RAJ_UNO_PYTHON", "/usr/bin/python3"),
                                    advanced=True, scripts=True, python_execution=True))
        self.call = self.bridge.call

    def tearDown(self):
        self.bridge.close()
        self.temp.cleanup()

    def new(self, kind):
        return self.call("document_create", kind=kind)["document"]

    def test_writer_page_structures_styles_review_roundtrip(self):
        doc = self.new("writer")
        self.call("writer_insert", document=doc, text="Heading\nBody text\n")
        self.call("writer_format", document=doc, start=0, length=7, properties={"ParaStyleName": "Heading 1"})
        self.call("style_create", document=doc, family="ParagraphStyles", name="RAJ Body",
                  parent="Standard", properties={"CharHeight": 13.0})
        self.call("writer_page", document=doc, header="Header test", footer="Footer test")
        for kind in ["section", "frame", "footnote", "endnote"]:
            obj = self.call("writer_structure", document=doc, kind=kind, text=kind + " content")
            self.assertIn("$ref", obj)
        self.call("writer_structure", document=doc, kind="toc", position=0,
                  properties={"Title": "Contents", "CreateFromOutline": True})
        self.call("writer_review", document=doc, comment="Check this", author="Tester", position=0)
        self.call("writer_review", document=doc, record=True)
        self.call("writer_insert", document=doc, text="Tracked insertion")
        review = self.call("writer_review", document=doc)
        self.assertTrue(review["recording"])
        self.assertGreater(review["total"], 0)
        self.call("document_save", document=doc, path="advanced.odt")
        self.call("document_close", document=doc)
        doc = self.call("document_open", path="advanced.odt")["document"]
        page = self.call("writer_page", document=doc)
        self.assertEqual(page["header"], "Header test")
        self.assertEqual(page["footer"], "Footer test")
        self.assertIn("RAJ Body", self.call("style_list", document=doc, family="ParagraphStyles"))
        counts = self.call("python_run", document=doc, code="result = [document.TextSections.Count, document.TextFrames.Count, document.Footnotes.Count, document.Endnotes.Count, document.DocumentIndexes.Count]")
        self.assertGreaterEqual(counts["result"][0], 1)
        self.assertEqual(counts["result"][1:], [1, 1, 1, 1])

    def test_calc_rules_filters_functions_goalseek_and_arrays(self):
        doc = self.new("calc")
        self.call("calc_write", document=doc, sheet=0, range="A1:B4", data=[["Group", "Amount"], ["A", 2], ["B", 3], ["A", 4]])
        self.call("calc_filter", document=doc, sheet=0, range="A1:B4", fields=[{"column": 0, "value": "A"}])
        result = self.call("python_run", document=doc, code="result = [document.Sheets[0].Rows[1].IsVisible, document.Sheets[0].Rows[2].IsVisible, document.Sheets[0].Rows[3].IsVisible]")
        self.assertEqual(result["result"], [True, False, True])
        self.call("calc_filter", document=doc, sheet=0, range="A1:B4", fields=[])
        rules = self.call("calc_validation", document=doc, sheet=0, range="B2:B4", properties={"Type": "WHOLE", "Operator": "BETWEEN", "Formula1": "1", "Formula2": "10", "ShowErrorMessage": True})
        self.assertEqual(rules["Type"]["value"], "WHOLE")
        self.call("style_create", document=doc, family="CellStyles", name="Highlight", properties={"CellBackColor": 0xFFFF00})
        self.assertEqual(self.call("calc_conditional", document=doc, sheet=0, range="B2:B4", entries=[{"Operator": "GREATER", "Formula1": "2", "StyleName": "Highlight"}])["rules"], 1)
        self.call("calc_annotation", document=doc, sheet=0, cell="A2", text="Comment", visible=False)
        self.assertEqual(self.call("calc_annotation", document=doc, sheet=0, cell="A2")["text"], "Comment")
        self.assertEqual(self.call("calc_function", name="SUM", arguments=[[[2, 3], [4, 5]]]), 14.0)
        self.call("calc_write", document=doc, sheet=0, range="D1:D1", data=[[2]])
        self.call("calc_write", document=doc, sheet=0, range="E1:E1", data=[["=D1*3"]], formulas=True)
        goal = self.call("calc_goal_seek", document=doc, sheet=0, formula_cell="E1", variable_cell="D1", target="12")
        self.assertAlmostEqual(goal["fields"]["Result"], 4.0, places=4)
        self.assertEqual(self.call("calc_read", document=doc, sheet=0, range="D1")["data"], [[2.0]])
        self.call("calc_array_formula", document=doc, sheet=0, range="G1:G2", formula="=B2:B3*2")
        self.assertEqual(self.call("calc_read", document=doc, sheet=0, range="G1:G2")["data"], [[4.0], [6.0]])
        self.assertTrue(self.call("calc_protect", document=doc, sheet=0, password="test")["protected"])
        self.assertFalse(self.call("calc_protect", document=doc, sheet=0, protect=False, password="test")["protected"])
        self.call("document_save", document=doc, path="rules.ods")
        self.call("document_close", document=doc)
        doc = self.call("document_open", path="rules.ods")["document"]
        self.assertEqual(self.call("calc_annotation", document=doc, sheet=0, cell="A2")["text"], "Comment")
        self.assertEqual(self.call("calc_validation", document=doc, sheet=0, range="B2:B4")["Type"]["value"], "WHOLE")
        self.assertEqual(self.call("python_run", document=doc, code="result = document.Sheets[0].getCellRangeByName('B2:B4').ConditionalFormat.Count")["result"], 1)

    def test_calc_pivots_subtotals_and_chart_configuration(self):
        doc = self.new("calc")
        self.call("calc_write", document=doc, sheet=0, range="A1:B4", data=[["Group", "Amount"], ["A", 2], ["A", 4], ["B", 3]])
        pivot = self.call("calc_pivot", document=doc, sheet=0, range="A1:B4", name="Summary", output="E1", fields=[{"name": "Group", "orientation": "ROW"}, {"name": "Amount", "orientation": "DATA", "function": "SUM"}])
        self.assertIn("$ref", pivot)
        cells = self.call("calc_read", document=doc, sheet=0, range="E1:G8")["data"]
        self.assertIn(6.0, [x for row in cells for x in row])
        chart = self.call("calc_chart", document=doc, sheet=0, range="A1:B4", name="Chart")["$ref"]
        self.call("calc_chart_configure", object=chart, diagram="com.sun.star.chart.BarDiagram", title="Totals", legend=False)
        self.assertEqual(self.call("python_run", document=doc, code="result = document.Sheets[0].Charts.getByName('Chart').EmbeddedObject.getTitle().String")["result"], "Totals")
        self.call("calc_subtotals", document=doc, sheet=0, range="A1:B4", columns=[{"column": 1, "function": "SUM"}])
        values = self.call("calc_read", document=doc, sheet=0, range="A1:B8")["data"]
        self.assertIn(9.0, [x for row in values for x in row])
        self.call("calc_subtotals", document=doc, sheet=0, range="A1:B8", remove=True)
        self.assertEqual(self.call("calc_read", document=doc, sheet=0, range="A1:B4")["data"][-1], ["B", 3.0])

    def test_drawing_groups_layers_masters_page_changes_and_export(self):
        doc = self.new("draw")
        self.call("presentation_shape", document=doc, page=0, kind="rectangle", text="First")
        self.call("presentation_shape", document=doc, page=0, kind="ellipse", text="Second", x=13000)
        group = self.call("presentation_group", document=doc, page=0, indexes=[0, 1])
        self.assertIn("$ref", group)
        self.assertEqual(len(self.call("presentation_read", document=doc, page=0)["shapes"]), 1)
        self.call("presentation_group", document=doc, page=0, indexes=[0], ungroup=True)
        self.call("presentation_shape_edit", document=doc, page=0, index=0, text="Edited", properties={"FillColor": 0x336699})
        self.assertIn("Edited", str(self.call("presentation_read", document=doc, page=0)))
        self.call("presentation_layers", document=doc, action="add", properties={"Name": "RAJ Layer", "IsVisible": True})
        self.assertIn("RAJ Layer", [x["name"] for x in self.call("presentation_layers", document=doc)])
        masters = self.call("presentation_masters", document=doc, action="add", index=1, name="RAJ Master")
        self.assertGreaterEqual(len(masters), 2)
        self.call("presentation_page_configure", document=doc, page=0, master=1, name="First Page", background={"FillColor": 0xFFFFFF})
        for extension in ["png", "svg"]:
            self.call("presentation_export", document=doc, page=0, path="page." + extension)
            self.assertGreater((self.root / ("page." + extension)).stat().st_size, 50)
        self.assertTrue((self.root / "page.png").read_bytes().startswith(b"\x89PNG"))
        self.call("presentation_pages", document=doc, action="add", index=1, name="Extra")
        self.call("presentation_pages", document=doc, action="remove", index=1)
        self.call("presentation_shape_edit", document=doc, page=0, index=1, remove=True)
        self.assertEqual(len(self.call("presentation_read", document=doc, page=0)["shapes"]), 1)
        self.call("document_save", document=doc, path="drawing.odg")

    def test_database_query_definitions_and_office_services(self):
        doc = self.new("base")
        self.assertEqual(self.call("base_configure", document=doc, properties={"URL": "sdbc:embedded:firebird"})["URL"], "sdbc:embedded:firebird")
        query = self.call("base_queries", document=doc, action="create", name="Report", sql="SELECT 1 FROM RDB$DATABASE")
        self.assertEqual(query[0]["name"], "Report")
        self.call("document_save", document=doc, path="queries.odb")
        self.call("document_close", document=doc)
        doc = self.call("document_open", path="queries.odb")["document"]
        self.assertIn("SELECT 1", self.call("base_queries", document=doc)[0]["sql"])
        self.call("base_queries", document=doc, action="update", name="Report", sql="SELECT 2 FROM RDB$DATABASE")
        self.assertEqual(self.call("base_queries", document=doc, action="remove", name="Report"), [])
        self.assertIsInstance(self.call("office_extensions"), list)
        config = self.call("office_configuration", node="/org.openoffice.Setup/Product")
        self.assertIn("ooName", config["values"])
        spelling = self.call("linguistic_check", word="LibreOffice")
        self.assertIn("available", spelling)
        writer = self.new("writer")
        self.assertFalse(self.call("document_print", document=writer)["submitted"])

    def test_ooxml_text_html_epub_and_encrypted_odf(self):
        for kind, extension, read_operation in [("writer", "docx", "writer_read"), ("calc", "xlsx", "calc_read"), ("impress", "pptx", "presentation_read")]:
            doc = self.new(kind)
            if kind == "writer":
                self.call("writer_insert", document=doc, text="Conversion sample")
            elif kind == "calc":
                self.call("calc_write", document=doc, sheet=0, range="A1", data=[["Conversion sample"]])
            else:
                self.call("presentation_shape", document=doc, page=0, text="Conversion sample")
            self.call("document_save", document=doc, path="sample." + extension)
            self.call("document_close", document=doc)
            doc = self.call("document_open", path="sample." + extension)["document"]
            args = {"document": doc}
            if kind == "calc":
                args.update(sheet=0, range="A1")
            elif kind == "impress":
                args["page"] = 0
            self.assertIn("Conversion sample", str(self.call(read_operation, **args)))
            if kind == "writer":
                for output in ["txt", "html", "epub"]:
                    self.call("document_save", document=doc, path="sample." + output)
                    self.assertGreater((self.root / ("sample." + output)).stat().st_size, 0)
                self.call("document_save", document=doc, path="encrypted.odt", options={"Password": "secret"})
                self.call("document_close", document=doc)
                locked = self.call("document_open", path="encrypted.odt", password="secret")["document"]
                self.assertIn("Conversion sample", self.call("writer_read", document=locked)["text"])


    def test_templates_form_controls_custom_shows_and_solver(self):
        writer = self.new("writer")
        self.call("writer_insert", document=writer, text="Template body")
        self.call("document_export", document=writer, path="template.odt", filter_name="writer8")
        copy = self.call("document_from_template", path="template.odt")["document"]
        self.assertIn("Template body", self.call("writer_read", document=copy)["text"])
        self.assertIsNone(self.call("document_info", document=copy)["path"])
        self.call("form_control", document=copy, kind="TextField", name="Input", properties={"Text": "Form text"})
        self.assertEqual(self.call("python_run", document=copy, code="result = document.DrawPage.Forms.getByName('RAJ Form').getByName('Input').Text")["result"], "Form text")
        self.call("writer_refresh", document=copy)
        self.call("document_save", document=copy, path="form.odt")
        self.call("document_close", document=copy)
        copy = self.call("document_open", path="form.odt")["document"]
        self.assertEqual(self.call("python_run", document=copy, code="result = document.DrawPage.Forms.getByName('RAJ Form').Count")["result"], 1)
        slides = self.new("impress")
        self.call("presentation_pages", document=slides, action="add", index=1)
        self.assertEqual(self.call("presentation_custom_shows", document=slides, action="create", name="Demo", indexes=[1, 0])[0]["slides"], 2)
        ordered = self.call("python_run", document=slides, code="show=document.getCustomPresentations().getByName('Demo'); result=[show.getByIndex(i).getName() for i in range(show.Count)]")["result"]
        pages = self.call("presentation_pages", document=slides)
        self.assertEqual(ordered, [pages[1]["name"], pages[0]["name"]])
        self.call("presentation_page_configure", document=slides, page=0, properties={"TransitionType": 1, "TransitionSubtype": 0, "TransitionDuration": 1.5})
        self.assertEqual(self.call("presentation_custom_shows", document=slides, action="remove", name="Demo"), [])
        calc = self.new("calc")
        self.call("calc_write", document=calc, sheet=0, range="A1", data=[[1]])
        self.call("calc_write", document=calc, sheet=0, range="B1", data=[["=A1*3"]], formulas=True)
        result = self.call("calc_solver", document=calc, sheet=0, objective="B1", variables=["A1"], constraints=[{"cell": "A1", "operator": "LESS_EQUAL", "value": 10}, {"cell": "A1", "operator": "GREATER_EQUAL", "value": 0}])
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["solution"][0], 10.0, places=4)

    def test_basic_script_invocation_and_mail_merge(self):
        doc = self.new("writer")
        self.call("python_run", document=doc, code="document.BasicLibraries.createLibrary('RAJTests'); document.BasicLibraries.getByName('RAJTests').insertByName('Module', 'Function Add(a, b)\\nAdd = a + b\\nEnd Function'.replace('\\n', chr(10))); result = True")
        result = self.call("script_run", document=doc, uri="vnd.sun.star.script:RAJTests.Module.Add?language=Basic&location=document", arguments=[2.0, 3.0])
        self.assertEqual(result[0], 5.0)
        database = self.new("base")
        self.call("base_configure", document=database, properties={"URL": "sdbc:embedded:firebird"})
        self.call("document_save", document=database, path="contacts.odb")
        connection = self.call("base_connect", document=database)["$ref"]
        self.call("base_query", connection=connection, sql='CREATE TABLE "contacts" ("name" VARCHAR(80))', write=True)
        self.call("base_transaction", connection=connection, action="begin")
        self.call("base_query", connection=connection, sql='INSERT INTO "contacts" VALUES (?)', parameters=["Alice"], write=True)
        self.call("base_transaction", connection=connection, action="commit")
        self.call("document_save", document=database)
        self.call("base_transaction", connection=connection, action="close")
        self.call("document_close", document=database)
        database = self.call("document_open", path="contacts.odb")["document"]
        verify = self.call("base_connect", document=database)["$ref"]
        self.assertEqual(self.call("base_query", connection=verify, sql='SELECT "name" FROM "contacts"')["rows"], [["Alice"]])
        self.call("base_transaction", connection=verify, action="close")
        self.call("writer_insert", document=doc, text="Hello ")
        self.call("writer_database_field", document=doc, database="contacts.odb", table="contacts", column="name")
        self.call("document_save", document=doc, path="letter.odt")
        merged = self.call("writer_mail_merge", template="letter.odt", database="contacts.odb", table="contacts", output_directory="merged")
        self.assertTrue(merged["files"])
        merged_doc = self.call("document_open", path=merged["files"][0])["document"]
        self.assertIn("Alice", self.call("writer_read", document=merged_doc)["text"])
