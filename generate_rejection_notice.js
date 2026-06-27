const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, BorderStyle, WidthType, ShadingType, UnderlineType } = require("docx");
const fs = require("fs");

const data = JSON.parse(fs.readFileSync("rejection_notice_data.json"));

const W  = 9360;
const C1 = 2600; const C2 = 6760;
const bdr  = { style: BorderStyle.SINGLE, size: 4, color: "1B4F9A" };
const bdrs = { top: bdr, bottom: bdr, left: bdr, right: bdr };
const cm   = { top: 80, bottom: 80, left: 120, right: 120 };

function lc(text, w) {
  return new TableCell({
    borders: bdrs, width: { size: w||C1, type: WidthType.DXA },
    shading: { fill: "1B4F9A", type: ShadingType.CLEAR }, margins: cm,
    children: [new Paragraph({ children: [
      new TextRun({ text, bold: true, color: "FFFFFF", size: 19, font: "Arial" })
    ]})]
  });
}
function vc(text, w) {
  return new TableCell({
    borders: bdrs, width: { size: w||C2, type: WidthType.DXA }, margins: cm,
    children: [new Paragraph({ children: [
      new TextRun({ text: text||"-", size: 20, font: "Arial" })
    ]})]
  });
}
function row2(label, value) {
  return new TableRow({ children: [lc(label), vc(value)] });
}
function row4(l1,v1,l2,v2) {
  return new TableRow({ children: [
    lc(l1,2300), vc(v1,2380), lc(l2,2300), vc(v2,2380)
  ]});
}
function secRow(title) {
  return new TableRow({ children: [
    new TableCell({
      columnSpan: 2, borders: bdrs,
      width: { size: W, type: WidthType.DXA },
      shading: { fill: "0D2B5E", type: ShadingType.CLEAR }, margins: cm,
      children: [new Paragraph({ children: [
        new TextRun({ text: title, bold: true, color: "F0A500", size: 22, font: "Arial" })
      ]})]
    })
  ]});
}

const d = data;
const doc = new Document({
  sections:[{
    properties: { page: { size: { width: 11906, height: 16838 },
      margin: { top: 720, right: 720, bottom: 720, left: 720 } } },
    children:[
      // College Header - same as closure report
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 0 },
        children: [new TextRun({ text:"Seshadri Rao Gudlavalleru Engineering College",
          bold:true, size:32, font:"Arial", color:"1B4F9A" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 0 },
        children: [new TextRun({ text:"Gudlavalleru, Krishna District, Andhra Pradesh \u2014 521 356",
          size:20, font:"Arial", color:"444444" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 60 },
        children: [new TextRun({ text:"An Autonomous Institute \u2014 Permanently Affiliated to JNTUK, Kakinada",
          size:18, font:"Arial", color:"666666", italics:true })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 100 },
        border: { bottom: { style: BorderStyle.SINGLE, size:6, color:"F0A500" } },
        children: [new TextRun({ text: (d.module_name || "SRGEC-SIMS").toUpperCase() + " \u2014 MAINTENANCE SYSTEM",
          bold:true, size:22, font:"Arial", color:"1B4F9A" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before:100, after:200 },
        children: [new TextRun({ text:"COMPLAINT REJECTION NOTICE",
          bold:true, size:28, font:"Arial", color:"C00000",
          underline: { type: UnderlineType.SINGLE } })]
      }),
      // Complaint Details
      new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [C1, C2], rows: [
        secRow("1.  COMPLAINT DETAILS"),
        row4("Call Number", d.call_number, "Date Raised", d.raised_at),
        row2("Asset UID", d.asset_uid),
        row2("Asset Description", d.asset_desc),
        row2("Department", d.dept_name),
        row2("Raised By", d.raised_by),
      ]}),
      new Paragraph({ text:"", spacing:{after:200} }),
      // Rejection Details
      new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [C1, C2], rows: [
        secRow("2.  REJECTION DETAILS"),
        row4("Rejected At Stage", d.rejection_stage, "Rejection Date", d.rejection_at),
        row2("Rejected By", d.rejected_by),
        row2("Reason for Rejection", d.rejection_reason),
      ]}),
      new Paragraph({ text:"", spacing:{after:200} }),
      // Timeline
      new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [C1, C2], rows: [
        secRow("3.  COMPLAINT TIMELINE"),
        new TableRow({ children: [
          lc("Date/Time", 2000), lc("Action", 2500), lc("By", 2500), lc("Comment", 2360)
        ]}),
        ...d.timeline.map(t => new TableRow({ children: [
          vc(t.at, 2000), vc(t.step, 2500), vc(t.actor, 2500), vc(t.comment||"-", 2360)
        ]}))
      ]}),
      new Paragraph({ text:"", spacing:{after:400} }),
      // Signatures
      new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [C1, C2], rows: [
        secRow("4.  AUTHORIZATION"),
        row4("System Administrator", "________________", "HEAD-UPS", "________________"),
      ]}),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("rejection_notice.docx", buf);
  console.log("Done");
});
