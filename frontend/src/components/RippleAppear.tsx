"use client"

import * as motion from "motion/react-client"
import { useEffect, useRef, useState } from "react"

export default function StaggeredGrid({
    baseDelay = 0.0015,
    noise = 0.1,
}: {
    baseDelay?: number
    noise?: number
}) {
    const gridSize = 10
    const totalCells = gridSize * gridSize
    const grid = useRef<HTMLDivElement>(null)
    const [originIndex, setOriginIndex] = useState<number | null>(null)
    const [calculatedDelay, setCalculatedDelay] = useState<number[]>([])

    useEffect(() => {
        const originIndex = Math.floor(Math.random() * totalCells)
        const cells = grid.current?.querySelectorAll(".cell")

        if (!cells) return

        const originCell = cells[originIndex]

        const originPoint = getCenter(originCell as HTMLElement)
        const delays: number[] = []

        for (let i = 0; i < totalCells; i++) {
            const cell = cells[i]
            const cellPoint = getCenter(cell as HTMLElement)
            const distance = Math.sqrt(
                (cellPoint.x - originPoint.x) ** 2 +
                    (cellPoint.y - originPoint.y) ** 2
            )
            const delay = distance * baseDelay + Math.random() * noise
            delays.push(delay)
        }

        setCalculatedDelay(delays)
        setOriginIndex(originIndex)
    }, [])

    const cells = Array.from({ length: totalCells }, (_, index) => (
        <motion.div
            className={`cell ${index === originIndex ? "origin" : ""}`}
            variants={variants}
            transition={{
                type: "spring",
                stiffness: 600,
                damping: 20,
                delay: index === originIndex ? 0 : calculatedDelay[index],
            }}
            key={index}
        />
    ))

    return (
        <div className="grid-container">
            <motion.div
                ref={grid}
                className="grid"
                initial="hidden"
                animate={originIndex !== null ? "visible" : "hidden"}
            >
                {cells}
            </motion.div>
            <StyleSheet />
        </div>
    )
}

const variants = {
    hidden: { opacity: 0, scale: 0.5 },
    visible: { opacity: 1, scale: 1 },
}

/**
 * ==============   Utils   ================
 */
function getCenter(element: HTMLElement) {
    const { x, y, width, height } = element.getBoundingClientRect()
    return { x: x + width / 2, y: y + height / 2 }
}

/**
 * ==============   Styles   ================
 */

function StyleSheet() {
    return (
        <style>
            {`
                .grid-container {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    width: 100%;
                    height: 100%;
                }
                
                .grid {
                    display: grid;
                    grid-template-columns: repeat(10, 1fr);
                    grid-template-rows: repeat(10, 1fr);
                    gap: 10px;
                    width: 400px;
                    height: 400px;
                }
                
                .cell {
                    background-color: rgba(255,255,255,0.2);
                    border-radius: 4px;
                }
                
                .origin {
                    background-color: #ff0088;
                }
            `}
        </style>
    )
}
