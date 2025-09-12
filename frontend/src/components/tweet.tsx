import { useState } from 'react';

export interface TweetData {
  id: string;
  text: string;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  score: number;
  followers: number;
  created_at: string;
  url: string;
  thread?: string[];
}

interface TweetDisplayProps {
  tweet: TweetData;
  replyText: string;
  onPublish: (text: string) => void;
  onSkip: () => void;
}

export default function TweetDisplay({ tweet, replyText, onPublish, onSkip }: TweetDisplayProps) {
  const [editedText, setEditedText] = useState(replyText);

  // For demo purposes, we'll use some static values that match the screenshot
  // In a real app, you might want to get these from user data or the tweet itself
  const displayName = "stef 🫴";
  const handle = "@stefaesthesia";
  const verified = true;
  const userAvatar = "https://pbs.twimg.com/profile_images/1700172320733253632/2QWw2Xrj_400x400.jpg";
  const myAvatar = "https://randomuser.me/api/portraits/women/44.jpg";
  
  // Parse created_at to show a relative time (like "5h")
  const getRelativeTime = (dateStr: string): string => {
    try {
      const tweetDate = new Date(dateStr);
      const now = new Date();
      const diffHours = Math.floor((now.getTime() - tweetDate.getTime()) / (1000 * 60 * 60));
      
      if (diffHours < 1) return "now";
      if (diffHours < 24) return `${diffHours}h`;
      if (diffHours < 48) return "1d";
      return `${Math.floor(diffHours / 24)}d`;
    } catch (e) {
      return "5h"; // Fallback to match screenshot
    }
  };

  return (
    <div
      style={{
        background: '#000000',
        borderRadius: '16px',
        maxWidth: '600px',
        margin: '0 auto',
        boxShadow: '0 4px 15px rgba(0, 0, 0, 0.5)',
        position: 'relative',
        color: '#fff',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
      }}
    >
      {/* Modal header with close button */}
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #333' }}>
        <div>
          <button 
            style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: '8px' }}
            onClick={onSkip}
          >
            ✕
          </button>
        </div>
        <div style={{ color: '#1d9bf0', fontWeight: 'bold', fontSize: '16px' }}>
          Drafts
        </div>
      </div>

      {/* Tweet content */}
      <div style={{ padding: '16px' }}>
        {/* Tweet author info */}
        <div style={{ display: 'flex', marginBottom: '12px' }}>
          <img 
            src={userAvatar} 
            alt={displayName} 
            style={{ width: '48px', height: '48px', borderRadius: '50%', marginRight: '12px' }} 
          />
          <div>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ fontWeight: 'bold', marginRight: '4px' }}>{displayName}</span>
              {verified && <span style={{ color: '#1d9bf0', marginRight: '4px' }}>✓</span>}
              <span style={{ color: '#71767b', marginRight: '4px' }}>{handle}</span>
              <span style={{ color: '#71767b' }}>· {getRelativeTime(tweet.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Tweet text */}
        <div style={{ fontSize: '16px', lineHeight: '1.5', marginBottom: '12px', whiteSpace: 'pre-wrap' }}>
          {tweet.text}
          {tweet.text.length > 140 && (
            <span style={{ color: '#1d9bf0', cursor: 'pointer' }}>Show more</span>
          )}
        </div>

        {/* Replying to */}
        <div style={{ color: '#71767b', fontSize: '14px', marginBottom: '16px' }}>
          Replying to <span style={{ color: '#1d9bf0' }}>{handle}</span>
        </div>

        {/* Reply box */}
        <div style={{ display: 'flex', marginTop: '12px', position: 'relative' }}>
          <img 
            src={myAvatar} 
            alt="Your avatar" 
            style={{ width: '40px', height: '40px', borderRadius: '50%', marginRight: '12px', alignSelf: 'flex-start' }} 
          />
          <div style={{ flexGrow: 1 }}>
            <textarea
              placeholder="Post your reply"
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              style={{
                width: '100%',
                minHeight: '80px',
                background: 'transparent',
                border: 'none',
                color: '#fff',
                fontSize: '18px',
                resize: 'none',
                outline: 'none',
                padding: '0',
                marginBottom: '16px',
                fontFamily: 'inherit'
              }}
            />

            {/* Action buttons */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button style={{ background: 'none', border: 'none', color: '#1d9bf0', cursor: 'pointer', padding: '8px' }}>
                  📷
                </button>
                <button style={{ background: 'none', border: 'none', color: '#1d9bf0', cursor: 'pointer', padding: '8px' }}>
                  📊
                </button>
                <button style={{ background: 'none', border: 'none', color: '#1d9bf0', cursor: 'pointer', padding: '8px' }}>
                  😀
                </button>
                <button style={{ background: 'none', border: 'none', color: '#1d9bf0', cursor: 'pointer', padding: '8px' }}>
                  📅
                </button>
                <button style={{ background: 'none', border: 'none', color: '#1d9bf0', cursor: 'pointer', padding: '8px' }}>
                  📍
                </button>
              </div>
              <button
                onClick={() => onPublish(editedText)}
                style={{
                  background: '#1d9bf0',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '9999px',
                  padding: '8px 16px',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Reply
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
}
            ✅
          </span>
        )}
      </div>
    </div>
  );
}

// Add type declaration
declare global {
  interface Window {
    twttr?: any;
  }
}