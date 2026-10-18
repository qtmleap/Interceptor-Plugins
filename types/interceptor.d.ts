/** Interceptor's synchronous synthetic-test contract. Optional fields depend on input and read grants.
 * Types aid authoring; the app validates limits and permissions at runtime.
 */
declare namespace Interceptor {
  type JSON = null | boolean | number | string | JSON[] | { [key: string]: JSON };
  type Phase = 'request.headers' | 'request.completed' | 'response.headers' | 'response.completed';
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
    phase?: Phase;
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
}
