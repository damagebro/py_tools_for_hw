const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");
const { runHwTool } = require("../hw_tool_client");
const { contextDirectory } = require("../workspace_context");
const { resolveRtlRoot, selectRtlRoot } = require("./rtl_root");


const CORE_SUFFIXES = new Set([".toml", ".core"]);
const FLIST_MODES = [
    { label: "sim", description: "RTL, testbench, and simulation models" },
    { label: "synth", description: "Synthesis filelist" },
    { label: "lint", description: "Lint filelist" },
    { label: "emu", description: "Emulation filelist" },
    { label: "fpga", description: "FPGA filelist" }
];


function flistOutputPath(corePath, mode) {
    const parsed = path.parse(corePath);
    return path.join(parsed.dir, "out", "flist", `${parsed.name}_${mode}.f`);
}


function coreUriFromResource(resource) {
    const candidates = [
        resource,
        vscode.window.activeTextEditor?.document.uri,
        vscode.window.tabGroups?.activeTabGroup?.activeTab?.input?.uri
    ];
    return candidates.find(
        (uri) => uri?.fsPath && CORE_SUFFIXES.has(path.extname(uri.fsPath).toLowerCase())
    );
}


function parseCoreList(stdout, workspace) {
    const items = [];
    for (const line of stdout.split(/\r?\n/)) {
        const match = line.match(/^(\S+)\s{2,}(.+)$/);
        if (!match || match[1].endsWith(":")) {
            continue;
        }
        items.push({
            coreId: match[1],
            manifest: path.resolve(workspace, match[2].trim())
        });
    }
    return items;
}


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


class RtlCoreTreeProvider {
    constructor() {
        this.items = [];
        this.workspace = undefined;
        this.changeEmitter = new vscode.EventEmitter();
        this.onDidChangeTreeData = this.changeEmitter.event;
    }

    setItems(workspace, items) {
        this.workspace = workspace;
        this.items = items;
        this.changeEmitter.fire(undefined);
    }

    getTreeItem(item) {
        const treeItem = new vscode.TreeItem(item.coreId, vscode.TreeItemCollapsibleState.None);
        treeItem.description = path.relative(this.workspace, item.manifest).replaceAll("\\", "/");
        treeItem.tooltip = item.manifest;
        treeItem.iconPath = new vscode.ThemeIcon("symbol-namespace");
        treeItem.command = {
            command: "vscode.open",
            title: "Open RTL Core",
            arguments: [vscode.Uri.file(item.manifest)]
        };
        return treeItem;
    }

    getChildren() {
        return this.items;
    }
}


async function generateFlist(resource, context, output) {
    const coreUri = coreUriFromResource(resource);
    if (!coreUri) {
        vscode.window.showWarningMessage("Open or select a core .toml/.core file first.");
        return;
    }
    const mode = await vscode.window.showQuickPick(FLIST_MODES, {
        placeHolder: "Choose the RTL filelist mode"
    });
    if (!mode) {
        return;
    }
    const corePath = coreUri.fsPath;
    const outputPath = flistOutputPath(corePath, mode.label);
    try {
        await fs.access(corePath);
        if (!(await confirmOverwrite(outputPath))) {
            return;
        }
        const workspace = await resolveRtlRoot(path.dirname(corePath), coreUri, context, output);
        if (!workspace) {
            return;
        }
        const listing = await runHwTool(
            context,
            ["rtl_flist_mgr", "--list-core", "--all", "-w", workspace, "--rescan"],
            { cwd: workspace, output, processName: "rtl_flist_mgr --list-core", echoStdout: false, resource: coreUri }
        );
        const realCorePath = await fs.realpath(corePath);
        const matches = [];
        for (const item of parseCoreList(listing.stdout, workspace)) {
            if (await fs.realpath(item.manifest) === realCorePath) {
                matches.push(item);
            }
        }
        if (matches.length !== 1) {
            throw new Error("Selected file does not identify exactly one indexed RTL core.");
        }
        await fs.mkdir(path.dirname(outputPath), { recursive: true });
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Generating ${mode.label} filelist...`,
                cancellable: false
            },
            () => runHwTool(
                context,
                [
                    "rtl_flist_mgr",
                    "--core",
                    matches[0].coreId,
                    "-w",
                    workspace,
                    "-m",
                    mode.label,
                    "-o",
                    outputPath
                ],
                {
                    cwd: workspace,
                    output,
                    processName: "rtl_flist_mgr",
                    resource: coreUri
                }
            )
        );
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(outputPath));
        await vscode.window.showTextDocument(document);
        vscode.window.showInformationMessage(`RTL filelist generated: ${outputPath}`);
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            `RTL filelist generation failed: ${error.message}`,
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


async function refreshCoreList(resource, provider, context, output, selectedRoot) {
    const start = selectedRoot || await contextDirectory(resource);
    if (!start) {
        vscode.window.showWarningMessage("Open a file, Terminal, or workspace first.");
        return;
    }
    try {
        const workspace = selectedRoot || await resolveRtlRoot(start, resource || vscode.window.activeTextEditor?.document.uri, context, output);
        if (!workspace) {
            return;
        }
        const result = await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: "Scanning RTL cores...",
                cancellable: false
            },
            () => runHwTool(
                context,
                ["rtl_flist_mgr", "--list-core", "-w", workspace, "--rescan"],
                {
                    cwd: workspace,
                    output,
                    processName: "rtl_flist_mgr --list-core",
                    echoStdout: false
                }
            )
        );
        const items = parseCoreList(result.stdout, workspace);
        provider.setItems(workspace, items);
        vscode.window.showInformationMessage(
            `Found ${items.length} RTL core(s) in ${workspace}`
        );
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            `RTL core scan failed: ${error.message}`,
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


function registerRtlFlistCommands(context, output) {
    const provider = new RtlCoreTreeProvider();
    return [
        vscode.window.registerTreeDataProvider("dmgHwTool.rtlCores", provider),
        vscode.commands.registerCommand(
            "dmgHwTool.rtlFlist.setRoot",
            async (resource) => {
                try {
                    const uri = resource || vscode.window.activeTextEditor?.document.uri;
                    const root = await selectRtlRoot(await contextDirectory(uri), uri, context, output);
                    if (root) {
                        provider.setItems(root, []);
                        await refreshCoreList(uri, provider, context, output, root);
                    }
                }
                catch (error) {
                    output.appendLine(`[ERROR] ${error.message}`);
                    vscode.window.showErrorMessage(`Failed to set RTL root: ${error.message}`);
                }
            }
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.rtlFlist.generate",
            (resource) => generateFlist(resource, context, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.rtlFlist.refreshCores",
            (resource) => refreshCoreList(resource, provider, context, output)
        )
    ];
}


module.exports = {
    flistOutputPath,
    parseCoreList,
    registerRtlFlistCommands
};
