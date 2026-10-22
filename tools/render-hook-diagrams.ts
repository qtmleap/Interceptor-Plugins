import { createHash } from "node:crypto";
import { resolve } from "node:path";

// Both themes share geometry; generated files contain no external resources.
const palettes = {
  light: {
    background: '#ffffff', panel: '#f6f8fb', border: '#dce2ea', text: '#202b3c',
    muted: '#64748b', guide: '#d5dde7', accent: '#2563eb', tint: '#edf4ff',
    accentBorder: '#a8c7fa', after: '#68778d', card: '#ffffff', badge: '#e9eef5',
  },
  dark: {
    background: '#1b1b1f', panel: '#22252c', border: '#373e49', text: '#edf1f7',
    muted: '#a5b1c2', guide: '#3c4553', accent: '#8cb8ff', tint: '#25344f',
    accentBorder: '#5275aa', after: '#a5b1c2', card: '#2a2e37', badge: '#303744',
  },
} as const;

export function renderPluginHooks(theme: keyof typeof palettes, locale: "ja" | "en" = "ja"): string {
  const c = palettes[theme];
  const hook = (x: number, y: number, number: string, name: string, detail: string, editable: boolean) => `
    <g transform="translate(${x} ${y})">
      <rect width="256" height="76" rx="12" fill="${editable ? c.tint : c.card}" stroke="${editable ? c.accentBorder : c.border}"/>
      <circle cx="25" cy="27" r="12" fill="${editable ? c.accent : c.badge}"/>
      <text x="25" y="31" text-anchor="middle" font-size="12" font-weight="650" fill="${editable ? c.background : c.text}">${number}</text>
      <text class="code" x="47" y="33" font-size="17" fill="${editable ? c.accent : c.text}">${name}</text>
      <text x="47" y="58" font-size="15" fill="${c.muted}">${detail}</text>
    </g>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="760" height="568" viewBox="0 0 760 568" role="img" aria-labelledby="title desc">
  <title id="title">通信と4つのHookの位置</title>
  <desc id="desc">リクエストはクライアントからInterceptorを経由してサーバーへ、レスポンスは逆向きに流れます。onEnterでは転送前の内容を変更でき、onLeaveは転送後の後処理です。</desc>
  <style>
    text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans JP', sans-serif; }
    .code { font-family: ui-monospace, 'SFMono-Regular', Consolas, monospace; font-weight: 500; }
  </style>
  <defs>
    <marker id="forward" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9" fill="none" stroke="${c.accent}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></marker>
    <marker id="after" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1 L9 5 L1 9" fill="none" stroke="${c.after}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></marker>
  </defs>
  <rect width="760" height="568" rx="16" fill="${c.background}"/>
  <rect x="216" y="24" width="328" height="490" rx="18" fill="${c.panel}" stroke="${c.border}"/>
  <text x="380" y="64" text-anchor="middle" font-size="23" font-weight="650" fill="${c.text}">Interceptor</text>
  <text x="380" y="87" text-anchor="middle" font-size="13" fill="${c.muted}">条件が一致した通信のHookを実行</text>
  <path d="M240 108 H520" stroke="${c.border}"/>
  <text x="102" y="61" text-anchor="middle" font-size="18" font-weight="600" fill="${c.text}">クライアント</text>
  <text x="102" y="84" text-anchor="middle" font-size="13" fill="${c.muted}">元のアプリ</text>
  <text x="658" y="61" text-anchor="middle" font-size="18" font-weight="600" fill="${c.text}">サーバー</text>
  <path d="M102 108 V496 M658 108 V496" stroke="${c.guide}" stroke-width="1.5" stroke-dasharray="3 7"/>

  <rect x="42" y="130" width="120" height="28" rx="6" fill="${c.background}"/>
  <text x="102" y="150" text-anchor="middle" font-size="15" font-weight="600" fill="${c.accent}">リクエスト</text>
  <path d="M102 184 H252 M508 184 H658" fill="none" stroke="${c.accent}" stroke-width="2.5" marker-end="url(#forward)"/>
  <circle cx="102" cy="184" r="4" fill="${c.accent}"/>
  <text x="589" y="170" text-anchor="middle" font-size="13" fill="${c.muted}">送信</text>
  <path d="M530 184 V278 H508" fill="none" stroke="${c.after}" stroke-width="1.8" stroke-dasharray="4 5" stroke-linejoin="round" marker-end="url(#after)"/>
  <circle cx="530" cy="184" r="3" fill="${c.after}"/>
  ${hook(252, 146, '1', 'request.onEnter', '送信前・JSONを変更', true)}
  ${hook(252, 240, '2', 'request.onLeave', '送信成功後の処理', false)}

  <path d="M240 329 H520" stroke="${c.border}"/>
  <rect x="598" y="324" width="120" height="28" rx="6" fill="${c.background}"/>
  <text x="658" y="344" text-anchor="middle" font-size="15" font-weight="600" fill="${c.accent}">レスポンス</text>
  <path d="M658 380 H508 M252 380 H102" fill="none" stroke="${c.accent}" stroke-width="2.5" marker-end="url(#forward)"/>
  <circle cx="658" cy="380" r="4" fill="${c.accent}"/>
  <text x="175" y="366" text-anchor="middle" font-size="13" fill="${c.muted}">返却</text>
  <path d="M232 380 V474 H252" fill="none" stroke="${c.after}" stroke-width="1.8" stroke-dasharray="4 5" stroke-linejoin="round" marker-end="url(#after)"/>
  <circle cx="232" cy="380" r="3" fill="${c.after}"/>
  ${hook(252, 342, '3', 'response.onEnter', '返却前・JSONを変更', true)}
  ${hook(252, 436, '4', 'response.onLeave', '返却成功後の処理', false)}

  <path d="M36 542 H60" stroke="${c.accent}" stroke-width="2.5"/>
  <text x="69" y="547" font-size="13" fill="${c.muted}">通信の流れ</text>
  <path d="M178 542 H202" stroke="${c.after}" stroke-width="1.8" stroke-dasharray="4 5"/>
  <text x="211" y="547" font-size="13" fill="${c.muted}">転送後の処理</text>
  <text x="724" y="547" text-anchor="end" font-size="12" fill="${c.muted}">schemaVersion 2</text>
</svg>
`.replace(/[ \t]+$/gm, "");
  if (locale === 'ja') return svg;
  const translations = {
    '通信と4つのHookの位置': 'Traffic and four Hook positions',
    'リクエストはクライアントからInterceptorを経由してサーバーへ、レスポンスは逆向きに流れます。onEnterでは転送前の内容を変更でき、onLeaveは転送後の後処理です。': 'Requests flow from client through Interceptor to server; responses flow back. onEnter can edit content before forwarding; onLeave runs after forwarding.',
    '条件が一致した通信のHookを実行': 'Run hooks for matching traffic',
    'クライアント': 'Client', '元のアプリ': 'Original app', 'サーバー': 'Server',
    'リクエスト': 'Request', 'レスポンス': 'Response',
    '送信前・JSONを変更': 'Before sending · edit JSON',
    '送信成功後の処理': 'After successful forwarding',
    '返却前・JSONを変更': 'Before returning · edit JSON',
    '返却成功後の処理': 'After successful forwarding',
    '送信': 'Send', '返却': 'Return', '通信の流れ': 'Traffic',
    '転送後の処理': 'After forwarding', 'schemaVersion 2': 'schemaVersion 2',
  };
  return Object.entries(translations).reduce((text, [ja, en]) => text.replaceAll(ja, en), svg);
}

