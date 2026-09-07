import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = process.argv[2];
const outputPath = process.argv[3];
const sourcePath = `${projectRoot}/data/reviews/evidence-review-export.json`;
const payload = JSON.parse(await fs.readFile(sourcePath, "utf8"));

const workbook = Workbook.create();

function addSheet({ name, title, note, headers, rows, widths, tableName }) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.getRange("A1:J1").merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format = {
    fill: "#0F4C5C",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  sheet.getRange("A1").format.rowHeight = 30;
  sheet.getRange("A2:J2").merge();
  sheet.getRange("A2").values = [[note]];
  sheet.getRange("A2").format = {
    fill: "#E8F3F5",
    font: { color: "#214E59", size: 10 },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A2").format.rowHeight = 42;
  sheet.getRange("A3").values = [[`共 ${rows.length} 条；请只填写“审核结论”和“审核备注”两列。`]];
  sheet.getRange("A3:J3").merge();
  sheet.getRange("A3").format = {
    fill: "#FFF7E6",
    font: { bold: true, color: "#8A4B08" },
    verticalAlignment: "center",
  };
  sheet.getRange("A3").format.rowHeight = 22;

  const lastRow = rows.length + 4;
  sheet.getRange(`A4:J${lastRow}`).values = [headers, ...rows];
  const table = sheet.tables.add(`A4:J${lastRow}`, true, tableName);
  table.style = "TableStyleMedium2";
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(2);
  for (const [column, width] of Object.entries(widths)) {
    sheet.getRange(`${column}:${column}`).format.columnWidth = width;
  }
  sheet.getRange(`A5:J${lastRow}`).format.wrapText = true;
  sheet.getRange(`A5:J${lastRow}`).format.verticalAlignment = "top";
  sheet.getRange(`I5:I${lastRow}`).dataValidation = {
    rule: { type: "list", values: ["approved", "rejected", "needs_review"] },
  };
  sheet.getRange(`I5:J${lastRow}`).format.fill = "#FFFDEB";
  sheet.getRange(`I5:I${lastRow}`).conditionalFormats.add("containsText", {
    text: "approved",
    format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  sheet.getRange(`I5:I${lastRow}`).conditionalFormats.add("containsText", {
    text: "rejected",
    format: { fill: "#FEE2E2", font: { color: "#991B1B", bold: true } },
  });
  return sheet;
}

const linkHeaders = [
  "关联编号", "文物名称", "Word 文档标题", "来源文件名", "匹配置信度", "自动匹配理由",
  "当前状态", "当前备注", "审核结论", "审核备注",
];
const linkRows = payload.links.map((item) => [
  item.link_id, item.artifact_name, item.document_title, item.source_filename, item.confidence,
  item.match_reasons, item.current_status, item.current_note, item.review_decision, item.review_note,
]);
addSheet({
  name: "关联审核",
  title: "文物—Word 资料关联审核表",
  note: "只有确实直接涉及该文物的资料，才填 approved；不相关填 rejected；暂时拿不准保留 needs_review。未审核资料不会进入 GPT 的馆藏事实回答。",
  headers: linkHeaders,
  rows: linkRows,
  widths: { A: 24, B: 20, C: 28, D: 28, E: 12, F: 42, G: 16, H: 32, I: 18, J: 36 },
  tableName: "EvidenceLinks",
});

const documentHeaders = [
  "文档编号", "Word 文档标题", "来源文件名", "当前状态", "当前备注", "审核结论",
  "审核备注", "", "", "",
];
const documentRows = payload.documents.map((item) => [
  item.document_id, item.document_title, item.source_filename, item.current_status, item.current_note,
  item.review_decision, item.review_note, "", "", "",
]);
addSheet({
  name: "文档审核",
  title: "Word 文档总体审核表",
  note: "请判断文档本身是否可以作为馆内资料使用：approved 表示可用，rejected 表示不采用，needs_review 表示暂不进入问答证据。",
  headers: documentHeaders,
  rows: documentRows,
  widths: { A: 24, B: 30, C: 30, D: 16, E: 42, F: 18, G: 36, H: 4, I: 4, J: 4 },
  tableName: "EvidenceDocuments",
});

const inspection = await workbook.inspect({
  kind: "table",
  range: "关联审核!A1:J10",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 10,
});
if (!inspection.ndjson.includes("凤凰") && !inspection.ndjson.includes("关联编号")) {
  throw new Error("Workbook verification did not find the review table.");
}

const preview = await workbook.render({ sheetName: "关联审核", range: "A1:J14", scale: 1.5, format: "png" });
await fs.mkdir(outputPath.substring(0, outputPath.lastIndexOf("/")), { recursive: true });
await fs.writeFile(`${outputPath}.preview.png`, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, rows: linkRows.length + documentRows.length }));
