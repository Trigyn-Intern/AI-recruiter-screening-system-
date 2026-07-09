// XLSX export for the Recent runs table.
//
// Pure browser implementation: no Node, no server endpoint. We build a
// minimal OOXML (.xlsx) zip by hand because SheetJS / xlsx-populate are
// not installed. The resulting file opens natively in Excel, LibreOffice
// Calc, and Google Sheets.
//
// 13 columns matching reports/report.html:
//   1. Sr No
//   2. CR No
//   3. Name
//   4. Description
//   5. Pre-requisite
//   6. Test Steps
//   7. Input Data
//   8. Expected Result
//   9. Actual Result
//   10. Pass/Fail
//   11. New Enhancement
//   12. Email sent to Requester
//   13. Reference

const SHEET_NAME = "Recent Runs";

const COLUMNS = [
  { key: "srNo",          header: "Sr No" },
  { key: "crNo",          header: "CR No" },
  { key: "name",          header: "Name" },
  { key: "description",   header: "Description" },
  { key: "prerequisite",  header: "Pre-requisite" },
  { key: "testSteps",     header: "Test Steps" },
  { key: "inputData",     header: "Input Data" },
  { key: "expectedResult",header: "Expected Result" },
  { key: "actualResult",  header: "Actual Result" },
  { key: "passFail",      header: "Pass/Fail" },
  { key: "enhancement",   header: "New Enhancement" },
  { key: "email",         header: "Email sent to Requester" },
  { key: "reference",     header: "Reference" },
];

function pickList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (typeof value === "string") {
    return value.split(/[,;|\n]/g).map((s) => s.trim()).filter(Boolean);
  }
  return [String(value)];
}

function cellFor(row, key) {
  const v = row[key];
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function toRows(runs) {
  return (runs || []).map((r, i) => {
    const raw = r && r.raw ? r.raw : {};
    const grading = raw.grading || {};
    const jdInfo = raw.jd_info || {};
    const detail = raw.detail || raw;
    const status = r.ok === true ? "Pass" : r.ok === false ? "Fail" : "-";
    if (r.kind === "test") {
      return {
        srNo: i + 1,
        crNo: r.crNo || "102423",
        name: r.fixtureLabel || r.label || "",
        description: r.description || r.sub || "",
        prerequisite: r.prerequisite || "Test environment and required services must be available before execution.",
        testSteps: r.command ? `Run command:\n${r.command}` : "",
        inputData: r.inputData || r.detail || "",
        expectedResult: r.expectedResult || "Command exits successfully and configured report artifacts are refreshed.",
        actualResult: r.error || r.summary || `Exit code: ${r.exitCode ?? "-"}\nElapsed: ${r.elapsedMs ?? 0} ms`,
        passFail: status,
        enhancement: r.enhancement || (r.ok ? "Run completed successfully. Review generated report for evidence." : "Investigate command logs and regenerate report after fixing failures."),
        email: r.email || `Subject: AI Recruiter Test ${status} - ${r.fixtureLabel || r.label || "Run"}\n\nStatus: ${status}\nReport: ${r.reportPath || "N/A"}`,
        reference: r.reportPath || r.file || "",
      };
    }
    return {
      srNo: i + 1,
      crNo: r.crNo || "102423",
      name: r.fixtureLabel || r.fixtureId || "",
      description: `Analyzer fixture run${jdInfo.scenario ? ` for ${jdInfo.scenario}` : ""}.`,
      prerequisite: "FastAPI backend on http://localhost:8000 must be running.",
      testSteps: "1. Submit fixture job description and resume text.\n2. Wait for analyzer response.\n3. Verify score, grade, and summary.",
      inputData: [
        raw.provider || r.provider ? `Provider: ${raw.provider || r.provider}` : "",
        raw.model_name || r.model ? `Model: ${raw.model_name || r.model}` : "",
        `Fixture: ${r.fixtureLabel || r.fixtureId || ""}`,
      ].filter(Boolean).join("\n"),
      expectedResult: "Analyzer returns a valid score, grade, and justification.",
      actualResult: r.error || `Score: ${r.score ?? raw.match_score ?? "-"}\nGrade: ${(r.grade || grading.grade || "-").toString().toUpperCase()}\nLatency: ${r.elapsedMs ?? 0} ms\n${r.summary || grading.summary || detail.justification || ""}`,
      passFail: status,
      enhancement: [
        pickList(r.matchingSkills || detail.matching_skills).length ? `Matching skills: ${pickList(r.matchingSkills || detail.matching_skills).join(", ")}` : "",
        pickList(r.missingSkills || detail.missing_skills).length ? `Missing skills: ${pickList(r.missingSkills || detail.missing_skills).join(", ")}` : "",
      ].filter(Boolean).join("\n") || "No additional enhancement notes.",
      email: `Subject: AI Recruiter Analyzer ${status} - ${r.fixtureLabel || "Fixture"}\n\nStatus: ${status}\nGenerated: ${r.at ? new Date(r.at).toISOString() : ""}`,
      reference: r.reportPath || "Browser localStorage recent run",
    };
  });
}

// ---------- Minimal ZIP writer (STORE, no compression) ----------
// We only need a handful of small XML files. STORE is fine for files
// that are already small and random-access-friendly; Excel accepts it.

function crc32(bytes) {
  // Pre-computed CRC32 table
  const table = crc32._t || (crc32._t = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      t[n] = c >>> 0;
    }
    return t;
  })());
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = (table[(c ^ bytes[i]) & 0xff] ^ (c >>> 8)) >>> 0;
  return (c ^ 0xffffffff) >>> 0;
}

