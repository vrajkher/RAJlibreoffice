# Feature coverage and verification

Common workflows have dedicated tools; generic UNO exposes additional installed APIs. This is not exhaustive tested coverage.

Verification is scoped to the cases below. Consult GitHub Actions for the exact tested commit. Generic UNO access does not imply every installed API has been tested.

| Area | Features | Access | Verification |
|---|---|---|---|
| Documents | Creation, opening, metadata, save, export, close, undo | dedicated: `document_*; filter_list` | Roundtrip and overwrite integration tests |
| Writer body | Read, insert, replace, character and paragraph formatting | dedicated: `writer_read/insert/replace/format` | Writer roundtrip test |
| Writer structures | Tables, bookmarks, fields, images, styles | dedicated: `writer_table/bookmark/field/image; style_*` | Tables/bookmarks/fields/images/style editing and style creation covered by integration tests |
| Writer advanced text | Headers/footers, sections, frames, footnotes, endnotes | dedicated: `writer_page; writer_structure` | Headers/footers and section/frame/footnote/endnote ODT roundtrip |
| Writer review | Comments, tracked changes, redlines, text comparisons | dedicated + generic UNO: `writer_review; generic redline/dispatch APIs` | Annotation insertion and tracked-change recording/listing tested; accepting/rejecting/comparison use generic UNO and remain unverified |
| Writer publishing | Indexes/TOC, mail merge, templates, linked content | dedicated + generic UNO: `writer_structure(toc); writer_refresh; writer_database_field; writer_mail_merge; document_from_template` | TOC creation, templates, database fields and local Firebird file mail merge tested; linked content unverified |
| Calc cells | Values, formulas, formats, clear/merge, recalculate | dedicated: `calc_read/write/format/clear/merge/recalculate` | Values/formulas/format roundtrip test |
| Calc sheets | List, add, remove, rename, move, copy | dedicated: `calc_sheets` | Add and list covered; remaining actions need more tests |
| Calc analysis | Sorting, named ranges, default chart creation | dedicated: `calc_sort/named_range/chart` | Calc integration test |
| Calc advanced analysis | Filters, pivots, subtotals, solver, goal seek | dedicated: `calc_filter/pivot/subtotals/solver/goal_seek` | Filter row visibility, pivot aggregation, subtotals, goal-seek proposal and linear solver result tested; alternate solver engines remain installation dependent |
| Calc rules | Validation, conditional formatting, protection, annotations | dedicated: `calc_validation/conditional/protect/annotation` | Validation and annotation ODS roundtrip; conditional rule count and protection toggling tested |
| Calc charts | Chart type, axes, legends, data providers, series formatting | dedicated + generic UNO: `calc_chart; calc_chart_configure; Chart2 services` | Default chart, BarDiagram/title/legend configuration tested; axes/data providers/series remain generic and unverified |
| Calc functions | Function evaluation, add-ins, matrix and array formulas | dedicated + generic UNO: `calc_function; calc_array_formula; installed add-ins` | Numeric-array SUM, formula cells and matrix results tested; arbitrary functions/add-ins unverified |
| Impress/Draw pages | Page/slide management, text, shapes and images | dedicated: `presentation_pages/shape/read` | Text/shape saves, page addition/removal and shape edits tested; presentation images unverified |
| Impress notes | Read and write speaker notes | dedicated: `presentation_notes` | Notes integration test |
| Impress advanced | Masters, transitions, animations, custom shows, slideshow | dedicated + generic UNO / desktop dependent: `presentation_masters/page_configure/custom_shows; AnimationNode; Presentation` | Masters, page configuration, transition property acceptance and custom-show order/count tested; animations/playback remain generic or desktop dependent |
| Draw advanced | Groups, paths, connectors, layers, transformations, embedded objects | dedicated + generic UNO: `presentation_group/layers/shape_edit; polygon/polyline/Bezier/custom/OLE shape services` | Groups/ungrouping, layers, masters, shape edits/removal and PNG/SVG exports tested; paths/connectors/OLE embedding unverified |
| Math | Read/write StarMath formulas and native storage | dedicated: `math_formula; document_save` | Formula/native save integration test |
| Base SQL | Connect, list tables, prepared queries/updates, transactions | dedicated: `base_connect/tables/query/transaction` | Embedded Firebird integration test |
| Base documents | Data sources, query definitions, forms, reports | dedicated + generic UNO: `base_configure; base_queries; form_control; FormDocuments/ReportDocuments` | DataSource and query-definition ODB roundtrip tested; Base form/report document containers remain generic and unverified |
| Base drivers | Firebird, JDBC, ODBC, PostgreSQL/MySQL and other SDBC backends | installation dependent: `Installed SDBC services, driver packages and credentials` | Only embedded Firebird integration fixture |
| Import/export | Common ODF/OOXML/PDF/text/HTML formats; discovery of all installed filters | dedicated + installed filters: `document_save; document_export; filter_list` | ODF/PDF plus DOCX/XLSX/PPTX readback, text/HTML/EPUB output and encrypted ODT readback tested; format fidelity depends on content |
| PDF options | Page selection, PDF/A versions, forms, bookmarks, tagging | generic export options: `FilterData through document_save or UNO filters` | Basic PDF and FilterData option acceptance tested; PDF/A conformance and remaining options unverified |
| Images/rendering | Embedded graphics; page/image export | dedicated: `writer_image; presentation_shape(image); presentation_export` | Writer graphics and Draw PNG/SVG export tested; other image export formats and presentation image insertion unverified |
| Printing | Printer selection, job settings, print submission | dedicated / host dependent: `document_print; printer options` | Printer descriptor reading tested; actual print submission needs configured host printer and is unverified |
| Security/signatures | Document protection, encryption, digital signatures, certificates | dedicated + generic UNO / host dependent: `calc_protect; document_save Password; digital signature services` | Sheet protection toggling and password-protected ODT readback tested; digital signatures need certificates and remain unverified |
| Forms/controls | Document form controls, binding, events | dedicated + generic UNO: `form_control; form model/shape handles and generic event/binding APIs` | Writer TextField form-control ODT roundtrip tested; other controls/bindings/events require further verification |
| Accessibility/localization | Accessible trees, spellcheck, dictionaries, language tools | dedicated + generic UNO / GUI dependent: `linguistic_check; Accessible contexts and dictionaries` | Installed spellchecker invocation tested; unavailable locales reported; accessible trees and dictionary modification unverified |
| Extensions/configuration | Discover/instantiate installed services and configuration APIs | dedicated + generic UNO: `office_extensions/configuration; uno_services/service` | Extension enumeration and configuration-node reads tested; configuration writes require advanced mode and are unverified |
| SDK/reflection | Methods, properties, runtime types, structs, enums, Any, sequences | dedicated: `uno_inspect/type/get/set/call/service` | Reflection and Point struct integration test; more types needed |
| Scripts | Installed Basic/Python scripts | optional trusted automation: `script_run with ScriptProvider URI` | Document Basic invocation tested; Python ScriptProvider and additional installed providers remain host dependent |
| Python | Arbitrary trusted automation using PyUNO and standard Python | optional trusted automation: `python_run` | Integration test edits text and returns result |
| OpenAI extensions | Composer file mentions and native settings | optional native SDK integration: `OpenAIExtensions; OpenAISettings; document_save_preferred; office_workspace MCP App` | SDK registration, stdio, settings/mentions, authenticated HTTP and browser panel flows tested; native host UX requires an MCP Apps host |
| MCP workflow | Ordered dependent operations, resources, editing prompt | dedicated: `workflow_run; libreoffice://guide/tools/coverage; edit_document` | Unit and MCP schema tests |
| GUI/cloud hosting | Interactive dialogs, browser document editor, authenticated remote multi-user sessions | partial / external host required: `office_workspace; authenticated single-user HTTP; Docker/Compose` | Basic workspace panel and transport are implemented. Full WYSIWYG editing, OAuth, multi-user isolation and hosted deployment are not implemented |

## Boundaries

A single worker serializes requests; handles are process-local. Workflows are ordered, not atomic. There is no multi-user tenancy, automatic backup or workflow rollback. Trusted UNO/Python can bypass dedicated tool boundaries.

The native panel provides basic editing rather than a full LibreOffice interface. Public hosting still requires TLS, hosting configuration and a client supporting explicit bearer headers. OAuth, full collaborative WYSIWYG editing, signature certificates, installed external drivers, physical printers and GUI playback are external prerequisites or unimplemented features.

## Extension points

Add a convenience method to `Office` or `FeatureMethods`, register it in `OPERATIONS`/`FEATURES`, map its signature and add a real UNO integration test. SDK reflection and generic UNO invocation expose installed services without one tool per UNO method.
