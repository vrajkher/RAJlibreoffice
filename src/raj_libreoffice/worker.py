"""Standalone PyUNO worker; intentionally uses only Python's standard library.

Run with LibreOffice's compatible Python, not the MCP server's virtualenv.
"""
from __future__ import annotations

import contextlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

# Permit direct execution without installing this package in the UNO interpreter.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from raj_libreoffice.config import Config, workspace_path
from raj_libreoffice.features import FeatureMethods, FEATURES


KINDS = {
    "writer": "swriter", "calc": "scalc", "impress": "simpress",
    "draw": "sdraw", "math": "smath", "base": "sdatabase",
}
FORMATS = {
    "writer": {"odt": "writer8", "docx": "Office Open XML Text",
               "pdf": "writer_pdf_Export", "txt": "Text", "html": "HTML (StarWriter)",
               "rtf": "Rich Text Format", "epub": "EPUB"},
    "calc": {"ods": "calc8", "xlsx": "Calc MS Excel 2007 XML",
             "pdf": "calc_pdf_Export", "csv": "Text - txt - csv (StarCalc)",
             "html": "HTML (StarCalc)"},
    "impress": {"odp": "impress8", "pptx": "Impress MS PowerPoint 2007 XML",
                "pdf": "impress_pdf_Export"},
    "draw": {"odg": "draw8", "pdf": "draw_pdf_Export"},
    "math": {"odf": "math8", "pdf": "math_pdf_Export"},
    "base": {"odb": "StarOffice XML (Base)"},
}


