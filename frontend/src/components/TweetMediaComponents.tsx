import styled, { css } from 'styled-components';
import { type MediaItem, type QuotedTweet } from '../api/client';

// --- Types (re-exported for convenience) ---
export type { MediaItem, QuotedTweet };

// --- Quoted Tweet Styled Components ---
const QuotedTweetLink = styled.a`
  margin-top: 0.75rem;
  display: block;
  border-radius: 1rem;
  border: 1px solid #404040;
  padding: 0.75rem;
  transition: background-color 0.2s;
  text-decoration: none;

  &:hover {
    background-color: #171717;
  }
`;

const QuotedTweetHeader = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
`;

const QuotedTweetAvatar = styled.img`
  height: 1.25rem;
  width: 1.25rem;
  border-radius: 9999px;
`;

const QuotedTweetMeta = styled.div`
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
`;

const QuotedTweetAuthor = styled.span`
  font-weight: 600;
  color: #d4d4d4;
`;

const QuotedTweetHandle = styled.span`
  color: #737373;
`;

const QuotedTweetText = styled.p`
  white-space: pre-wrap;
  font-size: 0.875rem;
  color: #d4d4d4;
  margin: 0 0 0.5rem 0;
`;

const QuotedTweetMediaContainer = styled.div`
  border-radius: 0.75rem;
  overflow: hidden;
  margin-top: 0.5rem;

  img {
    width: 100%;
    max-height: 12rem;
    object-fit: cover;
  }
`;

// --- Media Grid Styled Components ---
const MediaGridContainer = styled.div<{ $count: number }>`
  margin-top: 0.75rem;
  border-radius: 1rem;
  overflow: hidden;
  border: 1px solid #262626;

  ${({ $count }) => $count === 1 && css`
    max-width: 42rem;
  `}

  ${({ $count }) => $count >= 2 && css`
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.125rem;
  `}
`;

const MediaImage = styled.img<{ $count: number; $index: number }>`
  width: 100%;
  display: block;

  ${({ $count }) => $count === 1 && css`
    object-fit: contain;
    max-height: 37.5rem;
  `}

  ${({ $count, $index }) => $count === 3 && $index === 0 && css`
    grid-row: span 2;
    height: 100%;
    object-fit: cover;
  `}

  ${({ $count, $index }) => ($count >= 2 && !($count === 3 && $index === 0)) && css`
    height: 12rem;
    object-fit: cover;
  `}
`;

// --- QuotedTweetDisplay Component ---
interface QuotedTweetDisplayProps {
  quotedTweet: QuotedTweet;
  /** Compact mode for smaller displays like comment cards */
  compact?: boolean;
  className?: string;
}

/**
 * Displays a quoted tweet with author info, text, and optional media.
 * Used in TweetDisplay, PostWithComments, and PostedTweet components.
 */
export function QuotedTweetDisplay({ quotedTweet, compact = false, className }: QuotedTweetDisplayProps) {
  const defaultAvatar = 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';

  if (compact) {
    // Compact version for comment cards
    return (
      <CompactQuotedTweetBox
        href={quotedTweet.url || '#'}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
      >
        <CompactQuotedTweetHeader>
          {quotedTweet.author_profile_pic_url && (
            <CompactQuotedTweetAvatar
              src={quotedTweet.author_profile_pic_url}
              alt={quotedTweet.author_name}
              onError={(e) => {
                (e.target as HTMLImageElement).src = defaultAvatar;
              }}
            />
          )}
          <CompactQuotedTweetAuthor>
            @{quotedTweet.author_handle}
          </CompactQuotedTweetAuthor>
        </CompactQuotedTweetHeader>
        <CompactQuotedTweetText>{quotedTweet.text}</CompactQuotedTweetText>
        {quotedTweet.media && quotedTweet.media.length > 0 && (
          <CompactQuotedTweetMedia>
            <img
              src={quotedTweet.media[0].url}
              alt={quotedTweet.media[0].alt_text || ''}
            />
          </CompactQuotedTweetMedia>
        )}
      </CompactQuotedTweetBox>
    );
  }

  // Full version for TweetDisplay and PostedTweet
  return (
    <QuotedTweetLink
      href={quotedTweet.url || '#'}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className={className}
    >
      <QuotedTweetHeader>
        <QuotedTweetAvatar
          src={quotedTweet.author_profile_pic_url || defaultAvatar}
          alt={quotedTweet.author_name}
          onError={(e) => {
            (e.target as HTMLImageElement).src = defaultAvatar;
          }}
        />
        <QuotedTweetMeta>
          <QuotedTweetAuthor>{quotedTweet.author_name}</QuotedTweetAuthor>
          <QuotedTweetHandle>@{quotedTweet.author_handle}</QuotedTweetHandle>
        </QuotedTweetMeta>
      </QuotedTweetHeader>

      <QuotedTweetText>
        {quotedTweet.text}
      </QuotedTweetText>

      {quotedTweet.media && quotedTweet.media.length > 0 && (
        <QuotedTweetMediaContainer>
          {quotedTweet.media.map((media, idx) => (
            <img
              key={idx}
              src={media.url}
              alt={media.alt_text || ''}
            />
          ))}
        </QuotedTweetMediaContainer>
      )}
    </QuotedTweetLink>
  );
}

// --- Compact Styled Components (for comment cards) ---
const CompactQuotedTweetBox = styled.a`
  display: block;
  background: #171717;
  border: 1px solid #262626;
  border-radius: 0.5rem;
  padding: 0.5rem;
  margin: 0.5rem 0;
  text-decoration: none;
  transition: background 0.2s;

  &:hover {
    background: #1f1f1f;
  }
