const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");
const { runHwTool } = require("../hw_tool_client");


const FILELIST_SUFFIX = ".f";


function genTbOutputDirectory(baseDirectory) {
    return path.join(baseDirectory, "out", "sim");
}


function activeTerminalDirectory() {
    return vscode.window.activeTerminal?.shellIntegration?.cwd?.fsPath;
}


function activeTabUri() {
    return vscode.window.tabGroups?.activeTabGroup?.activeTab?.input?.uri;
}


function filelistUriFromResource(resource) {
    const candidates = [
        resource,
        vscode.window.activeTextEditor?.document.uri,
        activeTabUri()
    ];
    return candidates.find(
        (uri) => uri?.fsPath && path.extname(uri.fsPath).toLowerCase() === FILELIST_SUFFIX
    );
}


async function confirmDirectoryOverwrite(directory) {
    try {
        await fs.access(directory);
        const action = await vscode.window.showWarningMessage(
            `${directory} already exists and generated files may be overwritten.`,
            { modal: true },
            "Generate"
        );
        return action === "Generate";
    }
    catch {
        return true;
    }
}


async function showTbResult(outputDirectory) {
    const action = await vscode.window.showInformationMessage(
        `TB environment generated: ${outputDirectory}`,
        "Open Generated README",
        "Open Terminal"
    );
    if (action === "Open Generated README") {
        const uri = vscode.Uri.file(path.join(outputDirectory, "README.md"));
        await vscode.commands.executeCommand("markdown.showPreview", uri);
    }
    else if (action === "Open Terminal") {
        vscode.window.createTerminal({ name: "HW Tool TB", cwd: outputDirectory }).show();
    }
}


async function generateTb(outputDirectory, args, resource, context, output) {
    if (!(await confirmDirectoryOverwrite(outputDirectory))) {
        return;
    }
    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: "Generating TB environment...",
            cancellable: false
        },
        () => runHwTool(
            context,
            ["gen_tb", "-o", outputDirectory, ...args],
            {
                cwd: path.dirname(path.dirname(outputDirectory)),
                output,
                processName: "gen_tb",
                resource
            }
        )
    );
    await showTbResult(outputDirectory);
}


async function generateEmptyTb(context, output) {
    const terminalDirectory = activeTerminalDirectory();
    if (!terminalDirectory) {
        vscode.window.showWarningMessage(
            "Open an active Terminal with Shell Integration before generating an empty TB."
        );
        return;
    }
    try {
        await generateTb(
            genTbOutputDirectory(terminalDirectory),
            [],
            undefined,
            context,
            output
        );
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            `TB generation failed: ${error.message}`,
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


async function generateTbFromFilelist(resource, context, output) {
    const filelistUri = filelistUriFromResource(resource);
    if (!filelistUri) {
        vscode.window.showWarningMessage("Open or select an RTL .f filelist first.");
        return;
    }
    const topModule = await vscode.window.showInputBox({
        prompt: "DUT top module name",
        placeHolder: "soc_top",
        validateInput: (value) => (
            /^[A-Za-z_][A-Za-z0-9_$]*$/.test(value.trim())
                ? undefined
                : "Enter a valid Verilog module identifier."
        )
    });
    if (!topModule) {
        return;
    }
    const filelistPath = filelistUri.fsPath;
    try {
        await fs.access(filelistPath);
        await generateTb(
            genTbOutputDirectory(path.dirname(filelistPath)),
            ["-t", topModule.trim(), "-f", filelistPath],
            filelistUri,
            context,
            output
        );
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            `TB generation failed: ${error.message}`,
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


function registerGenTbCommands(context, output) {
    return [
        vscode.commands.registerCommand(
            "dmgHwTool.genTb.empty",
            () => generateEmptyTb(context, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.genTb.fromFilelist",
            (resource) => generateTbFromFilelist(resource, context, output)
        )
    ];
}


module.exports = { genTbOutputDirectory, registerGenTbCommands };
