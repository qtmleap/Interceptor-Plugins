/// <reference path="../types/interceptor.d.ts" />
// The synthetic test does not apply manifest filters, so check method and host here too.
function onRequest(event: Interceptor.Event, config: Interceptor.Config): Interceptor.Result {
  const request = event && event.request;
  if (!request || request.method !== 'GET' || request.host !== 'example.com') {
    return { actions: [] };
  }
  return {
    actions: [{
      type: 'webhook',
      endpointId: config.endpoints.preview!,
      json: { summary: request.method + ' ' + request.host + request.path }
    }]
  };
}
