"use client"

import {
    motion,
    useMotionTemplate,
    useSpring,
    useTransform,
    useVelocity,
} from "motion/react"
import { useEffect, useRef, useState } from "react"

export default function SmoothTabs() {
    const [activeTab, setActiveTab] = useState(tabs[0].id)

    // Render Views only after mount since container width needs to be measured first
    const isMounted = useMounted()

    const viewsContainerRef = useRef<HTMLDivElement>(null)
    const [viewsContainerWidth, setViewsContainerWidth] = useState(0)

    useEffect(() => {
        const updateWidth = () => {
            if (viewsContainerRef.current) {
                const width =
                    viewsContainerRef.current.getBoundingClientRect().width
                setViewsContainerWidth(width)
            }
        }

        // Initial measurement
        updateWidth()

        window.addEventListener("resize", updateWidth)

        return () => {
            window.removeEventListener("resize", updateWidth)
        }
    }, [viewsContainerWidth])

    return (
        <div style={styles.container}>
            <div
                id="views-container"
                ref={viewsContainerRef}
                style={styles.viewsContainer}
            >
                {isMounted &&
                    tabs.map((tab, idx) => (
                        <View
                            key={tab.id}
                            containerWidth={viewsContainerWidth}
                            viewIndex={idx}
                            activeIndex={tabs.findIndex(
                                (t) => t.id === activeTab
                            )}
                        >
                            <DummyTabContent tab={tab} />
                        </View>
                    ))}
            </div>
            <Tabs
                tabs={tabs}
                activeTab={activeTab}
                onTabChange={(tab) => setActiveTab(tab)}
            />
        </div>
    )
}

const View = ({
    children,
    containerWidth,
    viewIndex,
    activeIndex,
}: {
    children: React.ReactNode
    containerWidth: number
    viewIndex: number
    activeIndex: number
}) => {
    // Calculate the index difference between the active tab and the current tab
    // Then use it as the factor you multiply the container width by to get the x position
    const [difference, setDifference] = useState(activeIndex - viewIndex)
    const x = useSpring(calculateViewX(difference, containerWidth), {
        stiffness: 400,
        damping: 60,
    })

    const xVelocity = useVelocity(x)

    // The closer the view is to the center, the more opaque it is
    const opacity = useTransform(
        x,
        [-containerWidth * 0.6, 0, containerWidth * 0.6],
        [0, 1, 0]
    )

    // The more the view is moving, the more blurred it is
    const blur = useTransform(xVelocity, [-1000, 0, 1000], [4, 0, 4], {
        clamp: false,
    })

    useEffect(() => {
        const newDifference = activeIndex - viewIndex
        setDifference(newDifference)
        const newX = calculateViewX(newDifference, containerWidth)
        x.set(newX)
    }, [activeIndex, containerWidth, difference, viewIndex, x])

    return (
        <motion.div
            style={{
                ...styles.view.outerContainer,
                x,
                opacity,
                filter: useMotionTemplate`blur(${blur}px)`,
            }}
        >
            <div style={styles.view.innerContainer}>{children}</div>
        </motion.div>
    )
}

const Tabs = ({
    tabs,
    activeTab,
    onTabChange,
}: {
    tabs: { id: string; label: string; color: string }[]
    activeTab: string
    onTabChange: (tab: string) => void
}) => {
    return (
        <ul style={styles.tabsContainer}>
            {tabs.map((tab, idx) => (
                <motion.li
                    key={tab.id}
                    style={{
                        ...styles.tab.outer,
                        padding:
                            idx === 0
                                ? "4px 0px 4px 4px"
                                : idx === tabs.length - 1
                                ? "4px 4px 4px 0px"
                                : 4,
                    }}
                >
                    <motion.button
                        style={{
                            ...styles.tab.inner,
                            color:
                                activeTab === tab.id
                                    ? "#f5f5f5"
                                    : "var(--feint-text)",
                        }}
                        whileFocus={{
                            outline: "2px solid var(--accent)",
                        }}
                        onClick={() => onTabChange(tab.id)}
                    >
                        <span
                            style={{
                                ...styles.tab.label,
                                color:
                                    activeTab === tab.id
                                        ? "#f5f5f5"
                                        : "var(--feint-text)",
                            }}
                        >
                            {tab.label}
                        </span>

                        {tab.id === activeTab ? (
                            <motion.span
                                layoutId="activeTab"
                                id="activeTab"
                                transition={{
                                    type: "spring",
                                    stiffness: 600,
                                    damping: 40,
                                }}
                                style={{
                                    ...styles.tab.activeTabBg,
                                    backgroundColor: tab.color,
                                }}
                            />
                        ) : null}
                    </motion.button>
                </motion.li>
            ))}
        </ul>
    )
}

