/// <reference path="../types/interceptor.d.ts" />
const serverError: Interceptor.Match = { hosts: ['example.com'], status: { min: 500, max: 599 } };

Interceptor.attach(serverError, {
  response: {
    onEnter(response) {
      if (!response.body || typeof response.body !== 'object' || Array.isArray(response.body)) return;
      response.body.maintenance = true;
    }
  }
});

Interceptor.attach(serverError, {
  response: {
    onLeave(response, config) {
      const endpointId = config.endpoints?.preview;
      if (!endpointId) return;
      return {
        actions: [{
          type: 'webhook',
          endpointId,
          json: { host: response.request.host!, status: response.status! }
        }]
      };
    }
  }
});
