const fs = require("fs/promises");
const path = require("path");
const vscode = require("vscode");
const {
    checkPythonRuntime,
    configuredPython,
    runProcess,
    runtimeHwToolPath
} = require("./hw_tool_client");
const { registerRtlDummyCommands } = require("./tools/rtl_dummy");
const { registerRtlInstCommands } = require("./tools/rtl_inst");
const { registerGenTbCommands } = require("./tools/gen_tb");
const { registerMemToolCommands } = require("./tools/mem_tool");
const { registerRtlFlistCommands } = require("./tools/rtl_flist");
const { registerGitRepoCommands } = require("./tools/git_repo");


const OUTPUT_CHANNEL_NAME = "HW Tool";
const CSR_EXTENSIONS = new Set([".md", ".xlsx"]);
const REGISTER_TYPES = [
    {
        label: "cfg",
        description: "RW configuration register",
        row: "|        | ctrl     | signal1 | 15  | 0   | RW        | 0x0           | cfg      | -                                        |             |"
    },
    {
        label: "status",
        description: "RO hardware status register",
        row: "|        | dbg      | signal1 | 15  | 0   | RO        |               | status   | -                                        |             |"
    },
    {
        label: "cmd",
        description: "W1T command register",
        row: "|        | cmd      | start   | 0   | 0   | W1T       | 0x0           | cmd      | -                                        |             |"
    },
    {
        label: "irq",
        description: "W1C interrupt register",
        row: "|        | irq      | info    | 31  | 0   | W1C       | 0x0           | irq      | -                                        |             |"
    },
    {
        label: "slave",
        description: "Nested CSR definition",
        row: "|        | slv1     |         |     |     |           |               | slave    | slv_filename=sub_node.md, bytesize=0x400 |             |"
    },
    {
        label: "mem",
        description: "Memory address range",
        row: "|        | slv2     |         |     |     |           |               | mem      | bytesize=0x100                           |             |"
    }
];
const CSR_TEMPLATE_CHOICES = [
    {
        label: "Markdown: reg_define only",
        description: "Create reg_define.md",
        extension: "md",
        baseInfo: false
    },
    {
        label: "Markdown: include base_info",
        description: "Create reg_define.md with base_info",
        extension: "md",
        baseInfo: true
    },
    {
        label: "Excel: reg_define only",
        description: "Create reg_define.xlsx",
        extension: "xlsx",
        baseInfo: false
    },
    {
        label: "Excel: include base_info",
        description: "Create reg_define.xlsx with base_info",
        extension: "xlsx",
        baseInfo: true
    }
];
const PREVIEW_THEME_CHOICES = [
    { label: "Light", description: "Use a light background", value: "light" },
    { label: "Dark", description: "Use a dark background", value: "dark" },
    { label: "Follow VS Code", description: "Follow the current VS Code color theme", value: "auto" }
];


function isCsrDocument(document) {
    return document && CSR_EXTENSIONS.has(path.extname(document.uri.fsPath).toLowerCase());
}


async function activeCsrEditor() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || !isCsrDocument(editor.document)) {
        vscode.window.showWarningMessage("Open a CSR .md or .xlsx definition first.");
        return undefined;
    }
    if (editor.document.isDirty && !(await editor.document.save())) {
        vscode.window.showWarningMessage("CSR generation requires the current file to be saved.");
        return undefined;
    }
    return editor;
}


function csrOutputDirectory(uri) {
    return path.join(path.dirname(uri.fsPath), "out");
}


async function toolDocumentSpecs(context) {
    const indexPath = path.join(
        context.extensionPath,
        "runtime",
        "hw_tool",
        "tool_docs.json"
    );
    let payload;
    try {
        payload = JSON.parse(await fs.readFile(indexPath, "utf-8"));
    }
    catch (error) {
        throw new Error(`Internal tool documentation index is unavailable: ${error.message}`);
    }
    if (!Array.isArray(payload.tools)) {
        throw new Error("Internal tool documentation index is invalid.");
    }
    return payload.tools;
}


function previewTheme(uri) {
    return vscode.workspace
        .getConfiguration("dmgHwTool.preview", uri)
        .get("theme", "light");
}


async function changePreviewTheme() {
    const currentTheme = previewTheme();
    const selected = await vscode.window.showQuickPick(
        PREVIEW_THEME_CHOICES.map((choice) => ({
            ...choice,
            picked: choice.value === currentTheme
        })),
        { placeHolder: "Choose the HW Tool documentation preview theme" }
    );
    if (!selected) {
        return;
    }
    await vscode.workspace
        .getConfiguration("dmgHwTool.preview")
        .update("theme", selected.value, vscode.ConfigurationTarget.Global);
    vscode.window.showInformationMessage(`HW Tool preview theme: ${selected.label}`);
}


