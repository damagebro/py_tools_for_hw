const vscode = require("vscode");
const fs = require("fs/promises");
const path = require("path");
const { runHwTool } = require("../hw_tool_client");
const { contextDirectory, findGitRepoWorkspace } = require("../workspace_context");


const SYNC_MODES = [
    { label: "Full clone", description: "Keep complete Git history", shallow: false },
    { label: "Shallow clone", description: "Use depth 1 for new checkouts", shallow: true }
];


async function gitWorkspace(resource) {
    const start = await contextDirectory(resource);
    return start ? findGitRepoWorkspace(start) : undefined;
}


async function showGitFailure(title, error, output, warning = false) {
    output.appendLine(`[ERROR] ${error.message}`);
    const action = warning
        ? await vscode.window.showWarningMessage(title, "Show HW Tool Output")
        : await vscode.window.showErrorMessage(title, "Show HW Tool Output");
    if (action) {
        output.show(true);
    }
}


async function showRepositoryStatus(resource, context, output) {
    const workspace = await gitWorkspace(resource);
    if (!workspace) {
        vscode.window.showWarningMessage("Open a Git workspace first.");
        return;
    }
    output.clear();
    output.show(true);
    try {
        try {
            await fs.access(path.join(workspace, ".git_repo", "resolved.toml"));
        }
        catch (error) {
            if (error.code !== "ENOENT") throw error;
            vscode.window.showWarningMessage('No repository status yet. Run "HW Tool: Sync Git Repositories..." first.');
            return;
        }
        const result = await runHwTool(
            context,
            ["git_repo_mgr", "status", "--workspace", workspace],
            {
                cwd: workspace,
                output,
                processName: "git_repo_mgr status",
                acceptedExitCodes: [0, 1]
            }
        );
        if (result.code === 0) {
            vscode.window.showInformationMessage("All managed Git repositories are clean (not a remote freshness check).");
        }
        else {
            vscode.window.showWarningMessage("Repository status needs attention. See HW Tool Output for details.");
        }
    }
    catch (error) {
        await showGitFailure(
            "Repository status found missing, dirty, or invalid checkouts.",
            error,
            output,
            true
        );
    }
}


async function syncRepositories(resource, context, output) {
    const workspace = await gitWorkspace(resource);
    if (!workspace) {
        vscode.window.showWarningMessage("Open a Git workspace first.");
        return;
    }
    const mode = await vscode.window.showQuickPick(SYNC_MODES, {
        placeHolder: "Choose how new repositories are cloned"
    });
    if (!mode) {
        return;
    }
    const confirmation = await vscode.window.showWarningMessage(
        `Sync Git repositories?\nWorkspace: ${workspace}\nImport: ${path.join(workspace, "import")}\nClone: ${mode.label}\nExisting checkouts are kept; no automatic pull or version switch.`,
        { modal: true },
        "Sync"
    );
    if (confirmation !== "Sync") {
        return;
    }
    const args = ["git_repo_mgr", "sync", "--workspace", workspace];
    if (mode.shallow) {
        args.push("--shallow");
    }
    output.show(true);
    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: "Synchronizing Git repositories...",
                cancellable: false
            },
            () => runHwTool(
                context,
                args,
                {
                    cwd: workspace,
                    output,
                    processName: "git_repo_mgr sync"
                }
            )
        );
        vscode.window.showInformationMessage(`Git repositories synchronized: ${workspace}`);
    }
    catch (error) {
        await showGitFailure(`Repository synchronization failed: ${error.message}`, error, output);
    }
}


async function createGitDependencies(resource, context, output) {
    const terminalDirectory = vscode.window.activeTerminal?.shellIntegration?.cwd?.fsPath;
    if (!terminalDirectory) {
        vscode.window.showWarningMessage("Open an active Terminal with Shell Integration before creating Git dependencies.");
        return;
    }
    const filename = path.join(terminalDirectory, "git_deps.toml");
    try {
        try {
            await fs.access(filename);
        }
        catch (error) {
            if (error.code !== "ENOENT") throw error;
            await runHwTool(context, ["git_repo_mgr", "template", "-o", filename], {
                cwd: terminalDirectory, output, processName: "git_repo_mgr template"
            });
        }
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(filename));
        await vscode.window.showTextDocument(document, { preview: true });
    }
    catch (error) {
        await showGitFailure(`Unable to create or open Git dependencies: ${error.message}`, error, output);
    }
}


function registerGitRepoCommands(context, output) {
    return [
        vscode.commands.registerCommand(
            "dmgHwTool.gitRepo.status",
            (resource) => showRepositoryStatus(resource, context, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.gitRepo.sync",
            (resource) => syncRepositories(resource, context, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.gitRepo.template",
            (resource) => createGitDependencies(resource, context, output)
        )
    ];
}


module.exports = { registerGitRepoCommands };
