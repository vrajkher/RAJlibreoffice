"""Convenience workflows over the public LibreOffice UNO API (stdlib only).

The standalone worker imports this module with the Office-compatible interpreter.
"""
from __future__ import annotations


FEATURES = {
    "writer_page": "Read or set a Writer page style, header and footer text. Default style is taken from the body cursor.",
    "writer_structure": "Insert a section, text frame, footnote, endnote or table of contents at a body position. Returns its object handle.",
    "writer_review": "Read or set tracked-change recording; list redlines; optionally add an annotation at a body position.",
    "style_create": "Create a named style in an existing style family, optionally deriving it from a parent style.",
    "calc_filter": "Apply a filter descriptor to a range. Fields use range-relative columns and UNO FilterOperator names.",
    "calc_pivot": "Create a DataPilot pivot from an A1 source range, with named row/column/data fields and an output cell.",
    "calc_validation": "Read or set data validation properties on a Calc range. Type and Operator accept enum names.",
    "calc_conditional": "Replace conditional formatting on a range using entries with Operator, Formula1/2 and StyleName.",
    "calc_annotation": "Read or replace a cell comment; optionally change its visibility.",
    "calc_protect": "Protect or unprotect a sheet with a password. Returns current protection state.",
    "calc_function": "Evaluate an installed Calc function by name and arguments using FunctionAccess, without creating cells.",
    "calc_array_formula": "Read or set a matrix/array formula on a Calc range.",
    "calc_goal_seek": "Find a variable-cell value that makes a formula cell reach a target. Returns a proposal without changing cells.",
    "calc_subtotals": "Apply or remove range subtotals. Group and subtotal column indexes are relative to the range.",
    "calc_chart_configure": "Set a chart's diagram service, titles, legend and diagram properties using its chart handle.",
    "presentation_page_configure": "Set page properties, background, master page or page name. Indexes are zero-based.",
    "presentation_masters": "List, add or remove Impress/Draw master pages. Use presentation_page_configure to assign one.",
    "presentation_shape_edit": "Update or remove a page shape by index, with text and UNO properties.",
    "presentation_group": "Group specified shape indexes, or ungroup one group shape. Returns the resulting group handle.",
    "presentation_layers": "List, add, remove or configure drawing layers, including visibility, printability and locking.",
    "presentation_export": "Export an Impress/Draw page to PNG, SVG, JPEG or PDF through GraphicExportFilter.",
    "base_configure": "Read or set Base DataSource connection properties. Driver availability and credentials depend on the host.",
    "base_queries": "List, create, update or remove stored Base query definitions; queries are not executed by this tool.",
    "document_print": "Read printer configuration or submit a print job with UNO options. submit=true requires a configured host printer.",
    "linguistic_check": "Check spelling or hyphenation with installed dictionaries; returns available locale information.",
    "office_extensions": "List installed LibreOffice extensions through PackageInformationProvider.",
    "office_configuration": "Read a bounded configuration node, or write existing properties with advanced mode enabled.",
}


