Interceptor.attach({
  response: {
    onLeave(res) {
      const body = res.body;
      if (res.status !== 200 || !body || typeof body !== 'object' || Array.isArray(body) || !('accessToken' in body)) return;
      const token = body.accessToken;
      if (typeof token !== 'string' || !/^[A-Za-z0-9._~-]{1,256}$/.test(token)) return;
      Interceptor.send('bearer', { headers: { authorization: 'Bearer ' + token } });
      const setCookie = res.headers?.['set-cookie'];
      const cookie = typeof setCookie === 'string' ? setCookie.split(';', 1)[0]?.trim() : undefined;
      if (cookie && /^fixture_session=[A-Za-z0-9._~-]{1,256}$/.test(cookie)) {
        Interceptor.send('cookie', { headers: { cookie } });
      }
    }
  }
});
