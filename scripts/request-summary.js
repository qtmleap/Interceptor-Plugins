// Request hook: summarises GET requests to example.com. The dry run does not apply manifest
// filters, so the method and host are checked here as well.
function onRequest(event, config) {
  var request = event && event.request;
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
