import TweetDisplay from './components/tweet_new'

const sampleTweet = {
    id: "1970220396541812896",
    text: "Just like dogs, different breeds of humans are designed for different kinds of lives\n\n(sorry to everyone who hoped this would be racist) https://t.co/k18HdoINOL",
    likes: 163,
    retweets: 11,
    quotes: 1,
    replies: 8,
    score: 196,
    followers: 23154,
    created_at: "Mon Sep 22 20:15:22 +0000 2025",
    url: "https://x.com/divya_venn/status/1970220396541812896",
    username: "divya venn",
    handle: "divya_venn",
    thread: [
      "Just like dogs, different breeds of humans are designed for different kinds of lives\n\n(sorry to everyone who hoped this would be racist) https://t.co/k18HdoINOL",
      "read how to find your calling in life here\nhttps://t.co/hcSFdkZAmk https://t.co/tPhbPMfw5E"
    ],
    reply: "tbh it’s always weird to me how some people get offended by the idea that temperament and talent aren’t distributed evenly. like, yes, obviously?  \nthe real trick is finding the “breed” you’re most similar to and designing your environment around it instead of coping relentlessly"
  }

function App() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-950 p-6">
      <TweetDisplay
        tweet={sampleTweet}
        replyText="Post your reply"
        onPublish={(text) => console.log('Published:', text)}
        onSkip={() => console.log('Skipped')}
      />
    </div>
  )
}

export default App
