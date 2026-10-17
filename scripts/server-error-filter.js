// Response hook: reports 5xx responses from example.com. The dry run does not apply manifest
// filters, so the host and the 500...599 status range are checked here as well.
function onResponse(event, config) {
  var request = event && event.request;
  var response = event && event.response;
  if (!request || !response || request.host !== 'example.com') {
    return { actions: [] };
  }
  if (typeof response.status !== 'number' || response.status < 500 || response.status > 599) {
    return { actions: [] };
  }
  return {
    actions: [{
      type: 'webhook',
      endpointId: config.endpoints.preview,
      json: { host: request.host, status: response.status }
    }]
  };
}
