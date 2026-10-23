/** Interceptor's plugin contract: synchronous schema 2 HTTP hooks (only `response.onLeave` may be async) and legacy synthetic tests.
 * Optional fields depend on input and read grants.
 * Types aid authoring; the app validates limits and permissions at runtime.
 */
declare namespace Interceptor {
  type JSON = null | boolean | number | string | JSON[] | { [key: string]: JSON };
  /** Legacy schema 1 phases. */
  type Phase = 'request.headers' | 'request.completed' | 'response.headers' | 'response.completed';
  /** Schema 2 lifecycle phases; `onEnter` runs before forwarding, `onLeave` after a successful forward. */
  type HookPhase = 'request.onEnter' | 'request.onLeave' | 'response.onEnter' | 'response.onLeave';
  interface Request {
    method?: string;
    host?: string;
    path?: string;
    headers?: { [name: string]: string };
    query?: { [name: string]: string };
    body?: JSON;
  }
  interface Response {
    status?: number;
    headers?: { [name: string]: string };
    body?: JSON;
  }
  interface Event {
    id?: string;
    exchangeID?: string;
    phase?: Phase | HookPhase;
    time?: string;
    request?: Request;
    response?: Response;
  }
  interface Config {
    endpoints: { [binding: string]: string | undefined };
    settings?: { [name: string]: JSON };
  }
  interface WebhookAction {
    type: 'webhook';
    endpointId: string;
    json: JSON;
  }
  interface Result { actions: WebhookAction[] }

  /** The request as granted by the manifest. `body` is the JSON tree; edit it in place on `onEnter` only. */
  interface RequestLeg {
    readonly id?: string;
    readonly method?: string;
    readonly host?: string;
    readonly path?: string;
    readonly headers?: { readonly [name: string]: string };
    readonly query?: { readonly [name: string]: string };
    body: any;
  }
  interface ResponseLeg {
    readonly status?: number;
    readonly headers?: { readonly [name: string]: string };
    readonly request: ReadOnlyRequestLeg;
    body: any;
  }
  /** `onLeave` traffic is read-only: edits made there are rejected. */
  type ReadOnlyJSON = null | boolean | number | string | readonly ReadOnlyJSON[] | { readonly [key: string]: ReadOnlyJSON };
  type ReadOnlyRequestLeg = Omit<RequestLeg, 'body'> & { readonly body?: ReadOnlyJSON };
  type ReadOnlyResponseLeg = Omit<ResponseLeg, 'body'> & { readonly body?: ReadOnlyJSON };
  type Outcome = Result | void;
  interface Hooks {
    request?: {
      onEnter?(req: RequestLeg, cfg: Config): Outcome;
      onLeave?(req: ReadOnlyRequestLeg, cfg: Config): Outcome;
    };
    response?: {
      onEnter?(res: ResponseLeg, cfg: Config): Outcome;
      /** Requires a compatible host that implements global `fetch` and awaits this callback. */
      onLeave?(res: ReadOnlyResponseLeg, cfg: Config): Outcome | Promise<Outcome>;
    };
  }
  /** Options for `send`. Supply a string header map, including an empty map when no headers are needed. */
  interface SendOptions {
    readonly headers: { readonly [name: string]: string };
  }
  /**
   * Records an HTTP request intent for a binding declared in the manifest `outbound` metadata.
   * Synchronous and non-blocking: it returns no value, Promise or Response, and the hook never sees the result.
   */
  function send(binding: string, options: SendOptions): void;
  /** Options for the global `fetch`, available only inside a `response.onLeave` callback. */
  interface FetchInit {
    method?: 'GET' | 'POST' | 'PUT';
    headers?: { [name: string]: string };
    body?: string;
  }
  interface FetchResponse {
    readonly status: number;
    readonly ok: boolean;
    readonly bodyUsed: boolean;
    text(): Promise<string>;
    json(): Promise<any>;
  }
  /**
   * Stores `jsonText` (valid JSON text) under `key` in the plugin's own files. Requires `write.files: true`.
   * Call it directly (not aliased or via `globalThis`) inside a registered `response.onLeave` callback and await it;
   * a failure rejects. The compiler checks direct references; runtime enforcement remains the host's responsibility.
   */
  function saveJSON(key: string, jsonText: string): Promise<void>;
  /** Registers this file's handlers. The build derives targets from its path. */
  function attach(hooks: Hooks): void;
}
/**
 * Asynchronous HTTP request. Call it directly (not aliased, shadowed or via `globalThis`) inside a
 * `response.onLeave` callback body, including nested functions there. The compiler checks direct
 * references; runtime enforcement remains the host's responsibility.
 */
declare function fetch(url: string, init?: Interceptor.FetchInit): Promise<Interceptor.FetchResponse>;
