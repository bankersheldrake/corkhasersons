"use strict";
exports.__esModule = true;
var ts = require("typescript");
var fs = require("fs");
var generateAst = function (node, sourceFile) {
    var _a, _b;
    var syntaxKind = ts.SyntaxKind[node.kind];
    var nodeText = node.getText(sourceFile);
    if (ts.isFunctionDeclaration(node)) {
        var functionName = (_a = node.name) === null || _a === void 0 ? void 0 : _a.getText(sourceFile);
        var parameters = node.parameters.map(function (param) { return param.getText(sourceFile); });
        var returnType = node.type ? node.type.getText(sourceFile) : "void";
        var leadingComments = ts.getLeadingCommentRanges(sourceFile.text, node.pos);
        var docstring = leadingComments && leadingComments.length > 0
            ? sourceFile.text.substring(leadingComments[0].pos, leadingComments[0].end)
            : "";
        var parsedObject = {
            type: syntaxKind,
            name: functionName || "",
            params: parameters,
            returnType: returnType,
            docstring: docstring
        };
        console.log(parsedObject);
    }
    else if (ts.isClassDeclaration(node) ||
        (ts.isTypeAliasDeclaration(node) && node.type && ts.isTypeLiteralNode(node.type))) {
        var typeName = (_b = node.name) === null || _b === void 0 ? void 0 : _b.getText(sourceFile);
        var leadingComments = ts.getLeadingCommentRanges(sourceFile.text, node.pos);
        var docstring = leadingComments && leadingComments.length > 0
            ? sourceFile.text.substring(leadingComments[0].pos, leadingComments[0].end)
            : "";
        var parsedObject = {
            type: syntaxKind,
            name: typeName || "",
            docstring: docstring
        };
        console.log(parsedObject);
    }
    node.forEachChild(function (child) { return generateAst(child, sourceFile); });
};
var old_generateAst = function (node, sourceFile) {
    var _a;
    var syntaxKind = ts.SyntaxKind[node.kind];
    var nodeText = node.getText(sourceFile);
    var parsedObject = {
        type: syntaxKind,
        name: "",
        params: []
    };
    if (ts.isFunctionDeclaration(node)) {
        console.log(node);
        var functionName = (_a = node.name) === null || _a === void 0 ? void 0 : _a.getText(sourceFile);
        if (functionName) {
            parsedObject.name = functionName;
            parsedObject.params = node.parameters.map(function (param) { return param.getText(sourceFile); });
            var leadingComments = ts.getLeadingCommentRanges(sourceFile.text, node.pos);
            if (leadingComments && leadingComments.length > 0) {
                parsedObject.docstring = sourceFile.text.substring(leadingComments[0].pos, leadingComments[0].end);
            }
            return parsedObject;
        }
    }
    node.forEachChild(function (child) { return generateAst(child, sourceFile); });
};
var parseFile = function (filePath) {
    fs.readFile(filePath, "utf-8", function (err, data) {
        if (err) {
            console.error("Error reading file:", err);
            return;
        }
        var sourceFile = ts.createSourceFile(filePath, data, ts.ScriptTarget.Latest);
        var parsedObjects = [];
        generateAst(sourceFile, sourceFile);
        fs.writeFile("output.json", JSON.stringify(parsedObjects, null, 2), function (err) {
            if (err) {
                console.error("Error writing to file:", err);
            }
            else {
                console.log("Parsing completed. Output saved to output.json.");
            }
        });
    });
};
// Usage: node parser.js <file-path>
var filePath = process.argv[2];
if (filePath) {
    parseFile(filePath);
}
else {
    console.error("Please provide a file path.");
}
