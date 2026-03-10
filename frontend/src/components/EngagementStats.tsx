"use client"

import { mix, motion } from "framer-motion"
import { useEffect, useState } from "react"

const format: Intl.NumberFormatOptions = {
    notation: "compact",
    compactDisplay: "short",
}

function AnimateNumber({
    children,
    format: numberFormat,
}: {
    children: number
    format?: Intl.NumberFormatOptions
}) {
    return <>{new Intl.NumberFormat("en-US", numberFormat).format(children)}</>
}

export default function EngagementStats() {
    const [stats, setStats] = useState({
        views: 1200,
        retweets: 15,
        likes: 97,
        bookmarks: 10,
    })

    const [isRetweetSelected, setIsRetweetSelected] = useState(false)
    const [isLikeSelected, setIsLikeSelected] = useState(false)
    const [isBookmarkSelected, setIsBookmarkSelected] = useState(false)

    const retweet = isRetweetSelected ? 1 : 0
    const like = isLikeSelected ? 1 : 0
    const bookmark = isBookmarkSelected ? 1 : 0

    useEffect(() => {
        const timer = setTimeout(() => {
            setStats({
                views: increment(stats.views, 100, 1000),
                retweets: increment(stats.retweets, 1, 5),
                likes: increment(stats.likes, 50, 100),
                bookmarks: increment(stats.bookmarks, 1, 10),
            })
        }, 5000)

        return () => clearTimeout(timer)
    }, [stats])

    return (
        <div className="engagement-stats">
            <div className="item">
                <div className="icon">
                    <ViewsIcon isSelected={stats.views > 0} />
                </div>
                <div className="text">
                    <AnimateNumber format={format}>{stats.views}</AnimateNumber>
                </div>
            </div>
            <SocialButton
                isSelected={isRetweetSelected}
                onClick={() => setIsRetweetSelected(!isRetweetSelected)}
            >
                <div className="icon">
                    <RetweetIcon isSelected={isRetweetSelected} />
                </div>
                <div className="text">
                    <AnimateNumber format={format}>
                        {stats.retweets + retweet}
                    </AnimateNumber>
                </div>
            </SocialButton>
            <SocialButton
                isSelected={isLikeSelected}
                onClick={() => setIsLikeSelected(!isLikeSelected)}
            >
                <div className="icon">
                    <LikeIcon isSelected={isLikeSelected} />
                </div>
                <div className="text">
                    <AnimateNumber format={format}>
                        {stats.likes + like}
                    </AnimateNumber>
                </div>
            </SocialButton>
            <SocialButton
                isSelected={isBookmarkSelected}
                onClick={() => setIsBookmarkSelected(!isBookmarkSelected)}
            >
                <div className="icon">
                    <BookmarkIcon isSelected={isBookmarkSelected} />
                </div>
                <div className="text">
                    <AnimateNumber format={format}>
                        {stats.bookmarks + bookmark}
                    </AnimateNumber>
                </div>
            </SocialButton>
            <StyleSheet />
        </div>
    )
}

function SocialButton({
    children,
    isSelected,
    onClick,
}: {
    children: React.ReactNode
    isSelected: boolean
    onClick?: () => void
}) {
    return (
        <motion.button
            className="item"
            initial="default"
            whileTap="pressed"
            animate={isSelected ? "selected" : "default"}
            onClick={onClick}
        >
            {children}
        </motion.button>
    )
}

/**
 * ==============   Utils   ================
 */

const increment = (value: number, min: number, max: number) => {
    return Math.round(value + mix(min, max, Math.random()))
}

/**
 * ==============   Icons   ================
 */

const Icon = ({
    children,
    isSelected,
    height = 24,
    hue,
}: {
    children: React.ReactNode
    isSelected?: boolean
    height?: number
    hue?: number
}) => (
    <motion.svg
        xmlns="http://www.w3.org/2000/svg"
        width={24}
        height={24}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={isSelected ? "selected" : ""}
        viewBox={`0 0 24 ${height}`}
        variants={{
            default: { scale: 1 },
            pressed: { scale: 0.9 },
        }}
        style={{ height, color: hue ? `var(--hue-${hue})` : `#f5f5f5` }}
    >
        {children}
    </motion.svg>
)

const RetweetIcon = ({ isSelected }: { isSelected: boolean }) => (
    <Icon isSelected={isSelected} height={20} hue={6}>
        <path d="m2 9 3-3 3 3" />
        <path d="M13 18H7a2 2 0 0 1-2-2V6" />
        <path d="m22 15-3 3-3-3" />
        <path d="M11 6h6a2 2 0 0 1 2 2v10" />
    </Icon>
)
const LikeIcon = ({ isSelected }: { isSelected: boolean }) => (
    <Icon isSelected={isSelected} height={22} hue={1}>
        <motion.path
            variants={{
                default: { fill: "#ff008800" },
                selected: { fill: "#ff0088" },
            }}
            d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"
        />
    </Icon>
)
const ViewsIcon = ({ isSelected }: { isSelected: boolean }) => (
    <Icon isSelected={isSelected}>
        <line x1="18" x2="18" y1="20" y2="10" />
        <line x1="12" x2="12" y1="20" y2="4" />
        <line x1="6" x2="6" y1="20" y2="14" />
    </Icon>
)
const BookmarkIcon = ({ isSelected }: { isSelected: boolean }) => (
    <Icon isSelected={isSelected} height={22} hue={4}>
        <motion.path
            variants={{
                default: { fill: "#0d63f800" },
                selected: { fill: "#0d63f8" },
            }}
            d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"
        />
    </Icon>
)

/**
 * ==============   Styles   ================
 */

function StyleSheet() {
    return (
        <style>{`
        .engagement-stats {
            display: flex;
            justify-content: space-evenly;
            align-items: center;
            width: 100%;
            max-width: 400px;
        }

        .item {
            display: flex;
            flex-direction: row;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .text {
            font-variant-numeric: tabular-nums;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            width: 50px;
        }
    `}</style>
    )
}
