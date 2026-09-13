const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const root = path.resolve("workspace");
const terminalDirectory = path.join(root, "subdir");
const commands = new Map();
const calls = [];
const opened = [];
const warnings = [];
let hasTemplate = false;
let hasState = false;
let mode;
let confirmation;
let exitCode = 0;
let failTemplate = false;
const output = { clear() {}, show() {}, appendLine() {} };
const vscode = {
    Uri: { file: (fsPath) => ({ fsPath }) },
    ProgressLocation: { Notification: 15 },
    commands: { registerCommand: (id, handler) => { commands.set(id, handler); return {}; } },
    workspace: { openTextDocument: async (uri) => { opened.push(uri.fsPath); return uri; } },
    window: {
        showTextDocument: async () => {},
        showInformationMessage() {},
        showErrorMessage: async () => {},
        showWarningMessage: async (message, options) => {
            warnings.push(message);
            return options?.modal ? confirmation : undefined;
        },
        showQuickPick: async (items) => mode === undefined ? undefined : items[mode],
        withProgress: async (_options, task) => task()
    }
};
const load = Module._load;
Module._load = function(request, parent, isMain) {
    if (request === "vscode") return vscode;
    if (request === "fs/promises") return { access: async (filename) => {
        if (filename.endsWith("resolved.toml") ? hasState : hasTemplate) return;
        throw Object.assign(new Error("missing"), { code: "ENOENT" });
    } };
    if (request === "../workspace_context") return {
        contextDirectory: async () => root,
        findGitRepoWorkspace: async () => root
    };
    if (request === "../hw_tool_client") return { runHwTool: async (_context, args, options) => {
        calls.push({ args, options });
        if (args[1] === "template" && failTemplate) throw new Error("template failed");
        return { code: exitCode, stdout: "Git Repository Status", stderr: "" };
    } };
    return load.call(this, request, parent, isMain);
};
const { registerGitRepoCommands } = require("../src/tools/git_repo");
Module._load = load;
registerGitRepoCommands({}, output);
const run = (name) => commands.get(`dmgHwTool.gitRepo.${name}`)();

(async () => {
    const manifest = require("../package.json");
    const registered = manifest.contributes.commands.filter((item) => item.command.startsWith("dmgHwTool.gitRepo."));
    assert.deepEqual(registered.map((item) => item.command).sort(), [...commands.keys()].sort());
    assert.equal(commands.size, 3);
    assert(!JSON.stringify(manifest).includes("gitRepo.graph"));
    await run("template");
    assert.equal(calls.length, 0);
    assert.equal(opened.length, 0);
    assert(warnings.pop().includes("Shell Integration"));
    vscode.window.activeTerminal = {};
    await run("template");
    assert.equal(calls.length, 0);
    assert.equal(opened.length, 0);
    vscode.window.activeTerminal = { shellIntegration: { cwd: { fsPath: terminalDirectory } } };
    await run("template");
    const templateCall = calls.pop();
    assert.deepEqual(templateCall.args, ["git_repo_mgr", "template", "-o", path.join(terminalDirectory, "git_deps.toml")]);
    assert.equal(templateCall.options.cwd, terminalDirectory);
    assert.equal(opened[0], path.join(terminalDirectory, "git_deps.toml"));
    assert.equal(opened.length, 1);
    hasTemplate = true;
    await run("template");
    assert.equal(calls.length, 0);
    assert.equal(opened.length, 2);
    assert.equal(opened[1], path.join(terminalDirectory, "git_deps.toml"));
    hasTemplate = false;
    failTemplate = true;
    await run("template");
    assert.equal(opened.length, 2);
    calls.length = 0;
    await run("status");
    assert.equal(calls.length, 0);
    assert(warnings.pop().includes("Sync Git Repositories"));
    hasState = true;
    exitCode = 1;
    await run("status");
    assert.deepEqual(calls.pop().options.acceptedExitCodes, [0, 1]);
    assert(warnings.pop().includes("needs attention"));
    await run("sync");
    assert.equal(calls.length, 0);
    mode = 0;
    await run("sync");
    assert.equal(calls.length, 0);
    assert(warnings.at(-1).includes(path.join(root, "import")));
    confirmation = "Sync";
    await run("sync");
    assert.deepEqual(calls.pop().args, ["git_repo_mgr", "sync", "--workspace", root]);
    mode = 1;
    await run("sync");
    assert.equal(calls.pop().args.at(-1), "--shallow");
    console.log("Git repository interaction tests passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
