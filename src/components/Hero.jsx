import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import jobsImage from "./image/jobs.png";
import docsImage from "./image/docs.png";
import supportImage from "./image/support.png";

export default function Hero() {
  const navigate = useNavigate();

const slides = [
  {
    title: "Jobs",
    subtitle:
      "Submit and monitor cluster compute jobs",

    image: jobsImage,
    route: "/jobs",
  },

  {
    title: "Docs",
    subtitle:
      "Browse HPC setup guides and tutorials",

    image: docsImage,
    route: "/docs",
  },

  {
    title: "Support",
    subtitle:
      "Get help from admins and technical teams",

    image: supportImage,
    route: "/support",
  },
];

  // Infinite loop setup
  const loopedSlides = [
    slides[slides.length - 1],
    ...slides,
    slides[0],
  ];

  const [current, setCurrent] =
    useState(1);

  const [
    transitionEnabled,
    setTransitionEnabled,
  ] = useState(true);

  // Auto slide
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrent(
        (prev) => prev + 1
      );
    }, 3000);

    return () =>
      clearInterval(interval);
  }, []);

  // Infinite loop logic
  useEffect(() => {
    if (
      current ===
      loopedSlides.length - 1
    ) {
      setTimeout(() => {
        setTransitionEnabled(
          false
        );

        setCurrent(1);
      }, 700);
    }

    if (current === 0) {
      setTimeout(() => {
        setTransitionEnabled(
          false
        );

        setCurrent(
          slides.length
        );
      }, 700);
    }
  }, [current]);

  // Re-enable transition
  useEffect(() => {
    if (!transitionEnabled) {
      requestAnimationFrame(
        () =>
          setTransitionEnabled(
            true
          )
      );
    }
  }, [transitionEnabled]);

  return (
    <section style={styles.hero}>
      <div style={styles.carousel}>

        {/* Slides */}
        <div
          style={{
            ...styles.sliderTrack,
            transform: `translateX(-${
              current * 100
            }%)`,
            transition:
              transitionEnabled
                ? "transform 0.7s ease-in-out"
                : "none",
          }}
        >
          {loopedSlides.map(
  (slide, index) => (
    <div
      key={index}
      style={{
        ...styles.slide,
        backgroundImage: `
          linear-gradient(
            rgba(0,0,0,0.50),
            rgba(0,0,0,0.50)
          ),
          url(${slide.image})
        `,
      }}
      onClick={() =>
        navigate(slide.route)
      }
    >

      {/* Slide-specific info */}
      <div style={styles.slideInfo}>
        <h3 style={styles.slideTitle}>
          {slide.title}
        </h3>

        <p style={styles.slideSubtitle}>
          {slide.subtitle}
        </p>
      </div>

    </div>
  )
)}
        </div>

        {/* Static Overlay Content */}
        <div
          style={
            styles.centerOverlay
          }
        >
          <span
            style={styles.heroBadge}
          >
            High Performance
            Computing
          </span>

          <h1
            style={styles.heroHeading}
          >
            INDIAN INSTITUTE OF
            <br />
            SCIENCE EDUCATION
            <br />
            AND RESEARCH PUNE
          </h1>

          <h2
            style={
              styles.portalTitle
            }
          >
            HIGH PERFORMANCE
            COMPUTING PORTAL
          </h2>

          <p
            style={
              styles.heroSubheading
            }
          >
            Advanced
            computational
            infrastructure for
            researchers,
            students, and
            faculty. Access
            documentation,
            submit jobs, and
            receive technical
            support — all in
            one place.
          </p>
        </div>

        {/* Left Arrow */}
        <button
          style={{
            ...styles.arrow,
            left: "28px",
          }}
          onClick={() =>
            setCurrent(
              (prev) =>
                prev - 1
            )
          }
        >
          ❮
        </button>

        {/* Right Arrow */}
        <button
          style={{
            ...styles.arrow,
            right: "28px",
          }}
          onClick={() =>
            setCurrent(
              (prev) =>
                prev + 1
            )
          }
        >
          ❯
        </button>

        {/* Indicators */}
        <div
          style={
            styles.indicators
          }
        >
          {slides.map(
            (_, index) => (
              <button
                key={index}
                onClick={() =>
                  setCurrent(
                    index + 1
                  )
                }
                style={{
                  ...styles.dot,
                  background:
                    (
                      (current -
                        1 +
                        slides.length) %
                      slides.length
                    ) === index
                      ? "#ffffff"
                      : "rgba(255,255,255,0.45)",
                }}
              />
            )
          )}
        </div>
      </div>
    </section>
  );
}

