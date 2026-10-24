// Compile independent global scripts; routing is generated from files, never executed author code.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { builtinModules } from 'node:module';
import resolve from 'enhanced-resolve';
import ts from 'typescript';

const root = path.resolve(process.argv[2] || '.');
// Promise (as a type) and Uint8Array (createFile contents) are allowed only inside response.onLeave callbacks.
const forbidden = new Set(['Promise', 'ArrayBuffer', 'SharedArrayBuffer', 'DataView', 'Atomics',
  'Int8Array', 'Uint8Array', 'Uint8ClampedArray', 'Int16Array', 'Uint16Array', 'Int32Array',
  'Uint32Array', 'Float32Array', 'Float64Array', 'BigInt64Array', 'BigUint64Array']);
const options = {
  strict: true, noUncheckedIndexedAccess: true, exactOptionalPropertyTypes: true,
  noEmitOnError: true, target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None,
  lib: ['lib.es2020.d.ts'], types: [], newLine: ts.NewLineKind.LineFeed,
  declaration: false, sourceMap: false, removeComments: false, noResolve: false,
};
const MAX_OUTPUT = 131072;
const BUILTINS = new Set(builtinModules.flatMap(name => [name, 'node:' + name]));
// Bun prioritizes builtin polyfills even over installed packages with the same name.
const installedResolvers = Object.fromEntries(['import', 'require'].map(kind => [kind, resolve.create.sync({
  conditionNames: ['browser', kind, 'default'], mainFields: ['browser', 'module', 'main'], aliasFields: ['browser'],
  extensions: ['.js', '.mjs', '.cjs', '.ts', '.mts', '.cts', '.json'],
})]));
const importOptions = { ...options, module: ts.ModuleKind.ES2015, moduleResolution: ts.ModuleResolutionKind.Bundler,
  esModuleInterop: true, allowSyntheticDefaultImports: true, customConditions: ['browser'], preserveSymlinks: true };
const unsupportedGlobals = new Set(['require', 'module', 'exports', 'process', 'Buffer', '__dirname', '__filename',
  'TextEncoder', 'TextDecoder', 'console', 'setTimeout', 'setInterval', 'setImmediate', 'window', 'document',
  'self', 'global', 'navigator', 'XMLHttpRequest', 'WebSocket', 'crypto', 'URL', 'URLSearchParams']);
const isDependency = file => path.resolve(file).startsWith(path.join(root, 'node_modules') + path.sep);
const isPropertyName = node =>
  (ts.isPropertyAccessExpression(node.parent) && node.parent.name === node)
  || (ts.isQualifiedName(node.parent) && node.parent.right === node)
  || (ts.isBindingElement(node.parent) && node.parent.propertyName === node)
  || ((ts.isPropertyAssignment(node.parent) || ts.isPropertyDeclaration(node.parent)
    || ts.isMethodDeclaration(node.parent) || ts.isGetAccessorDeclaration(node.parent)
    || ts.isSetAccessorDeclaration(node.parent)) && node.parent.name === node);
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
// Any `Interceptor.createFile` property access, whether or not it is a direct call.
const isCreateAccess = node => ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)
  && node.expression.text === 'Interceptor' && node.name.text === 'createFile';
// Any `Interceptor.Storage` value access; only `Interceptor.Storage.<case>` is accepted.
const isStorageAccess = node => ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)
  && node.expression.text === 'Interceptor' && node.name.text === 'Storage';
const STORAGE_CASES = ['local', 'iCloudDrive'];

function checkSpecifier(specifier) {
  if (/^(node:|bun:)/.test(specifier)) {
    throw new Error(`Unsupported runtime module ${specifier}: use a package that runs without Node or Bun APIs`);
  }
  if (!/^(?:@[a-z0-9_.-]+\/)?[a-z0-9_][a-z0-9_.-]*(?:\/[a-z0-9_@.\/-]+)?$/i.test(specifier)
      || specifier.split('/').some(part => part === '.' || part === '..')) {
    throw new Error(`Only installed package imports are supported: ${specifier}`);
  }
}

function approvedImports(source) {
  const imports = source.statements.filter(ts.isImportDeclaration);
  for (const node of imports) {
    if (!ts.isStringLiteral(node.moduleSpecifier) || node.attributes) {
      throw new Error(`${source.fileName}: use static package imports without attributes`);
    }
    checkSpecifier(node.moduleSpecifier.text);
  }
  return imports;
}