async function openToolDocumentation(context, requestedName, output) {
    try {
        const documents = await toolDocumentSpecs(context);
        let selected = documents.find((item) => item.name === requestedName);
        if (!requestedName) {
            selected = await vscode.window.showQuickPick(
                documents.map((item) => ({
                    label: item.name,
                    description: item.description,
                    document: item
                })),
                { placeHolder: "Choose a hardware tool README" }
            );
            selected = selected?.document;
        }
        if (!selected) {
            if (requestedName) {
                throw new Error(`README is not registered for '${requestedName}'.`);
            }
            return;
        }
        const readmePath = path.resolve(
            context.extensionPath,
            "runtime",
            "hw_tool",
            selected.readme
        );
        await fs.access(readmePath);
        const previewDirectory = path.join(context.globalStorageUri.fsPath, "documentation");
        const htmlPath = path.join(
            previewDirectory,
            `${selected.name.replace(/[^A-Za-z0-9_.-]/g, "_")}.html`
        );
        await fs.mkdir(previewDirectory, { recursive: true });
        const readmeUri = vscode.Uri.file(readmePath);
        const pythonPath = configuredPython(readmeUri);
        const hwToolPath = await runtimeHwToolPath(context);
        const args = [
            "-B",
            hwToolPath,
            "de",
            "md2html",
            readmePath,
            "-o",
            htmlPath,
            "--toc",
            "--theme",
            previewTheme(readmeUri)
        ];
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Opening ${selected.name} documentation...`,
                cancellable: false
            },
            async () => {
                await checkPythonRuntime(
                    pythonPath,
                    path.dirname(readmePath),
                    output,
                    ["markdown"]
                );
                await runProcess(
                    pythonPath,
                    args,
                    path.dirname(readmePath),
                    output,
                    "md2html"
                );
            }
        );
        await openMarkdownHtml(htmlPath, path.dirname(readmePath));
    }
    catch (error) {
        vscode.window.showErrorMessage(`Unable to open tool documentation: ${error.message}`);
    }
}


async function treeHtmlCandidates(outputDirectory) {
    const docDirectory = path.join(outputDirectory, "doc");
    try {
        const entries = await fs.readdir(docDirectory, { withFileTypes: true });
        return entries
            .filter((entry) => entry.isFile() && entry.name.endsWith("_tree.html"))
            .map((entry) => path.join(docDirectory, entry.name));
    }
    catch {
        return [];
    }
}


async function openTreeHtml(outputDirectory) {
    const candidates = await treeHtmlCandidates(outputDirectory);
    if (!candidates.length) {
        vscode.window.showWarningMessage("No generated CSR tree HTML was found. Generate in nested mode first.");
        return;
    }
    let htmlPath = candidates[0];
    if (candidates.length > 1) {
        const selected = await vscode.window.showQuickPick(
            candidates.map((candidate) => ({ label: path.basename(candidate), value: candidate })),
            { placeHolder: "Choose CSR tree HTML" }
        );
        if (!selected) {
            return;
        }
        htmlPath = selected.value;
    }
    const panel = vscode.window.createWebviewPanel(
        "dmgHwTool.csrTree",
        path.basename(htmlPath),
        vscode.ViewColumn.Active,
        { enableScripts: true }
    );
    panel.webview.html = await fs.readFile(htmlPath, "utf-8");
}


async function activeMarkdownUri(resource) {
    const candidate = resource?.fsPath
        ? resource
        : vscode.window.activeTextEditor?.document.uri;
    const suffix = candidate?.fsPath
        ? path.extname(candidate.fsPath).toLowerCase()
        : "";
    if (!candidate || ![".md", ".markdown"].includes(suffix)) {
        vscode.window.showWarningMessage("Open a Markdown file first.");
        return undefined;
    }
    const editor = vscode.window.activeTextEditor;
    if (editor?.document.uri.fsPath === candidate.fsPath && editor.document.isDirty) {
        if (!(await editor.document.save())) {
            vscode.window.showWarningMessage(
                "Markdown conversion requires the current file to be saved."
            );
            return undefined;
        }
    }
    return candidate;
}


async function openMarkdownHtml(htmlPath, sourceDirectory) {
    const panel = vscode.window.createWebviewPanel(
        "dmgHwTool.markdownHtml",
        path.basename(htmlPath),
        vscode.ViewColumn.Active,
        {
            enableScripts: false,
            localResourceRoots: [vscode.Uri.file(sourceDirectory)]
        }
    );
    const assetRoot = panel.webview
        .asWebviewUri(vscode.Uri.file(sourceDirectory))
        .toString()
        .replace(/\/?$/, "/");
    const document = await fs.readFile(htmlPath, "utf-8");
    panel.webview.html = document.replace(
        /<base href="[^"]*">/,
        `<base href="${assetRoot}">`
    );
}


async function convertMarkdownToHtml(resource, output, context) {
    const sourceUri = await activeMarkdownUri(resource);
    if (!sourceUri) {
        return;
    }
    const choice = await vscode.window.showQuickPick(
        [
            {
                label: "HTML",
                description: "Convert without an automatic table of contents",
                toc: false
            },
            {
                label: "HTML with TOC",
                description: "Insert an automatic table of contents",
                toc: true
            }
        ],
        { placeHolder: "Choose Markdown conversion mode" }
    );
    if (!choice) {
        return;
    }

    const sourcePath = sourceUri.fsPath;
    const outputPath = sourcePath.replace(/\.(md|markdown)$/i, ".html");
    if (!(await confirmTemplateOverwrite(outputPath))) {
        return;
    }

    const sourceDirectory = path.dirname(sourcePath);
    const pythonPath = configuredPython(sourceUri);
    output.show(true);
    try {
        const hwToolPath = await runtimeHwToolPath(context);
        const args = [
            "-B",
            hwToolPath,
            "de",
            "md2html",
            sourcePath,
            "-o",
            outputPath
        ];
        if (choice.toc) {
            args.push("--toc");
        }
        args.push("--theme", previewTheme(sourceUri));
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: "Converting Markdown to HTML...",
                cancellable: false
            },
            async () => {
                await checkPythonRuntime(
                    pythonPath,
                    sourceDirectory,
                    output,
                    ["markdown"]
                );
                await runProcess(
                    pythonPath,
                    args,
                    sourceDirectory,
                    output,
                    "md2html"
                );
            }
        );
        await openMarkdownHtml(outputPath, sourceDirectory);
        vscode.window.showInformationMessage(`HTML generated: ${outputPath}`);
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            "Markdown conversion failed.",
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


async function showGenerationResult(outputDirectory, nested) {
    const actions = nested ? ["Open Tree HTML"] : [];
    const action = await vscode.window.showInformationMessage(
        `CSR generated in ${outputDirectory}`,
        ...actions
    );
    if (action === "Open Tree HTML") {
        await openTreeHtml(outputDirectory);
    }
}


async function generateCsr(nested, output, context) {
    const editor = await activeCsrEditor();
    if (!editor) {
        return;
    }
    const outputDirectory = csrOutputDirectory(editor.document.uri);
    await fs.mkdir(outputDirectory, { recursive: true });
    const pythonPath = configuredPython(editor.document.uri);
    output.show(true);
    try {
        const hwToolPath = await runtimeHwToolPath(context);
        const args = ["-B", hwToolPath, "de", "csr_tool", "-i", editor.document.uri.fsPath, "-o", outputDirectory];
        if (nested) {
            args.push("--nested");
        }
        await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: "Generating CSR...", cancellable: false },
            async () => {
                const cwd = path.dirname(editor.document.uri.fsPath);
                await checkPythonRuntime(
                    pythonPath,
                    cwd,
                    output,
                    ["jinja2", "openpyxl"]
                );
                await runProcess(pythonPath, args, cwd, output, "csr_tool");
            }
        );
        await showGenerationResult(outputDirectory, nested);
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage("CSR generation failed.", "Show HW Tool Output");
        if (action) {
            output.show(true);
        }
    }
}


function csrTemplateDirectory() {
    const terminalCwd = vscode.window.activeTerminal?.shellIntegration?.cwd;
    if (terminalCwd?.fsPath) {
        return { directory: terminalCwd.fsPath, source: "active Terminal" };
    }
    const editor = vscode.window.activeTextEditor;
    if (editor?.document.uri.scheme === "file") {
        return {
            directory: path.dirname(editor.document.uri.fsPath),
            source: "current file directory"
        };
    }
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (folder) {
        return { directory: folder.uri.fsPath, source: "workspace root" };
    }
    return undefined;
}


async function confirmTemplateOverwrite(targetPath) {
    try {
        await fs.access(targetPath);
        const overwrite = await vscode.window.showWarningMessage(
            `${targetPath} already exists.`,
            { modal: true },
            "Overwrite"
        );
        return overwrite === "Overwrite";
    }
    catch {
        return true;
    }
}


async function openCsrTemplate(targetPath, extension) {
    const uri = vscode.Uri.file(targetPath);
    if (extension === "xlsx") {
        await vscode.env.openExternal(uri);
        return;
    }
    const document = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(document);
}


async function createCsrTemplate(interactive, output, context) {
    let choice = CSR_TEMPLATE_CHOICES[0];
    if (interactive) {
        choice = await vscode.window.showQuickPick(CSR_TEMPLATE_CHOICES, {
            placeHolder: "Choose CSR template format and optional sections"
        });
        if (!choice) {
            return;
        }
    }

    const location = csrTemplateDirectory();
    if (!location) {
        vscode.window.showWarningMessage(
            "Open a Terminal, file, or workspace before creating a CSR template."
        );
        return;
    }
    const targetPath = path.join(location.directory, `reg_define.${choice.extension}`);
    if (!(await confirmTemplateOverwrite(targetPath))) {
        return;
    }

    const pythonPath = configuredPython();
    output.show(true);
    try {
        const hwToolPath = await runtimeHwToolPath(context);
        const args = [
            "-B",
            hwToolPath,
            "de",
            "csr_tool",
            "template",
            "-o",
            targetPath
        ];
        if (choice.baseInfo) {
            args.push("--base-info");
        }
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: "Creating CSR template...",
                cancellable: false
            },
            async () => {
                await checkPythonRuntime(
                    pythonPath,
                    location.directory,
                    output,
                    ["jinja2", "openpyxl"]
                );
                await runProcess(
                    pythonPath,
                    args,
                    location.directory,
                    output,
                    "csr_tool template"
                );
            }
        );
        await openCsrTemplate(targetPath, choice.extension);
        vscode.window.showInformationMessage(
            `Created ${path.basename(targetPath)} in ${location.source}: ${location.directory}`
        );
    }
    catch (error) {
        output.appendLine(`[ERROR] ${error.message}`);
        const action = await vscode.window.showErrorMessage(
            "CSR template creation failed.",
            "Show HW Tool Output"
        );
        if (action) {
            output.show(true);
        }
    }
}


async function insertRegisterRow() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || path.extname(editor.document.uri.fsPath).toLowerCase() !== ".md") {
        vscode.window.showWarningMessage("Open a CSR Markdown definition first.");
        return;
    }
    const regType = await vscode.window.showQuickPick(REGISTER_TYPES, {
        placeHolder: "Choose a valid CSR register type"
    });
    if (!regType) {
        return;
    }
    const line = editor.document.lineAt(editor.selection.active.line).range.end;
    await editor.edit((builder) => builder.insert(line, `\n${regType.row}`));
}


function activate(context) {
    const output = vscode.window.createOutputChannel(OUTPUT_CHANNEL_NAME);
    context.subscriptions.push(output);
    context.subscriptions.push(
        ...registerRtlInstCommands(context, output),
        ...registerRtlDummyCommands(context, output),
        ...registerGenTbCommands(context, output),
        ...registerMemToolCommands(context, output),
        ...registerRtlFlistCommands(context, output),
        ...registerGitRepoCommands(context, output)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand(
            "dmgHwTool.csr.newDefinition",
            () => createCsrTemplate(true, output, context)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.csr.newDefaultDefinition",
            () => createCsrTemplate(false, output, context)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.docs.openCsr",
            () => openToolDocumentation(context, "csr_tool", output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.docs.openMemory",
            () => openToolDocumentation(context, "mem_tool", output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.docs.openTool",
            () => openToolDocumentation(context, undefined, output)
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.preview.changeTheme",
            changePreviewTheme
        ),
        vscode.commands.registerCommand(
            "dmgHwTool.md2html.convert",
            (resource) => convertMarkdownToHtml(resource, output, context)
        ),
        vscode.commands.registerCommand("dmgHwTool.csr.generateSingle", () => generateCsr(false, output, context)),
        vscode.commands.registerCommand("dmgHwTool.csr.generateNested", () => generateCsr(true, output, context)),
        vscode.commands.registerCommand("dmgHwTool.csr.openTreeHtml", async () => {
            const editor = await activeCsrEditor();
            if (!editor) {
                return;
            }
            await openTreeHtml(csrOutputDirectory(editor.document.uri));
        }),
        vscode.commands.registerCommand("dmgHwTool.csr.insertRegisterRow", insertRegisterRow)
    );
}


function deactivate() {}


module.exports = { activate, deactivate };