const styles = {
  hero: {
    height:
      "calc(100vh - 88px)",
    width: "100%",
    overflow: "hidden",
  },

  carousel: {
    height: "100%",
    width: "100%",
    position: "relative",
    overflow: "hidden",
  },

  sliderTrack: {
    display: "flex",
    height: "100%",
  },

  slide: {
    minWidth: "100%",
    height: "100%",
    backgroundSize: "cover",
    backgroundPosition:
      "center",
    cursor: "pointer",
  },

  centerOverlay: {
  position: "absolute",
  inset: 0,
  paddingTop: "80px",
  display: "flex",
  flexDirection: "column",
  justifyContent: "flex-start",
  alignItems: "center",
  textAlign: "center",
  color: "#ffffff",
  zIndex: 3,

  pointerEvents: "none",
},

  heroBadge: {
  background:
    "rgba(193,18,31,0.18)",
  border:
    "1px solid rgba(193,18,31,0.4)",
  backdropFilter:
    "blur(12px)",
  color: "#ffd7db",
  padding: "12px 24px",
  borderRadius: "999px",
  fontSize: "14px",
  fontWeight: "600",
  marginBottom: "28px",
},

  heroHeading: {
  fontSize:
    "clamp(28px, 3vw, 46px)",
  fontWeight: "500",
  lineHeight: "1.22",
  marginBottom: "10px",
  color:
    "rgba(255,255,255,0.88)",
  letterSpacing: "-0.8px",
  textShadow:
    "0 4px 18px rgba(0,0,0,0.25)",
},

  portalTitle: {
  fontSize:
    "clamp(24px, 2.2vw, 38px)",
  fontWeight: "600",
  marginBottom: "20px",
  color: "#ffffff",
  letterSpacing: "1px",
  textTransform: "uppercase",
},
heroSubheading: {
  fontSize: "17px",
  lineHeight: "1.85",
  maxWidth: "700px",
  color:
    "rgba(255,255,255,0.74)",
  textShadow:
    "0 2px 10px rgba(0,0,0,0.22)",
},

  arrow: {
    position: "absolute",
    top: "50%",
    transform:
      "translateY(-50%)",
    width: "56px",
    height: "56px",
    borderRadius: "50%",
    border: "none",
    background:
      "rgba(255,255,255,0.18)",
    color: "#ffffff",
    fontSize: "28px",
    cursor: "pointer",
    backdropFilter:
      "blur(14px)",
    zIndex: 5,
  },

  indicators: {
    position: "absolute",
    bottom: "28px",
    left: "50%",
    transform:
      "translateX(-50%)",
    display: "flex",
    gap: "10px",
    zIndex: 5,
  },

  dot: {
    width: "12px",
    height: "12px",
    borderRadius: "50%",
    border: "none",
    cursor: "pointer",
    transition:
      "0.2s ease",
  },
  slideInfo: {
  position: "absolute",

  bottom: "110px",
  left: "50%",

  transform:
    "translateX(-50%)",

  textAlign: "center",

  zIndex: 4,

  width: "80%",
},

slideTitle: {
  color: "#ffffff",

  fontSize: "30px",

  fontWeight: "600",

  marginBottom: "8px",

  textShadow:
    "0 4px 14px rgba(0,0,0,0.35)",

  letterSpacing: "-0.3px",
},

slideSubtitle: {
  color:
    "rgba(255,255,255,0.88)",

  fontSize: "16px",

  fontWeight: "400",

  maxWidth: "560px",

  margin: "0 auto",

  lineHeight: "1.6",

  textShadow:
    "0 2px 8px rgba(0,0,0,0.25)",
},
};