import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import TweetDisplay from './components/tweet_new'


const test_tweet = {
    "id": "1965306611846840558",
    "text": "Wow, Google built an AI system to help scientists write expert-level empirical software.\n\nThe system uses a Large Language Model (LLM) and Tree Search (TS) to systematically improve the quality metric and intelligently navigate the large space of possible solutions. \n\nThe system https://t.co/1Qh21dPheK",
    "likes": 122,
    "retweets": 19,
    "quotes": 5,
    "replies": 4,
    "score": 179,
    "followers": 8999,
    "created_at": "Tue Sep 09 06:49:44 +0000 2025",
    "url": "https://x.com/i/web/status/1965306611846840558",
    "thread": [
      "Wow, Google built an AI system to help scientists write expert-level empirical software.\n\nThe system uses a Large Language Model (LLM) and Tree Search (TS) to systematically improve the quality metric and intelligently navigate the large space of possible solutions. \n\nThe system https://t.co/1Qh21dPheK",
      "An AI system to help scientists write expert-level empirical software\n\nGoogle, et al.\nPaper: https://t.co/4z5mSI48Kq https://t.co/ERJN1CW4EM"
    ]
  }

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <div>
        <a href="https://vite.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
        <TweetDisplay
          tweet={test_tweet}
          replyText="This is a tweet"
          onPublish={(text) => console.log('Published:', text)}
          onSkip={() => console.log('Skipped')}
        />
      </div>
      <h1>Vite + React</h1>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>
        <p>
          Edit <code>src/App.tsx</code> and save to test HMR
        </p>
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
