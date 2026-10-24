const isHeaderValue = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0 && !/[\u0000-\u001f\u007f]/.test(value)

Interceptor.attach({
  response: {
    async onLeave(res) {
      if (res.status !== 201) return
      const body = res.body as { bulletToken?: unknown; lang?: unknown } | null | undefined
      const bulletToken = body?.bulletToken
      if (!isHeaderValue(bulletToken)) return

      const headers = res.request.headers ?? {}
      const webViewVersion = headers['x-web-view-ver']
      const language = isHeaderValue(body?.lang) ? body.lang : headers['accept-language']
      if (!isHeaderValue(webViewVersion) || !isHeaderValue(language)) throw new Error('missing-context')

      const userAgent = headers['user-agent']
      const context = {
        bulletToken, webViewVersion, language,
        ...(isHeaderValue(userAgent) ? { userAgent } : {}),
      }
      await Interceptor.createFile({
        storage: Interceptor.Storage.iCloudDrive,
        atPath: 'SplatNet3/auth.json',
        contents: JSON.stringify(context, null, 2) + '\n',
      })
    },
  },
})
