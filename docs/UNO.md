# Advanced UNO and SDK workflow

Enable `RAJ_ALLOW_ADVANCED=1` to expose `uno_get`, `uno_set`, `uno_call`, `uno_service` and `uno_dispatch`. All examples are MCP tool arguments, without the outer tool-response `result` envelope.

## Discover before editing

1. Create/open a document and obtain its `document` handle.
2. `uno_inspect({"object":"DOCUMENT","query":"Text"})` lists installed properties and signatures.
3. Get a property or call a getter to obtain child objects.
4. Inspect that child, then invoke a method or set its properties.
5. Read back values, then save explicitly.

`uno_services` queries the installed service manager; `uno_type` reads the runtime type-description manager. These use LibreOffice's actual API registry, rather than a fixed list of features remembered by a language model. SDK development files complement runtime reflection with IDL and examples.

## Typed JSON

| JSON representation | UNO value |
|---|---|
| string, number, boolean | corresponding scalar |
| `[value, ...]` | sequence |
| `{"$ref":"obj_..."}` | previously returned live object |
| `{"$struct":"com.sun.star.awt.Point","fields":{"X":1000,"Y":2000}}` | struct |
| `{"$enum":"com.sun.star.text.TextContentAnchorType","value":"AS_CHARACTER"}` | enum |
| `{"$any":"[]com.sun.star.beans.PropertyValue","value":{"$properties":{"Hidden":true}}}` | explicitly typed Any |
| `{"$properties":{"FilterName":"writer_pdf_Export","Overwrite":false}}` | sequence of PropertyValue structs |
| `{"$type":"com.sun.star.awt.Point"}` | UNO Type |
| `{"$bytes":"AAEC"}` | binary byte sequence encoded as base64 |

Plain dictionaries are ambiguous and are rejected by UNO argument decoding. They must use one of these typed representations. Method return objects get new `$ref` handles; repeated discovery may return a new handle for the same UNO object. Release temporary references with `handles_release`. Closing a document invalidates its associated references.

UNO methods with OUT/INOUT parameters follow PyUNO's returned-tuple convention. Pass required placeholder arguments according to the discovered signature; returned sequences are encoded as JSON arrays. Use `uno.invoke` through `uno_call`, especially for explicit `Any` types.

## Writer headers and footers

Use `style_list` to find page styles. Then:

```json
{"object":"DOCUMENT","method":"getStyleFamilies"}
```

Call `getByName` on the returned families object with `arguments:["PageStyles"]`. On the resulting family call `getByName` with `arguments:["Standard"]` (discover localized names first). Enable the header:

```json
{"object":"PAGE_STYLE","properties":{"HeaderIsOn":true}}
```

Get `HeaderText` with `uno_get`, then call its `setString` with the desired text. `FooterIsOn` and `FooterText` follow the same flow.

## Writer comments, sections and indexes

- Create `com.sun.star.text.TextField.Annotation` with `writer_field`; set `Author` and `Content`.
- Create `com.sun.star.text.TextSection` using document-scoped `uno_service`. Inspect and configure it, then insert with the document Text object's `insertTextContent(cursor, section, false)`.
- Create document-scoped `com.sun.star.text.ContentIndex` for a table of contents, insert it as text content and call `update`.
- Traverse `getTextTables`, `getBookmarks`, `getTextFields`, `getDocumentIndexes` and their name/index containers to edit existing objects.
- Footnotes, endnotes, text frames, embedded objects, mail merge and tracked changes use their respective UNO services/suppliers. Inspect availability and verify save/reopen behavior before relying on a recipe.

These are API traversal recipes, not assertions that each workflow has dedicated integration coverage.

## Calc validation, conditional formatting and pivot tables

Get Sheets from the document, call `getByName`/`getByIndex`, then `getCellRangeByName`. Inspect the range's `Validation`, `ConditionalFormat` and related property types. Decode/edit descriptor properties and assign the completed descriptor back to the range.

