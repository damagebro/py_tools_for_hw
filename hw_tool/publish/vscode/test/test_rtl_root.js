const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const root = path.resolve("workspace");
const resource = { fsPath: path.join(root, "top.toml") };
let configured = "";
let selected;
let warningAction;
let failInit = false;
const calls = [];
const updates = [];
const vscode = {
    Uri: { file: (fsPath) => ({ fsPath }) },
    ConfigurationTarget: { Workspace: 2, WorkspaceFolder: 3 },
    workspace: {
        workspaceFolders: [{ uri: { fsPath: root } }],
        getWorkspaceFolder: () => ({ uri: { fsPath: root } }),
        getConfiguration: () => ({
            get: () => configured,
            update: async (...args) => { updates.push(args); configured = args[1]; }
        })
    },
    window: {
        showOpenDialog: async () => selected,
        showQuickPick: async (items) => items[0],
        showWarningMessage: async () => warningAction,
        showInformationMessage: () => {}
    }
};
const load = Module._load;
Module._load = function(request, parent, isMain) {
    if (request === "vscode") return vscode;
    if (request === "../hw_tool_client") return { runHwTool: async (...args) => {
        calls.push(args);
        if (failInit) throw new Error("init failed");
    } };
    if (request === "../workspace_context") return { findRtlFlistWorkspace: async () => { throw new Error("missing marker"); } };
    return load.call(this, request, parent, isMain);
};
const { selectRtlRoot, resolveRtlRoot } = require("../src/tools/rtl_root");
Module._load = load;

(async () => {
    assert.equal(await selectRtlRoot(root, resource, {}, {}), undefined);
    assert.equal(calls.length, 0);
    assert.equal(await resolveRtlRoot(root, resource, {}, {}), undefined);
    selected = [{ fsPath: __dirname }];
    warningAction = "Select Root...";
    assert.equal(await resolveRtlRoot(root, resource, {}, {}), __dirname);
    assert.deepEqual(calls[0][1], ["rtl_flist_mgr", "--init-root", "-w", __dirname]);
    assert.deepEqual(updates[0], ["rtlFlist.rootDir", __dirname, 3]);
    assert.equal(await resolveRtlRoot(root, resource, {}, {}), __dirname);
    assert.equal(calls.length, 1);
    failInit = true;
    await assert.rejects(selectRtlRoot(root, resource, {}, {}), /init failed/);
    assert.equal(updates.length, 1);
    console.log("RTL root interaction tests passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
