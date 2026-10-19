/** Interceptor's synchronous plugin contract: schema 2 HTTP hooks and legacy synthetic tests.
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

  /** Must equal one `matches` entry of the manifest. Fields combine with AND, values within a field with OR. */
  interface Match {
    hosts: string[];
    methods?: string[];
    path?: { kind: 'exact' | 'prefix'; value: string };
    status?: { min: number; max: number };
  }
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
      onEnter?(request: RequestLeg, config: Config): Outcome;
      onLeave?(request: ReadOnlyRequestLeg, config: Config): Outcome;
    };
    response?: {
      onEnter?(response: ResponseLeg, config: Config): Outcome;
      onLeave?(response: ReadOnlyResponseLeg, config: Config): Outcome;
    };
  }
  /** Registers callbacks for one declared match; a source may call this up to 16 times. */
  function attach(match: Match, hooks: Hooks): void;
}
