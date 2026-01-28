/**
 * Job executor using Playwright for headless browser automation
 */

const { chromium } = require('playwright');
const fs = require('fs');
const { loadConfig, getSessionFile } = require('./config');
const { logInfo, logError, logSuccess } = require('./logger');

/**
 * Execute a job using headless browser
 */
async function executeJob(job) {
    const config = loadConfig();
    const sessionFile = getSessionFile();

    logInfo(`Starting browser for job ${job.id}`);

    const browser = await chromium.launch({
        headless: config.headless,
        args: ['--disable-blink-features=AutomationControlled']
    });

    try {
        // Load saved Twitter session if it exists
        let context;
        if (fs.existsSync(sessionFile)) {
            logInfo('Loading saved Twitter session');
            const session = JSON.parse(fs.readFileSync(sessionFile, 'utf8'));
            context = await browser.newContext({ storageState: session });
        } else {
            logInfo('No saved session found - creating new context');
            context = await browser.newContext();
        }

        const page = await context.newPage();

        let result;

        // Route to appropriate handler based on job type
        switch (job.job_type) {
            case 'fetch_home_timeline':
                result = await fetchHomeTimeline(page, job.params);
                break;
            case 'search_tweets':
                result = await searchTweets(page, job.params);
                break;
            case 'fetch_user_timeline':
                result = await fetchUserTimeline(page, job.params);
                break;
            case 'deep_scrape_thread':
                result = await deepScrapeThread(page, job.params);
                break;
            default:
                throw new Error(`Unknown job type: ${job.job_type}`);
        }

        // Save session (in case cookies refreshed)
        logInfo('Saving Twitter session');
        const newSession = await context.storageState();
        fs.writeFileSync(sessionFile, JSON.stringify(newSession, null, 2));

        await browser.close();

        logSuccess(`Browser job completed: ${job.job_type}`);
        return result;
    } catch (error) {
        logError(`Browser job failed: ${error.message}`);
        await browser.close();
        throw error;
    }
}

/**
 * Fetch home timeline
 */
async function fetchHomeTimeline(page, params) {
    logInfo('Fetching home timeline');

    await page.goto('https://twitter.com/home', { waitUntil: 'networkidle' });

    // Wait for tweets to load
    await page.waitForSelector('[data-testid="tweet"]', { timeout: 10000 });

    // Scroll to load more tweets
    const maxTweets = params.max_tweets || 50;
    await scrollAndLoadTweets(page, maxTweets);

    // Extract tweets
    const tweets = await page.$$eval('[data-testid="tweet"]', (elements, max) => {
        return elements.slice(0, max).map(el => {
            try {
                const text = el.querySelector('[data-testid="tweetText"]')?.innerText || '';
                const author = el.querySelector('[data-testid="User-Name"]')?.innerText || '';
                const time = el.querySelector('time')?.getAttribute('datetime') || '';

                return {
                    text,
                    author,
                    created_at: time,
                    html: el.innerHTML.slice(0, 500) // Truncate for size
                };
            } catch (e) {
                return null;
            }
        }).filter(t => t !== null);
    }, maxTweets);

    logSuccess(`Scraped ${tweets.length} tweets from home timeline`);

    return {
        tweets,
        count: tweets.length,
        source: 'home_timeline'
    };
}

/**
 * Search tweets
 */
async function searchTweets(page, params) {
    const query = params.query;
    logInfo(`Searching tweets: ${query}`);

    const searchUrl = `https://twitter.com/search?q=${encodeURIComponent(query)}&src=typed_query&f=live`;
    await page.goto(searchUrl, { waitUntil: 'networkidle' });

    // Wait for results
    await page.waitForSelector('[data-testid="tweet"]', { timeout: 10000 });

    // Scroll to load more
    const maxResults = params.max_results || 50;
    await scrollAndLoadTweets(page, maxResults);

    // Extract tweets
    const tweets = await page.$$eval('[data-testid="tweet"]', (elements, max) => {
        return elements.slice(0, max).map(el => {
            try {
                const text = el.querySelector('[data-testid="tweetText"]')?.innerText || '';
                const author = el.querySelector('[data-testid="User-Name"]')?.innerText || '';
                const time = el.querySelector('time')?.getAttribute('datetime') || '';

                return {
                    text,
                    author,
                    created_at: time
                };
            } catch (e) {
                return null;
            }
        }).filter(t => t !== null);
    }, maxResults);

    logSuccess(`Found ${tweets.length} tweets for query: ${query}`);

    return {
        tweets,
        count: tweets.length,
        query,
        source: 'search'
    };
}