function packageNotices(file, packages) {
  for (const directory of [path.dirname(file), ...parents(path.dirname(file))]) {
    const metadata = path.join(directory, 'package.json');
    if (!fs.existsSync(metadata)) continue;
    const pkg = JSON.parse(fs.readFileSync(metadata, 'utf8'));
    if (!pkg.name || !pkg.version) continue;
    const key = `${pkg.name}@${pkg.version}`;
    if (!packages.has(key)) {
      const noticeDirectories = [directory, ...parents(directory)].filter(parent => {
        const metadata = path.join(parent, 'package.json');
        if (!fs.existsSync(metadata)) return false;
        const candidate = JSON.parse(fs.readFileSync(metadata, 'utf8'));
        return candidate.name === pkg.name && candidate.version === pkg.version;
      });
      const notices = noticeDirectories.flatMap(parent => fs.readdirSync(parent).sort()
        .filter(name => /^(licen[cs]e|copying|notice)(?:[.\-]|$)/i.test(name))
        .map(name => path.join(parent, name)).filter(name => fs.statSync(name).isFile())
        .map(name => fs.readFileSync(name, 'utf8')));
      packages.set(key, [key, ...new Set(notices)].join('\n'));
    }
    return;
  }
}

function parents(directory) {
  const parent = path.dirname(directory);
  return parent === directory ? [] : [parent, ...parents(parent)];
}

// Normal Bun package resolution; only the checked entry is replaced with TypeScript's emitted JS.
async function bundle(code, file) {
  const packages = new Map();
  const build = await Bun.build({
    entrypoints: [file], root, target: 'browser', format: 'iife', packages: 'bundle',
    minify: { whitespace: true, syntax: true, identifiers: true }, sourcemap: 'none', splitting: false,
    env: 'disable', define: { 'process.env.NODE_ENV': '"production"' }, conditions: ['browser'], throw: false,
    plugins: [{ name: 'interceptor-packages', setup(api) {
      api.onResolve({ filter: /.*/ }, args => {
        if (/^(node:|bun:|https?:|data:|file:)/.test(args.path)) {
          throw new Error(`Unsupported runtime module ${args.path} imported by ${args.importer}`);
        }
        if (BUILTINS.has(args.path)) {
          try {
            const resolver = installedResolvers[args.kind === 'require-call' ? 'require' : 'import'];
            const resolved = resolver(path.dirname(args.importer || file), args.path);
            if (resolved === false) return { path: args.path, namespace: 'interceptor-empty' };
            if (resolved) return { path: resolved };
          } catch { /* A builtin without an installed implementation is unavailable. */ }
          throw new Error(`Unsupported runtime module ${args.path}: install a QuickJS-compatible package implementation`);
        }
      });
      api.onLoad({ filter: /.*/, namespace: 'interceptor-empty' }, () => ({ contents: 'module.exports = {};', loader: 'js' }));
      api.onLoad({ filter: /.*/, namespace: 'file' }, args => {
        if (args.path === file) return { contents: code, loader: 'js' };
        if (!/\.(?:[cm]?[jt]sx?|json)$/.test(args.path)) {
          throw new Error(`Unsupported package asset ${args.path}: only JavaScript, TypeScript and JSON can be bundled`);
        }
        const contents = fs.readFileSync(args.path, 'utf8');
        if (!args.path.endsWith('.json')) checkRuntimeLoading(contents, args.path);
        packageNotices(args.path, packages);
      });
    } }],
  });
  if (!build.success) throw new Error(`Bundling failed: ${build.logs.map(log => log.message).join('; ')}`);
  if (build.outputs.length !== 1 || build.outputs[0].kind !== 'entry-point') {
    throw new Error('A hook must bundle into one JavaScript file without external assets');
  }
  const notices = [...packages.entries()].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([, text]) => text).join('\n\n');
  const output = (notices ? `/*! Bundled packages\n${notices.replaceAll('*/', '* /')}\n*/\n` : '') + await build.outputs[0].text();
  postguard(output);
  return output;
}

