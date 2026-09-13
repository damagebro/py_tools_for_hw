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
            if ((options.acceptedExitCodes || [0]).includes(code)) {
                resolve({ stdout, stderr, code });
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
    return configuration.get("pythonPath", "").trim();
}


async function resolvePython(configured, cwd, output, platform = process.platform) {
    const candidates = configured ? [[configured, []]] : [
        ["python", []], ["python3", []], ...(platform === "win32" ? [["py", ["-3"]]] : [])
    ];
    const failures = [];
    const probe = "import sys,json; print(json.dumps({'version':list(sys.version_info[:3]),'executable':sys.executable}))";
    for (const [command, prefix] of candidates) {
        try {
            const result = await runProcess(command, [...prefix, "-B", "-c", probe], cwd, output, "Python version check", { echoStdout: false });
            const info = JSON.parse(result.stdout.trim());
            if (!Array.isArray(info.version) || info.version.length < 2 ||
                !info.version.every(Number.isInteger) ||
                !(info.version[0] > 3 || (info.version[0] === 3 && info.version[1] >= 11))) {
                throw new Error(`Python ${info.version} does not meet Python 3.11+`);
            }
            if (typeof info.executable !== "string" || !path.isAbsolute(info.executable)) {
                throw new Error("Python did not report an absolute executable path");
            }
            output.appendLine(`Python ${info.version.join(".")}: ${info.executable}`);
            return info.executable;
        }
        catch (error) {
            failures.push(`${command}: ${error.message}`);
        }
    }
    throw new Error(`${configured ? "Configured Python is invalid" : "No Python 3.11+ found"}. Set dmgHwTool.pythonPath or install Python 3.11+. ${failures.join("; ")}`);
}


async function checkPythonRuntime(pythonPath, cwd, output, packages = []) {
    const executable = await resolvePython(pythonPath, cwd, output);
    if (!packages.length) return executable;
    const imports = packages.map((packageName) => `import ${packageName}`).join("; ");
    const code = [
        "import sys",
        imports,
        "print(f'Python {sys.version.split()[0]}')"
    ].filter(Boolean).join("; ");
    try {
        await runProcess(
            executable,
            ["-B", "-c", code],
            cwd,
            output,
            "Python dependency check"
        );
    }
    catch (error) {
        throw new Error(`Python dependency check failed for ${executable}. Install ${packages.join("/")} in this interpreter: ${error.message}`);
    }
    return executable;
}


async function runHwTool(context, toolArgs, options) {
    const {
        cwd,
        output,
        processName,
        resource,
        requiredPackages = [],
        echoStdout = true,
        acceptedExitCodes = [0]
    } = options;
    let pythonPath = configuredPython(resource);
    const hwToolPath = await runtimeHwToolPath(context);
    pythonPath = await checkPythonRuntime(pythonPath, cwd, output, requiredPackages);
    return runProcess(
        pythonPath,
        ["-X", "utf8", "-B", hwToolPath, "de", ...toolArgs],
        cwd,
        output,
        processName,
        { echoStdout, acceptedExitCodes }
    );
}


module.exports = {
    resolvePython,
    checkPythonRuntime,
    configuredPython,
    runHwTool,
    runProcess,
    runtimeHwToolPath
};