const DummyTabContent = ({ tab }: { tab: Tab }) => {
    return (
        <>
            <div style={styles.dummyTabContent.titleContainer}>
                <span
                    style={{
                        ...styles.dummyTabContent.icon,
                        backgroundColor: tab.color,
                    }}
                />
                <h3 style={styles.dummyTabContent.title}>{tab.label}</h3>
            </div>
            <p style={styles.dummyTabContent.description}>{tab.description}</p>
        </>
    )
}

type Tab = {
    id: string
    label: string
    color: string
    description: string
}
const tabs = [
    {
        id: "tab-1",
        label: "Home",
        color: "#ff0088",
        description:
            "This is your home tab, where you can see all your recent activity",
    },
    {
        id: "tab-2",
        label: "DMs",
        color: "#dd00ee",
        description:
            "This is your DMs tab, where you can see all your recent DMs",
    },
    {
        id: "tab-3",
        label: "Activity",
        color: "#9911ff",
        description:
            "This is your Activity tab, where you can see all your recent activity",
    },
    {
        id: "tab-4",
        label: "More",
        color: "#0d63f8",
        description:
            "This is your More tab, where you can find a bunch of other stuff, like settings, help, etc.",
    },
]

/**
 * ==============   Styles   ================
 */
type NestedStyles = {
    [key: string]: React.CSSProperties | any
}

const styles: NestedStyles = {
    container: {
        position: "relative",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        justifyContent: "center",
        alignItems: "center",
        minWidth: 280,
        width: "clamp(280px, 90dvw, 400px)",
        height: "100%",
    },
    viewsContainer: {
        overflow: "hidden",
        position: "relative",
        width: "100%",
        height: 300,
        border: "1px solid #1d2628",
        backgroundColor: "var(--layer-transparent)",
        backdropFilter: "blur(10px)",
        borderRadius: 12,
    },
    view: {
        outerContainer: {
            position: "absolute",
            inset: 0,
            padding: 8,
            transformOrigin: "center",
            transform: "translate3d(0, 0, 0)",
            willChange: "transform, filter",
            isolation: "isolate",
        },
        innerContainer: {
            width: "100%",
            height: "100%",
            padding: "32px 36px",
            boxSizing: "border-box",
            textWrap: "balance",
            display: "flex",
            flexDirection: "column",
            gap: 12,
        },
    },
    tabsContainer: {
        border: "1px solid #1d2628",
        backgroundColor: "var(--layer-transparent)",
        backdropFilter: "blur(10px)",
        borderRadius: 12,
        display: "flex",
        padding: 0,
        width: "100%",
        margin: 0,
    },
    tab: {
        outer: {
            display: "flex",

            cursor: "pointer",
            flexGrow: 1,
        },
        inner: {
            position: "relative",
            width: "100%",
            padding: 8,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            fontSize: 14,
            borderRadius: 8,
        },
        label: {
            zIndex: 1,
        },
        activeTabBg: {
            position: "absolute",
            inset: 0,
            borderRadius: 8,
        },
    },
    dummyTabContent: {
        titleContainer: {
            display: "flex",
            gap: 12,
            alignItems: "center",
        },
        icon: {
            height: 20,
            width: 20,
            borderRadius: 16,
        },
        title: {
            margin: 0,
        },
        description: {
            color: "var(--feint-text)",
        },
    },
}

/**
 * ==============   Utils   ================
 */
const calculateViewX = (difference: number, containerWidth: number) => {
    return difference * (containerWidth * 0.75) * -1
}

const useMounted = () => {
    const [isMounted, setIsMounted] = useState(false)
    useEffect(() => {
        setIsMounted(true)
    }, [])
    return isMounted
}