// Evaluate simple feature conditions with known host globals; undefined means unknown.
function absentValue(node, checker) {
  if (ts.isParenthesizedExpression(node)) return absentValue(node.expression, checker);
  if (ts.isTypeOfExpression(node) && ts.isIdentifier(node.expression)) {
    if (checker.getSymbolAtLocation(node.expression)?.declarations?.length) return undefined;
    if (node.expression.text === 'globalThis') return 'object';
    if (unsupportedGlobals.has(node.expression.text)) return 'undefined';
  }
  if (ts.isStringLiteral(node)) return node.text;
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.ExclamationToken) {
    const value = absentValue(node.operand, checker);
    return value === undefined ? undefined : !value;
  }
  if (!ts.isBinaryExpression(node)) return undefined;
  const left = absentValue(node.left, checker);
  const right = absentValue(node.right, checker);
  const op = node.operatorToken.kind;
  if (op === ts.SyntaxKind.AmpersandAmpersandToken) {
    return left === undefined ? undefined : (left ? right : left);
  }
  if (op === ts.SyntaxKind.BarBarToken) {
    return left === undefined ? undefined : (left ? left : right);
  }
  if (left === undefined || right === undefined) return undefined;
  if ([ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken].includes(op) && typeof left !== typeof right) return undefined;
  if ([ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken].includes(op)) return left === right;
  if ([ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(op)) return left !== right;
  if (op === ts.SyntaxKind.LessThanToken) return left < right;
  if (op === ts.SyntaxKind.GreaterThanToken) return left > right;
  if (op === ts.SyntaxKind.LessThanEqualsToken) return left <= right;
  if (op === ts.SyntaxKind.GreaterThanEqualsToken) return left >= right;
  return undefined;
}

function featureProbe(node, checker) {
  if (ts.isTypeOfExpression(node.parent)) return true;
  for (const child of [node, ...ancestors(node)]) {
    const parent = child.parent;
    if (!parent) break;
    const condition = ts.isIfStatement(parent) ? parent.expression : ts.isConditionalExpression(parent) ? parent.condition
      : ts.isBinaryExpression(parent) && parent.right === child ? parent.left : null;
    const value = condition ? absentValue(condition, checker) : undefined;
    if (value === undefined) continue;
    if (ts.isIfStatement(parent) && (child === parent.thenStatement ? !value : child === parent.elseStatement && !!value)) return true;
    if (ts.isConditionalExpression(parent) && (child === parent.whenTrue ? !value : child === parent.whenFalse && !!value)) return true;
    if (ts.isBinaryExpression(parent) && parent.right === child
        && ((parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken && !value)
          || (parent.operatorToken.kind === ts.SyntaxKind.BarBarToken && !!value))) return true;
  }
  return false;
}

function* ancestors(node) {
  for (const parent of node.parent ? [node.parent] : []) {
    yield parent;
    yield* ancestors(parent);
  }
}

function scopedSource(code, name) {
  const parsed = ts.createSourceFile(name, code, ts.ScriptTarget.Latest, true);
  const options = { allowJs: true, noLib: true, noResolve: true };
  const host = ts.createCompilerHost(options);
  host.getSourceFile = file => file === name ? parsed : undefined;
  return { parsed, checker: ts.createProgram([name], options, host).getTypeChecker() };
}

function checkRuntimeLoading(contents, name) {
  const { parsed, checker } = scopedSource(contents, name);
  const walk = node => {
    if (ts.isMetaProperty(node) && node.keywordToken === ts.SyntaxKind.ImportKeyword) throw new Error(`Unsupported import.meta in package file ${name}`);
    if (ts.isCallExpression(node)) {
      const requireCall = ts.isIdentifier(node.expression) && node.expression.text === 'require';
      const dynamicImport = node.expression.kind === ts.SyntaxKind.ImportKeyword;
      if ((requireCall || dynamicImport) && (node.arguments.length !== 1 || !ts.isStringLiteralLike(node.arguments[0]))) {
        const symbol = requireCall ? checker.getSymbolAtLocation(node.expression) : null;
        if (!symbol?.declarations?.some(declaration => declaration.getSourceFile() === parsed)) {
          throw new Error(`Unsupported runtime module loading in ${name}: use a static package dependency`);
        }
      }
    }
    ts.forEachChild(node, walk);
  };
  walk(parsed);
}

// Diagnose unresolved runtime loading and common absent host APIs, without banning local names or JS builtins.
function postguard(output) {
  if (Buffer.byteLength(output) > MAX_OUTPUT) throw new Error('Bundled hook is too large (128 KiB limit)');
  if (output.includes(root) || output.includes(fs.realpathSync(root))) throw new Error('Bundled hook leaked a build path');
  const { parsed, checker } = scopedSource(output, path.join(root, '__interceptor_bundle.js'));
  const walk = node => {
    if (ts.isImportDeclaration(node) || ts.isImportEqualsDeclaration(node) || ts.isExportDeclaration(node)
        || ts.isExportAssignment(node) || node.kind === ts.SyntaxKind.ImportKeyword
        || (ts.isMetaProperty(node) && node.keywordToken === ts.SyntaxKind.ImportKeyword)) {
      throw new Error(`Bundled hook contains unresolved module loading: ${node.getText(parsed).slice(0, 60)}`);
    }
    if (ts.isIdentifier(node) && !isPropertyName(node) && unsupportedGlobals.has(node.text) && !featureProbe(node, checker)) {
      const symbol = ts.isShorthandPropertyAssignment(node.parent)
        ? checker.getShorthandAssignmentValueSymbol(node.parent) : checker.getSymbolAtLocation(node);
      if (!symbol?.declarations?.some(declaration => declaration.getSourceFile() === parsed)) {
        throw new Error(`Bundled hook needs unsupported runtime API ${node.text}`);
      }
    }
    ts.forEachChild(node, walk);
  };
  walk(parsed);
}