For pivots, get a sheet's `getDataPilotTables`, call `createDataPilotDescriptor`, set a source `CellRangeAddress`, configure `getDataPilotFields` and their orientations, then call `insertNewByName` with a destination `CellAddress`. Use `uno_type` to inspect orientation enum/constants and address structs. Exact field names depend on the source headers.

For database filtering use the range's `createFilterDescriptor` and `filter`; create `TableFilterField` structs with the appropriate comparison operator. For protection inspect the sheet/document's `protect`, `unprotect` and `isProtected` methods. For chart styles use the returned chart handle, its diagrams/data providers and properties; `calc_chart` itself creates a default chart.

## Impress and Draw

`presentation_shape` returns a shape handle. Set `FillColor`, `LineColor`, text properties and other discovered properties using `uno_set`. Change position/size using `setPosition` and `setSize` with typed `Point`/`Size` structs.

Traverse `getDrawPages` and `getMasterPages` for page backgrounds, dimensions and master assignments. Animation nodes, custom shows, transitions, groups, embedded objects and drawing paths require their installed interfaces. Dispatch slideshow/UI commands only in a desktop environment that supports them; headless operation does not make interactive dialogs usable.

## Export beyond convenience formats

Discover installed names with `filter_list`. Use `uno_call` on the document with `storeToURL`, passing a file URL and typed PropertyValue sequence. Example PDF selection options:

```json
{
  "document":"DOCUMENT",
  "path":"selected.pdf",
  "export":true,
  "options":{"FilterData":{"$properties":{"PageRange":"1-2","SelectPdfVersion":2}}}
}
```

Installed filter options and accepted types vary across LibreOffice versions. Use dedicated `document_save` for workspace path checks. Arbitrary UNO `storeToURL` is advanced and bypasses those checks. Digital signatures and encryption interoperability require separate verification with the target reader.

## Base and database permissions

`base_connect` uses the document's configured DataSource, installed SDBC drivers and supplied credentials. Use `base_query` with `parameters` for values; table/column identifiers are part of SQL and cannot be parameterized. Result cells are returned as strings or null, preserving a straightforward portable representation. `limit` caps rows at 10,000; `has_more` indicates truncation.

Scalar integers inside the signed 32-bit range bind with `setInt`; larger integers use `setLong`. Strict drivers such as Firebird require the binding type to match the SQL column. Use typed parameters when needed, for example `{"type":"bigint","value":1}` or `{"type":"date","value":{"$struct":"com.sun.star.util.Date","fields":{"Year":2026,"Month":10,"Day":7}}}`. Supported explicit types are boolean, byte, short, int, bigint, float, double, string, date, time, timestamp and bytes.

Request `read_only:true` on `base_connect` for a connection-level read-only flag. Some drivers do not enforce that setting, so use a database account with SELECT-only privileges when enforcement matters. Query mode uses `executeQuery`; it does not classify arbitrary SQL or change connection state. `write:true` executes an update and rejects a connection reporting read-only. The server preserves transaction state across queries. `base_transaction(begin)` disables autocommit; commit/rollback keep it disabled until `autocommit` is requested. DDL transaction behavior is driver-dependent. These SQL transactions are independent of MCP `workflow_run`.

Base forms, reports, query definitions and database document structures are available through their UNO containers/services; they are not dedicated convenience tools. Driver setup, credentials and database availability remain prerequisites.

## Trusted Python and installed scripts

With both advanced mode and `RAJ_ALLOW_PYTHON=1`, call:

```json
{
  "document":"DOCUMENT",
  "code":"text = document.getText()\ntext.setString('Generated through PyUNO')\nresult = document.getSupportedServiceNames()"
}
```

The worker supplies `uno`, `context`, `desktop`, `document` and `result`. Assign a JSON/UNO-compatible value to `result`. Standard output is captured so it does not corrupt MCP framing. Python has normal process privileges and can import modules installed for the UNO interpreter.

With `RAJ_ALLOW_SCRIPTS=1`, `script_run` invokes an installed `vnd.sun.star.script:` URI through the document's ScriptProvider. Basic/Python providers and libraries must be installed. The tool does not silently enable automatic macros in opened documents.

