import { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Autoplay, Pagination } from 'swiper/modules';
import 'swiper/css';
import 'swiper/css/pagination';
import 'swiper/css/autoplay';

// --- Types ---
export type MediaType = 'image' | 'video' | 'carousel';

export interface MediaData {
  type: MediaType;
  url?: string;  // For image and video
  urls?: string[];  // For carousel
}

// --- Animations ---
const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

// --- Styled Components ---
const MediaContainer = styled.div`
  margin-top: 1rem;
  margin-bottom: 1rem;
  width: 100%;
  animation: ${fadeIn} 0.6s ease-out;
`;

const StyledImage = styled.img`
  width: 100%;
  height: auto;
  border-radius: 8px;
  display: block;
`;

const StyledVideo = styled.video`
  width: 100%;
  height: auto;
  border-radius: 8px;
  display: block;
`;

const CarouselContainer = styled.div`
  width: 100%;

  .swiper {
    border-radius: 8px;
    overflow: hidden;
  }

  .swiper-pagination-bullet {
    background: #E5E5E5;
    opacity: 0.5;
  }

  .swiper-pagination-bullet-active {
    background: #60a5fa;
    opacity: 1;
  }
`;

const CarouselImage = styled.img`
  width: 100%;
  height: auto;
  display: block;
`;

// --- Image Component ---
interface ImageMediaProps {
  url: string;
}

export function ImageMedia({ url }: ImageMediaProps) {
  const [loaded, setLoaded] = useState(false);

  return (
    <MediaContainer>
      <StyledImage
        src={url}
        alt=""
        onLoad={() => setLoaded(true)}
        style={{ opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease' }}
      />
    </MediaContainer>
  );
}

// --- Video Component ---
interface VideoMediaProps {
  url: string;
}

export function VideoMedia({ url }: VideoMediaProps) {
  return (
    <MediaContainer>
      <StyledVideo controls>
        <source src={url} type="video/mp4" />
        Your browser does not support the video tag.
      </StyledVideo>
    </MediaContainer>
  );
}

// --- Carousel Component ---
interface CarouselMediaProps {
  urls: string[];
}

export function CarouselMedia({ urls }: CarouselMediaProps) {
  return (
    <MediaContainer>
      <CarouselContainer>
        <Swiper
          modules={[Autoplay, Pagination]}
          spaceBetween={0}
          slidesPerView={1}
          pagination={{ clickable: true }}
          autoplay={{
            delay: 3000,
            disableOnInteraction: false,
          }}
          loop={urls.length > 1}
        >
          {urls.map((url, index) => (
            <SwiperSlide key={index}>
              <CarouselImage src={url} alt={`Slide ${index + 1}`} />
            </SwiperSlide>
          ))}
        </Swiper>
      </CarouselContainer>
    </MediaContainer>
  );
}

// --- Main Media Component ---
interface MediaComponentProps {
  media: MediaData;
}

export function MediaComponent({ media }: MediaComponentProps) {
  switch (media.type) {
    case 'image':
      return media.url ? <ImageMedia url={media.url} /> : null;
    case 'video':
      return media.url ? <VideoMedia url={media.url} /> : null;
    case 'carousel':
      return media.urls && media.urls.length > 0 ? <CarouselMedia urls={media.urls} /> : null;
    default:
      return null;
  }
}