if (import.meta.main) {
  const root = resolve(import.meta.dir, '..');
  const check = process.argv.includes('--check');
  const sha = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex');
  const outputs: Record<string, string> = {};
  for (const locale of ['ja', 'en'] as const) {
    for (const theme of ['light', 'dark'] as const) {
      const path = resolve(root, `website/public/diagrams/plugin-hooks-${locale}-${theme}.svg`);
      const content = renderPluginHooks(theme, locale);
      outputs[`website/public/diagrams/plugin-hooks-${locale}-${theme}.svg`] = sha(new TextEncoder().encode(content));
      if (check) {
        if (!(await Bun.file(path).exists()) || await Bun.file(path).text() !== content) {
          throw new Error(`Diagram is out of date: ${path}`);
        }
      } else {
        await Bun.write(path, content);
      }
    }
  }
  const manifestPath = resolve(root, 'docs/diagrams/generated.json');
  const input = 'tools/render-hook-diagrams.ts';
  const manifest = { generator: 'SVG renderer (Bun)', inputs: { [input]: sha(new Uint8Array(await Bun.file(resolve(root, input)).arrayBuffer())) }, outputs };
  if (check) {
    if (JSON.stringify(await Bun.file(manifestPath).json()) !== JSON.stringify(manifest)) throw new Error('Diagram manifest is out of date; run bun run diagrams:render');
    console.log('SVG source and generated diagrams match');
  } else {
    await Bun.write(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  }
}