/**
 * Fetch user timeline
 */
async function fetchUserTimeline(page, params) {
    const targetUser = params.target_user;
    logInfo(`Fetching timeline for @${targetUser}`);

    await page.goto(`https://twitter.com/${targetUser}`, { waitUntil: 'networkidle' });

    // Wait for tweets
    await page.waitForSelector('[data-testid="tweet"]', { timeout: 10000 });

    const maxTweets = params.max_tweets || 50;
    await scrollAndLoadTweets(page, maxTweets);

    // Extract tweets
    const tweets = await page.$$eval('[data-testid="tweet"]', (elements, max) => {
        return elements.slice(0, max).map(el => {
            try {
                const text = el.querySelector('[data-testid="tweetText"]')?.innerText || '';
                const time = el.querySelector('time')?.getAttribute('datetime') || '';

                return {
                    text,
                    created_at: time
                };
            } catch (e) {
                return null;
            }
        }).filter(t => t !== null);
    }, maxTweets);

    logSuccess(`Scraped ${tweets.length} tweets from @${targetUser}`);

    return {
        tweets,
        count: tweets.length,
        user: targetUser,
        source: 'user_timeline'
    };
}

/**
 * Deep scrape thread (get replies)
 */
async function deepScrapeThread(page, params) {
    const tweetId = params.tweet_id;
    const authorHandle = params.author_handle;

    logInfo(`Deep scraping thread ${tweetId}`);

    const tweetUrl = `https://twitter.com/${authorHandle}/status/${tweetId}`;
    await page.goto(tweetUrl, { waitUntil: 'networkidle' });

    // Wait for main tweet and replies
    await page.waitForSelector('[data-testid="tweet"]', { timeout: 10000 });

    // Scroll to load replies
    await scrollAndLoadTweets(page, 100);

    // Extract main tweet and replies
    const threadData = await page.$$eval('[data-testid="tweet"]', (elements) => {
        const results = elements.map((el, index) => {
            try {
                const text = el.querySelector('[data-testid="tweetText"]')?.innerText || '';
                const author = el.querySelector('[data-testid="User-Name"]')?.innerText || '';
                const time = el.querySelector('time')?.getAttribute('datetime') || '';

                return {
                    text,
                    author,
                    created_at: time,
                    is_main_tweet: index === 0
                };
            } catch (e) {
                return null;
            }
        }).filter(t => t !== null);

        return results;
    });

    const mainTweet = threadData.find(t => t.is_main_tweet);
    const replies = threadData.filter(t => !t.is_main_tweet);

    logSuccess(`Scraped thread with ${replies.length} replies`);

    return {
        main_tweet: mainTweet,
        replies,
        reply_count: replies.length,
        tweet_id: tweetId
    };
}

/**
 * Helper: Scroll page to load more tweets
 */
async function scrollAndLoadTweets(page, targetCount) {
    let lastHeight = 0;
    let scrollAttempts = 0;
    const maxScrollAttempts = 10;

    while (scrollAttempts < maxScrollAttempts) {
        // Scroll down
        await page.evaluate(() => window.scrollBy(0, window.innerHeight));

        // Wait for new content to load
        await page.waitForTimeout(1000);

        // Check if we have enough tweets
        const tweetCount = await page.$$eval('[data-testid="tweet"]', els => els.length);
        if (tweetCount >= targetCount) {
            break;
        }

        // Check if we've reached the bottom
        const currentHeight = await page.evaluate(() => document.body.scrollHeight);
        if (currentHeight === lastHeight) {
            break; // No more content loading
        }

        lastHeight = currentHeight;
        scrollAttempts++;
    }
}

module.exports = {
    executeJob
};
