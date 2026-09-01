const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");
const { runHwTool } = require("../hw_tool_client");


const EXCEL_SUFFIX = ".xlsx";


function memoryInitOutputDirectory(baseDirectory) {
    return path.join(baseDirectory, "out", "mem_tool");
}


function activeTerminalDirectory() {
    return vscode.window.activeTerminal?.shellIntegration?.cwd?.fsPath;
}


function activeTabUri() {
    return vscode.window.tabGroups?.activeTabGroup?.activeTab?.input?.uri;
}


function excelUriFromResource(resource) {
    const candidates = [
        resource,
        vscode.window.activeTextEditor?.document.uri,
        activeTabUri()
    ];
    return candidates.find(
        (uri) => uri?.fsPath && path.extname(uri.fsPath).toLowerCase() === EXCEL_SUFFIX
    );
}


function generatedSvPaths(directory, prefix, names) {
    const filePrefix = `${prefix}_`;
    return names
        .filter((name) => name.startsWith(filePrefix) && name.toLowerCase().endsWith(".sv"))
        .map((name) => path.join(directory, name));
}


function preferredMemoryShell(paths) {
    return [...paths].sort((left, right) => {
        const leftName = path.basename(left);
        const rightName = path.basename(right);
        const score = (name) => {
            if (name.endsWith("_spram_shell.sv") && !name.includes("_ecc_")) {
                return 0;
            }
            if (name.endsWith("_shell.sv")) {
                return 1;
            }
            return 2;
        };
        return score(leftName) - score(rightName) || leftName.localeCompare(rightName);
    })[0];
}


async function openGeneratedMemoryShell(directory, prefix) {
    const names = await fs.readdir(directory);
    const shellPath = preferredMemoryShell(generatedSvPaths(directory, prefix, names));
    if (!shellPath) {
        return;
    }
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(shellPath));
    await vscode.window.showTextDocument(document);
}


async function promptSubsystemPrefix() {
    const prefix = await vscode.window.showInputBox({
        prompt: "Subsystem prefix used in generated SRAM shell names",
        placeHolder: "cpu",
        validateInput: (value) => (
            /^[A-Za-z_][A-Za-z0-9_]*$/.test(value.trim())
                ? undefined
                : "Enter a valid subsystem prefix."
        )
    });
    return prefix?.trim();
}


async function generateMemoryShell(context, output) {
    const terminalDirectory = activeTerminalDirectory();
    if (!terminalDirectory) {
        vscode.window.showWarningMessage(
            "Open an active Terminal with Shell Integration before generating memory shells."
        );
        return;
    }
    const prefix = await promptSubsystemPrefix();
    if (!prefix) {
        return;
    }
    const outputDirectory = memoryInitOutputDirectory(terminalDirectory);
    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Generating ${prefix} memory shells...`,
                cancellable: false
            },
            () => runHwTool(
                context,
                ["mem_tool", "-p", prefix, "-m", "init", "-w", outputDirectory],
                {
                    cwd: terminalDirectory,
                    output,
                    processName: "mem_tool init",
                    requiredPackages: ["openpyxl"]
                }
            )
        );
        await openGeneratedMemoryShell(outputDirectory, prefix);
        vscode.window.showInformationMessage(`Memory shells generated: ${outputDirectory}`);
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            `Memory shell generation failed: ${error.message}`,
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


async function integrateMemoryFromExcel(resource, context, output) {
    const excelUri = excelUriFromResource(resource);
    if (!excelUri) {
        vscode.window.showWarningMessage("Open or select an SRAM .xlsx file first.");
        return;
    }
    const excelPath = excelUri.fsPath;
    const workDirectory = path.dirname(excelPath);
    const prefix = await promptSubsystemPrefix();
    if (!prefix) {
        return;
    }
    try {
        await fs.access(excelPath);
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Integrating memory from ${path.basename(excelPath)}...`,
                cancellable: false
            },
            () => runHwTool(
                context,
                [
                    "mem_tool",
                    "-p",
                    prefix,
                    "-m",
                    "inst",
                    "-w",
                    workDirectory,
                    "-x",
                    path.basename(excelPath)
                ],
                {
                    cwd: workDirectory,
                    output,
                    processName: "mem_tool inst",
                    resource: excelUri,
                    requiredPackages: ["openpyxl"]
                }
            )
        );
        await openGeneratedMemoryShell(workDirectory, prefix);
        vscode.window.showInformationMessage(`Memory integration completed: ${workDirectory}`);
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            `Memory integration failed: ${error.message}`,
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


function registerMemToolCommands(context, output) {
    return [
        vscode.commands.registerCommand(
            "dmgHwTool.memTool.init",
            () => generateMemoryShell(context, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.memTool.inst",
            (resource) => integrateMemoryFromExcel(resource, context, output)
        )
    ];
}


module.exports = {
    generatedSvPaths,
    memoryInitOutputDirectory,
    preferredMemoryShell,
    registerMemToolCommands
};
