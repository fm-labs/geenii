/** Join a base url and a path, independent of trailing/leading slashes. */
export function joinUrl(baseUrl: string, path: string) {
  return baseUrl.replace(/\/+$/, '') + '/' + path.replace(/^\/+/, '')
}