class Office(FeatureMethods):
    def __init__(self, config):
        self.config = Config(**{**config, "workspace": Path(config["workspace"]).resolve()})
        self.config.workspace.mkdir(parents=True, exist_ok=True)
        self.uno = None
        self.context = None
        self.desktop = None
        self.process = None
        self.profile = None
        self.objects = {}
        self.owners = {}
        self.documents = {}

    def connect(self):
        if self.context is not None:
            return
        try:
            import uno
        except ImportError as error:
            raise RuntimeError(
                "PyUNO unavailable. Install python3-uno and set RAJ_UNO_PYTHON "
                "to LibreOffice's matching Python interpreter."
            ) from error
        self.uno = uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local)
        connection = self.config.connection
        if not connection:
            pipe = "raj_" + uuid.uuid4().hex
            self.profile = tempfile.mkdtemp(prefix="raj-office-")
            connection = f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext"
            self.process = subprocess.Popen([
                self.config.soffice, "--headless", "--nologo", "--nodefault",
                "--nofirststartwizard", "--norestore",
                "-env:UserInstallation=" + Path(self.profile).as_uri(),
                f"--accept=pipe,name={pipe};urp;StarOffice.ServiceManager",
            ], stdout=sys.stderr, stderr=sys.stderr)
        elif not connection.startswith("uno:"):
            raise ValueError("RAJ_UNO_CONNECTION must be a UNO resolver URL")
        deadline = time.monotonic() + min(self.config.timeout, 30)
        last = None
        while time.monotonic() < deadline:
            try:
                self.context = resolver.resolve(connection)
                break
            except Exception as error:
                last = error
                if self.process and self.process.poll() is not None:
                    raise RuntimeError("LibreOffice exited while starting") from error
                time.sleep(0.1)
        if self.context is None:
            raise RuntimeError(f"Cannot connect to LibreOffice: {last}")
        self.desktop = self.service("com.sun.star.frame.Desktop")

    def service(self, name):
        return self.context.ServiceManager.createInstanceWithContext(name, self.context)

    def props(self, values):
        result = []
        for name, value in (values or {}).items():
            prop = self.uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            prop.Name, prop.Value = name, self.decode(value)
            result.append(prop)
        return tuple(result)

    def handle(self, obj, owner=None):
        key = "obj_" + uuid.uuid4().hex
        self.objects[key], self.owners[key] = obj, owner
        return {"$ref": key}

    def ref(self, key):
        if isinstance(key, dict):
            key = key["$ref"]
        if key not in self.objects:
            raise ValueError("Unknown or expired handle; reopen or rediscover the object")
        return self.objects[key]

    def encode(self, value, owner=None, depth=0):
        if depth > 12:
            raise ValueError("UNO result nesting exceeds 12 levels")
        if value is None or isinstance(value, (str, bool, int)):
            if isinstance(value, str) and len(value) > self.config.max_text:
                raise ValueError("Result exceeds text limit; read a smaller range")
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else {"nonfinite": str(value)}
        if isinstance(value, (tuple, list)):
            if len(value) > self.config.max_cells:
                raise ValueError("Result exceeds sequence limit")
            return [self.encode(x, owner, depth + 1) for x in value]
        if isinstance(value, dict):
            return {str(k): self.encode(v, owner, depth + 1) for k, v in value.items()}
        if isinstance(value, self.uno.Enum):
            return {"$enum": value.typeName, "value": value.value}
        if isinstance(value, self.uno.Type):
            return {"$type": value.typeName}
        if isinstance(value, self.uno.ByteSequence):
            import base64
            return {"$bytes": base64.b64encode(value.value).decode("ascii")}
        if hasattr(value, "__pyunostruct__"):
            type_name = value.__class__.__pyunostruct__
            description = self.context.getValueByName(
                "/singletons/com.sun.star.reflection.theTypeDescriptionManager").getByHierarchicalName(
                    type_name)
            names = list(description.getMemberNames())
            base = description.getBaseType()
            while base:
                names = list(base.getMemberNames()) + names
                base = base.getBaseType()
            return {"$struct": type_name, "fields": {
                n: self.encode(getattr(value, n), owner, depth + 1) for n in names}}
        return self.handle(value, owner)

    def decode(self, value):
        if isinstance(value, list):
            return tuple(self.decode(x) for x in value)
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            return self.ref(value)
        if "$enum" in value:
            return self.uno.Enum(value["$enum"], value["value"])
        if "$type" in value:
            return self.uno.getTypeByName(value["$type"])
        if "$any" in value:
            return self.uno.Any(value["$any"], self.decode(value["value"]))
        if "$bytes" in value:
            import base64
            return self.uno.ByteSequence(base64.b64decode(value["$bytes"], validate=True))
        if "$struct" in value:
            struct = self.uno.createUnoStruct(value["$struct"])
            for key, val in value.get("fields", {}).items():
                setattr(struct, key, self.decode(val))
            return struct
        if "$properties" in value:
            return self.uno.Any("[]com.sun.star.beans.PropertyValue", self.props(value["$properties"]))
        raise ValueError("UNO dictionaries need $struct, $properties, $any, $enum or $ref")

    def doc(self, document, kind=None):
        if document not in self.documents:
            raise ValueError("Unknown document handle")
        if kind and self.documents[document]["kind"] not in kind.split(","):
            raise ValueError(f"This operation requires {kind}")
        return self.ref(document)

    def register(self, doc, kind, path=None):
        if doc is None:
            raise RuntimeError("LibreOffice did not load the document; check format or password")
        key = self.handle(doc)["$ref"]
        self.owners[key] = key
        self.documents[key] = {"document": key, "kind": kind, "path": path}
        return dict(self.documents[key])

    def kind(self, doc):
        services = {"writer": "text.TextDocument", "calc": "sheet.SpreadsheetDocument",
                    "impress": "presentation.PresentationDocument", "draw": "drawing.DrawingDocument",
                    "math": "formula.FormulaProperties", "base": "sdb.OfficeDatabaseDocument"}
        for kind, service in services.items():
            if doc.supportsService("com.sun.star." + service):
                return kind
        return "unknown"

    def path(self, value, exists=False):
        return workspace_path(self.config.workspace, value, exists=exists)

    def status(self):
        return {"connected": self.context is not None, "workspace": str(self.config.workspace),
                "documents": list(self.documents.values()), "advanced": self.config.advanced,
                "scripts": self.config.scripts, "python_execution": self.config.python_execution}

    def document_create(self, kind):
        if kind not in KINDS:
            raise ValueError("kind must be writer, calc, impress, draw, math or base")
        return self.register(self.desktop.loadComponentFromURL(
            "private:factory/" + KINDS[kind], "_blank", 0,
            self.props({"Hidden": True, "MacroExecutionMode": self.uno.getConstantByName(
                "com.sun.star.document.MacroExecMode.NEVER_EXECUTE"), "UpdateDocMode": 0})), kind)

    def document_open(self, path, read_only=False, password=None):
        file = self.path(path, True)
        props = {"Hidden": True, "ReadOnly": read_only, "MacroExecutionMode": self.uno.getConstantByName(
                 "com.sun.star.document.MacroExecMode.NEVER_EXECUTE"),
                 "UpdateDocMode": 0}
        if password:
            props["Password"] = password
        doc = self.desktop.loadComponentFromURL(file.as_uri(), "_blank", 0, self.props(props))
        return self.register(doc, self.kind(doc) if doc else "unknown", str(file))

    def document_list(self):
        return list(self.documents.values())

    def document_info(self, document):
        doc = self.doc(document)
        return {**self.documents[document], "modified": bool(doc.isModified()),
                "read_only": bool(doc.isReadonly()),
                "services": list(doc.getSupportedServiceNames())}

    def document_save(self, document, path=None, format=None, overwrite=False, options=None,
                      export=False):
        doc = self.doc(document)
        if doc.isReadonly():
            raise ValueError("Document is read-only")
        if not path:
            if export or format or options:
                raise ValueError("Specify an output path when exporting or selecting a format")
            if not doc.hasLocation():
                raise ValueError("New documents require a path for the first save")
            doc.store()
            return {"saved": True, "path": self.documents[document]["path"]}
        target = self.path(path)
        if target.exists() and not overwrite:
            raise FileExistsError("Output exists; set overwrite=true to replace it")
        target.parent.mkdir(parents=True, exist_ok=True)
        extension = (format or target.suffix.lstrip(".")).lower()
        kind = self.documents[document]["kind"]
        name = FORMATS.get(kind, {}).get(extension)
        if not name:
            raise ValueError("Unsupported convenience format; use filter_list and explicit UNO export")
        props = {"FilterName": name, "Overwrite": overwrite}
        if options:
            allowed = {"FilterData", "FilterOptions", "Password", "Selection"}
            if set(options) - allowed:
                raise ValueError("Unsupported export options")
            props.update(options)
        # Export formats must not become the editable document's storage location.
        native = {"writer": "odt", "calc": "ods", "impress": "odp", "draw": "odg",
                  "math": "odf", "base": "odb"}
        export = export or extension in {"pdf", "csv", "txt", "html", "epub"}
        if export:
            doc.storeToURL(target.as_uri(), self.props(props))
        else:
            doc.storeAsURL(target.as_uri(), self.props(props))
            self.documents[document]["path"] = str(target)
        return {"saved": True, "exported": export, "path": str(target),
                "format": extension, "native": extension == native.get(kind)}

    def document_close(self, document, discard=False):
        doc = self.doc(document)
        if doc.isModified() and not discard:
            raise ValueError("Document has unsaved changes; save or set discard=true")
        doc.close(True)
        for key in [k for k, owner in self.owners.items() if owner == document]:
            self.objects.pop(key, None)
            self.owners.pop(key, None)
        self.documents.pop(document)
        return {"closed": True}

    def document_metadata(self, document, values=None):
        metadata = self.doc(document).getDocumentProperties()
        names = {"Title", "Subject", "Description", "Author", "Keywords", "Language"}
        for name, value in (values or {}).items():
            if name not in names:
                raise ValueError(f"Unsupported metadata field: {name}")
            setattr(metadata, name, self.decode(value))
        return {n: self.encode(getattr(metadata, n), document) for n in sorted(names)}

    def document_undo(self, document, redo=False):
        manager = self.doc(document).getUndoManager()
        if redo:
            manager.redo()
        else:
            manager.undo()
        return {"undo_available": manager.isUndoPossible(), "redo_available": manager.isRedoPossible()}

    def filter_list(self, query=""):
        factory = self.service("com.sun.star.document.FilterFactory")
        return [name for name in factory.getElementNames() if query.lower() in name.lower()]

    def writer_read(self, document, start=0, length=10000):
        text = self.doc(document, "writer").getText().getString()
        if start < 0 or length < 0 or length > self.config.max_text:
            raise ValueError("Invalid start or length")
        return {"text": text[start:start + length], "total_characters": len(text),
                "has_more": start + length < len(text)}

    def cursor(self, document, start, length=0):
        text = self.doc(document, "writer").getText()
        if start < 0 or length < 0 or start + length > len(text.getString()):
            raise ValueError("Text selection is outside the document")
        cursor = text.createTextCursor()
        # goRight takes an IDL short; chunk large offsets.
        for offset, select in [(start, False), (length, True)]:
            while offset:
                step = min(offset, 32767)
                if not cursor.goRight(step, select):
                    raise ValueError("Cannot move cursor to requested position")
                offset -= step
        return cursor

    def writer_insert(self, document, text, position=None, properties=None):
        doc = self.doc(document, "writer")
        if len(text) > self.config.max_text:
            raise ValueError("Text exceeds configured limit")
        cursor = self.cursor(document, len(doc.Text.String) if position is None else position)
        self.set_properties(cursor, properties)
        doc.Text.insertString(cursor, text, False)
        return {"inserted_characters": len(text)}

    def writer_replace(self, document, search, replacement, regex=False, case_sensitive=False):
        if not search:
            raise ValueError("Search cannot be empty")
        doc = self.doc(document, "writer")
        descriptor = doc.createReplaceDescriptor()
        descriptor.SearchString, descriptor.ReplaceString = search, replacement
        descriptor.SearchRegularExpression = regex
        descriptor.SearchCaseSensitive = case_sensitive
        return {"replacements": doc.replaceAll(descriptor)}

    def set_properties(self, obj, properties):
        for name, value in (properties or {}).items():
            self.uno.invoke(obj, "setPropertyValue", (name, self.decode(value)))

    def writer_format(self, document, start, length, properties):
        self.set_properties(self.cursor(document, start, length), properties)
        return {"formatted": True}

    def writer_table(self, document, data, position=None, name=None):
        if not data or not data[0] or any(len(row) != len(data[0]) for row in data):
            raise ValueError("Table data must be a nonempty rectangular array")
        if len(data) * len(data[0]) > self.config.max_cells:
            raise ValueError("Table exceeds cell limit")
        doc = self.doc(document, "writer")
        table = doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(len(data), len(data[0]))
        cursor = self.cursor(document, len(doc.Text.String) if position is None else position)
        doc.Text.insertTextContent(cursor, table, False)
        if name:
            table.setName(name)
        for row, values in enumerate(data):
            for col, value in enumerate(values):
                table.getCellByPosition(col, row).setString(str(value))
        return self.handle(table, document)

    def writer_bookmark(self, document, name, position):
        doc = self.doc(document, "writer")
        bookmark = doc.createInstance("com.sun.star.text.Bookmark")
        bookmark.setName(name)
        doc.Text.insertTextContent(self.cursor(document, position), bookmark, False)
        return self.handle(bookmark, document)

    def writer_field(self, document, service, position=None, properties=None):
        if not service.startswith("com.sun.star.text.TextField."):
            raise ValueError("Use a com.sun.star.text.TextField.* service")
        doc = self.doc(document, "writer")
        field = doc.createInstance(service)
        self.set_properties(field, properties)
        doc.Text.insertTextContent(self.cursor(
            document, len(doc.Text.String) if position is None else position), field, False)
        return self.handle(field, document)

    def writer_image(self, document, path, width=5000, height=5000, position=None):
        self.dimensions(width, height)
        doc = self.doc(document, "writer")
        image = doc.createInstance("com.sun.star.text.TextGraphicObject")
        image.Graphic = self.service("com.sun.star.graphic.GraphicProvider").queryGraphic(
            self.props({"URL": self.path(path, True).as_uri()}))
        if image.Graphic is None:
            raise ValueError("LibreOffice could not decode this image")
        image.Width, image.Height = width, height
        image.AnchorType = self.uno.Enum("com.sun.star.text.TextContentAnchorType", "AS_CHARACTER")
        doc.Text.insertTextContent(self.cursor(
            document, len(doc.Text.String) if position is None else position), image, False)
        return self.handle(image, document)

    def style_list(self, document, family=None):
        families = self.doc(document).getStyleFamilies()
        if family:
            return list(families.getByName(family).getElementNames())
        return list(families.getElementNames())

    def style_update(self, document, family, name, properties):
        style = self.doc(document).getStyleFamilies().getByName(family).getByName(name)
        self.set_properties(style, properties)
        return self.handle(style, document)

    def sheet(self, document, sheet):
        sheets = self.doc(document, "calc").getSheets()
        return sheets.getByIndex(sheet) if isinstance(sheet, int) else sheets.getByName(sheet)

    def calc_sheets(self, document, action="list", name=None, index=0, new_name=None):
        sheets = self.doc(document, "calc").getSheets()
        if action == "add":
            sheets.insertNewByName(name, index)
        elif action == "remove":
            sheets.removeByName(name)
        elif action == "rename":
            sheets.getByName(name).setName(new_name)
        elif action == "move":
            sheets.moveByName(name, index)
        elif action == "copy":
            sheets.copyByName(name, new_name, index)
        elif action != "list":
            raise ValueError("Unknown sheet action")
        return list(sheets.getElementNames())

    def cell_range(self, document, sheet, range):
        cells = self.sheet(document, sheet).getCellRangeByName(range)
        address = cells.getRangeAddress()
        count = (address.EndColumn - address.StartColumn + 1) * (
            address.EndRow - address.StartRow + 1)
        if count > self.config.max_cells:
            raise ValueError("Range exceeds cell limit; split into smaller ranges")
        return cells, address

    def calc_read(self, document, sheet, range, formulas=False):
        cells, _ = self.cell_range(document, sheet, range)
        return {"data": self.encode(cells.getFormulaArray() if formulas else cells.getDataArray(),
                                    document)}

    def calc_write(self, document, sheet, range, data, formulas=False):
        cells, address = self.cell_range(document, sheet, range)
        rows, cols = address.EndRow - address.StartRow + 1, address.EndColumn - address.StartColumn + 1
        if len(data) != rows or any(len(row) != cols for row in data):
            raise ValueError(f"Data must have exactly {rows} rows and {cols} columns")
        if formulas:
            if any(not isinstance(x, str) for row in data for x in row):
                raise ValueError("Formula arrays must contain strings")
            cells.setFormulaArray(tuple(tuple(row) for row in data))
        else:
            if any(isinstance(x, bool) or not isinstance(x, (str, int, float))
                   for row in data for x in row):
                raise ValueError("Data values must be strings or numbers; use empty string for blank")
            cells.setDataArray(tuple(tuple(row) for row in data))
        return {"written_cells": rows * cols}

    def calc_format(self, document, sheet, range, properties=None, number_format=None):
        cells, _ = self.cell_range(document, sheet, range)
        if number_format:
            doc = self.doc(document, "calc")
            locale = self.uno.createUnoStruct("com.sun.star.lang.Locale")
            locale.Language, locale.Country = "en", "US"
            formats = doc.getNumberFormats()
            key = formats.queryKey(number_format, locale, True)
            if key == -1:
                key = formats.addNew(number_format, locale)
            cells.NumberFormat = key
        self.set_properties(cells, properties)
        return {"formatted": True}

    def calc_merge(self, document, sheet, range, merge=True):
        cells, _ = self.cell_range(document, sheet, range)
        cells.merge(merge)
        return {"merged": merge}

    def calc_clear(self, document, sheet, range, flags=1023):
        cells, _ = self.cell_range(document, sheet, range)
        cells.clearContents(flags)
        return {"cleared": True}

    def calc_recalculate(self, document):
        self.doc(document, "calc").calculateAll()
        return {"recalculated": True}

    def calc_chart(self, document, sheet, range, name, x=1000, y=1000, width=12000, height=8000):
        self.dimensions(width, height)
        _, address = self.cell_range(document, sheet, range)
        charts = self.sheet(document, sheet).getCharts()
        rectangle = self.uno.createUnoStruct("com.sun.star.awt.Rectangle")
        rectangle.X, rectangle.Y, rectangle.Width, rectangle.Height = x, y, width, height
        charts.addNewByName(name, rectangle, (address,), True, True)
        return self.handle(charts.getByName(name).getEmbeddedObject(), document)

    def calc_named_range(self, document, name, content, sheet=0, column=0, row=0):
        doc = self.doc(document, "calc")
        address = self.uno.createUnoStruct("com.sun.star.table.CellAddress")
        address.Sheet, address.Column, address.Row = sheet, column, row
        doc.getPropertyValue("NamedRanges").addNewByName(name, content, address, 0)
        return {"created": name}

    def calc_sort(self, document, sheet, range, column=0, ascending=True, header=False):
        cells, address = self.cell_range(document, sheet, range)
        if column < 0 or column > address.EndColumn - address.StartColumn:
            raise ValueError("Sort column is a zero-based offset inside the range")
        field = self.uno.createUnoStruct("com.sun.star.table.TableSortField")
        field.Field, field.IsAscending = column, ascending
        descriptor = {p.Name: p.Value for p in cells.createSortDescriptor()}
        # PropertyValue.Value is Any: a plain tuple becomes []any and is silently
        # ignored by Calc's sort parser. Supply the exact sequence type.
        descriptor.update({"SortFields": self.uno.Any(
            "[]com.sun.star.table.TableSortField", (field,)),
            "ContainsHeader": header, "IsSortColumns": False})
        # Already-native structs must bypass JSON decoding.
        props = []
        for name, value in descriptor.items():
            prop = self.uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            prop.Name, prop.Value = name, value
            props.append(prop)
        cells.sort(tuple(props))
        return {"sorted": True}

    def page(self, document, index):
        pages = self.doc(document, "impress,draw").getDrawPages()
        if index < 0 or index >= pages.getCount():
            raise ValueError("Page index is out of bounds")
        return pages.getByIndex(index)

    def presentation_pages(self, document, action="list", index=0, name=None):
        pages = self.doc(document, "impress,draw").getDrawPages()
        if action == "add":
            page = pages.insertNewByIndex(index)
            if name:
                page.setName(name)
        elif action == "remove":
            pages.remove(self.page(document, index))
        elif action != "list":
            raise ValueError("action must be list, add or remove")
        return [{"index": i, "name": pages.getByIndex(i).getName(),
                 "shapes": pages.getByIndex(i).getCount()} for i in range(pages.getCount())]

    @staticmethod
    def dimensions(width, height):
        if width <= 0 or height <= 0:
            raise ValueError("Width and height must be positive, in 1/100 millimetres")

    def presentation_shape(self, document, page, kind="text", text="", x=1000, y=1000,
                           width=10000, height=3000, properties=None, image_path=None):
        self.dimensions(width, height)
        names = {"text": "TextShape", "rectangle": "RectangleShape", "ellipse": "EllipseShape",
                 "line": "LineShape", "image": "GraphicObjectShape", "connector": "ConnectorShape",
                 "polygon": "PolyPolygonShape", "polyline": "PolyLineShape",
                 "bezier": "ClosedBezierShape", "custom": "CustomShape", "ole": "OLE2Shape"}
        if kind not in names:
            raise ValueError("Unknown shape kind")
        if kind == "image" and not image_path:
            raise ValueError("Image shapes require image_path")
        if image_path and kind != "image":
            raise ValueError("image_path is only supported for image shapes")
        graphic = None
        if image_path:
            graphic = self.service("com.sun.star.graphic.GraphicProvider").queryGraphic(
                self.props({"URL": self.path(image_path, True).as_uri()}))
            if graphic is None:
                raise ValueError("LibreOffice could not decode this image")
        doc = self.doc(document, "impress,draw")
        shape = doc.createInstance("com.sun.star.drawing." + names[kind])
        position = self.uno.createUnoStruct("com.sun.star.awt.Point")
        position.X, position.Y = x, y
        size = self.uno.createUnoStruct("com.sun.star.awt.Size")
        size.Width, size.Height = width, height
        shape.setPosition(position)
        shape.setSize(size)
        self.page(document, page).add(shape)
        if text:
            shape.setString(text)
        if image_path:
            shape.Graphic = graphic
        self.set_properties(shape, properties)
        return self.handle(shape, document)

    def presentation_read(self, document, page):
        page_obj = self.page(document, page)
        shapes = []
        for i in range(page_obj.getCount()):
            shape = page_obj.getByIndex(i)
            shapes.append({"index": i, "type": shape.getShapeType(),
                           "text": shape.getString() if hasattr(shape, "getString") else "",
                           "object": self.handle(shape, document)})
        return {"shapes": shapes}

    def presentation_notes(self, document, page, text=None):
        notes = self.page(document, page).getNotesPage()
        for i in range(notes.getCount()):
            shape = notes.getByIndex(i)
            if shape.getShapeType() == "com.sun.star.presentation.NotesShape":
                if text is not None:
                    shape.setString(text)
                return {"text": shape.getString(), "object": self.handle(shape, document)}
        if text is None:
            return {"text": ""}
        shape = self.doc(document, "impress").createInstance("com.sun.star.presentation.NotesShape")
        notes.add(shape)
        size = self.uno.createUnoStruct("com.sun.star.awt.Size")
        size.Width, size.Height = 15000, 10000
        shape.setSize(size)
        shape.setString(text)
        return {"text": shape.getString(), "object": self.handle(shape, document)}

    def math_formula(self, document, formula=None):
        doc = self.doc(document, "math")
        if formula is not None:
            doc.setPropertyValue("Formula", formula)
        return {"formula": doc.getPropertyValue("Formula")}

    def base_connect(self, document, user="", password="", read_only=False):
        # Shared Base connections disallow transaction/read-only state changes.
        connection = self.doc(document, "base").DataSource.getIsolatedConnection(user, password)
        if read_only:
            connection.setReadOnly(True)
        return self.handle(connection, document)

    def base_tables(self, connection):
        tables = self.ref(connection).getTables()
        if hasattr(tables, "refresh"):
            tables.refresh()
        return list(tables.getElementNames())

    def base_query(self, connection, sql, parameters=None, limit=1000, write=False):
        if not 1 <= limit <= 10000:
            raise ValueError("limit must be between 1 and 10000")
        conn = self.ref(connection)
        if write and conn.isReadOnly():
            raise ValueError("The database connection is read-only")
        statement = None
        result = None
        try:
            # Never toggle connection state inside a transaction: some drivers
            # restart/commit transactions on setReadOnly. Request that at connect.
            statement = conn.prepareStatement(sql)
            statement.setPropertyValue("MaxRows", limit + 1)
            for i, value in enumerate(parameters or [], 1):
                if isinstance(value, dict):
                    setters = {"boolean": "setBoolean", "byte": "setByte", "short": "setShort",
                               "int": "setInt", "bigint": "setLong", "float": "setFloat",
                               "double": "setDouble", "string": "setString", "date": "setDate",
                               "time": "setTime", "timestamp": "setTimestamp", "bytes": "setBytes"}
                    kind = value.get("type")
                    if kind not in setters or "value" not in value:
                        raise ValueError("Typed SQL parameters need a supported type and value")
                    self.uno.invoke(statement, setters[kind], (i, self.decode(value["value"])))
                elif value is None:
                    statement.setNull(i, 0)
                elif isinstance(value, bool):
                    statement.setBoolean(i, value)
                elif isinstance(value, int):
                    if -(2 ** 31) <= value < 2 ** 31:
                        statement.setInt(i, value)
                    else:
                        statement.setLong(i, value)
                elif isinstance(value, float):
                    statement.setDouble(i, value)
                elif isinstance(value, str):
                    statement.setString(i, value)
                else:
                    raise ValueError("SQL parameters must be scalars or typed parameter objects")
            if write:
                return {"updated_rows": statement.executeUpdate()}
            result = statement.executeQuery()
            metadata = result.getMetaData()
            columns = [metadata.getColumnLabel(i) for i in range(1, metadata.getColumnCount() + 1)]
            rows = []
            while len(rows) < limit and result.next():
                row = []
                for i in range(1, len(columns) + 1):
                    value = result.getString(i)
                    row.append(None if result.wasNull() else value)
                rows.append(row)
            # Firebird rejects another fetch after EOF; probe only when the
            # row limit stopped the loop before it reached EOF.
            has_more = len(rows) == limit and result.next()
            return {"columns": columns, "rows": rows, "has_more": has_more}
        finally:
            if result:
                result.close()
            if statement:
                statement.close()

    def base_transaction(self, connection, action):
        conn = self.ref(connection)
        if action == "begin":
            conn.setAutoCommit(False)
        elif action == "commit":
            conn.commit()
        elif action == "rollback":
            conn.rollback()
        elif action == "autocommit":
            conn.setAutoCommit(True)
        elif action == "close":
            conn.close()
        else:
            raise ValueError("action must be begin, commit, rollback, autocommit or close")
        return {"action": action}

    def require_advanced(self):
        if not self.config.advanced:
            raise PermissionError("Set RAJ_ALLOW_ADVANCED=1 for unrestricted UNO automation")

    def uno_inspect(self, object, query=""):
        obj = self.ref(object)
        services = list(obj.getSupportedServiceNames()) if hasattr(obj, "getSupportedServiceNames") else []
        properties = []
        if hasattr(obj, "getPropertySetInfo"):
            info = obj.getPropertySetInfo()
            if info:
                properties = [{"name": p.Name, "type": p.Type.typeName, "attributes": p.Attributes}
                              for p in info.getProperties() if query.lower() in p.Name.lower()]
        introspection = self.service("com.sun.star.beans.Introspection").inspect(obj)
        methods = []
        if introspection:
            for method in introspection.getMethods(65535):
                if query.lower() in method.getName().lower():
                    methods.append({"name": method.getName(), "return_type": method.getReturnType().getName(),
                                    "parameters": [{"name": p.aName, "type": p.aType.getName(),
                                                    "mode": str(p.aMode)}
                                                   for p in method.getParameterInfos()]})
        return {"services": services, "properties": properties, "methods": methods}

    def uno_get(self, object, name):
        # Property getters can return arbitrary live UNO objects. Treat as advanced.
        self.require_advanced()
        obj = self.ref(object)
        value = obj.getPropertyValue(name) if hasattr(obj, "getPropertyValue") else getattr(obj, name)
        return self.encode(value, self.owners.get(object))

    def uno_set(self, object, properties):
        self.require_advanced()
        obj = self.ref(object)
        for name, value in properties.items():
            if hasattr(obj, "setPropertyValue"):
                self.uno.invoke(obj, "setPropertyValue", (name, self.decode(value)))
            else:
                setattr(obj, name, self.decode(value))
        return {"updated": list(properties)}

    def uno_call(self, object, method, arguments=None):
        self.require_advanced()
        if method.startswith("_"):
            raise ValueError("Only public UNO methods are supported")
        result = self.uno.invoke(self.ref(object), method, tuple(
            self.decode(x) for x in (arguments or [])))
        return self.encode(result, self.owners.get(object))

    def uno_service(self, service, document=None, arguments=None):
        self.require_advanced()
        args = tuple(self.decode(x) for x in arguments or [])
        if document:
            doc = self.doc(document)
            obj = self.uno.invoke(doc, "createInstanceWithArguments", (service, args)) if args else doc.createInstance(service)
        else:
            obj = self.uno.invoke(self.context.ServiceManager, "createInstanceWithArgumentsAndContext",
                                  (service, args, self.context)) if args else self.service(service)
        if obj is None:
            raise ValueError("Service is unavailable in this LibreOffice installation")
        return self.handle(obj, document)

    def uno_services(self, query=""):
        return [s for s in self.context.ServiceManager.getAvailableServiceNames()
                if query.lower() in s.lower()]

    def uno_type(self, name):
        manager = self.context.getValueByName(
            "/singletons/com.sun.star.reflection.theTypeDescriptionManager")
        description = manager.getByHierarchicalName(name)
        result = {"name": description.getName(), "class": str(description.getTypeClass())}
        for method, label in [("getMemberNames", "members"), ("getEnumNames", "enum_names"),
                              ("getEnumValues", "enum_values")]:
            if hasattr(description, method):
                result[label] = list(getattr(description, method)())
        result["object"] = self.handle(description)
        return result

    def uno_dispatch(self, document, command, properties=None):
        self.require_advanced()
        if not command.startswith(".uno:"):
            raise ValueError("Use a .uno: dispatch command")
        frame = self.doc(document).getCurrentController().getFrame()
        result = self.service("com.sun.star.frame.DispatchHelper").executeDispatch(
            frame, command, "", 0, self.props(properties))
        return self.encode(result, document)

    def script_run(self, document, uri, arguments=None):
        self.require_advanced()
        if not self.config.scripts:
            raise PermissionError("Set RAJ_ALLOW_SCRIPTS=1 to invoke trusted installed scripts")
        if not uri.startswith("vnd.sun.star.script:"):
            raise ValueError("Use a vnd.sun.star.script: URI")
        script = self.doc(document).getScriptProvider().getScript(uri)
        return self.encode(script.invoke(tuple(self.decode(x) for x in arguments or []), (), ()), document)

    def python_run(self, code, document=None):
        self.require_advanced()
        if not self.config.python_execution:
            raise PermissionError("Set RAJ_ALLOW_PYTHON=1 to execute trusted Python automation")
        # This is deliberately NOT a sandbox. Standard I/O is redirected so user
        # print statements cannot corrupt the JSON worker protocol.
        import io
        output = io.StringIO()
        scope = {"uno": self.uno, "context": self.context, "desktop": self.desktop,
                 "document": self.doc(document) if document else None, "result": None}
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            exec(compile(code, "<raj-python>", "exec"), scope, scope)
        return {"result": self.encode(scope["result"], document),
                "stdout": output.getvalue()[:self.config.max_text]}

    def handles_release(self, handles):
        for handle in handles:
            if handle in self.documents:
                raise ValueError("Close documents using document_close")
        for handle in handles:
            self.objects.pop(handle, None)
            self.owners.pop(handle, None)
        return {"released": len(handles)}

    def shutdown(self):
        # An attached external office belongs to the user and is never terminated.
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.profile:
            shutil.rmtree(self.profile, ignore_errors=True)
        self.process = None
        self.profile = None


