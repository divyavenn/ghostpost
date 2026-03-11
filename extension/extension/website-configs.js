// Website configurations for cookie monitoring
// Each trigger is a tuple: [url, handlerFunction]
// Handler function should return an object with data to send along with cookies

import { getUsernameFromOAuth, getUsernameFromXHome } from './cookie-handlers.js';

export function getWebsiteConfigs() {
  return [
    {
      website: 'twitter',
      triggers: [
        ['http://localhost/login-success', getUsernameFromOAuth],
        ['http://localhost:5173/login-success', getUsernameFromOAuth],
        ['https://x.ghostposter.app/login-success', getUsernameFromOAuth],
        ['https://x.com/home', getUsernameFromXHome]
      ],
      backend_urls: [
        'https://x.ghostposter.app',
        'http://127.0.0.1:8000',
        'http://0.0.0.0:8000'
      ],
      endpoint: `/auth/twitter/import-cookies`,
      domains: ['.x.com', '.twitter.com']
    }
    // Add more websites here in the future
    // Example:
    // {
    //   website: 'linkedin',
    //   triggers: [
    //     ['https://www.linkedin.com/feed/', getLinkedInUsername]
    //   ],
    //   endpoint: `${API_BASE_URL}/auth/linkedin/import-cookies`,
    //   domains: ['.linkedin.com']
    // }
  ];
}
