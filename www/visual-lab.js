(function () {
    const grid = document.getElementById("lab-grid");
    const modal = document.getElementById("lab-modal");
    const modalImage = document.getElementById("lab-modal-image");
    const closeButton = document.getElementById("lab-close");
    const fallback = "/static/favicon.jpg";
    const skyCanvas = document.getElementById("lab-sky");
    const isMoonTheme = document.body.dataset.visualTheme === "b";
    let stopSky = null;

    async function loadSamples() {
        try {
            const response = await fetch("/api/gallery/albums");
            if (!response.ok) {
                throw new Error("albums unavailable");
            }
            const data = await response.json();
            const albums = (data.albums || []).slice(0, 6);
            if (albums.length > 0) {
                renderCards(albums.map((album) => ({ cover_url: album.cover_url || fallback })));
                return;
            }
        } catch (_error) {
            // ignore and use fallback cards
        }

        renderCards(Array.from({ length: 6 }, () => ({ cover_url: fallback })));
    }

    function renderCards(cards) {
        grid.innerHTML = "";
        cards.forEach((card) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "lab-card";
            button.innerHTML = `<img src="${card.cover_url}" alt="">`;
            button.addEventListener("click", () => openModal(card.cover_url));
            grid.appendChild(button);
        });
    }

    function openModal(src) {
        modalImage.src = src;
        modal.hidden = false;
        document.body.style.overflow = "hidden";
    }

    function closeModal() {
        modal.hidden = true;
        modalImage.src = "";
        document.body.style.overflow = "";
    }

    closeButton.addEventListener("click", closeModal);
    document.querySelector("[data-close]").addEventListener("click", closeModal);
    document.addEventListener("keydown", (event) => {
        if (!modal.hidden && event.key === "Escape") {
            closeModal();
        }
    });

    if (isMoonTheme && skyCanvas) {
        stopSky = startMoonSky(skyCanvas);
        window.addEventListener("beforeunload", () => {
            if (stopSky) {
                stopSky();
            }
        }, { once: true });
    }

    loadSamples();

    function startMoonSky(canvas) {
        const context = canvas.getContext("2d");
        if (!context) {
            return null;
        }

        const dpi = window.devicePixelRatio || 1;
        const moonImage = new Image();
        moonImage.src = "/static/moon.png";

        let width = 0;
        let height = 0;
        let frame = 0;
        let animationId = 0;
        let start = performance.now();

        const stars = Array.from({ length: 36 }, () => createStar());
        const clouds = [
            createCloud(-0.52, 0.12, 0.56, 0.16, 0.000015, 0.9, 0.34),
            createCloud(-0.18, 0.22, 0.44, 0.13, 0.000021, 1.7, 0.28),
            createCloud(-0.74, 0.32, 0.62, 0.18, 0.000011, 2.4, 0.24),
            createCloud(-0.28, 0.42, 0.5, 0.14, 0.000017, 1.1, 0.2),
        ];

        function createStar() {
            return {
                x: Math.random(),
                y: Math.random() * 0.9,
                radius: Math.random() * 1.8 + 0.8,
                phase: Math.random() * Math.PI * 2,
                speed: Math.random() * 0.8 + 0.35,
                alpha: Math.random() * 0.36 + 0.5,
                glow: Math.random() * 10 + 10,
            };
        }

        function createCloud(x, y, w, h, drift, phase, alpha) {
            return { x, y, w, h, drift, phase, alpha };
        }

        function resize() {
            width = window.innerWidth;
            height = window.innerHeight;
            canvas.width = Math.floor(width * dpi);
            canvas.height = Math.floor(height * dpi);
            context.setTransform(dpi, 0, 0, dpi, 0, 0);
        }

        function drawCloud(cloud, time) {
            const track = 2.2;
            const travel = ((cloud.x + time * cloud.drift) % track + track) % track - 0.7;
            const gust = Math.sin(time * 0.00024 + cloud.phase * 1.9) * width * 0.018;
            const rise = Math.cos(time * 0.00014 + cloud.phase * 0.7) * height * 0.009;
            const x = travel * width + gust;
            const y = cloud.y * height + rise;
            const w = cloud.w * width;
            const h = cloud.h * height;

            context.save();
            context.globalAlpha = cloud.alpha;
            context.filter = `blur(${Math.max(30, width * 0.012)}px)`;

            const gradient = context.createRadialGradient(x + w * 0.3, y + h * 0.5, 0, x + w * 0.48, y + h * 0.52, w * 0.55);
            gradient.addColorStop(0, "rgba(249, 251, 255, 0.2)");
            gradient.addColorStop(0.38, "rgba(232, 239, 250, 0.14)");
            gradient.addColorStop(0.68, "rgba(180, 210, 246, 0.08)");
            gradient.addColorStop(1, "rgba(168, 201, 240, 0)");
            context.fillStyle = gradient;
            context.beginPath();
            context.ellipse(x + w * 0.5, y + h * 0.5, w * 0.55, h * 0.5, 0, 0, Math.PI * 2);
            context.fill();
            context.restore();
        }

        function drawStars(time) {
            stars.forEach((star) => {
                const alpha = star.alpha + Math.sin(time * 0.0012 * star.speed + star.phase) * 0.24;
                const x = star.x * width;
                const y = star.y * height;

                context.save();
                context.globalAlpha = Math.min(1, Math.max(0.2, alpha));
                context.fillStyle = "rgba(255,255,255,0.98)";
                context.shadowColor = "rgba(236, 241, 255, 0.92)";
                context.shadowBlur = star.glow;
                context.beginPath();
                context.arc(x, y, star.radius, 0, Math.PI * 2);
                context.fill();
                context.restore();
            });
        }

        function drawMoon() {
            const moonSize = Math.min(width, height) * 0.1254;
            const x = width * 0.79;
            const y = height * 0.16;

            context.save();
            context.globalCompositeOperation = "screen";

            const glow = context.createRadialGradient(x, y, moonSize * 0.2, x, y, moonSize * 1.75);
            glow.addColorStop(0, "rgba(255, 250, 238, 0.22)");
            glow.addColorStop(0.2, "rgba(248, 246, 241, 0.16)");
            glow.addColorStop(0.42, "rgba(231, 236, 248, 0.09)");
            glow.addColorStop(0.72, "rgba(205, 219, 243, 0.035)");
            glow.addColorStop(1, "rgba(205, 219, 243, 0)");
            context.fillStyle = glow;
            context.beginPath();
            context.arc(x, y, moonSize * 1.75, 0, Math.PI * 2);
            context.fill();

            if (moonImage.complete) {
                context.filter = "brightness(1.16) contrast(1.04)";
                context.drawImage(moonImage, x - moonSize * 0.5, y - moonSize * 0.5, moonSize, moonSize);
            }

            context.restore();
        }

        function render(time) {
            frame += 1;
            context.clearRect(0, 0, width, height);

            drawStars(time);
            clouds.forEach((cloud) => drawCloud(cloud, time));
            drawMoon();

            animationId = window.requestAnimationFrame(render);
        }

        resize();
        animationId = window.requestAnimationFrame(render);
        window.addEventListener("resize", resize);

        return function stop() {
            window.cancelAnimationFrame(animationId);
            window.removeEventListener("resize", resize);
        };
    }
})();