function staticHooks(source, checker, namespace, globalObject) {
  const calls = [];
  const sends = [];
  const saves = [];
  const storages = [];
  const references = [];
  const walk = (node, parent) => {
    if (isAttach(node) && checker.getSymbolAtLocation(node.expression.expression) === namespace) calls.push(node);
    if (isSend(node) && checker.getSymbolAtLocation(node.expression.expression) === namespace) sends.push(node);
    if (isCreateAccess(node) && checker.getSymbolAtLocation(node.expression) === namespace) saves.push({ access: node, parent });
    if (isStorageAccess(node) && checker.getSymbolAtLocation(node.expression) === namespace) storages.push({ access: node, parent });
    if ((ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node))
        && ts.isIdentifier(node.expression) && node.expression.text === 'Interceptor'
        && (ts.isElementAccessExpression(node) || ['attach', 'send', 'createFile', 'Storage'].includes(node.name.text))
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
    ...saves.map(save => save.access.expression), ...storages.map(storage => storage.access.expression)]);
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
  // createFile must be a direct call to the property inside a registered response.onLeave callback.
  for (const { access, parent } of saves) {
    if (!ts.isCallExpression(parent) || parent.expression !== access
        || !leaveRegions.some(region => access.pos >= region.pos && access.end <= region.end)) {
      throw new Error(`${source.fileName}: Interceptor.createFile must be called directly inside a registered response.onLeave callback`);
    }
  }
  // Storage is read only as Interceptor.Storage.<case>, never copied, destructured or aliased.
  for (const { access, parent } of storages) {
    if (!ts.isPropertyAccessExpression(parent) || parent.expression !== access || !STORAGE_CASES.includes(parent.name.text)) {
      throw new Error(`${source.fileName}: use Interceptor.Storage only as Interceptor.Storage.local or Interceptor.Storage.iCloudDrive`);
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

async function compile(file, sdk, legacyHooks = [], routed = false) {
  regular(file);
  const imports = routed ? approvedImports(ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), options.target, true)) : [];
  const hasImports = imports.length > 0;
  const programOptions = hasImports ? importOptions : options;
  const checkFile = path.join(root, '__interceptor_hook_check.ts');
  const checkText = legacyHooks.map(hook => `const __interceptorCheck_${hook}: (event: Interceptor.Event, config: Interceptor.Config) => Interceptor.Result = ${hook};`).join('\n');
  const host = ts.createCompilerHost(programOptions);
  const originalGetSourceFile = host.getSourceFile.bind(host);
  host.getSourceFile = (name, version, onError, shouldCreate) => name === checkFile
    ? ts.createSourceFile(name, checkText, version, true) : originalGetSourceFile(name, version, onError, shouldCreate);
  const program = ts.createProgram([file, sdk, checkFile], programOptions, host);
  const source = program.getSourceFile(file);
  for (const authored of [source, program.getSourceFile(sdk)]) {
    if (authored.libReferenceDirectives.length || authored.typeReferenceDirectives.length || authored.hasNoDefaultLib
        || authored.referencedFiles.some(ref => path.resolve(path.dirname(authored.fileName), ref.fileName) !== sdk)) {
      throw new Error(`${file}: only the supplied SDK reference is supported; plugins must be self-contained`);
    }
  }
  for (const input of program.getSourceFiles()) {
    if (![file, sdk, checkFile].includes(input.fileName) && !program.isSourceFileDefaultLibrary(input)
        && !(hasImports && isDependency(input.fileName))) {
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
  const isPropertyDeclaration = declaration => [ts.SyntaxKind.PropertyAssignment, ts.SyntaxKind.ShorthandPropertyAssignment,
    ts.SyntaxKind.PropertyDeclaration, ts.SyntaxKind.MethodDeclaration, ts.SyntaxKind.PropertySignature,
    ts.SyntaxKind.MethodSignature, ts.SyntaxKind.GetAccessor, ts.SyntaxKind.SetAccessor].includes(declaration.kind);
  function inspect(node) {
    if (hasImports && ts.isImportDeclaration(node)) return;
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
      const symbol = ts.isShorthandPropertyAssignment(node.parent)
        ? checker.getShorthandAssignmentValueSymbol(node.parent) : checker.getSymbolAtLocation(node);
      if (hasImports && !isPropertyName(node) && symbol?.declarations?.length
          && symbol.declarations.every(declaration =>
            /lib\.(?:dom|webworker)/.test(declaration.getSourceFile().fileName)
            || (isDependency(declaration.getSourceFile().fileName)
              && !program.isSourceFileDefaultLibrary(declaration.getSourceFile())))) {
        throw new Error(`${file}: ${node.text} is a dependency-only global, not an Interceptor runtime API`);
      }
      const typeUse = ts.isTypeReferenceNode(node.parent) && node.parent.typeName === node;
      const allowedHere = inLeave(node) && ((node.text === 'Promise' && typeUse) || node.text === 'Uint8Array');
      if (forbidden.has(node.text) && !allowedHere) {
        throw new Error(`${file}: ${node.text} is unavailable in this host`);
      }
      if (node.text === 'fetch' && !ts.isTypeReferenceNode(node.parent)) {
        const symbol = ts.isShorthandPropertyAssignment(node.parent) ? checker.getShorthandAssignmentValueSymbol(node.parent) : checker.getSymbolAtLocation(node);
        if (symbol === fetchSymbol) {
          if (!inLeave(node) || !ts.isCallExpression(node.parent) || node.parent.expression !== node) {
            throw new Error(`${file}: fetch must be called directly inside a response.onLeave callback`);
          }
        } else if (symbol?.declarations?.some(d => d.name === node && !isPropertyDeclaration(d))
            || (ts.isBindingElement(node.parent) && node.parent.name === node)) {
          throw new Error(`${file}: fetch cannot be shadowed or redeclared`);
        }
      }
    }
    ts.forEachChild(node, inspect);
  }
  inspect(source);
  const diagnostics = ts.getPreEmitDiagnostics(program).filter(diagnostic => !hasImports || !diagnostic.file || !isDependency(diagnostic.file.fileName));
  if (diagnostics.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: f => f, getCurrentDirectory: () => root, getNewLine: () => '\n',
  }).replaceAll('npm i --save-dev', 'bun add --dev'));
  const output = {};
  const result = program.emit(source, (name, contents) => {
    if (!name.endsWith('.js') || output.code !== undefined) throw new Error('Unexpected compiler output');
    output.code = contents;
  });
  if (result.emitSkipped || output.code === undefined) throw new Error(`Compilation failed: ${file}`);
  const code = hasImports ? await bundle(output.code, file) : output.code;
  return { code, hooks, usesFiles: routedResult?.usesFiles ?? false };
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
      outputs[name] = (await compile(path.join(sourceDir, entry), sdk, hooks)).code;
    }
  }
  if (fs.existsSync(path.join(root, 'plugins'))) {
    const discover = path.join(import.meta.dirname, 'discover_routes.py');
    const discovered = JSON.parse(execFileSync(process.env.INTERCEPTOR_PYTHON || 'python3', [discover, '--root', root], { encoding: 'utf8', maxBuffer: 1048576 }));
    for (const [name, plugin] of Object.entries(discovered)) {
      if (name in outputs) throw new Error(`Duplicate plugin basename: ${name}`);
      const sourceFiles = {};
      const matches = [];
      for (const route of plugin.routes) {
        const result = await compile(path.join(root, 'plugins', name, route.file), sdk, [], true);
        if (result.usesFiles && plugin.metadata.write?.files !== true) {
          throw new Error(`plugins/${name}/${route.file}: Interceptor.createFile requires write.files: true in plugin.json`);
        }
        sourceFiles[route.emitted] = result.code;
        const hooks = Object.fromEntries(Object.entries(result.hooks).map(([leg, callbacks]) =>
          [leg, Object.fromEntries(Object.keys(callbacks).map(phase => [phase, route.emitted]))]));
        matches.push({ hosts: [route.host], methods: [route.method], path: { kind: 'exact', value: route.path }, hooks });
      }
      outputs[name] = { manifest: { ...plugin.metadata, matches }, sourceFiles };
    }
  }
  if (!Object.keys(outputs).length) throw new Error('No TypeScript plugins found');
  process.stdout.write(JSON.stringify(outputs));
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
