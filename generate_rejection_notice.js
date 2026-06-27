const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, BorderStyle, AlignmentType, HeadingLevel } = require("docx");
const fs = require("fs");

const data = JSON.parse(fs.readFileSync("rejection_notice_data.json"));

const bold = (text, size=22) => new TextRun({ text: String(text||"-"), bold: true, size });
const normal = (text, size=22) => new TextRun({ text: String(text||"-"), size });

const row = (label, value) => new TableRow({ children: [
    new TableCell({ width:{size:35,type:WidthType.PERCENTAGE}, children:[new Paragraph({children:[bold(label)]})] }),
    new TableCell({ width:{size:65,type:WidthType.PERCENTAGE}, children:[new Paragraph({children:[normal(value)]})] }),
]});

const doc = new Document({ sections:[{ children:[
    new Paragraph({ text: data.module_name + " — Complaint Rejection Notice", heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER }),
    new Paragraph({ text: "" }),
    new Paragraph({ children:[bold("COMPLAINT DETAILS", 24)], heading: HeadingLevel.HEADING_2 }),
    new Table({ width:{size:100,type:WidthType.PERCENTAGE}, rows:[
        row("Call Number", data.call_number),
        row("Asset UID", data.asset_uid),
        row("Asset Description", data.asset_desc),
        row("Department", data.dept_name),
        row("Raised By", data.raised_by),
        row("Raised On", data.raised_at),
    ]}),
    new Paragraph({ text: "" }),
    new Paragraph({ children:[bold("REJECTION DETAILS", 24)], heading: HeadingLevel.HEADING_2 }),
    new Table({ width:{size:100,type:WidthType.PERCENTAGE}, rows:[
        row("Rejected By", data.rejected_by),
        row("Rejected At Stage", data.rejection_stage),
        row("Rejection Date", data.rejection_at),
        row("Reason for Rejection", data.rejection_reason),
    ]}),
    new Paragraph({ text: "" }),
    new Paragraph({ children:[bold("COMPLAINT TIMELINE", 24)], heading: HeadingLevel.HEADING_2 }),
    new Table({ width:{size:100,type:WidthType.PERCENTAGE}, rows:[
        new TableRow({ children:[
            new TableCell({ children:[new Paragraph({children:[bold("Date/Time")]})] }),
            new TableCell({ children:[new Paragraph({children:[bold("Action")]})] }),
            new TableCell({ children:[new Paragraph({children:[bold("By")]})] }),
            new TableCell({ children:[new Paragraph({children:[bold("Comment")]})] }),
        ]}),
        ...data.timeline.map(t => new TableRow({ children:[
            new TableCell({ children:[new Paragraph({children:[normal(t.at)]})] }),
            new TableCell({ children:[new Paragraph({children:[normal(t.step)]})] }),
            new TableCell({ children:[new Paragraph({children:[normal(t.actor)]})] }),
            new TableCell({ children:[new Paragraph({children:[normal(t.comment)]})] }),
        ]}))
    ]}),
    new Paragraph({ text: "" }),
    new Paragraph({ text: "Signature", alignment: AlignmentType.RIGHT }),
    new Paragraph({ children:[bold("System Administrator")], alignment: AlignmentType.RIGHT }),
]}]});

Packer.toBuffer(doc).then(buf => {
    fs.writeFileSync("rejection_notice.docx", buf);
    console.log("Done");
});
