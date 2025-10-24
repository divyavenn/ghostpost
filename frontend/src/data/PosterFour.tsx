import { motion } from 'framer-motion';

export default function PosterFour() {
  return (
    <div className="relative w-full max-w-2xl aspect-[3/4] overflow-hidden rounded-2xl bg-gradient-to-br from-slate-950 via-slate-900 to-slate-900 shadow-2xl">
      {/* Animated background orbs */}
      <motion.div
        className="absolute top-[-20%] right-[-10%] w-96 h-96 rounded-full bg-slate-500/20 blur-3xl"
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <motion.div
        className="absolute bottom-[-15%] left-[-15%] w-80 h-80 rounded-full bg-orange-500/20 blur-3xl"
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.2, 0.4, 0.2],
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 1,
        }}
      />

      {/* Abstract Faces SVG */}
      <svg className="absolute inset-0 w-full h-full opacity-20" viewBox="0 0 400 600" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="darkTexture4" x="0" y="0" width="100" height="100" patternUnits="userSpaceOnUse">
            <rect width="100" height="100" fill="#0f172a"/>
            <line x1="0" y1="10" x2="100" y2="10" stroke="#1e3a8a" strokeWidth="8" opacity="0.6"/>
            <line x1="0" y1="25" x2="100" y2="25" stroke="#1e40af" strokeWidth="6" opacity="0.5"/>
            <line x1="0" y1="40" x2="100" y2="40" stroke="#1e3a8a" strokeWidth="10" opacity="0.7"/>
            <line x1="0" y1="55" x2="100" y2="55" stroke="#1e40af" strokeWidth="5" opacity="0.4"/>
            <line x1="0" y1="70" x2="100" y2="70" stroke="#1e3a8a" strokeWidth="7" opacity="0.6"/>
            <line x1="0" y1="85" x2="100" y2="85" stroke="#1e40af" strokeWidth="9" opacity="0.5"/>
          </pattern>
          
          <pattern id="colorTexture1_4" x="0" y="0" width="100" height="100" patternUnits="userSpaceOnUse">
            <rect width="100" height="100" fill="#64748b"/>
            <rect y="20" width="100" height="15" fill="#94a3b8" opacity="0.8"/>
            <rect y="40" width="100" height="12" fill="#475569" opacity="0.7"/>
            <rect y="60" width="100" height="18" fill="#334155" opacity="0.6"/>
            <rect y="80" width="100" height="10" fill="#94a3b8" opacity="0.8"/>
          </pattern>
          
          <pattern id="colorTexture2_4" x="0" y="0" width="100" height="100" patternUnits="userSpaceOnUse">
            <rect width="100" height="100" fill="#475569"/>
            <rect y="15" width="100" height="20" fill="#64748b" opacity="0.7"/>
            <rect y="38" width="100" height="14" fill="#cbd5e1" opacity="0.6"/>
            <rect y="58" width="100" height="16" fill="#94a3b8" opacity="0.8"/>
            <rect y="78" width="100" height="12" fill="#64748b" opacity="0.7"/>
          </pattern>

          <pattern id="colorTexture3_4" x="0" y="0" width="100" height="100" patternUnits="userSpaceOnUse">
            <rect width="100" height="100" fill="#94a3b8"/>
            <rect y="12" width="100" height="18" fill="#64748b" opacity="0.7"/>
            <rect y="35" width="100" height="22" fill="#e2e8f0" opacity="0.6"/>
            <rect y="60" width="100" height="15" fill="#94a3b8" opacity="0.8"/>
            <rect y="82" width="100" height="10" fill="#64748b" opacity="0.6"/>
          </pattern>
        </defs>

        <motion.path
          d="M 50 150 Q 45 180, 48 210 Q 50 240, 55 270 Q 58 300, 62 330 Q 65 360, 70 390 Q 75 420, 82 450 L 120 450 Q 115 430, 110 410 Q 108 390, 105 370 Q 103 350, 100 330 Q 98 310, 95 290 Q 93 270, 90 250 Q 88 230, 87 210 Q 87 190, 90 170 Q 95 150, 105 135 Q 115 125, 125 120 Q 135 118, 145 120 L 145 150 Z"
          fill="url(#darkTexture4)"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 1.5, delay: 0.3 }}
        />

        <motion.path
          d="M 350 150 Q 355 180, 352 210 Q 350 240, 345 270 Q 342 300, 338 330 Q 335 360, 330 390 Q 325 420, 318 450 L 280 450 Q 285 430, 290 410 Q 292 390, 295 370 Q 297 350, 300 330 Q 302 310, 305 290 Q 307 270, 310 250 Q 312 230, 313 210 Q 313 190, 310 170 Q 305 150, 295 135 Q 285 125, 275 120 Q 265 118, 255 120 L 255 150 Z"
          fill="url(#colorTexture1_4)"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 1.5, delay: 0.3 }}
        />

        <motion.path
          d="M 60 180 Q 58 210, 60 240 Q 62 270, 65 300 Q 68 330, 72 360 Q 76 390, 82 420 L 100 420 Q 96 395, 92 370 Q 90 345, 88 320 Q 86 295, 85 270 Q 84 245, 85 220 Q 87 195, 92 175 Q 98 160, 108 150 L 90 160 Q 75 168, 60 180 Z"
          fill="url(#darkTexture4)"
          opacity="0.6"
          initial={{ opacity: 0, x: -15 }}
          animate={{ opacity: 0.6, x: 0 }}
          transition={{ duration: 1.5, delay: 0.5 }}
        />

        <motion.path
          d="M 340 180 Q 342 210, 340 240 Q 338 270, 335 300 Q 332 330, 328 360 Q 324 390, 318 420 L 300 420 Q 304 395, 308 370 Q 310 345, 312 320 Q 314 295, 315 270 Q 316 245, 315 220 Q 313 195, 308 175 Q 302 160, 292 150 L 310 160 Q 325 168, 340 180 Z"
          fill="url(#colorTexture2_4)"
          opacity="0.6"
          initial={{ opacity: 0, x: 15 }}
          animate={{ opacity: 0.6, x: 0 }}
          transition={{ duration: 1.5, delay: 0.5 }}
        />

        <motion.path
          d="M 330 200 Q 328 230, 326 260 Q 324 290, 322 320 Q 320 350, 318 380 L 305 380 Q 307 355, 309 330 Q 311 305, 313 280 Q 315 255, 316 230 Q 317 210, 315 190 L 330 200 Z"
          fill="url(#colorTexture3_4)"
          opacity="0.5"
          initial={{ opacity: 0, x: 10 }}
          animate={{ opacity: 0.5, x: 0 }}
          transition={{ duration: 1.5, delay: 0.7 }}
        />

        <motion.rect
          x="65"
          y="260"
          width="40"
          height="25"
          fill="#64748b"
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 0.9, scale: 1 }}
          transition={{ duration: 0.8, delay: 1.2 }}
        />
      </svg>

      {/* Content */}
      <div className="relative z-10 h-full flex flex-col items-center justify-center px-16 py-20">
        <motion.div
          className="text-center space-y-10"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: "easeOut" }}
        >
          <div className="space-y-8">
            <motion.h1
              className="text-slate-50 font-sans tracking-tight leading-none"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 1, delay: 0.2 }}
            >
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-slate-300 via-slate-400 to-slate-300 block text-6xl md:text-7xl uppercase tracking-wider">
                No
              </span>
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-slate-300 via-slate-400 to-slate-300 block text-5xl md:text-6xl mt-3 font-serif italic">
                AI slop,
              </span>
            </motion.h1>

            <motion.div
              className="w-32 h-px bg-gradient-to-r from-transparent via-slate-400/60 to-transparent mx-auto"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 1.5, delay: 0.8 }}
            />

            <motion.p
              className="text-3xl md:text-4xl text-slate-200/90 font-serif italic"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, delay: 1 }}
            >
              no spam.
            </motion.p>
          </div>

          <motion.div
            className="flex items-center justify-center gap-3 mt-16"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 1.4 }}
          >
            <svg width="50" height="16" viewBox="0 0 50 16" fill="none">
              <path
                d="M 2 8 Q 12 4, 25 8 T 48 8"
                stroke="rgba(148, 163, 184, 0.4)"
                strokeWidth="1"
                fill="none"
                strokeLinecap="round"
              />
            </svg>
          </motion.div>
        </motion.div>
      </div>

      <div 
        className="absolute inset-0 opacity-[0.015] mix-blend-overlay pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />
    </div>
  );
}
