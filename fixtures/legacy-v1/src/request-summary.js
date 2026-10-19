// The synthetic test does not apply manifest filters, so check method and host here too.
function onRequest(event, config) {
  const request = event && event.request;
  if (!request || request.method !== 'GET' || request.host !== 'example.com') {
    return { actions: [] };
  }
  return {
    actions: [{
      type: 'webhook',
      endpointId: config.endpoints.preview,
      json: { summary: request.method + ' ' + request.host + request.path }
    }]
  };
}
