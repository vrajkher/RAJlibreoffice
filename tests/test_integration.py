"""Real LibreOffice integration: executed in CI with python3-uno installed."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from raj_libreoffice.bridge import Bridge, OfficeError
from raj_libreoffice.config import Config


def pyuno_available():
    try:
        return subprocess.run([os.getenv("RAJ_UNO_PYTHON", "/usr/bin/python3"), "-c", "import uno"],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@unittest.skipUnless(pyuno_available(), "requires LibreOffice/PyUNO; CI installs both")
class LibreOfficeTests(unittest.TestCase):
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

    def test_writer_roundtrip_format_table_fields_metadata_and_pdf(self):
        doc = self.new("writer")
        self.call("writer_insert", document=doc, text="Hello LibreOffice\nSecond paragraph")
        self.call("writer_format", document=doc, start=0, length=5,
                  properties={"CharWeight": 150.0, "CharHeight": 18.0})
        self.assertEqual(self.call("writer_replace", document=doc, search="Hello", replacement="Hi")["replacements"], 1)
        self.call("writer_bookmark", document=doc, name="intro", position=0)
        table = self.call("writer_table", document=doc, data=[["Name", "Count"], ["UNO", 2]], name="Summary")
        self.assertIn("$ref", table)
        self.call("writer_field", document=doc, service="com.sun.star.text.TextField.PageNumber",
                  properties={"NumberingType": 4})
        self.call("document_metadata", document=doc, values={"Title": "Integration"})
        self.call("document_save", document=doc, path="report.odt")
        self.call("document_save", document=doc, path="report.pdf", export=True)
        self.assertTrue((self.root / "report.pdf").read_bytes().startswith(b"%PDF"))
        self.call("document_close", document=doc)
        reopened = self.call("document_open", path="report.odt")["document"]
        self.assertIn("Hi LibreOffice", self.call("writer_read", document=reopened)["text"])
        self.assertEqual(self.call("document_metadata", document=reopened)["Title"], "Integration")

    def test_calc_values_formulas_sort_named_range_chart_and_roundtrip(self):
        doc = self.new("calc")
        self.call("calc_write", document=doc, sheet=0, range="A1:B3",
                  data=[["Label", "Value"], ["B", 3], ["A", 2]])
        self.call("calc_sort", document=doc, sheet=0, range="A1:B3", header=True)
        self.assertEqual(self.call("calc_read", document=doc, sheet=0, range="A2:B2")["data"], [["A", 2.0]])
        self.call("calc_write", document=doc, sheet=0, range="C2:C2", data=[["=SUM(B2:B3)"]], formulas=True)
        self.call("calc_recalculate", document=doc)
        self.assertEqual(self.call("calc_read", document=doc, sheet=0, range="C2:C2")["data"], [[5.0]])
        self.call("calc_format", document=doc, sheet=0, range="B2:B3", number_format="0.00",
                  properties={"CellBackColor": 0xEEEEEE})
        self.call("calc_named_range", document=doc, name="Metrics", content="$Sheet1.$A$1:$B$3")
        self.assertIn("$ref", self.call("calc_chart", document=doc, sheet=0, range="A1:B3", name="Chart"))
        self.call("calc_sheets", document=doc, action="add", name="Extra", index=1)
        self.call("document_save", document=doc, path="book.ods")
        self.call("document_close", document=doc)
        reopened = self.call("document_open", path="book.ods")["document"]
        self.assertEqual(self.call("calc_read", document=reopened, sheet=0, range="C2:C2")["data"], [[5.0]])

    def test_impress_draw_math_and_typed_uno(self):
        for kind, extension in [("impress", "odp"), ("draw", "odg")]:
            doc = self.new(kind)
            shape = self.call("presentation_shape", document=doc, page=0, text="MCP powered",
                              properties={"CharHeight": 24.0})["$ref"]
            self.assertIn("MCP powered", str(self.call("presentation_read", document=doc, page=0)))
            self.call("uno_set", object=shape, properties={"CharColor": 0x112233})
            position = self.call("uno_call", object=shape, method="getPosition")
            self.assertEqual(position["$struct"], "com.sun.star.awt.Point")
            self.assertEqual(position["fields"]["X"], 1000)
            self.call("uno_call", object=shape, method="setPosition", arguments=[
                {"$struct": "com.sun.star.awt.Point", "fields": {"X": 2000, "Y": 3000}}])
            if kind == "impress":
                self.call("presentation_notes", document=doc, page=0, text="Speaker notes")
                self.assertEqual(self.call("presentation_notes", document=doc, page=0)["text"], "Speaker notes")
            self.call("document_save", document=doc, path="slides." + extension)
            self.call("document_close", document=doc)
        math = self.new("math")
        self.call("math_formula", document=math, formula="E = m c^2")
        self.assertIn("m", self.call("math_formula", document=math)["formula"])
        self.call("document_save", document=math, path="formula.odf")

    def test_base_connection_parameterized_sql_and_transactions(self):
        doc = self.new("base")
        data = self.call("uno_get", object=doc, name="DataSource")["$ref"]
        self.call("uno_set", object=data, properties={"URL": "sdbc:embedded:firebird"})
        self.call("document_save", document=doc, path="database.odb")
        conn = self.call("base_connect", document=doc)["$ref"]
        self.call("base_query", connection=conn, sql='CREATE TABLE "items" ("id" INTEGER, "name" VARCHAR(80))', write=True)
        self.call("base_transaction", connection=conn, action="begin")
        self.call("base_query", connection=conn, sql='INSERT INTO "items" VALUES (?, ?)',
                  parameters=[1, "UNO"], write=True)
        pending = self.call("base_query", connection=conn, sql='SELECT "name" FROM "items" WHERE "id" = ?',
                            parameters=[1])
        self.assertEqual(pending["rows"], [["UNO"]])
        self.call("base_transaction", connection=conn, action="commit")
        self.assertIn("items", self.call("base_tables", connection=conn))
        result = self.call("base_query", connection=conn, sql='SELECT "name" FROM "items" WHERE "id" = ?',
                           parameters=[1])
        self.assertEqual(result["rows"], [["UNO"]])
        self.call("base_query", connection=conn, sql='INSERT INTO "items" VALUES (?, ?)',
                  parameters=[2, "Rollback"], write=True)
        self.assertEqual(self.call("base_query", connection=conn,
                                  sql='SELECT "name" FROM "items" WHERE "id" = 2')["rows"], [["Rollback"]])
        self.call("base_transaction", connection=conn, action="rollback")
        self.assertEqual(self.call("base_query", connection=conn,
                                  sql='SELECT "name" FROM "items" WHERE "id" = 2')["rows"], [])
        self.call("base_transaction", connection=conn, action="close")
        self.call("document_save", document=doc)

    def test_discovery_python_and_handle_invalidation(self):
        doc = self.new("writer")
        self.assertTrue(self.call("uno_services", query="Introspection"))
        description = self.call("uno_type", name="com.sun.star.awt.Point")
        self.assertIn("X", description["members"])
        info = self.call("uno_inspect", object=doc, query="Text")
        self.assertTrue(info["methods"])
        result = self.call("python_run", document=doc,
                           code="print('automation'); document.Text.String = 'Python edit'; result = 42")
        self.assertEqual(result["result"], 42)
        self.assertIn("automation", result["stdout"])
        self.call("document_close", document=doc, discard=True)
        with self.assertRaises(OfficeError):
            self.call("uno_inspect", object=doc)

    def test_typed_any_values_metadata_images_styles_and_pdf_options(self):
        import struct
        import zlib
        image = self.root / "pixel.png"

        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

        image.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                          + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))
        doc = self.new("writer")
        self.call("writer_insert", document=doc, text="Styled document\n")
        self.assertIn("ParagraphStyles", self.call("style_list", document=doc))
        styles = self.call("style_list", document=doc, family="ParagraphStyles")
        self.call("style_update", document=doc, family="ParagraphStyles", name=styles[0],
                  properties={"CharHeight": 14.0})
        picture = self.call("writer_image", document=doc, path="pixel.png", width=1000, height=1000)["$ref"]
        graphic = self.call("uno_get", object=picture, name="Graphic")["$ref"]
        self.assertNotEqual(self.call("uno_call", object=graphic, method="getType"), 0)
        self.call("document_metadata", document=doc, values={
            "Keywords": ["MCP", "UNO"],
            "Language": {"$struct": "com.sun.star.lang.Locale", "fields": {"Language": "en", "Country": "US"}}})
        metadata = self.call("document_metadata", document=doc)
        self.assertEqual(metadata["Keywords"], ["MCP", "UNO"])
        self.assertEqual(metadata["Language"]["fields"]["Language"], "en")
        sheet_doc = self.new("calc")
        sheets = self.call("uno_call", object=sheet_doc, method="getSheets")["$ref"]
        sheet = self.call("uno_call", object=sheets, method="getByIndex", arguments=[0])["$ref"]
        cells = self.call("uno_call", object=sheet, method="getCellRangeByName", arguments=["A1:A1"])["$ref"]
        self.call("uno_set", object=cells, properties={"CellBackColor": {"$any": "long", "value": 0x112233}})
        self.assertEqual(self.call("uno_get", object=cells, name="CellBackColor"), 0x112233)
        self.call("document_save", document=doc, path="options.pdf", export=True,
                  options={"FilterData": {"$properties": {"PageRange": "1", "SelectPdfVersion": 2}}})
        self.assertTrue((self.root / "options.pdf").read_bytes().startswith(b"%PDF"))

    def test_overwrite_and_unsaved_close_protection(self):
        doc = self.new("writer")
        self.call("writer_insert", document=doc, text="Unsaved")
        with self.assertRaisesRegex(OfficeError, "unsaved"):
            self.call("document_close", document=doc)
        self.call("document_save", document=doc, path="file.odt")
        with self.assertRaisesRegex(OfficeError, "exists"):
            self.call("document_save", document=doc, path="file.odt")
        self.call("document_save", document=doc, path="file.odt", overwrite=True)


if __name__ == "__main__":
    unittest.main()

