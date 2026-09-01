const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");


const originalLoad = Module._load;
Module._load = function loadWithVscodeStub(request, parent, isMain) {
    if (request === "vscode") {
        return {};
    }
    return originalLoad.call(this, request, parent, isMain);
};

const {
    selectedAbsoluteRtlPath,
    stripPathDelimiters
} = require("../src/editor_context");
const { dummyOutputPath } = require("../src/tools/rtl_dummy");
const { genTbOutputDirectory } = require("../src/tools/gen_tb");
const {
    generatedSvPaths,
    memoryInitOutputDirectory,
    preferredMemoryShell
} = require("../src/tools/mem_tool");
const { flistOutputPath, parseCoreList } = require("../src/tools/rtl_flist");
const { ancestorDirectories } = require("../src/workspace_context");

Module._load = originalLoad;


function testSelectedRtlPath() {
    const rtlPath = path.resolve("workspace", "rtl", "module.sv");
    assert.equal(stripPathDelimiters(`\"${rtlPath}\"`), rtlPath);
    assert.equal(stripPathDelimiters(`'${rtlPath}'`), rtlPath);
    const editor = {
        selection: { isEmpty: false },
        document: { getText: () => `\"${rtlPath}\"` }
    };
    assert.equal(selectedAbsoluteRtlPath(editor), path.normalize(rtlPath));
}


function testDummyOutputPath() {
    const source = path.resolve("workspace", "rtl", "abc.sv");
    assert.equal(
        dummyOutputPath(source, "bbox"),
        path.resolve("workspace", "rtl", "out", "rtl_dummy", "abc_bbox.sv")
    );
    assert.equal(
        dummyOutputPath(source, "port_swap"),
        path.resolve("workspace", "rtl", "out", "rtl_dummy", "abc_port_swap.sv")
    );
}


function testGenTbOutputPath() {
    const cwd = path.resolve("workspace", "sim_project");
    assert.equal(
        genTbOutputDirectory(cwd),
        path.resolve("workspace", "sim_project", "out", "sim")
    );
}


function testMemoryHelpers() {
    const cwd = path.resolve("workspace", "memory_project");
    assert.equal(
        memoryInitOutputDirectory(cwd),
        path.resolve("workspace", "memory_project", "out", "mem_tool")
    );
    const spram = path.resolve(cwd, "cpu_spram_shell.sv");
    const ecc = path.resolve(cwd, "cpu_ecc_spram_shell.sv");
    assert.deepEqual(
        generatedSvPaths(
            cwd,
            "cpu",
            ["cpu_ecc_spram_shell.sv", "cpu_spram_shell.sv", "npu_spram_shell.sv"]
        ),
        [ecc, spram]
    );
    assert.equal(preferredMemoryShell([ecc, spram]), spram);
}


function testRtlFlistHelpers() {
    const workspace = path.resolve("workspace");
    const core = path.resolve(workspace, "filelist", "soc.toml");
    assert.equal(
        flistOutputPath(core, "synth"),
        path.resolve(workspace, "filelist", "out", "flist", "soc_synth.f")
    );
    const items = parseCoreList(
        "root_dir: C:/workspace (--workspace)\n" +
        "dmg:soc:top                               soc.toml\n",
        workspace
    );
    assert.equal(items.length, 1);
    assert.equal(items[0].coreId, "dmg:soc:top");
    assert.equal(items[0].manifest, path.resolve(workspace, "soc.toml"));
}


function testAncestorDirectories() {
    const target = path.resolve("workspace", "import", "cpu");
    const ancestors = ancestorDirectories(target);
    assert.equal(ancestors[0], target);
    assert.equal(ancestors[1], path.dirname(target));
    assert.equal(ancestors.at(-1), path.parse(target).root);
}


testSelectedRtlPath();
testDummyOutputPath();
testGenTbOutputPath();
testMemoryHelpers();
testRtlFlistHelpers();
testAncestorDirectories();
console.log("helper tests passed");
