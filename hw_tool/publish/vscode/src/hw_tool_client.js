const childProcess = require("child_process");
const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");


function runProcess(command, args, cwd, output, processName, options = {}) {
    const echoStdout = options.echoStdout !== false;
    return new Promise((resolve, reject) => {
        let stdout = "";
        let stderr = "";
        output.appendLine(`> ${command} ${args.map((item) => JSON.stringify(item)).join(" ")}`);
        const child = childProcess.spawn(command, args, {
            cwd,
            windowsHide: true
        });
        child.stdout.on("data", (data) => {
            const text = data.toString();
            stdout += text;
            if (echoStdout) {
                output.append(text);
            }
        });
        child.stderr.on("data", (data) => {
            const text = data.toString();
            stderr += text;
            output.append(text);
        });
        child.on("error", reject);
        child.on("close", (code) => {
            if (code === 0) {
                resolve({ stdout, stderr });
            }
            else {
                reject(new Error(`${processName || path.basename(command)} exited with code ${code}`));
            }
        });
    });
}


async function runtimeHwToolPath(context) {
    const scriptPath = path.join(context.extensionPath, "runtime", "hw_tool", "src", "hw_tool.py");
    try {
        await fs.access(scriptPath);
        return scriptPath;
    }
    catch {
        throw new Error("Internal HW Tool runtime is missing. Reinstall the VSIX package.");
    }
}


function configuredPython(resource) {
    const configuration = vscode.workspace.getConfiguration("dmgHwTool", resource);
    return configuration.get("pythonPath", "python").trim() || "python";
}


async function checkPythonRuntime(pythonPath, cwd, output, packages = []) {
    const imports = packages.map((packageName) => `import ${packageName}`).join("; ");
    const code = [
        "import sys",
        imports,
        "print(f'Python {sys.version.split()[0]}')"
    ].filter(Boolean).join("; ");
    try {
        await runProcess(
            pythonPath,
            ["-B", "-c", code],
            cwd,
            output,
            "Python dependency check"
        );
    }
    catch (error) {
        const dependencyText = packages.length
            ? ` or missing ${packages.join("/")}`
            : "";
        throw new Error(`System Python is unavailable${dependencyText}: ${error.message}`);
    }
}


async function runHwTool(context, toolArgs, options) {
    const {
        cwd,
        output,
        processName,
        resource,
        requiredPackages = [],
        echoStdout = true
    } = options;
    const pythonPath = configuredPython(resource);
    const hwToolPath = await runtimeHwToolPath(context);
    await checkPythonRuntime(pythonPath, cwd, output, requiredPackages);
    return runProcess(
        pythonPath,
        ["-B", hwToolPath, "de", ...toolArgs],
        cwd,
        output,
        processName,
        { echoStdout }
    );
}


module.exports = {
    checkPythonRuntime,
    configuredPython,
    runHwTool,
    runProcess,
    runtimeHwToolPath
};
