const path = require("path");
const vscode = require("vscode");
const {
    activeRtlEditor,
    chooseRtlFile,
    isRtlUri,
    requireRtlFile,
    selectedAbsoluteRtlPath
} = require("../editor_context");
const { runHwTool } = require("../hw_tool_client");


async function generateInstance(context, output, rtlPath, resource) {
    await requireRtlFile(rtlPath);
    const result = await runHwTool(
        context,
        ["rtl_inst", rtlPath, "--stdout"],
        {
            cwd: path.dirname(rtlPath),
            output,
            processName: "rtl_inst",
            resource,
            echoStdout: false
        }
    );
    if (!result.stdout.trim()) {
        throw new Error("rtl_inst returned an empty instance snippet.");
    }
    return result.stdout;
}


async function showCommandError(message, error, output) {
    output.appendLine(`[ERROR] ${error.message}`);
    const action = await vscode.window.showErrorMessage(
        `${message}: ${error.message}`,
        "Show HW Tool Output"
    );
    if (action) {
        output.show(true);
    }
}


async function replaceSelectedPath(context, output) {
    const editor = activeRtlEditor();
    if (!editor) {
        return;
    }
    const selection = editor.selection;
    try {
        const rtlPath = selectedAbsoluteRtlPath(editor);
        const snippet = await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Generating instance for ${path.basename(rtlPath)}...`,
                cancellable: false
            },
            () => generateInstance(context, output, rtlPath, editor.document.uri)
        );
        const applied = await editor.edit((builder) => builder.replace(selection, snippet));
        if (!applied) {
            throw new Error("VS Code rejected the editor replacement.");
        }
    }
    catch (error) {
        await showCommandError("Unable to replace the selected RTL path", error, output);
    }
}


async function insertFromFile(context, output) {
    const editor = activeRtlEditor();
    if (!editor) {
        return;
    }
    const sourceUri = await chooseRtlFile(path.dirname(editor.document.uri.fsPath));
    if (!sourceUri) {
        return;
    }
    try {
        const snippet = await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Generating instance for ${path.basename(sourceUri.fsPath)}...`,
                cancellable: false
            },
            () => generateInstance(context, output, sourceUri.fsPath, editor.document.uri)
        );
        const position = editor.selection.active;
        const applied = await editor.edit((builder) => builder.insert(position, snippet));
        if (!applied) {
            throw new Error("VS Code rejected the editor insertion.");
        }
    }
    catch (error) {
        await showCommandError("Unable to insert the RTL instance", error, output);
    }
}


async function copyInstanceToClipboard(sourceUri, context, output) {
    const snippet = await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: `Generating instance for ${path.basename(sourceUri.fsPath)}...`,
            cancellable: false
        },
        () => generateInstance(context, output, sourceUri.fsPath, sourceUri)
    );
    await vscode.env.clipboard.writeText(snippet);
    vscode.window.showInformationMessage(
        `RTL instance copied to clipboard: ${path.basename(sourceUri.fsPath)}`
    );
}


async function copyRtlInstance(resource, context, output) {
    const editor = vscode.window.activeTextEditor;
    let sourceUri = isRtlUri(resource) ? resource : undefined;
    if (!sourceUri) {
        const activeEditor = activeRtlEditor();
        if (!activeEditor) {
            return;
        }
        sourceUri = activeEditor.document.uri;
    }
    if (
        editor?.document.uri.fsPath === sourceUri.fsPath &&
        editor.document.isDirty &&
        !(await editor.document.save())
    ) {
        vscode.window.showWarningMessage(
            "Save the selected RTL file before generating its instance."
        );
        return;
    }
    try {
        await copyInstanceToClipboard(sourceUri, context, output);
    }
    catch (error) {
        await showCommandError("Unable to copy the RTL instance", error, output);
    }
}


function registerRtlInstCommands(context, output) {
    return [
        vscode.commands.registerCommand(
            "dmgHwTool.rtlInst.replaceSelectedPath",
            () => replaceSelectedPath(context, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.rtlInst.insertFromFile",
            () => insertFromFile(context, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.rtlInst.copy",
            (resource) => copyRtlInstance(resource, context, output)
        )
    ];
}


module.exports = { registerRtlInstCommands };
