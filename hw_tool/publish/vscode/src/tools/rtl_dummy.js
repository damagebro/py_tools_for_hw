const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");
const { requireRtlFile, rtlUriFromResource } = require("../editor_context");
const { runHwTool } = require("../hw_tool_client");


const DUMMY_MODES = [
    { label: "bbox", description: "Keep port directions and tie ordinary outputs to zero" },
    { label: "stub", description: "Keep only module, parameter, and port declarations" },
    { label: "port_swap", description: "Swap ordinary input/output ports and i_/o_ prefixes" }
];


async function confirmOverwrite(outputPath) {
    try {
        await fs.access(outputPath);
        const action = await vscode.window.showWarningMessage(
            `${outputPath} already exists.`,
            { modal: true },
            "Overwrite"
        );
        return action === "Overwrite";
    }
    catch {
        return true;
    }
}


function dummyOutputPath(sourcePath, mode) {
    const parsed = path.parse(sourcePath);
    return path.join(parsed.dir, "out", "rtl_dummy", `${parsed.name}_${mode}.sv`);
}


async function generateRtlDummy(resource, context, output) {
    const sourceUri = rtlUriFromResource(resource);
    if (!sourceUri) {
        vscode.window.showWarningMessage("Open or select a Verilog/SystemVerilog file first.");
        return;
    }
    const mode = await vscode.window.showQuickPick(DUMMY_MODES, {
        placeHolder: "Choose the RTL dummy mode"
    });
    if (!mode) {
        return;
    }

    const sourcePath = sourceUri.fsPath;
    const outputPath = dummyOutputPath(sourcePath, mode.label);
    try {
        await requireRtlFile(sourcePath);
        if (!(await confirmOverwrite(outputPath))) {
            return;
        }
        await fs.mkdir(path.dirname(outputPath), { recursive: true });
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Generating ${mode.label} for ${path.basename(sourcePath)}...`,
                cancellable: false
            },
            () => runHwTool(
                context,
                ["rtl_dummy", sourcePath, "-m", mode.label, "-o", outputPath],
                {
                    cwd: path.dirname(sourcePath),
                    output,
                    processName: "rtl_dummy",
                    resource: sourceUri
                }
            )
        );
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(outputPath));
        await vscode.window.showTextDocument(document);
        vscode.window.showInformationMessage(`RTL dummy generated: ${outputPath}`);
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            `RTL dummy generation failed: ${error.message}`,
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


function registerRtlDummyCommands(context, output) {
    return [
        vscode.commands.registerCommand(
            "dmgHwTool.rtlDummy.generate",
            (resource) => generateRtlDummy(resource, context, output)
        )
    ];
}


module.exports = { dummyOutputPath, registerRtlDummyCommands };
