// Compile independent global scripts; routing is generated from files, never executed author code.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import ts from 'typescript';

const root = path.resolve(process.argv[2] || '.');
// Promise is allowed only as a type inside response.onLeave callbacks.
const forbidden = new Set(['Promise', 'ArrayBuffer', 'SharedArrayBuffer', 'DataView', 'Atomics',
  'Int8Array', 'Uint8Array', 'Uint8ClampedArray', 'Int16Array', 'Uint16Array', 'Int32Array',
  'Uint32Array', 'Float32Array', 'Float64Array', 'BigInt64Array', 'BigUint64Array']);
const options = {
  strict: true, noUncheckedIndexedAccess: true, exactOptionalPropertyTypes: true,
  noEmitOnError: true, target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None,
  lib: ['lib.es2020.d.ts'], types: [], newLine: ts.NewLineKind.LineFeed,
  declaration: false, sourceMap: false, removeComments: false, noResolve: false,
};
const regular = file => {
  const info = fs.lstatSync(file);
  if (!info.isFile() || info.isSymbolicLink()) throw new Error(`Expected a regular file: ${file}`);
  if (info.size > 131072) throw new Error(`Source too large: ${file}`);
};
const isAttach = node => ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
  && ts.isIdentifier(node.expression.expression) && node.expression.expression.text === 'Interceptor'
  && node.expression.name.text === 'attach';
const isSend = node => ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
  && ts.isIdentifier(node.expression.expression) && node.expression.expression.text === 'Interceptor'
  && node.expression.name.text === 'send';
// Any `Interceptor.saveJSON` property access, whether or not it is a direct call.
const isSaveAccess = node => ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)
  && node.expression.text === 'Interceptor' && node.name.text === 'saveJSON';

