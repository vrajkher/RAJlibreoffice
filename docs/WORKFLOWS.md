# Simple advanced workflows

Start every flow with `document_create` or `document_open`, then keep the returned `document` handle. MCP tool responses wrap worker output in `result`; `workflow_run` references the worker result directly. Finish with `document_save` and `document_close`.

## Writer

| Task | Tool and essential arguments |
|---|---|
| Header/footer | `writer_page(document, header="Report", footer="Confidential")` |
| Footnote/frame/section | `writer_structure(document, kind="footnote", text="Source note", position=10)` |
| Table of contents | `writer_structure(document, kind="toc", position=0, properties={"Title":"Contents","CreateFromOutline":true})`, then `writer_refresh` |
| Review | `writer_review(document, record=true)`; insert/edit; `writer_review(document)` returns redline metadata/handles |
| Comment | `writer_review(document, comment="Please check", author="Reviewer", position=0)` |
| Style | `style_create(document, family="ParagraphStyles", name="ReportBody", parent="Standard", properties={"CharHeight":12.0})` |
| Template | `document_from_template(path="template.odt")` creates an untitled editable copy |
| Mail merge | Insert `writer_database_field(document, database="contacts.odb", table="contacts", column="name")`, save the template, then `writer_mail_merge(template="letter.odt", database="contacts.odb", table="contacts", output_directory="merged")` |

Mail merge requires advanced mode and an empty output directory. It produces files, without sending email or printing. Commit and save database changes before merging; mail merge refreshes its own connection table catalog. Redline acceptance/rejection and comparison use generic UNO/dispatch; inspect installed APIs first.

## Calc

| Task | Tool and essential arguments |
|---|---|
| Filter | `calc_filter(document, sheet=0, range="A1:B20", fields=[{"column":0,"operator":"EQUAL","value":"Active"}])`; empty `fields` clears the filter |
| Pivot | `calc_pivot(document, sheet=0, range="A1:B20", name="Summary", output="E1", fields=[{"name":"Group","orientation":"ROW"},{"name":"Amount","orientation":"DATA","function":"SUM"}])` |
| Validation | `calc_validation(document, sheet=0, range="B2:B20", properties={"Type":"WHOLE","Operator":"BETWEEN","Formula1":"1","Formula2":"100"})` |
| Conditional format | Create a CellStyle, then `calc_conditional(document, sheet=0, range="B2:B20", entries=[{"Operator":"GREATER","Formula1":"50","StyleName":"Highlight"}])` |
| Comment/protection | `calc_annotation(..., cell="A2", text="Source")`; `calc_protect(..., protect=true, password="...")` |
| Functions/arrays | `calc_function(name="SUM", arguments=[[[2,3],[4,5]]])`; `calc_array_formula(..., range="C1:C2", formula="=B1:B2*2")` |
| Goal seek | `calc_goal_seek(..., formula_cell="B1", variable_cell="A1", target="12")` returns a proposal without applying it |
| Solver | `calc_solver(..., objective="B1", variables=["A1"], constraints=[{"cell":"A1","operator":"LESS_EQUAL","value":10}])`; inspect returned solution before writing it |
| Subtotals | `calc_subtotals(..., range="A1:B20", group_column=0, columns=[{"column":1,"function":"SUM"}])` |
| Chart | Create with `calc_chart`, then use its handle with `calc_chart_configure(object=handle, diagram="com.sun.star.chart.BarDiagram", title="Totals")` |

Array function arguments must be rectangular, containing only numbers or only strings. The default solver selects the native Lpsolve implementation to avoid GUI-dependent Java engines. Other engines can be selected with `service`; availability/options depend on installed components. Pivot field names match source headers exactly. Filters and subtotals use columns relative to the source range.

## Impress, Draw, forms and Base

Use `presentation_page_configure` for names, master assignment, backgrounds and transition properties. Use `presentation_masters`, `presentation_group`, `presentation_layers` and `presentation_shape_edit` for page structure. `presentation_export(document, page=0, path="page.png")` renders a page; `presentation_custom_shows` selects an ordered set of slides. Animation nodes and detailed path geometry are available through reflected UNO objects.

`form_control(document, kind="TextField", name="Customer", properties={"Text":"Name"})` returns model, shape and form handles. Generic UNO adds bindings/events and edits other properties. Executable script events are trusted automation.

Use `base_configure` to select a driver URL, save an ODB, then `base_connect`/`base_query`/`base_transaction`. `base_queries` manages saved SQL definitions. External JDBC/ODBC/SDBC drivers and credentials must be installed/configured separately.

## Export, services and scripts

`document_export(document, path="output.ext", filter_name=exact_name)` supports any installed filter discovered with `filter_list`. The output remains an export; it does not become the document's editable location. PDF options use `options={"FilterData":{"$properties":{...}}}`. Password-protected ODF uses `document_save(..., options={"Password":"..."})`.

`linguistic_check` reports unavailable locales rather than assuming a dictionary is installed. `office_extensions` lists installed packages; `office_configuration` reads nodes and only writes with advanced mode. `document_print` reads printer settings by default; `submit=true` sends a real host print job.

For installed Basic/Python providers, `script_run` requires advanced and script settings. Its result is `[return_value, out_argument_indexes, out_argument_values]`. `python_run` executes trusted PyUNO code without a sandbox. Digital signatures need certificates; physical printing and GUI playback need their host facilities.