`;

const CompactQuotedTweetHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin-bottom: 0.25rem;
`;

const CompactQuotedTweetAvatar = styled.img`
  width: 1rem;
  height: 1rem;
  border-radius: 9999px;
`;

const CompactQuotedTweetAuthor = styled.span`
  font-size: 0.75rem;
  color: #a3a3a3;
`;

const CompactQuotedTweetText = styled.p`
  font-size: 0.8125rem;
  color: #d4d4d4;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const CompactQuotedTweetMedia = styled.div`
  margin-top: 0.375rem;
  border-radius: 0.375rem;
  overflow: hidden;

  img {
    width: 100%;
    max-height: 6rem;
    object-fit: cover;
  }
`;

// --- TweetMediaGrid Component ---
interface TweetMediaGridProps {
  media: MediaItem[];
  className?: string;
  /** Compact mode for smaller displays */
  compact?: boolean;
}

/**
 * Displays a grid of media items (photos).
 * Handles 1-4 images with proper grid layout.
 */
export function TweetMediaGrid({ media, className, compact = false }: TweetMediaGridProps) {
  const photos = media.filter(m => m.type === 'photo');
  if (photos.length === 0) return null;

  if (compact) {
    // Compact version for comment cards
    return (
      <CompactMediaGrid data-count={photos.length} className={className}>
        {photos.slice(0, 4).map((item, idx) => (
          <CompactMediaImage
            key={idx}
            src={item.url}
            alt={item.alt_text || `Image ${idx + 1}`}
            onClick={() => window.open(item.url, '_blank')}
          />
        ))}
      </CompactMediaGrid>
    );
  }

  // Full version
  return (
    <MediaGridContainer $count={photos.length} className={className}>
      {photos.map((item, idx) => (
        <MediaImage
          key={idx}
          src={item.url}
          alt={item.alt_text || `Image ${idx + 1}`}
          $count={photos.length}
          $index={idx}
          loading="lazy"
        />
      ))}
    </MediaGridContainer>
  );
}

// --- Compact Media Grid Styled Components ---
const CompactMediaGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.375rem;
  margin: 0.5rem 0;
  border-radius: 0.5rem;
  overflow: hidden;

  &[data-count="1"] {
    grid-template-columns: 1fr;
  }
`;

const CompactMediaImage = styled.img`
  width: 100%;
  height: 80px;
  object-fit: cover;
  cursor: pointer;
  transition: opacity 0.2s;

  &:hover {
    opacity: 0.9;
  }
`;
