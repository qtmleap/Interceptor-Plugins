// The synthetic test does not apply manifest filters, so check host and status here too.
function onResponse(event, config) {
  const request = event && event.request;
  const response = event && event.response;
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