function buildZip(files) {
  // files: [{name: string, data: Uint8Array}]
  const enc = new TextEncoder();
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  for (const file of files) {
    const nameBytes = enc.encode(file.name);
    const crc = crc32(file.data);
    const size = file.data.length;
    // Local file header (30 bytes + name + extra = 0 + data)
    const local = new Uint8Array(30 + nameBytes.length);
    const dv = new DataView(local.buffer);
    dv.setUint32(0, 0x04034b50, true);       // signature
    dv.setUint16(4, 20, true);                // version needed
    dv.setUint16(6, 0, true);                 // flags
    dv.setUint16(8, 0, true);                 // compression: store
    dv.setUint16(10, 0, true);                // mod time
    dv.setUint16(12, 0, true);                // mod date
    dv.setUint32(14, crc, true);              // crc32
    dv.setUint32(18, size, true);             // compressed size
    dv.setUint32(22, size, true);             // uncompressed size
    dv.setUint16(26, nameBytes.length, true); // file name length
    dv.setUint16(28, 0, true);                // extra field length
    local.set(nameBytes, 30);
    localParts.push(local, file.data);
    // Central directory entry (46 bytes + name)
    const central = new Uint8Array(46 + nameBytes.length);
    const cdv = new DataView(central.buffer);
    cdv.setUint32(0, 0x02014b50, true);
    cdv.setUint16(4, 20, true);                // version made by
    cdv.setUint16(6, 20, true);                // version needed
    cdv.setUint16(8, 0, true);                 // flags
    cdv.setUint16(10, 0, true);                // compression
    cdv.setUint16(12, 0, true);                // mod time
    cdv.setUint16(14, 0, true);                // mod date
    cdv.setUint32(16, crc, true);
    cdv.setUint32(20, size, true);
    cdv.setUint32(24, size, true);
    cdv.setUint16(28, nameBytes.length, true);
    cdv.setUint16(30, 0, true);                // extra field
    cdv.setUint16(32, 0, true);                // comment
    cdv.setUint16(34, 0, true);                // disk number
    cdv.setUint16(36, 0, true);                // internal attrs
    cdv.setUint32(38, 0, true);                // external attrs
    cdv.setUint32(42, offset, true);           // local header offset
    central.set(nameBytes, 46);
    centralParts.push(central);
    offset += local.length + file.data.length;
  }
  // EOCD
  const centralSize = centralParts.reduce((a, b) => a + b.length, 0);
  const eocd = new Uint8Array(22);
  const ev = new DataView(eocd.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(4, 0, true);                    // disk number
  ev.setUint16(6, 0, true);                    // disk with central dir
  ev.setUint16(8, centralParts.length, true);  // entries on this disk
  ev.setUint16(10, centralParts.length, true); // total entries
  ev.setUint32(12, centralSize, true);
  ev.setUint32(16, offset, true);
  ev.setUint16(20, 0, true);                   // comment length
  const out = new Uint8Array(
    localParts.reduce((a, b) => a + b.length, 0) +
    centralSize +
    eocd.length
  );
  let p = 0;
  for (const part of localParts)  { out.set(part, p); p += part.length; }
  for (const part of centralParts){ out.set(part, p); p += part.length; }
  out.set(eocd, p);
  return out;
}

// ---------- XML escaping ----------

function xmlEscape(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

// Excel inline-string preservation requires preserveSpace when leading
// or trailing whitespace matters, but for our values it does not.
function inlineStringCell(ref, text) {
  return `<c r="${ref}" t="inlineStr"><is><t xml:space="preserve">${xmlEscape(text)}</t></is></c>`;
}

function numberCell(ref, value) {
  return `<c r="${ref}"><v>${value}</v></c>`;
}

function cellForXml(ref, text) {
  if (text === "" || text === null || text === undefined) return `<c r="${ref}"/>`;
  const num = Number(text);
  if (text !== "" && Number.isFinite(num) && /^-?\d+(\.\d+)?$/.test(String(text).trim())) {
    return numberCell(ref, num);
  }
  return inlineStringCell(ref, text);
}

function colLetter(index) {
  // 1 -> A, 26 -> Z, 27 -> AA
  let s = "";
  let n = index;
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function buildSheetXml(rows) {
  const cols = COLUMNS.length;
  const lastCol = colLetter(cols);
  // Build header row
  const headerCells = COLUMNS.map((c, i) => inlineStringCell(`${colLetter(i + 1)}1`, c.header)).join("");
  // Build data rows
  const dataXml = rows.map((row, rowIdx) => {
    const r = rowIdx + 2;
    return `<row r="${r}">${
      COLUMNS.map((c, i) => cellForXml(`${colLetter(i + 1)}${r}`, cellFor(row, c.key))).join("")
    }</row>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:${lastCol}${rows.length + 1}"/>
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>${COLUMNS.map((_, i) =>
    `<col min="${i + 1}" max="${i + 1}" width="${i === 0 ? 5 : i === 11 || i === 12 ? 60 : 24}" customWidth="1"/>`
  ).join("")}</cols>
  <sheetData>
    <row r="1">${headerCells}</row>
    ${dataXml}
  </sheetData>
</worksheet>`;
}

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"  ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml"   ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml"     ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
  <Override PartName="/docProps/core.xml"  ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml"   ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>`;

const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`;

const WORKBOOK_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>`;

const WORKBOOK_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="${xmlEscape(SHEET_NAME)}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>`;

const STYLES_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/></font>
  </fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf/></cellStyleXfs>
  <cellXfs count="2">
    <xf fontId="0"/>
    <xf fontId="1" applyFont="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;

const SHARED_STRINGS_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="0" uniqueCount="0"/>`;

function coreXml(createdAt) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>AI Recruiter - Recent Runs</dc:title>
  <dc:creator>AI Recruiter Testing Dashboard</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">${createdAt}</dcterms:created>
</cp:coreProperties>`;
}

const APP_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>AI Recruiter Testing Dashboard</Application>
</Properties>`;

// ---------- Public API ----------

export function exportRunsToXlsx(runs, filename) {
  const rows = toRows(runs);
  const enc = new TextEncoder();
  const createdAt = new Date().toISOString();
  const sheetXml = buildSheetXml(rows);
  const files = [
    { name: "[Content_Types].xml",       data: enc.encode(CONTENT_TYPES) },
    { name: "_rels/.rels",               data: enc.encode(ROOT_RELS) },
    { name: "xl/workbook.xml",           data: enc.encode(WORKBOOK_XML) },
    { name: "xl/_rels/workbook.xml.rels",data: enc.encode(WORKBOOK_RELS) },
    { name: "xl/worksheets/sheet1.xml",  data: enc.encode(sheetXml) },
    { name: "xl/styles.xml",             data: enc.encode(STYLES_XML) },
    { name: "xl/sharedStrings.xml",      data: enc.encode(SHARED_STRINGS_XML) },
    { name: "docProps/core.xml",         data: enc.encode(coreXml(createdAt)) },
    { name: "docProps/app.xml",          data: enc.encode(APP_XML) },
  ];
  const zipBytes = buildZip(files);
  const blob = new Blob([zipBytes], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `recent-runs-${createdAt.replace(/[:.]/g, "-")}.xlsx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export { COLUMNS, toRows };
