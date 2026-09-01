const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");


const RTL_SUFFIXES = new Set([".v", ".sv"]);


function isRtlUri(uri) {
    return Boolean(uri?.fsPath) && RTL_SUFFIXES.has(path.extname(uri.fsPath).toLowerCase());
}


function activeRtlEditor() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || !isRtlUri(editor.document.uri)) {
        vscode.window.showWarningMessage("Open an editable Verilog/SystemVerilog file first.");
        return undefined;
    }
    return editor;
}


function rtlUriFromResource(resource) {
    if (isRtlUri(resource)) {
        return resource;
    }
    const editor = vscode.window.activeTextEditor;
    return isRtlUri(editor?.document.uri) ? editor.document.uri : undefined;
}


function stripPathDelimiters(value) {
    let text = value.trim();
    const pairs = [
        ["\"", "\""],
        ["'", "'"],
        ["`", "`"],
        ["<", ">"]
    ];
    for (const [left, right] of pairs) {
        if (text.startsWith(left) && text.endsWith(right) && text.length >= 2) {
            text = text.slice(1, -1).trim();
            break;
        }
    }
    return text;
}


function selectedAbsoluteRtlPath(editor) {
    if (editor.selection.isEmpty) {
        throw new Error("Select one absolute RTL file path first.");
    }
    const selectedText = stripPathDelimiters(editor.document.getText(editor.selection));
    if (!selectedText || /[\r\n]/.test(selectedText)) {
        throw new Error("The selected RTL path must be on one line.");
    }
    if (!path.isAbsolute(selectedText)) {
        throw new Error(`The selected RTL path is not absolute: ${selectedText}`);
    }
    if (!RTL_SUFFIXES.has(path.extname(selectedText).toLowerCase())) {
        throw new Error("The selected file must use the .v or .sv suffix.");
    }
    return path.normalize(selectedText);
}


async function requireRtlFile(filePath) {
    try {
        const stat = await fs.stat(filePath);
        if (!stat.isFile()) {
            throw new Error("not a file");
        }
    }
    catch {
        throw new Error(`RTL file not found: ${filePath}`);
    }
}


async function chooseRtlFile(defaultDirectory) {
    const selected = await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        canSelectMany: false,
        defaultUri: defaultDirectory ? vscode.Uri.file(defaultDirectory) : undefined,
        filters: {
            "RTL files": ["v", "sv"]
        },
        openLabel: "Select RTL File"
    });
    return selected?.[0];
}


module.exports = {
    RTL_SUFFIXES,
    activeRtlEditor,
    chooseRtlFile,
    isRtlUri,
    requireRtlFile,
    rtlUriFromResource,
    selectedAbsoluteRtlPath,
    stripPathDelimiters
};