function staticHooks(source, checker, namespace, globalObject) {
  const calls = [];
  const sends = [];
  const saves = [];
  const references = [];
  const walk = (node, parent) => {
    if (isAttach(node) && checker.getSymbolAtLocation(node.expression.expression) === namespace) calls.push(node);
    if (isSend(node) && checker.getSymbolAtLocation(node.expression.expression) === namespace) sends.push(node);
    if (isSaveAccess(node) && checker.getSymbolAtLocation(node.expression) === namespace) saves.push({ access: node, parent });
    if ((ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node))
        && ts.isIdentifier(node.expression) && node.expression.text === 'Interceptor'
        && (ts.isElementAccessExpression(node) || ['attach', 'send', 'saveJSON'].includes(node.name.text))
        && checker.getSymbolAtLocation(node.expression) !== namespace) {
      throw new Error(`${source.fileName}: Interceptor host calls cannot use a shadowed name`);
    }
    if ((ts.isIdentifier(node) || ts.isStringLiteral(node)) && !ts.isQualifiedName(parent) && !ts.isTypeQueryNode(parent)) {
      const symbol = ts.isShorthandPropertyAssignment(parent) && parent.name === node
        ? checker.getShorthandAssignmentValueSymbol(parent) : checker.getSymbolAtLocation(node);
      if (globalObject && symbol === globalObject) throw new Error(`${source.fileName}: access the host only through direct Interceptor.attach or callback Interceptor.send calls`);
      if (symbol === namespace) references.push(node);
    }
    ts.forEachChild(node, child => walk(child, node));
  };
  walk(source, source);
  if (calls.length !== 1 || !source.statements.some(s => ts.isExpressionStatement(s) && s.expression === calls[0])) {
    throw new Error(`${source.fileName}: use one direct top-level Interceptor.attach({ ... })`);
  }
  const call = calls[0];
  const directReferences = new Set([call.expression.expression, ...sends.map(send => send.expression.expression),
    ...saves.map(save => save.access.expression)]);
  if (references.some(node => !directReferences.has(node))) {
    throw new Error(`${source.fileName}: Interceptor host calls cannot be aliased or called indirectly`);
  }
  if (call.arguments.length !== 1 || !ts.isObjectLiteralExpression(call.arguments[0])) {
    throw new Error(`${source.fileName}: attach takes one hooks object; conditions come from the file path`);
  }
  function entries(object, allowed) {
    const seen = new Set();
    return object.properties.map(property => {
      if ((!ts.isPropertyAssignment(property) && !ts.isMethodDeclaration(property))
          || !property.name || (!ts.isIdentifier(property.name) && !ts.isStringLiteral(property.name))) {
        throw new Error(`${source.fileName}: use static hook keys without spread or computed properties`);
      }
      const key = property.name.text;
      if (!allowed.includes(key) || seen.has(key)) throw new Error(`${source.fileName}: invalid or duplicate hook key ${key}`);
      seen.add(key);
      return [key, property];
    });
  }
  const hooks = {};
  const callbackBodies = [];
  const leaveRegions = [];
  for (const [leg, property] of entries(call.arguments[0], ['request', 'response'])) {
    if (!ts.isPropertyAssignment(property) || !ts.isObjectLiteralExpression(property.initializer)) {
      throw new Error(`${source.fileName}: ${leg} must be a static hooks object`);
    }
    hooks[leg] = {};
    for (const [phase, callback] of entries(property.initializer, ['onEnter', 'onLeave'])) {
      hooks[leg][phase] = true;
      const fn = ts.isMethodDeclaration(callback) ? callback : callback.initializer;
      if (fn && (ts.isMethodDeclaration(fn) || ts.isFunctionExpression(fn) || ts.isArrowFunction(fn)) && fn.body) {
        callbackBodies.push(fn.body);
        if (leg === 'response' && phase === 'onLeave') leaveRegions.push(fn);
      }
    }
    if (!Object.keys(hooks[leg]).length) throw new Error(`${source.fileName}: empty ${leg} hooks`);
  }
  if (!Object.keys(hooks).length) throw new Error(`${source.fileName}: declare at least one hook`);
  for (const send of sends) {
    if (!callbackBodies.some(body => send.pos >= body.pos && send.end <= body.end)) {
      throw new Error(`${source.fileName}: Interceptor.send is available only inside a registered callback`);
    }
  }
  // saveJSON must be a direct call to the property inside a registered response.onLeave callback.
  for (const { access, parent } of saves) {
    if (!ts.isCallExpression(parent) || parent.expression !== access
        || !leaveRegions.some(region => access.pos >= region.pos && access.end <= region.end)) {
      throw new Error(`${source.fileName}: Interceptor.saveJSON must be called directly inside a registered response.onLeave callback`);
    }
  }
  return { hooks, leaveRegions, usesFiles: saves.length > 0 };
}

function legacyHostValues(source, checker, namespace) {
  const walk = (node, parent) => {
    if ((ts.isIdentifier(node) || ts.isStringLiteral(node)) && !ts.isQualifiedName(parent) && !ts.isTypeQueryNode(parent)) {
      const symbol = ts.isShorthandPropertyAssignment(parent) && parent.name === node
        ? checker.getShorthandAssignmentValueSymbol(parent) : checker.getSymbolAtLocation(node);
      if (symbol === namespace) {
        throw new Error(`${source.fileName}: Interceptor host calls require schema 2 plugins/NAME/hooks; legacy scripts may use the namespace only for types`);
      }
    }
    ts.forEachChild(node, child => walk(child, node));
  };
  walk(source, source);
}

