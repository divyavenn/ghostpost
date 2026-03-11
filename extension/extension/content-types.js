export const TWITTER_THREAD_REGEX = /^https?:\/\/(?:www\.)?x\.com\/([^/]+)\/status\/(\d+)(?:[/?#].*)?$/i;
export const SUBSTACK_ARTICLE_REGEX = /^https?:\/\/[^/]+\/p\/[A-Za-z0-9-_.]+(?:[?#].*)?$/i;
export const PDF_REMOTE_REGEX = /^https?:\/\/[^?#]+\.pdf(?:[?#].*)?$/i;
export const PDF_LOCAL_REGEX = /^file:\/\/.+\.pdf(?:[?#].*)?$/i;
export const GENERIC_ARTICLE_REGEX = /^https?:\/\//i;
export const YOUTUBE_URL_REGEX = /^https?:\/\/(?:www\.)?youtube\.com\/(?:watch\?v=[\w-]{11}|shorts\/[\w-]{11})(?:[&#?].*)?$/i;

export const ContentTypes = Object.freeze({
  TWITTER: {
    name: 'twitter',
    regex: TWITTER_THREAD_REGEX,
    endpoint: 'convert-tweet',
    domain: "https://x.com",
    requiredCookies: ['auth_token', 'ct0'],
    errorMessage: 'Log in to X to download threads.',
    captureHtml: false,
  },
  SUBSTACK: {
    name: 'substack',
    regex: SUBSTACK_ARTICLE_REGEX,
    endpoint: 'convert-substack',
    domain:  "https://substack.com",
    requiredCookies: ['substack.sid'],
    errorMessage: 'only public previews without logging in.',
    captureHtml: true,
  },
  PDF_REMOTE: {
    name: 'pdf-remote',
    regex: PDF_REMOTE_REGEX,
    endpoint: 'convert-pdf',
    domain: null,
    requiredCookies: [],
    errorMessage: 'unable to fetch this PDF link.',
    captureHtml: false,
  },
  PDF_LOCAL: {
    name: 'pdf-local',
    regex: PDF_LOCAL_REGEX,
    endpoint: 'convert-pdf/stream',
    domain: null,
    requiredCookies: [],
    errorMessage: 'unable to read this local PDF.',
    captureHtml: false,
  },
  YOUTUBE: {
    name: 'youtube',
    regex: YOUTUBE_URL_REGEX,
    endpoint: 'convert-youtube',
    domain: null,
    requiredCookies: ['*'],
    errorMessage: 'unable to capture this YouTube page.',
    captureHtml: false,
    isVideo: true,
  },
  ARTICLE: {
    name: 'article',
    regex: GENERIC_ARTICLE_REGEX,
    endpoint: 'convert-article',
    domain: null,
    requiredCookies: [],
    errorMessage: 'unable to capture this page.',
    captureHtml: true,
  },
});



export const contentTypes = Object.freeze(Object.values(ContentTypes));
