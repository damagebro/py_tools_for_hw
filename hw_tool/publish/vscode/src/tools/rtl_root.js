const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");
const { runHwTool } = require("../hw_tool_client");
const { findRtlFlistWorkspace } = require("../workspace_context");

let sessionRoot;

async function selectRtlRoot(start, resource, context, output, candidates = []) {
    let root;
    if (candidates.length > 1) {
        const choice = await vscode.window.showQuickPick([
            ...candidates.map((value) => ({ label: value, root: value })),
            { label: "Browse for another root..." }
        ], { placeHolder: "Select the RTL workspace root" });
        if (!choice) {
            return undefined;
        }
        root = choice.root;
    }
    if (!root) {
        const folder = resource && vscode.workspace.getWorkspaceFolder(resource);
        const initial = folder?.uri || vscode.workspace.workspaceFolders?.[0]?.uri || (start && vscode.Uri.file(start));
        const selected = await vscode.window.showOpenDialog({
            canSelectFolders: true,
            canSelectFiles: false,
            canSelectMany: false,
            defaultUri: initial,
            openLabel: "Set RTL Root"
        });
        if (!selected?.length) {
            return undefined;
        }
        root = selected[0].fsPath;
    }
    if (!path.isAbsolute(root) || !(await fs.stat(root)).isDirectory()) {
        throw new Error(`RTL workspace root is not a directory: ${root}`);
    }
    await runHwTool(context, ["rtl_flist_mgr", "--init-root", "-w", root], {
        cwd: root, output, resource, processName: "Initialize RTL workspace"
    });
    const folder = resource && vscode.workspace.getWorkspaceFolder(resource);
    const scope = folder?.uri || vscode.workspace.workspaceFolders?.[0]?.uri;
    if (scope || vscode.workspace.workspaceFile) {
        await vscode.workspace.getConfiguration("dmgHwTool", scope).update(
            "rtlFlist.rootDir", root,
            folder ? vscode.ConfigurationTarget.WorkspaceFolder : vscode.ConfigurationTarget.Workspace
        );
    }
    else {
        sessionRoot = root;
    }
    vscode.window.showInformationMessage(`RTL root: ${root}${scope || vscode.workspace.workspaceFile ? "" : " (current session)"}`);
    return root;
}

async function resolveRtlRoot(start, resource, context, output) {
    const configScope = resource || vscode.workspace.workspaceFolders?.[0]?.uri;
    const configured = vscode.workspace.getConfiguration("dmgHwTool", configScope).get("rtlFlist.rootDir", "");
    try {
        const explicit = configured || sessionRoot;
        if (explicit) {
            if (!path.isAbsolute(explicit) || !(await fs.stat(explicit)).isDirectory()) {
                throw new Error(`Invalid configured RTL root: ${explicit}`);
            }
            return explicit;
        }
        return await findRtlFlistWorkspace(start);
    }
    catch (error) {
        const action = await vscode.window.showWarningMessage(error.message, "Select Root...");
        if (action !== "Select Root...") {
            return undefined;
        }
        return selectRtlRoot(start, resource, context, output, error.roots || []);
    }
}

module.exports = { resolveRtlRoot, selectRtlRoot };