function compile(file, sdk, legacyHooks = [], routed = false) {
  regular(file);
  const checkFile = path.join(root, '__interceptor_hook_check.ts');
  const checkText = legacyHooks.map(hook => `const __interceptorCheck_${hook}: (event: Interceptor.Event, config: Interceptor.Config) => Interceptor.Result = ${hook};`).join('\n');
  const host = ts.createCompilerHost(options);
  const originalGetSourceFile = host.getSourceFile.bind(host);
  host.getSourceFile = (name, version, onError, shouldCreate) => name === checkFile
    ? ts.createSourceFile(name, checkText, version, true) : originalGetSourceFile(name, version, onError, shouldCreate);
  const program = ts.createProgram([file, sdk, checkFile], options, host);
  const source = program.getSourceFile(file);
  for (const authored of [source, program.getSourceFile(sdk)]) {
    if (authored.libReferenceDirectives.length || authored.typeReferenceDirectives.length || authored.hasNoDefaultLib
        || authored.referencedFiles.some(ref => path.resolve(path.dirname(authored.fileName), ref.fileName) !== sdk)) {
      throw new Error(`${file}: only the supplied SDK reference is supported; plugins must be self-contained`);
    }
  }
  for (const input of program.getSourceFiles()) {
    if (![file, sdk, checkFile].includes(input.fileName) && !program.isSourceFileDefaultLibrary(input)) {
      throw new Error(`${file}: additional TypeScript dependencies are not emitted; keep this plugin self-contained`);
    }
  }
  for (const hook of legacyHooks) {
    if (!source.statements.some(s => ts.isFunctionDeclaration(s) && s.name?.text === hook && s.body)) {
      throw new Error(`${file}: declare a top-level function ${hook} for its manifest subscriptions`);
    }
  }
  const checker = program.getTypeChecker();
  const sdkFile = program.getSourceFile(sdk);
  const namespace = sdkFile.statements.find(node => ts.isModuleDeclaration(node) && node.name.text === 'Interceptor');
  const fetchDeclaration = sdkFile.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'fetch');
  const fetchSymbol = checker.getSymbolAtLocation(fetchDeclaration.name);
  const globalObject = checker.getSymbolsInScope(source, ts.SymbolFlags.Value).find(symbol => symbol.getName() === 'globalThis');
  if (!routed) legacyHostValues(source, checker, checker.getSymbolAtLocation(namespace.name));
  const routedResult = routed ? staticHooks(source, checker, checker.getSymbolAtLocation(namespace.name), globalObject) : null;
  const hooks = routedResult?.hooks ?? null;
  // Async code and fetch exist only inside a response.onLeave callback of a routed plugin.
  const inLeave = node => !!routedResult?.leaveRegions.some(region => node.pos >= region.pos && node.end <= region.end);
  const isPropertyName = declaration => [ts.SyntaxKind.PropertyAssignment, ts.SyntaxKind.ShorthandPropertyAssignment,
    ts.SyntaxKind.PropertyDeclaration, ts.SyntaxKind.MethodDeclaration, ts.SyntaxKind.PropertySignature,
    ts.SyntaxKind.MethodSignature, ts.SyntaxKind.GetAccessor, ts.SyntaxKind.SetAccessor].includes(declaration.kind);
  function inspect(node) {
    if (ts.isImportDeclaration(node) || ts.isImportEqualsDeclaration(node) || ts.isExportDeclaration(node)
        || ts.isExportAssignment(node) || ts.isImportTypeNode(node) || node.kind === ts.SyntaxKind.ImportKeyword
        || node.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword)) {
      throw new Error(`${file}: imports, exports and asynchronous code are unavailable in this host`);
    }
    const asyncModifier = node.modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword);
    const generator = (ts.isFunctionLike(node) && node.asteriskToken) || (ts.isForOfStatement(node) && node.awaitModifier);
    if ((asyncModifier || ts.isAwaitExpression(node)) && !inLeave(node)) {
      throw new Error(`${file}: imports, exports and asynchronous code are unavailable in this host`);
    }
    if (asyncModifier && generator || (ts.isForOfStatement(node) && node.awaitModifier)) {
      throw new Error(`${file}: async generators and for await are unavailable in this host`);
    }
    if (ts.isIdentifier(node)) {
      const typeUse = ts.isTypeReferenceNode(node.parent) && node.parent.typeName === node;
      if (forbidden.has(node.text) && !(node.text === 'Promise' && typeUse && inLeave(node))) {
        throw new Error(`${file}: ${node.text} is unavailable in this host`);
      }
      if (node.text === 'fetch' && !ts.isTypeReferenceNode(node.parent)) {
        const symbol = ts.isShorthandPropertyAssignment(node.parent) ? checker.getShorthandAssignmentValueSymbol(node.parent) : checker.getSymbolAtLocation(node);
        if (symbol === fetchSymbol) {
          if (!inLeave(node) || !ts.isCallExpression(node.parent) || node.parent.expression !== node) {
            throw new Error(`${file}: fetch must be called directly inside a response.onLeave callback`);
          }
        } else if (symbol?.declarations?.some(d => d.name === node && !isPropertyName(d))
            || (ts.isBindingElement(node.parent) && node.parent.name === node)) {
          throw new Error(`${file}: fetch cannot be shadowed or redeclared`);
        }
      }
    }
    ts.forEachChild(node, inspect);
  }
  inspect(source);
  const diagnostics = ts.getPreEmitDiagnostics(program);
  if (diagnostics.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: f => f, getCurrentDirectory: () => root, getNewLine: () => '\n',
  }));
  const output = {};
  const result = program.emit(source, (name, contents) => {
    if (!name.endsWith('.js') || output.code !== undefined) throw new Error('Unexpected compiler output');
    output.code = contents;
  });
  if (result.emitSkipped || output.code === undefined) throw new Error(`Compilation failed: ${file}`);
  return { code: output.code, hooks, usesFiles: routedResult?.usesFiles ?? false };
}

