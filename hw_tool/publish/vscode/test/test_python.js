const assert = require("node:assert/strict");
const path = require("node:path");
const { EventEmitter } = require("node:events");
const Module = require("node:module");
const calls = [];
let replies = [];
const executable = path.resolve("Python311/python.exe");
const output = { append() {}, appendLine() {} };
const load = Module._load;
Module._load = function(request, parent, isMain) {
    if (request === "vscode") return { workspace: { getConfiguration: () => ({ get: (_key, fallback) => fallback }) } };
    if (request === "child_process") return { spawn(command, args) {
        calls.push([command, args]);
        const child = new EventEmitter();
        child.stdout = new EventEmitter();
        child.stderr = new EventEmitter();
        const reply = replies.shift();
        process.nextTick(() => {
            if (!reply) return child.emit("error", new Error("ENOENT"));
            child.stdout.emit("data", Buffer.from(reply.text || ""));
            child.emit("close", reply.code || 0);
        });
        return child;
    } };
    return load.call(this, request, parent, isMain);
};
const { resolvePython, checkPythonRuntime, configuredPython } = require("../src/hw_tool_client");
Module._load = load;
const version = (minor) => ({ text: JSON.stringify({ version: [3, minor, 0], executable }) });
function reset(values) { calls.length = 0; replies = values; }
(async () => {
    assert.equal(configuredPython(), "");
    reset([version(10), version(11)]);
    assert.equal(await resolvePython("", __dirname, output, "linux"), executable);
    assert.deepEqual(calls.map(c => c[0]), ["python", "python3"]);
    reset([null, null, version(12)]);
    assert.equal(await resolvePython("", __dirname, output, "win32"), executable);
    assert.equal(calls[2][0], "py");
    assert.equal(calls[2][1][0], "-3");
    reset([version(10), version(12)]);
    await assert.rejects(resolvePython("custom-python", __dirname, output), /Configured Python is invalid/);
    assert.equal(calls.length, 1);
    reset([version(11), { code: 1 }]);
    await assert.rejects(checkPythonRuntime("custom-python", __dirname, output, ["markdown"]), /dependency check failed/);
    assert.equal(calls.length, 2);
    assert.equal(calls[1][0], executable);
    reset([version(11), { text: "OK" }]);
    assert.equal(await checkPythonRuntime("custom-python", __dirname, output, ["markdown"]), executable);
    reset([]);
    await assert.rejects(resolvePython("", __dirname, output, "linux"), /No Python 3.11\+ found/);
    assert.equal(calls.length, 2);
    reset([{ text: "not Python" }, version(11)]);
    assert.equal(await resolvePython("", __dirname, output, "linux"), executable);
    console.log("Python discovery tests passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
