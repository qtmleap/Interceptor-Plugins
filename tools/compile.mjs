// No bundler, module loader or execution of author code: each plugin is a global script.
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const root = path.resolve(process.argv[2] || '.');
const forbidden = new Set(['Promise', 'ArrayBuffer', 'SharedArrayBuffer', 'DataView', 'Atomics',
  'Int8Array', 'Uint8Array', 'Uint8ClampedArray', 'Int16Array', 'Uint16Array', 'Int32Array',
  'Uint32Array', 'Float32Array', 'Float64Array', 'BigInt64Array', 'BigUint64Array']);
const options = {
  strict: true, noUncheckedIndexedAccess: true, exactOptionalPropertyTypes: true,
  noEmitOnError: true, target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None,
  lib: ['lib.es2020.d.ts'], types: [], newLine: ts.NewLineKind.LineFeed,
  declaration: false, sourceMap: false, removeComments: false, noResolve: false,
};

function regular(file) {
  if (!fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink()) {
    throw new Error(`Expected a regular file: ${file}`);
  }
}
try {
  if (globalThis.Bun?.version !== '1.3.6') throw new Error('Use the pinned Bun 1.3.6 runtime (see .bun-version)');
  if (ts.version !== '5.8.3') throw new Error('Run bun install --frozen-lockfile --ignore-scripts to install the pinned TypeScript 5.8.3 compiler');
  const sourceDir = path.join(root, 'src');
  if (fs.lstatSync(sourceDir).isSymbolicLink()) throw new Error('src cannot be a symlink');
  const entries = fs.readdirSync(sourceDir).sort();
  if (!entries.length) throw new Error('No TypeScript plugins found');
  const outputs = {};
  const sdk = path.join(root, 'types/interceptor.d.ts');
  regular(sdk);
  for (const entry of entries) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*\.ts$/.test(entry) || entry.length > 67) {
      throw new Error(`Unexpected source: src/${entry}`);
    }
    const file = path.join(sourceDir, entry);
    regular(file);
    if (fs.statSync(file).size > 131072) throw new Error(`Source too large: ${entry}`);
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifests', entry.slice(0, -3) + '.json'), 'utf8'));
    const hooks = ['request', 'response'].filter(hook => manifest.subscriptions.some(s => s.phase.startsWith(hook + '.')))
      .map(hook => hook === 'request' ? 'onRequest' : 'onResponse');
    const checkFile = path.join(root, '__interceptor_hook_check.ts');
    const checkText = hooks.map(hook => `const __interceptorCheck_${hook}: (event: Interceptor.Event, config: Interceptor.Config) => Interceptor.Result = ${hook};`).join('\n');
    const host = ts.createCompilerHost(options);
    const originalGetSourceFile = host.getSourceFile.bind(host);
    host.getSourceFile = (name, version, onError, shouldCreate) => name === checkFile
      ? ts.createSourceFile(name, checkText, version, true)
      : originalGetSourceFile(name, version, onError, shouldCreate);
    const program = ts.createProgram([file, sdk, checkFile], options, host);
    const source = program.getSourceFile(file);
    for (const authored of [source, program.getSourceFile(sdk)]) {
      if (authored.libReferenceDirectives.length || authored.typeReferenceDirectives.length || authored.hasNoDefaultLib
          || authored.referencedFiles.some(ref => path.resolve(path.dirname(authored.fileName), ref.fileName) !== sdk)) {
        throw new Error(`${entry}: only the supplied SDK reference is supported; plugins must be self-contained`);
      }
    }
    for (const input of program.getSourceFiles()) {
      if (![file, sdk, checkFile].includes(input.fileName) && !program.isSourceFileDefaultLibrary(input)) {
        throw new Error(`${entry}: additional TypeScript dependencies are not emitted; keep this plugin self-contained`);
      }
    }
    for (const hook of hooks) {
      if (!source.statements.some(s => ts.isFunctionDeclaration(s) && s.name?.text === hook && s.body)) {
        throw new Error(`${entry}: declare a top-level function ${hook} for its manifest subscriptions`);
      }
    }
    function inspect(node) {
      if (ts.isImportDeclaration(node) || ts.isImportEqualsDeclaration(node) || ts.isExportDeclaration(node)
          || ts.isExportAssignment(node) || ts.isImportTypeNode(node)
          || node.kind === ts.SyntaxKind.ImportKeyword
          || node.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword || m.kind === ts.SyntaxKind.AsyncKeyword)
          || ts.isAwaitExpression(node)) {
        throw new Error(`${entry}: imports, exports and asynchronous code are unavailable in this host`);
      }
      if (ts.isIdentifier(node) && forbidden.has(node.text)) {
        throw new Error(`${entry}: ${node.text} is unavailable in this host`);
      }
      ts.forEachChild(node, inspect);
    }
    inspect(source);
    const diagnostics = ts.getPreEmitDiagnostics(program);
    if (diagnostics.length) {
      throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
        getCanonicalFileName: f => f, getCurrentDirectory: () => root, getNewLine: () => '\n',
      }));
    }
    let emitted;
    const result = program.emit(source, (name, contents) => {
      if (!name.endsWith('.js') || emitted !== undefined) throw new Error('Unexpected compiler output');
      emitted = contents;
    });
    if (result.emitSkipped || emitted === undefined) throw new Error(`Compilation failed: ${entry}`);
    outputs[entry.slice(0, -3)] = emitted;
  }
  // The Python caller owns the output directory and atomically installs this complete result.
  process.stdout.write(JSON.stringify(outputs));
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