try {
  if (globalThis.Bun?.version !== '1.3.6') throw new Error('Use the pinned Bun 1.3.6 runtime (see .bun-version)');
  if (ts.version !== '5.8.3') throw new Error('Run bun install --frozen-lockfile --ignore-scripts to install the pinned TypeScript 5.8.3 compiler');
  const sdk = path.join(root, 'types/interceptor.d.ts');
  regular(sdk);
  const outputs = {};
  const sourceDir = path.join(root, 'src');
  if (fs.existsSync(sourceDir)) {
    if (fs.lstatSync(sourceDir).isSymbolicLink()) throw new Error('src cannot be a symlink');
    for (const entry of fs.readdirSync(sourceDir).filter(e => e !== '.DS_Store').sort()) {
      if (!/^[a-z0-9]+(?:-[a-z0-9]+)*\.ts$/.test(entry) || entry.length > 67) throw new Error(`Unexpected source: src/${entry}`);
      const name = entry.slice(0, -3);
      const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifests', name + '.json'), 'utf8'));
      if (manifest.schemaVersion !== 1) throw new Error(`${entry}: use plugins/NAME/hooks for new plugins`);
      const hooks = ['request', 'response'].filter(leg => manifest.subscriptions.some(s => s.phase.startsWith(leg + '.')))
        .map(leg => leg === 'request' ? 'onRequest' : 'onResponse');
      outputs[name] = compile(path.join(sourceDir, entry), sdk, hooks).code;
    }
  }
  if (fs.existsSync(path.join(root, 'plugins'))) {
    const discover = path.join(import.meta.dirname, 'discover_routes.py');
    const discovered = JSON.parse(execFileSync(process.env.INTERCEPTOR_PYTHON || 'python3', [discover, '--root', root], { encoding: 'utf8', maxBuffer: 1048576 }));
    for (const [name, plugin] of Object.entries(discovered)) {
      if (name in outputs) throw new Error(`Duplicate plugin basename: ${name}`);
      const sourceFiles = {};
      const matches = plugin.routes.map(route => {
        const result = compile(path.join(root, 'plugins', name, route.file), sdk, [], true);
        if (result.usesFiles && plugin.metadata.write?.files !== true) {
          throw new Error(`plugins/${name}/${route.file}: Interceptor.saveJSON requires write.files: true in plugin.json`);
        }
        sourceFiles[route.emitted] = result.code;
        const hooks = Object.fromEntries(Object.entries(result.hooks).map(([leg, callbacks]) =>
          [leg, Object.fromEntries(Object.keys(callbacks).map(phase => [phase, route.emitted]))]));
        return { hosts: [route.host], methods: [route.method], path: { kind: 'exact', value: route.path }, hooks };
      });
      outputs[name] = { manifest: { ...plugin.metadata, matches }, sourceFiles };
    }
  }
  if (!Object.keys(outputs).length) throw new Error('No TypeScript plugins found');
  process.stdout.write(JSON.stringify(outputs));
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
