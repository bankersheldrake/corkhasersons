import * as ts from "typescript";
//@ts-ignore
import fs = require("fs");

interface ParsedObject {
  type: string;
  name: string;
  params: string[];
  docstring?: string;
}
let parsedObjects: ParsedObject[] = []; // Global array to store all parsed objects
const generateAst = (node: ts.Node, sourceFile: ts.SourceFile) => {
  const syntaxKind = ts.SyntaxKind[node.kind];
  const nodeText = node.getText(sourceFile);

  if (ts.isFunctionDeclaration(node)) {
    const functionName = node.name?.getText(sourceFile);
    const parameters = node.parameters.map((param) => param.getText(sourceFile));
    const returnType = node.type ? node.type.getText(sourceFile) : "void";

    const leadingComments = ts.getLeadingCommentRanges(sourceFile.text, node.pos);
    const docstring = leadingComments && leadingComments.length > 0
      ? sourceFile.text.substring(leadingComments[0].pos, leadingComments[0].end)
      : "";

    const parsedObject = {
      type: syntaxKind,
      name: functionName || "",
      params: parameters,
      returnType: returnType,
      docstring: docstring,
    };

    parsedObjects.push(parsedObject); // Add the parsed object to the global array
  }
  else if (
    ts.isClassDeclaration(node) ||
    (ts.isTypeAliasDeclaration(node) && node.type && ts.isTypeLiteralNode(node.type))
  ) {
    const typeName = node.name?.getText(sourceFile);

    const leadingComments = ts.getLeadingCommentRanges(sourceFile.text, node.pos);
    const docstring = leadingComments && leadingComments.length > 0
      ? sourceFile.text.substring(leadingComments[0].pos, leadingComments[0].end)
      : "";

    const parsedObject = {
      type: syntaxKind,
      name: typeName || "",
      docstring: docstring,
    };

    parsedObjects.push(parsedObject); // Add the parsed object to the global array
  }
  node.forEachChild((child) => generateAst(child, sourceFile));
};



const parseFile = (filePath: string) => {
  fs.readFile(filePath, "utf-8", (err, data) => {
    if (err) {
      console.error("Error reading file:", err);
      return;
    }

    const sourceFile = ts.createSourceFile(filePath, data, ts.ScriptTarget.Latest);
    //const parsedObjects: ParsedObject[] = [];
    generateAst(sourceFile, sourceFile);

    // Output the array of parsed objects to the console as a JSON string
    console.log(JSON.stringify(parsedObjects, null, 2));
  });
};

// Usage: node parser.js <file-path>
//@ts-ignore
const filePath = process.argv[2];
if (filePath) {
  parseFile(filePath);
} else {
  console.error("Please provide a file path.");
}
