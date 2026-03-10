"use client"

import { motion, stagger } from "framer-motion"
import { useState } from "react"

export default function InfiniteLoading() {
    const [items, fetchMoreItems] = useFakeNews()

    return (
        <div className="container">
            <header>
                <h1 className="h1">News</h1>
                <p className="big">The latest news from the world of Motion</p>
            </header>

            <motion.main
                className="news-list"
                variants={{
                    hidden: {},
                    visible: {
                        transition: {
                            delayChildren: stagger(0.2),
                        },
                    },
                }}
                initial="hidden"
                animate="visible"
            >
                {items.map((item, index) => (
                    <NewsItem
                        key={`${item.headline}-${index}`}
                        headline={item.headline}
                        subtitle={item.subtitle}
                    />
                ))}
            </motion.main>

            <LoadingSpinner key={items.length} onInView={fetchMoreItems} />

            <Stylesheet />
        </div>
    )
}

function NewsItem({
    headline,
    subtitle,
}: {
    headline: string
    subtitle: string
}) {
    return (
        <motion.article
            className="news-item"
            variants={{
                hidden: { opacity: 0, y: 20 },
                visible: { opacity: 1, y: 0 },
            }}
            transition={{ duration: 0.4, ease: "easeOut" }}
        >
            <h3 className="h3">{headline}</h3>
            <p className="small">{subtitle}</p>
        </motion.article>
    )
}

function LoadingSpinner({ onInView }: { onInView: () => void }) {
    return (
        <motion.div
            className="loading-spinner"
            animate={{ rotate: 360 }}
            transition={{
                duration: 1.5,
                repeat: Infinity,
                ease: "linear",
            }}
            style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
            }}
            onViewportEnter={onInView}
        >
            <div className="spinner" />
        </motion.div>
    )
}

/**
 * ==============   Utils & Data   ================
 */

function useFakeNews(): [
    { headline: string; subtitle: string }[],
    () => Promise<void>
] {
    const [items, setItems] = useState(newsData.slice(0, 3))
    const [isLoading, setIsLoading] = useState(false)
    const [currentIndex, setCurrentIndex] = useState(3)

    const fetchMoreItems = async () => {
        if (isLoading) return

        setIsLoading(true)

        // Simulate API call delay
        await new Promise((resolve) => setTimeout(resolve, 1000))

        // Get next batch of items (3 at a time)
        const nextItems: typeof newsData = []
        for (let i = 0; i < 3; i++) {
            const index = (currentIndex + i) % newsData.length
            nextItems.push(newsData[index])
        }

        setItems((prev) => [...prev, ...nextItems])
        setCurrentIndex((prev) => (prev + 3) % newsData.length)
        setIsLoading(false)
    }

    return [items, fetchMoreItems]
}

// Motion-inspired fake news data
const newsData = [
    {
        headline: "Motion 12.23 revolutionizes staggered animations",
        subtitle:
            "delayChildren now accepts stagger() function enabling advanced timing control for variant children",
    },
    {
        headline: "Layout animation performance breakthrough announced",
        subtitle:
            "New optimization writes directly to element.style, reducing render overhead by 40%",
    },
    {
        headline: "React 19 compatibility officially confirmed",
        subtitle:
            "Motion library successfully tested with latest React version, strict mode issues resolved",
    },
    {
        headline: "WAAPI animations get linear() easing upgrade",
        subtitle:
            "Custom easing functions now compile to native CSS linear() for hardware acceleration",
    },
    {
        headline: "Spring animations receive visual duration control",
        subtitle:
            "New spring(visualDuration, bounce) syntax simplifies complex animation timing",
    },
    {
        headline: "Memory leak eliminated in component unmounting",
        subtitle:
            "Critical fix prevents memory buildup when motion components are frequently added and removed",
    },
    {
        headline: "Drag controls gain stop() and cancel() methods",
        subtitle:
            "useDragControls API expanded with imperative control over gesture interactions",
    },
    {
        headline: "CSS variables support enhanced for keyframes",
        subtitle:
            "Multi-keyframe animations now fully support CSS custom properties and unit conversion",
    },
    {
        headline: "AnimatePresence gets React 19 optimization",
        subtitle:
            "Exit animations now work seamlessly with concurrent rendering and Suspense boundaries",
    },
    {
        headline: "Bundle size reduced with tree-shaking improvements",
        subtitle:
            "Motion-dom package achieves significant size reduction through better dead code elimination",
    },
    {
        headline: "Scroll animations become lazy by default",
        subtitle:
            "Performance boost as scroll listeners now activate only when needed, reducing CPU usage",
    },
    {
        headline: "Server Components support officially launched",
        subtitle:
            "New motion/react-client entrypoint enables seamless SSR and hydration workflows",
    },
]

/**
 * ==============   Styles   ================
 */

function Stylesheet() {
    return (
        <style>
            {`
      #sandbox {
        justify-content: flex-start;
      }

      .container {
        padding: 140px 20px;
        display: flex;
        align-items: center;
        flex-direction: column;
        width: 100%;
        max-width: 550px;
        box-sizing: border-box;
        gap: 40px;
      }

      .container header {
        text-align: center;
        display: flex;
        align-items: center;
        flex-direction: column;
      }

      .container header p {
        max-width: 200px;
        text-wrap: balance;
      }

      .container main {
        display: flex;
        align-items: center;
        flex-direction: column;
        align-items: stretch;
      }

      .container h3 {
        text-wrap: balance;
      }

      .container article {
        border-bottom: 1px dashed #1d2628;
        padding: 20px 0;
        display: flex;
        align-items: flex-start;
        flex-direction: column;
        gap: 10px;
        flex: 1;
      }

      .loading-spinner {
          width: 50px;
          height: 50px;
          will-change: transform;
          position: relative;
      }

      .spinner {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          border: 4px solid var(--divider);
          border-top-color: #8df0cc;
      }
      `}
        </style>
    )
}