OPERATIONS = {
    name for name in (
        "status document_create document_open document_list document_info document_save "
        "document_close document_metadata document_undo filter_list writer_read writer_insert "
        "writer_replace writer_format writer_table writer_bookmark writer_field writer_image "
        "style_list style_update calc_sheets calc_read calc_write calc_format calc_merge calc_clear "
        "calc_recalculate calc_chart calc_named_range calc_sort presentation_pages presentation_shape "
        "presentation_read presentation_notes math_formula base_connect base_tables base_query "
        "base_transaction uno_inspect uno_get uno_set uno_call uno_service uno_services uno_type "
        "uno_dispatch script_run python_run handles_release"
    ).split()
}

OPERATIONS.update(FEATURES)


def main():
    office = None
    try:
        for line in sys.stdin:
            request = {}
            try:
                request = json.loads(line)
                if office is None:
                    office = Office(request["config"])
                operation = request["operation"]
                if operation not in OPERATIONS:
                    raise ValueError("Unknown operation")
                if operation != "status":
                    office.connect()
                result = getattr(office, operation)(**request.get("arguments", {}))
                response = {"id": request["id"], "result": result}
            except Exception as error:
                if office and office.context is None:
                    office.shutdown()
                response = {"id": request.get("id"), "error": {
                    "type": type(error).__name__, "message": str(error)}}
            print(json.dumps(response, allow_nan=False), flush=True)
    finally:
        if office:
            office.shutdown()


if __name__ == "__main__":
    main()
