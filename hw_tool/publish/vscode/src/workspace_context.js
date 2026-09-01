const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");


async function pathExists(target) {
    try {
        await fs.access(target);
        return true;
    }
    catch {
        return false;
    }
}


function ancestorDirectories(start) {
    const directories = [];
    let current = path.resolve(start);
    while (true) {
        directories.push(current);
        const parent = path.dirname(current);
        if (parent === current) {
            return directories;
        }
        current = parent;
    }
}


async function directoryForUri(uri) {
    if (!uri?.fsPath) {
        return undefined;
    }
    try {
        return (await fs.stat(uri.fsPath)).isDirectory()
            ? uri.fsPath
            : path.dirname(uri.fsPath);
    }
    catch {
        return path.dirname(uri.fsPath);
    }
}


async function contextDirectory(resource) {
    const candidates = [
        resource,
        vscode.window.activeTextEditor?.document.uri,
        vscode.window.tabGroups?.activeTabGroup?.activeTab?.input?.uri
    ];
    for (const candidate of candidates) {
        const directory = await directoryForUri(candidate);
        if (directory) {
            return directory;
        }
    }
    const terminalCwd = vscode.window.activeTerminal?.shellIntegration?.cwd?.fsPath;
    if (terminalCwd) {
        return terminalCwd;
    }
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}


async function findRtlFlistWorkspace(start) {
    for (const candidate of ancestorDirectories(start)) {
        if (await pathExists(path.join(candidate, ".rtl_flist"))) {
            return candidate;
        }
        if (await pathExists(path.join(candidate, "import"))) {
            return candidate;
        }
    }
    return path.resolve(start);
}


async function findGitRepoWorkspace(start) {
    let manifestRoot;
    let gitRoot;
    for (const candidate of ancestorDirectories(start)) {
        if (await pathExists(path.join(candidate, ".git_repo", "resolved.toml"))) {
            return candidate;
        }
        if (!manifestRoot && await pathExists(path.join(candidate, "git_deps.toml"))) {
            manifestRoot = candidate;
        }
        if (!gitRoot && await pathExists(path.join(candidate, ".git"))) {
            gitRoot = candidate;
        }
    }
    return manifestRoot || gitRoot || path.resolve(start);
}


module.exports = {
    ancestorDirectories,
    contextDirectory,
    findGitRepoWorkspace,
    findRtlFlistWorkspace
};