class FeatureMethods:
    def writer_page(self, document, style=None, header=None, footer=None, properties=None):
        doc = self.doc(document, "writer")
        style = style or doc.Text.createTextCursor().PageStyleName
        obj = doc.getStyleFamilies().getByName("PageStyles").getByName(style)
        self.set_properties(obj, properties)
        for name, value in [("Header", header), ("Footer", footer)]:
            if value is not None:
                if len(value) > self.config.max_text:
                    raise ValueError("Header/footer exceeds text limit")
                obj.setPropertyValue(name + "IsOn", True)
                obj.getPropertyValue(name + "Text").setString(value)
        return {"style": style, "header": obj.HeaderText.String if obj.HeaderIsOn else None,
                "footer": obj.FooterText.String if obj.FooterIsOn else None,
                "object": self.handle(obj, document)}

    def writer_structure(self, document, kind, text="", position=None, name=None, properties=None):
        names = {"section": "TextSection", "frame": "TextFrame", "footnote": "Footnote",
                 "endnote": "Endnote", "toc": "ContentIndex"}
        if kind not in names:
            raise ValueError("kind must be section, frame, footnote, endnote or toc")
        if len(text) > self.config.max_text:
            raise ValueError("Text exceeds limit")
        doc = self.doc(document, "writer")
        obj = doc.createInstance("com.sun.star.text." + names[kind])
        if name:
            obj.setName(name)
        if kind == "frame":
            obj.Width, obj.Height = 10000, 3000
        self.set_properties(obj, properties)
        cursor = self.cursor(document, len(doc.Text.String) if position is None else position)
        doc.Text.insertTextContent(cursor, obj, False)
        if text:
            if kind == "section":
                anchor = obj.getAnchor()
                anchor.getText().insertString(anchor, text, False)
            elif kind in {"frame", "footnote", "endnote"}:
                obj.getText().setString(text)
            else:
                raise ValueError("TOC content is generated; set Title through properties")
        if kind == "toc":
            obj.update()
        return self.handle(obj, document)

    def writer_review(self, document, record=None, comment=None, author="", position=None, limit=100):
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        doc = self.doc(document, "writer")
        if record is not None:
            doc.RecordChanges = record
        annotation = None
        if comment is not None:
            annotation = self.writer_field(document, "com.sun.star.text.TextField.Annotation",
                                           position, {"Content": comment, "Author": author})
        redlines = doc.getRedlines()
        result = []
        for i in range(min(limit, redlines.getCount())):
            obj = redlines.getByIndex(i)
            result.append({"type": obj.RedlineType, "author": obj.RedlineAuthor,
                           "object": self.handle(obj, document)})
        return {"recording": doc.RecordChanges, "redlines": result,
                "total": redlines.getCount(), "annotation": annotation}

    def style_create(self, document, family, name, parent=None, properties=None):
        services = {"ParagraphStyles": "ParagraphStyle", "CharacterStyles": "CharacterStyle",
                    "PageStyles": "PageStyle", "FrameStyles": "FrameStyle",
                    "NumberingStyles": "NumberingStyle", "CellStyles": "CellStyle"}
        if family not in services:
            raise ValueError("Unsupported convenience style family; use generic UNO for others")
        doc = self.doc(document)
        styles = doc.getStyleFamilies().getByName(family)
        if styles.hasByName(name):
            raise ValueError("Style already exists")
        obj = doc.createInstance("com.sun.star.style." + services[family])
        styles.insertByName(name, obj)
        if parent:
            obj.setParentStyle(parent)
        self.set_properties(obj, properties)
        return self.handle(obj, document)

    def calc_filter(self, document, sheet, range, fields=None, header=True, properties=None):
        cells, address = self.cell_range(document, sheet, range)
        descriptor = cells.createFilterDescriptor(True)
        descriptor.ContainsHeader = header
        self.set_properties(descriptor, properties)
        items = []
        for spec in fields or []:
            index = spec.get("column", 0)
            if not 0 <= index <= address.EndColumn - address.StartColumn:
                raise ValueError("Filter column is outside the range")
            field = self.uno.createUnoStruct("com.sun.star.sheet.TableFilterField")
            field.Field = index
            field.Operator = self.uno.Enum("com.sun.star.sheet.FilterOperator", spec.get("operator", "EQUAL"))
            field.Connection = self.uno.Enum("com.sun.star.sheet.FilterConnection", spec.get("connection", "AND"))
            value = spec.get("value", "")
            field.IsNumeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if field.IsNumeric:
                field.NumericValue = float(value)
            else:
                field.StringValue = str(value)
            items.append(field)
        descriptor.setFilterFields(tuple(items))
        cells.filter(descriptor)
        return {"filtered": True, "criteria": len(items), "object": self.handle(descriptor, document)}

    def calc_pivot(self, document, sheet, range, name, output, fields):
        _, address = self.cell_range(document, sheet, range)
        tables = self.sheet(document, sheet).getDataPilotTables()
        if tables.hasByName(name):
            raise ValueError("Pivot name already exists")
        descriptor = tables.createDataPilotDescriptor()
        descriptor.setSourceRange(address)
        available = descriptor.getDataPilotFields()
        for spec in fields:
            field = available.getByName(spec["name"])
            field.Orientation = self.uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation",
                                              spec.get("orientation", "ROW"))
            if spec.get("function"):
                field.Function = self.uno.Enum("com.sun.star.sheet.GeneralFunction", spec["function"])
        destination = self.sheet(document, sheet).getCellRangeByName(output).getCellAddress()
        tables.insertNewByName(name, destination, descriptor)
        return self.handle(tables.getByName(name), document)

    def calc_validation(self, document, sheet, range, properties=None):
        cells, _ = self.cell_range(document, sheet, range)
        descriptor = cells.Validation
        enum_types = {"Type": "ValidationType", "Operator": "ConditionOperator",
                      "ErrorAlertStyle": "ValidationAlertStyle"}
        for name, value in (properties or {}).items():
            if name in enum_types and isinstance(value, str):
                value = {"$enum": "com.sun.star.sheet." + enum_types[name], "value": value}
            if name in {"Operator", "Formula1", "Formula2", "SourcePosition"}:
                getattr(descriptor, "set" + name)(self.decode(value))
            else:
                self.set_properties(descriptor, {name: value})
        if properties is not None:
            cells.Validation = descriptor
        return {"Type": self.encode(descriptor.Type), "Operator": self.encode(descriptor.getOperator()),
                "Formula1": descriptor.getFormula1(), "Formula2": descriptor.getFormula2(),
                "object": self.handle(descriptor, document)}

    def calc_conditional(self, document, sheet, range, entries):
        cells, _ = self.cell_range(document, sheet, range)
        rules = cells.ConditionalFormat
        rules.clear()
        for entry in entries:
            values = dict(entry)
            if isinstance(values.get("Operator"), str):
                values["Operator"] = {"$enum": "com.sun.star.sheet.ConditionOperator", "value": values["Operator"]}
            rules.addNew(self.props(values))
        cells.ConditionalFormat = rules
        return {"rules": rules.getCount(), "object": self.handle(rules, document)}

    def calc_annotation(self, document, sheet, cell, text=None, visible=None):
        cells, address = self.cell_range(document, sheet, cell)
        if address.StartColumn != address.EndColumn or address.StartRow != address.EndRow:
            raise ValueError("Specify exactly one cell")
        annotation = cells.getAnnotation()
        if text is not None:
            if len(text) > self.config.max_text:
                raise ValueError("Comment exceeds limit")
            if annotation.getString():
                annotation.setString(text)
            else:
                self.sheet(document, sheet).getAnnotations().insertNew(cells.getCellAddress(), text)
                annotation = cells.getAnnotation()
        if visible is not None:
            annotation.setIsVisible(visible)
        return {"text": annotation.getString(), "visible": annotation.getIsVisible(),
                "object": self.handle(annotation, document)}

    def calc_protect(self, document, sheet, protect=True, password=""):
        obj = self.sheet(document, sheet)
        if protect:
            obj.protect(password)
        else:
            obj.unprotect(password)
        return {"protected": obj.isProtected()}

    def calc_function(self, name, arguments):
        values = []
        for value in arguments:
            if isinstance(value, list) and value and all(isinstance(row, list) for row in value):
                if all(isinstance(x, (int, float)) and not isinstance(x, bool) for row in value for x in row):
                    value = self.uno.Any("[][]double", tuple(tuple(float(x) for x in row) for row in value))
                elif all(isinstance(x, str) for row in value for x in row):
                    value = self.uno.Any("[][]string", tuple(tuple(row) for row in value))
                else:
                    raise ValueError("Function array arguments must contain only numbers or only strings")
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                value = float(value)
            else:
                value = self.decode(value)
            values.append(value)
        return self.encode(self.uno.invoke(self.service("com.sun.star.sheet.FunctionAccess"),
                                          "callFunction", (name, tuple(values))))

    def calc_array_formula(self, document, sheet, range, formula=None):
        cells, _ = self.cell_range(document, sheet, range)
        if formula is not None:
            cells.setArrayFormula(formula)
        return {"formula": cells.getArrayFormula()}

    def calc_goal_seek(self, document, sheet, formula_cell, variable_cell, target):
        formula = self.sheet(document, sheet).getCellRangeByName(formula_cell).getCellAddress()
        variable = self.sheet(document, sheet).getCellRangeByName(variable_cell).getCellAddress()
        return self.encode(self.doc(document, "calc").seekGoal(formula, variable, str(target)), document)

    def calc_subtotals(self, document, sheet, range, group_column=0, columns=None, remove=False, replace=True):
        cells, address = self.cell_range(document, sheet, range)
        if remove:
            cells.removeSubTotals()
            return {"removed": True}
        count = address.EndColumn - address.StartColumn + 1
        if not 0 <= group_column < count:
            raise ValueError("group_column is outside the range")
        descriptor = cells.createSubTotalDescriptor(True)
        items = []
        for spec in columns or []:
            item = self.uno.createUnoStruct("com.sun.star.sheet.SubTotalColumn")
            item.Column = spec["column"]
            if not 0 <= item.Column < count:
                raise ValueError("Subtotal column is outside the range")
            item.Function = self.uno.Enum("com.sun.star.sheet.GeneralFunction", spec.get("function", "SUM"))
            items.append(item)
        if not items:
            raise ValueError("Supply subtotal columns")
        descriptor.addNew(tuple(items), group_column)
        cells.applySubTotals(descriptor, replace)
        return {"applied": True}

    def calc_chart_configure(self, object, diagram=None, title=None, subtitle=None, legend=None, properties=None):
        chart = self.ref(object)
        if diagram:
            if not diagram.startswith("com.sun.star.chart."):
                raise ValueError("Use a com.sun.star.chart.*Diagram service")
            chart.setDiagram(chart.createInstance(diagram))
        for name, text in [("Title", title), ("SubTitle", subtitle)]:
            if text is not None:
                chart.setPropertyValue("HasMainTitle" if name == "Title" else "HasSubTitle", True)
                obj = chart.getTitle() if name == "Title" else chart.getSubTitle()
                obj.setPropertyValue("String", text)
        if legend is not None:
            chart.setPropertyValue("HasLegend", legend)
        self.set_properties(chart.getDiagram(), properties)
        return {"configured": True}

    def presentation_page_configure(self, document, page, name=None, master=None, background=None, properties=None):
        obj = self.page(document, page)
        if name is not None:
            obj.setName(name)
        if master is not None:
            obj.setMasterPage(self.doc(document).getMasterPages().getByIndex(master))
        if background is not None:
            bg = self.doc(document).createInstance("com.sun.star.drawing.Background")
            self.set_properties(bg, background)
            obj.Background = bg
        self.set_properties(obj, properties)
        return self.handle(obj, document)

    def presentation_masters(self, document, action="list", index=0, name=None):
        doc = self.doc(document, "impress,draw")
        pages = doc.getMasterPages()
        if action == "add":
            obj = pages.insertNewByIndex(index)
            if name:
                obj.setName(name)
        elif action == "remove":
            pages.remove(pages.getByIndex(index))
        elif action != "list":
            raise ValueError("action must be list, add or remove")
        return [{"index": i, "name": pages.getByIndex(i).getName(),
                 "object": self.handle(pages.getByIndex(i), document)} for i in range(pages.getCount())]

    def presentation_shape_edit(self, document, page, index, text=None, properties=None, remove=False):
        obj = self.page(document, page)
        if not 0 <= index < obj.getCount():
            raise ValueError("Shape index is outside the page")
        shape = obj.getByIndex(index)
        if remove:
            obj.remove(shape)
            return {"removed": True}
        if text is not None:
            shape.setString(text)
        self.set_properties(shape, properties)
        return self.handle(shape, document)

    def presentation_group(self, document, page, indexes, ungroup=False):
        obj = self.page(document, page)
        if not indexes or len(set(indexes)) != len(indexes) or any(i < 0 or i >= obj.getCount() for i in indexes):
            raise ValueError("Specify unique valid shape indexes")
        if ungroup:
            if len(indexes) != 1:
                raise ValueError("Specify one group index to ungroup")
            obj.ungroup(obj.getByIndex(indexes[0]))
            return {"ungrouped": True}
        shapes = self.service("com.sun.star.drawing.ShapeCollection")
        for i in indexes:
            shapes.add(obj.getByIndex(i))
        return self.handle(obj.group(shapes), document)

    def presentation_layers(self, document, action="list", index=0, properties=None):
        manager = self.doc(document, "impress,draw").getLayerManager()
        if action == "add":
            layer = manager.insertNewByIndex(index)
            self.set_properties(layer, properties)
        elif action == "remove":
            manager.remove(manager.getByIndex(index))
        elif action == "update":
            self.set_properties(manager.getByIndex(index), properties)
        elif action != "list":
            raise ValueError("action must be list, add, remove or update")
        return [{"index": i, "name": manager.getByIndex(i).Name,
                 "visible": manager.getByIndex(i).IsVisible,
                 "locked": manager.getByIndex(i).IsLocked,
                 "object": self.handle(manager.getByIndex(i), document)} for i in range(manager.getCount())]

    def presentation_export(self, document, page, path, format=None, overwrite=False, options=None):
        target = self.path(path)
        if target.exists() and not overwrite:
            raise FileExistsError("Output exists; set overwrite=true")
        extension = (format or target.suffix.lstrip(".")).lower()
        media = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg",
                 "jpeg": "image/jpeg", "pdf": "application/pdf"}
        if extension not in media:
            raise ValueError("format must be png, svg, jpg, jpeg or pdf")
        target.parent.mkdir(parents=True, exist_ok=True)
        exporter = self.service("com.sun.star.drawing.GraphicExportFilter")
        exporter.setSourceDocument(self.page(document, page))
        values = {"URL": target.as_uri(), "MediaType": media[extension], "Overwrite": overwrite}
        if options:
            values["FilterData"] = {"$properties": options}
        if not exporter.filter(self.props(values)):
            raise RuntimeError("Graphic export failed")
        return {"path": str(target), "bytes": target.stat().st_size}

    def base_configure(self, document, properties=None):
        source = self.doc(document, "base").DataSource
        allowed = {"URL", "User", "Password", "IsPasswordRequired", "Info"}
        if set(properties or {}) - allowed:
            raise ValueError("Supported DataSource properties: " + ", ".join(sorted(allowed)))
        self.set_properties(source, properties)
        return {"URL": source.URL, "User": source.User,
                "password_required": source.IsPasswordRequired, "object": self.handle(source, document)}

    def base_queries(self, document, action="list", name=None, sql=None, escape_processing=True):
        doc = self.doc(document, "base")
        queries = doc.DataSource.getQueryDefinitions()
        if action in {"create", "update"}:
            if not name or not sql:
                raise ValueError("name and sql are required")
            if action == "create":
                obj = self.service("com.sun.star.sdb.QueryDefinition")
                obj.Command, obj.EscapeProcessing = sql, escape_processing
                queries.insertByName(name, obj)
            else:
                obj = queries.getByName(name)
                obj.Command, obj.EscapeProcessing = sql, escape_processing
        elif action == "remove":
            queries.removeByName(name)
        elif action != "list":
            raise ValueError("action must be list, create, update or remove")
        return [{"name": n, "sql": queries.getByName(n).Command} for n in queries.getElementNames()]

    def document_print(self, document, submit=False, printer=None, options=None):
        doc = self.doc(document)
        if printer:
            doc.setPrinter(self.props(printer))
        if submit:
            doc.print(self.props(options or {"Wait": True}))
        return {"submitted": submit, "printer": {p.Name: self.encode(p.Value, document) for p in doc.getPrinter()}}

    def linguistic_check(self, word, language="en", country="US", hyphenate=False):
        locale = self.uno.createUnoStruct("com.sun.star.lang.Locale")
        locale.Language, locale.Country = language, country
        manager = self.service("com.sun.star.linguistic2.LinguServiceManager")
        checker = manager.getHyphenator() if hyphenate else manager.getSpellChecker()
        locales = [self.encode(x) for x in checker.getLocales()]
        if not checker.hasLocale(locale):
            return {"available": False, "locales": locales}
        # SpellChecker also implements XSpellChecker1, whose same-named methods
        # take a numeric language ID. Reflection selects the Locale interface.
        reflection = self.service("com.sun.star.reflection.CoreReflection")
        interface = "com.sun.star.linguistic2." + ("XHyphenator" if hyphenate else "XSpellChecker")
        def invoke(name):
            method = reflection.forName(interface).getMethod(name)
            return self.uno.invoke(method, "invoke", (checker, (
                word, locale, self.uno.Any("[]com.sun.star.beans.PropertyValue", ()))))[0]
        if hyphenate:
            result = invoke("createPossibleHyphens")
            return {"available": True, "hyphenated": result.getPossibleHyphens() if result else None,
                    "positions": list(result.getHyphenationPositions()) if result else []}
        result = invoke("spell")
        return {"available": True, "valid": invoke("isValid"),
                "alternatives": list(result.getAlternatives()) if result else []}

    def office_extensions(self):
        provider = self.context.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        return [{"id": x[0], "version": x[1]} for x in provider.getExtensionList()]

    def office_configuration(self, node, properties=None, limit=100):
        if not node.startswith("/org.openoffice."):
            raise ValueError("Use an /org.openoffice.* configuration node path")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if properties is not None and not self.config.advanced:
            raise ValueError("Configuration writes require RAJ_ALLOW_ADVANCED=1")
        provider = self.service("com.sun.star.configuration.ConfigurationProvider")
        name = "ConfigurationUpdateAccess" if properties is not None else "ConfigurationAccess"
        access = provider.createInstanceWithArguments("com.sun.star.configuration." + name,
                                                      self.props({"nodepath": node}))
        if properties is not None:
            self.set_properties(access, properties)
            access.commitChanges()
        names = list(access.getElementNames())
        return {"values": {n: self.encode(access.getByName(n)) for n in names[:limit]},
                "total": len(names), "object": self.handle(access)}

    def document_export(self, document, path, filter_name, overwrite=False, options=None):
        if document in self.database_dirty:
            raise ValueError("Save the embedded database while connected before exporting")
        target = self.path(path)
        if target.exists() and not overwrite:
            raise FileExistsError("Output exists; set overwrite=true")
        if filter_name not in self.filter_list():
            raise ValueError("Unknown installed filter; use filter_list")
        if set(options or {}) - {"FilterData", "FilterOptions", "Password", "Selection"}:
            raise ValueError("Unsupported export options")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.doc(document).storeToURL(target.as_uri(), self.props(
            {**(options or {}), "FilterName": filter_name, "Overwrite": overwrite}))
        return {"path": str(target), "exported": True, "bytes": target.stat().st_size}

    def document_from_template(self, path):
        source = self.path(path, True)
        doc = self.desktop.loadComponentFromURL(source.as_uri(), "_blank", 0, self.props({
            "AsTemplate": True, "Hidden": True, "UpdateDocMode": 0,
            "MacroExecutionMode": self.uno.getConstantByName("com.sun.star.document.MacroExecMode.NEVER_EXECUTE")}))
        return self.register(doc, self.kind(doc) if doc else "unknown")

    def writer_refresh(self, document):
        doc = self.doc(document, "writer")
        doc.getTextFields().refresh()
        indexes = doc.getDocumentIndexes()
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()
        return {"updated_indexes": indexes.getCount()}

    def calc_solver(self, document, sheet, objective, variables, constraints=None, maximize=True,
                    service="com.sun.star.comp.Calc.LpsolveSolver", properties=None):
        doc = self.doc(document, "calc")
        solver = self.service(service)
        if solver is None:
            raise ValueError("Solver service unavailable; discover installed services with uno_services")
        solver.Document = doc
        solver.Objective = self.sheet(document, sheet).getCellRangeByName(objective).getCellAddress()
        solver.Variables = tuple(self.sheet(document, sheet).getCellRangeByName(x).getCellAddress() for x in variables)
        solver.Maximize = maximize
        ops = {"LESS_EQUAL": 0, "GREATER_EQUAL": 1, "EQUAL": 2, "INTEGER": 3, "BINARY": 4}
        items = []
        for spec in constraints or []:
            item = self.uno.createUnoStruct("com.sun.star.sheet.SolverConstraint")
            item.Left = self.sheet(document, sheet).getCellRangeByName(spec["cell"]).getCellAddress()
            operator = spec.get("operator", "LESS_EQUAL")
            if operator not in ops:
                raise ValueError("Unsupported solver operator")
            item.Operator = self.uno.Enum("com.sun.star.sheet.SolverConstraintOperator", operator)
            right = spec.get("value", 0)
            item.Right = self.sheet(document, sheet).getCellRangeByName(right).getCellAddress() if isinstance(right, str) else float(right)
            items.append(item)
        solver.Constraints = tuple(items)
        self.set_properties(solver, properties)
        solver.solve()
        return {"success": solver.Success, "solution": list(solver.Solution),
                "result": solver.ResultValue, "object": self.handle(solver, document)}

    def form_control(self, document, kind="TextField", name="Control", page=0, x=1000, y=1000,
                     width=5000, height=1000, properties=None):
        allowed = {"TextField", "CommandButton", "CheckBox", "RadioButton", "ListBox", "ComboBox",
                   "FixedText", "NumericField", "DateField", "TimeField", "FormattedField", "ImageControl"}
        if kind not in allowed:
            raise ValueError("Unsupported form control kind")
        self.dimensions(width, height)
        doc = self.doc(document)
        doc_kind = self.documents[document]["kind"]
        if doc_kind == "writer":
            draw_page = doc.getDrawPage()
        elif doc_kind == "calc":
            draw_page = doc.getSheets().getByIndex(page).getDrawPage()
        else:
            draw_page = self.page(document, page)
        forms = draw_page.getForms()
        if forms.hasByName("RAJ Form"):
            form = forms.getByName("RAJ Form")
        else:
            form = doc.createInstance("com.sun.star.form.component.Form")
            forms.insertByName("RAJ Form", form)
        if form.hasByName(name):
            raise ValueError("Control name already exists")
        model = doc.createInstance("com.sun.star.form.component." + kind)
        model.Name = name
        self.set_properties(model, properties)
        form.insertByName(name, model)
        shape = doc.createInstance("com.sun.star.drawing.ControlShape")
        pos = self.uno.createUnoStruct("com.sun.star.awt.Point")
        size = self.uno.createUnoStruct("com.sun.star.awt.Size")
        pos.X, pos.Y, size.Width, size.Height = x, y, width, height
        shape.setPosition(pos)
        shape.setSize(size)
        draw_page.add(shape)
        shape.setControl(model)
        return {"model": self.handle(model, document), "shape": self.handle(shape, document),
                "form": self.handle(form, document)}

    def presentation_custom_shows(self, document, action="list", name=None, indexes=None):
        shows = self.doc(document, "impress").getCustomPresentations()
        if action == "create":
            if not name or not indexes:
                raise ValueError("Supply name and slide indexes")
            if shows.hasByName(name):
                raise ValueError("Custom show already exists")
            show = shows.createInstance()
            for i, index in enumerate(indexes):
                show.insertByIndex(i, self.page(document, index))
            shows.insertByName(name, show)
        elif action == "remove":
            shows.removeByName(name)
        elif action != "list":
            raise ValueError("action must be list, create or remove")
        return [{"name": n, "slides": shows.getByName(n).getCount()} for n in shows.getElementNames()]

    def writer_mail_merge(self, template, database, table, output_directory, prefix="merged", single_file=True):
        if not self.config.advanced:
            raise ValueError("Mail merge requires RAJ_ALLOW_ADVANCED=1")
        source = self.path(database, True)
        target = self.path(output_directory)
        if target.exists() and any(target.iterdir()):
            raise ValueError("Use an empty output directory to avoid overwriting merge outputs")
        if not prefix or any(x in prefix for x in ["/", "\\", ":"]) or prefix in {".", ".."}:
            raise ValueError("prefix must be a simple filename prefix")
        target.mkdir(parents=True, exist_ok=True)
        merge = self.service("com.sun.star.text.MailMerge")
        self.set_properties(merge, {"DocumentURL": self.path(template, True).as_uri(),
            "DataSourceName": source.as_uri(), "Command": table, "CommandType": 0,
            "OutputType": 2, "OutputURL": target.as_uri(), "FileNamePrefix": prefix,
            "FileNameFromColumn": False, "SaveAsSingleFile": single_file})
        # Bind an explicit fresh connection. Default MailMerge connections can
        # reuse a stale table catalog after SQL DDL on an already-open Base file.
        data_source = self.service("com.sun.star.sdb.DatabaseContext").getByName(source.as_uri())
        connection = data_source.getIsolatedConnection(data_source.User, data_source.Password)
        try:
            tables = connection.getTables()
            if hasattr(tables, "refresh"):
                tables.refresh()
            if not tables.hasByName(table):
                raise ValueError("Table not found; verify committed data with base_tables/base_query")
            merge.setPropertyValue("ActiveConnection", connection)
            merge.execute(())
        finally:
            connection.close()
        return {"files": [str(p.relative_to(self.config.workspace)) for p in sorted(target.iterdir()) if p.is_file()]}


    def writer_database_field(self, document, database, table, column, position=None):
        doc = self.doc(document, "writer")
        master = doc.createInstance("com.sun.star.text.FieldMaster.Database")
        self.set_properties(master, {"DataBaseURL": self.path(database, True).as_uri(),
                                    "DataTableName": table, "DataColumnName": column,
                                    "DataCommandType": 0})
        field = doc.createInstance("com.sun.star.text.TextField.Database")
        field.attachTextFieldMaster(master)
        doc.Text.insertTextContent(self.cursor(document,
            len(doc.Text.String) if position is None else position), field, False)
        return self.handle(field, document)


FEATURES.update({
    "writer_database_field": "Insert a Writer database field bound to a table column in a local Base database, for mail merge templates.",
    "document_export": "Export through any installed filter by exact filter name. Output stays inside the workspace.",
    "document_from_template": "Create an untitled document from a workspace template, with automatic macros and links disabled.",
    "writer_refresh": "Refresh Writer text fields and all document indexes, including tables of contents.",
    "calc_solver": "Run an installed Calc solver with cell variables and constraints. Service/components and supported properties vary by installation.",
    "form_control": "Create a named form control and its drawing shape in Writer, Calc, Impress or Draw; returns model, shape and form handles.",
    "presentation_custom_shows": "List, create or remove named Impress custom slideshows with an ordered slide-index list.",
    "writer_mail_merge": "ADVANCED: merge a local Writer template against a local Base table into a new empty workspace directory. Requires advanced mode.",
})
