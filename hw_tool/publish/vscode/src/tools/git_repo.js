const vscode = require("vscode");
const { runHwTool } = require("../hw_tool_client");
const { contextDirectory, findGitRepoWorkspace } = require("../workspace_context");


const SYNC_MODES = [
    { label: "Full clone", description: "Keep complete Git history", shallow: false },
    { label: "Shallow clone", description: "Use depth 1 for new checkouts", shallow: true }
];
const GRAPH_FORMATS = [
    { label: "Dependency tree", description: "Human-readable repository tree", value: "tree", language: "plaintext" },
    { label: "Graph JSON", description: "Machine-readable nodes and edges", value: "json", language: "json" }
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
        await runHwTool(
            context,
            ["git_repo_mgr", "status", "--top", workspace],
            {
                cwd: workspace,
                output,
                processName: "git_repo_mgr status"
            }
        );
        vscode.window.showInformationMessage("All managed Git repositories are clean.");
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
        `Sync recursive Git dependencies in ${workspace}?`,
        { modal: true },
        "Sync"
    );
    if (confirmation !== "Sync") {
        return;
    }
    const args = ["git_repo_mgr", "sync", "--top", workspace];
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


async function openDependencyGraph(resource, context, output) {
    const workspace = await gitWorkspace(resource);
    if (!workspace) {
        vscode.window.showWarningMessage("Open a Git workspace first.");
        return;
    }
    const format = await vscode.window.showQuickPick(GRAPH_FORMATS, {
        placeHolder: "Choose repository graph format"
    });
    if (!format) {
        return;
    }
    try {
        const result = await runHwTool(
            context,
            ["git_repo_mgr", "graph", "--top", workspace, "--format", format.value],
            {
                cwd: workspace,
                output,
                processName: "git_repo_mgr graph",
                echoStdout: false
            }
        );
        const document = await vscode.workspace.openTextDocument({
            content: result.stdout,
            language: format.language
        });
        await vscode.window.showTextDocument(document, { preview: true });
    }
    catch (error) {
        await showGitFailure(`Unable to open repository graph: ${error.message}`, error, output);
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
            "dmgHwTool.gitRepo.graph",
            (resource) => openDependencyGraph(resource, context, output)
        )
    ];
}


module.exports = { registerGitRepoCommands };
