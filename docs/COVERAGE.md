# Feature coverage and verification

Common workflows have dedicated tools; generic UNO exposes additional installed APIs. This is not exhaustive tested coverage.

A test listed below is an implemented test, not proof of a passing run. Consult the current GitHub Actions run. Features reached through generic UNO still depend on the installed version, service, driver and GUI capabilities.

| Area | Features | Access | Verification |
|---|---|---|---|
| Documents | Creation, opening, metadata, save, export, close, undo | dedicated: `document_*; filter_list` | Roundtrip and overwrite integration tests |
| Writer body | Read, insert, replace, character and paragraph formatting | dedicated: `writer_read/insert/replace/format` | Writer roundtrip test |
| Writer structures | Tables, bookmarks, fields, images, styles | dedicated: `writer_table/bookmark/field/image; style_*` | Tables/bookmarks/fields/images/style editing covered; broader structures use generic UNO |
| Writer advanced text | Headers/footers, sections, frames, footnotes, endnotes | generic UNO: `Text, TextSections, TextFrames, Footnotes, Endnotes, PageStyles` | Recipes only; not integration verified |
| Writer review | Comments, tracked changes, redlines, text comparisons | generic UNO: `Annotation fields; Redlines and document comparison APIs/dispatch` | Not integration verified |
| Writer publishing | Indexes/TOC, mail merge, templates, linked content | generic UNO: `ContentIndex, DocumentIndexes, MailMerge, document/template APIs` | Not integration verified |
| Calc cells | Values, formulas, formats, clear/merge, recalculate | dedicated: `calc_read/write/format/clear/merge/recalculate` | Values/formulas/format roundtrip test |
| Calc sheets | List, add, remove, rename, move, copy | dedicated: `calc_sheets` | Add and list covered; remaining actions need more tests |
| Calc analysis | Sorting, named ranges, default chart creation | dedicated: `calc_sort/named_range/chart` | Calc integration test |
| Calc advanced analysis | Filters, pivots, subtotals, solver, goal seek | generic UNO: `FilterDescriptor, DataPilotTables, SubTotalDescriptor, Solver, GoalSeek` | Not integration verified; solver component dependent |
| Calc rules | Validation, conditional formatting, protection, annotations | generic UNO: `Validation, ConditionalFormat, protect/unprotect, annotations` | Not integration verified |
| Calc charts | Chart type, axes, legends, data providers, series formatting | generic UNO: `Returned chart object; Chart2 services and suppliers` | Default creation tested; advanced styles unverified |
| Calc functions | Function evaluation, add-ins, matrix and array formulas | generic UNO: `FunctionAccess; XArrayFormulaRange; installed add-ins` | Formula cells tested; arbitrary functions/add-ins unverified |
| Impress/Draw pages | Page/slide management, text, shapes and images | dedicated: `presentation_pages/shape/read` | Text/shape native save tests; image and page actions need more tests |
| Impress notes | Read and write speaker notes | dedicated: `presentation_notes` | Notes integration test |
| Impress advanced | Masters, transitions, animations, custom shows, slideshow | generic UNO / desktop dependent: `MasterPages; AnimationNode; CustomPresentationSupplier; Presentation` | Not integration verified; playback needs desktop |
| Draw advanced | Groups, paths, connectors, layers, transformations, embedded objects | generic UNO: `drawing services and shape interfaces` | Basic shape tested; advanced interfaces unverified |
| Math | Read/write StarMath formulas and native storage | dedicated: `math_formula; document_save` | Formula/native save integration test |
| Base SQL | Connect, list tables, prepared queries/updates, transactions | dedicated: `base_connect/tables/query/transaction` | Embedded Firebird integration test |
| Base documents | Data sources, query definitions, forms, reports | generic UNO: `DataSource; CommandDefinitions; FormDocuments; ReportDocuments` | DataSource/SQL tested; forms/reports unverified |
| Base drivers | Firebird, JDBC, ODBC, PostgreSQL/MySQL and other SDBC backends | installation dependent: `Installed SDBC services, driver packages and credentials` | Only embedded Firebird integration fixture |
| Import/export | Common ODF/OOXML/PDF/text/HTML formats; discovery of all installed filters | dedicated + generic UNO: `document_save; filter_list; storeToURL/storeAsURL` | ODF/PDF integration; other conversions unverified |
| PDF options | Page selection, PDF/A versions, forms, bookmarks, tagging | generic export options: `FilterData through document_save or UNO filters` | Basic PDF and FilterData option acceptance tested; PDF/A conformance and remaining options unverified |
| Images/rendering | Embedded graphics; page/image export | dedicated + generic UNO: `GraphicProvider; GraphicExportFilter` | Writer image decoding/embedding covered; presentation images and graphic export unverified |
| Printing | Printer selection, job settings, print submission | generic UNO / host dependent: `XPrintable; .uno:Print; printer properties` | No dedicated print tool; requires configured printer; unverified |
| Security/signatures | Document protection, encryption, digital signatures, certificates | generic UNO / host dependent: `protect/unprotect; export Password; document digital signature services` | Not integration verified; certificates and target-reader validation required |
| Forms/controls | Document form controls, binding, events | generic UNO: `form/control services; DrawPage Forms` | Not integration verified |
| Accessibility/localization | Accessible trees, spellcheck, dictionaries, language tools | generic UNO / GUI dependent: `Accessible contexts; linguistic2 services; installed dictionaries` | Not integration verified; GUI availability varies |
| Extensions/configuration | Discover/instantiate installed services and configuration APIs | generic UNO: `uno_services; uno_service; ConfigurationProvider; PackageInformationProvider` | Service discovery tested; modifications unverified |
| SDK/reflection | Methods, properties, runtime types, structs, enums, Any, sequences | dedicated: `uno_inspect/type/get/set/call/service` | Reflection and Point struct integration test; more types needed |
| Scripts | Installed Basic/Python scripts | optional trusted automation: `script_run with ScriptProvider URI` | Registration/gating tested; providers/macros unverified |
| Python | Arbitrary trusted automation using PyUNO and standard Python | optional trusted automation: `python_run` | Integration test edits text and returns result |
| OpenAI extensions | Composer file mentions and native settings | optional SDK integration: `OpenAIExtensions; OpenAISettings; document_save_preferred` | Registration, stdio, settings persistence and file mentions tested; native host UX unverified |
| MCP workflow | Ordered dependent operations, resources, editing prompt | dedicated: `workflow_run; libreoffice://guide/tools/coverage; edit_document` | Unit and MCP schema tests |
| GUI/cloud hosting | Interactive dialogs, browser document editor, authenticated remote multi-user sessions | not implemented: `External application/hosting work required` | No coverage claim |

## Boundaries

The server does not implement a full LibreOffice user interface, compile arbitrary SDK components, configure every external driver, preserve every proprietary document feature, or guarantee every UNO/dispatch operation works headlessly. Generic invocation is a way to access available APIs, not evidence that all of those APIs have been tested.

Dedicated tools check file paths and cap text/cell results. Generic trusted UNO/Python can bypass those boundaries. Large documents should be read in bounded ranges. One worker serializes all requests; handles are process-local. There is no multi-user tenancy, distributed job scheduler, automatic backup, or workflow rollback.

## Extension points

Add a convenience method to `Office`, include it in `OPERATIONS`, add a description/schema mapping in `tools.py`, and add a real integration test. Runtime reflection already supports newly installed UNO services without needing to add one MCP tool per UNO method.
