import * as THREE from "/static/vendor/three.module.min.js";

(function () {
    const goTube = window.GoTube = window.GoTube || {};
    goTube.home = goTube.home || {};

    const state = {
        albums: [],
        currentAlbum: null,
        currentImageIndex: 0,
    };

    const sceneHost = document.getElementById("home-scene");
    const albumsGrid = document.getElementById("albums-grid");
    const albumsEmpty = document.getElementById("albums-empty");
    const modal = document.getElementById("gallery-modal");
    const modalImage = document.getElementById("gallery-modal-image");
    const modalClose = document.getElementById("gallery-modal-close");
    const modalBackdrop = document.querySelector("[data-modal-close]");
    const prevButton = document.getElementById("gallery-prev");
    const nextButton = document.getElementById("gallery-next");
    const secretEntry = document.getElementById("secret-entry");
    const secretEntryImage = document.getElementById("secret-entry-image");

    let disposeScene = null;

    secretEntryImage?.addEventListener("error", () => {
        const fallback = secretEntryImage.dataset.fallbackSrc;
        if (fallback && secretEntryImage.src !== fallback) {
            secretEntryImage.src = fallback;
        }
    });

    ensureScene();
    window.addEventListener("pageshow", () => {
        ensureScene();
    });
    window.addEventListener("beforeunload", () => {
        if (disposeScene) {
            disposeScene();
            disposeScene = null;
        }
    }, { once: true });

    modalClose?.addEventListener("click", closeModal);
    modalBackdrop?.addEventListener("click", closeModal);
    prevButton?.addEventListener("click", showPrevImage);
    nextButton?.addEventListener("click", showNextImage);
    document.addEventListener("keydown", (event) => {
        if (!modal || modal.hidden) return;
        if (event.key === "Escape") closeModal();
        if (event.key === "ArrowLeft") showPrevImage();
        if (event.key === "ArrowRight") showNextImage();
    });

    loadAlbums().catch(() => {
        if (albumsEmpty) {
            albumsEmpty.hidden = false;
        }
    });

    async function loadAlbums() {
        const response = await fetch("/api/gallery/albums");
        if (!response.ok) {
            throw new Error("Albums unavailable");
        }
        const data = await response.json();
        state.albums = data.albums || [];
        renderAlbumCards();
    }

    function renderAlbumCards() {
        if (!albumsGrid) return;
        albumsGrid.replaceChildren();
        const hasAlbums = state.albums.length > 0;
        if (albumsEmpty) {
            albumsEmpty.hidden = hasAlbums;
        }

        state.albums.forEach((album) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "album-card";
            button.addEventListener("click", () => openAlbum(album.slug));

            const image = document.createElement("img");
            image.className = "album-cover";
            image.src = album.cover_url;
            image.alt = "";

            button.appendChild(image);
            albumsGrid.appendChild(button);
        });
    }

    async function openAlbum(slug) {
        const response = await fetch(`/api/gallery/albums/${encodeURIComponent(slug)}`);
        if (!response.ok) {
            throw new Error("Album unavailable");
        }
        state.currentAlbum = await response.json();
        state.currentImageIndex = 0;
        renderModalImage();
        modal.hidden = false;
        document.body.style.overflow = "hidden";
    }

    function renderModalImage() {
        if (!state.currentAlbum || !state.currentAlbum.images?.length) {
            return;
        }
        const currentImage = state.currentAlbum.images[state.currentImageIndex];
        modalImage.src = currentImage.url;
        modalImage.alt = "";
    }

    function showNextImage() {
        if (!state.currentAlbum?.images?.length) return;
        state.currentImageIndex = (state.currentImageIndex + 1) % state.currentAlbum.images.length;
        renderModalImage();
    }

    function showPrevImage() {
        if (!state.currentAlbum?.images?.length) return;
        state.currentImageIndex =
            (state.currentImageIndex - 1 + state.currentAlbum.images.length) % state.currentAlbum.images.length;
        renderModalImage();
    }

    function closeModal() {
        if (!modal) return;
        modal.hidden = true;
        document.body.style.overflow = "";
    }

    goTube.home.ensureScene = ensureScene;
    goTube.home.closeGalleryModal = closeModal;

    function ensureScene() {
        if (!sceneHost || disposeScene || sceneHost.querySelector("canvas")) {
            return;
        }
        disposeScene = createNightSky(sceneHost);
    }

    function createNightSky(host) {
        const scene = new THREE.Scene();

        const renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: true,
            powerPreference: "high-performance",
        });
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.setClearColor(0x000000, 0);
        host.appendChild(renderer.domElement);

        const camera = new THREE.PerspectiveCamera(56, 1, 0.1, 1200);
        camera.position.set(0, 0, 0);

        const skyGroup = new THREE.Group();
        const starGroup = new THREE.Group();
        const moonNearStarGroup = new THREE.Group();
        const nearStarGroup = new THREE.Group();
        const midStarGroup = new THREE.Group();
        const farStarGroup = new THREE.Group();
        const moonGroup = new THREE.Group();
        scene.add(skyGroup);
        scene.add(starGroup);
        scene.add(moonGroup);
        starGroup.add(moonNearStarGroup);
        starGroup.add(nearStarGroup);
        starGroup.add(midStarGroup);
        starGroup.add(farStarGroup);

        const target = { yaw: 0, pitch: 0 };
        const current = { yaw: 0, pitch: 0 };
        const autoState = { yaw: 0, pitch: 0 };
        const autoDriftSeed = Math.random() * Math.PI * 2;
        const gyroVelocity = { yaw: 0, pitch: 0 };
        const motion = createMotionController(gyroVelocity);

        const sky = createSkyDome();
        skyGroup.add(sky);

        const stars = createStarField();
        moonNearStarGroup.add(stars.moonNear.points);
        nearStarGroup.add(stars.near.points);
        midStarGroup.add(stars.mid.points);
        farStarGroup.add(stars.far.points);

        const moon = createMoon();
        moonGroup.add(moon.occluder);
        moonGroup.add(moon.glow);
        moonGroup.add(moon.sprite);
        const moonScreenPosition = new THREE.Vector3();

        let rafId = 0;
        let disposed = false;

        function resize() {
            const width = host.clientWidth || window.innerWidth;
            const height = host.clientHeight || window.innerHeight;
            camera.aspect = width / Math.max(height, 1);
            camera.updateProjectionMatrix();
            renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
            renderer.setSize(width, height, false);
            sky.material.uniforms.uResolution.value.set(width, height);
            positionMoon(moon, width, height);
            updateSecretEntryPosition(width, height);
        }

        function onPointerMove(event) {
            const width = window.innerWidth || 1;
            const height = window.innerHeight || 1;
            const pointerX = event.clientX / width * 2 - 1;
            const pointerY = event.clientY / height * 2 - 1;
            target.yaw = pointerX * 0.075;
            target.pitch = pointerY * 0.068;
        }

        function onPointerLeave() {
            target.yaw = 0;
            target.pitch = 0;
        }

        function animate(now) {
            if (disposed) return;

            const time = now * 0.001;
            const isMobileLike = !matchMedia("(pointer:fine)").matches;
            if (isMobileLike) {
                const autoYaw = Math.sin(time * 0.2 + autoDriftSeed) * 0.048
                    + Math.sin(time * 0.21 + autoDriftSeed * 0.7) * 0.032;
                const autoPitch = Math.cos(time * 0.15 + autoDriftSeed) * 0.042
                    + Math.cos(time * 0.16 + autoDriftSeed * 0.5) * 0.025;

                autoState.yaw += (autoYaw - autoState.yaw) * 0.026;
                autoState.pitch += (autoPitch - autoState.pitch) * 0.03;

                gyroVelocity.yaw *= 0.94;
                gyroVelocity.pitch *= 0.935;

                target.yaw = autoState.yaw + gyroVelocity.yaw;
                target.pitch = autoState.pitch + gyroVelocity.pitch;
            }

            const desiredYaw = target.yaw;
            const desiredPitch = target.pitch;

            const yawEase = isMobileLike ? 0.08 : 0.06;
            const pitchEase = isMobileLike ? 0.085 : 0.065;
            current.yaw += (desiredYaw - current.yaw) * yawEase;
            current.pitch += (desiredPitch - current.pitch) * pitchEase;

            const skyYaw = isMobileLike ? 0.34 : 0.34;
            const skyPitch = isMobileLike ? 0.42 : 0.42;
            const moonNearYaw = isMobileLike ? 0.92 : 0.92;
            const moonNearPitch = isMobileLike ? 1.04 : 1.04;
            const nearYaw = isMobileLike ? 1.14 : 1.14;
            const nearPitch = isMobileLike ? 1.26 : 1.26;
            const midYaw = isMobileLike ? 1.42 : 1.42;
            const midPitch = isMobileLike ? 1.58 : 1.58;
            const farYaw = isMobileLike ? 1.78 : 1.78;
            const farPitch = isMobileLike ? 1.96 : 1.96;
            const moonYaw = isMobileLike ? 0.64 : 0.64;
            const moonPitch = isMobileLike ? 0.76 : 0.76;

            skyGroup.rotation.y = current.yaw * skyYaw;
            skyGroup.rotation.x = current.pitch * skyPitch;
            moonNearStarGroup.rotation.y = current.yaw * moonNearYaw;
            moonNearStarGroup.rotation.x = current.pitch * moonNearPitch;
            nearStarGroup.rotation.y = current.yaw * nearYaw;
            nearStarGroup.rotation.x = current.pitch * nearPitch;
            midStarGroup.rotation.y = current.yaw * midYaw;
            midStarGroup.rotation.x = current.pitch * midPitch;
            farStarGroup.rotation.y = current.yaw * farYaw;
            farStarGroup.rotation.x = current.pitch * farPitch;
            moonGroup.rotation.y = current.yaw * moonYaw;
            moonGroup.rotation.x = current.pitch * moonPitch;

            stars.moonNear.material.uniforms.uTime.value = time;
            stars.near.material.uniforms.uTime.value = time;
            stars.mid.material.uniforms.uTime.value = time;
            stars.far.material.uniforms.uTime.value = time;
            updateSecretEntryPosition(window.innerWidth || 1, window.innerHeight || 1);

            renderer.render(scene, camera);
            rafId = window.requestAnimationFrame(animate);
        }

        function updateSecretEntryPosition(width, height) {
            if (!secretEntry) {
                return;
            }
            moon.sprite.getWorldPosition(moonScreenPosition);
            moonScreenPosition.project(camera);
            const x = (moonScreenPosition.x * 0.5 + 0.5) * width;
            const y = (-moonScreenPosition.y * 0.5 + 0.5) * height;
            const isMobileLike = !matchMedia("(pointer:fine)").matches;
            const size = isMobileLike ? 58 : 70;
            secretEntry.style.left = `${x}px`;
            secretEntry.style.top = `${y}px`;
            secretEntry.style.width = `${size}px`;
            secretEntry.style.height = `${size}px`;
        }

        resize();
        window.addEventListener("resize", resize);
        window.addEventListener("pointermove", onPointerMove);
        window.addEventListener("pointerleave", onPointerLeave);
        rafId = window.requestAnimationFrame(animate);

        return function dispose() {
            disposed = true;
            window.cancelAnimationFrame(rafId);
            window.removeEventListener("resize", resize);
            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerleave", onPointerLeave);
            motion.cleanup();
            renderer.dispose();
            for (const layer of Object.values(stars)) {
                layer.geometry.dispose();
                layer.material.dispose();
            }
            moon.occluder.material.dispose();
            moon.sprite.material.map.dispose();
            moon.sprite.material.dispose();
            moon.glow.material.map.dispose();
            moon.glow.material.dispose();
            sky.geometry.dispose();
            sky.material.dispose();
            host.replaceChildren();
        };
    }

    function createSkyDome() {
        const geometry = new THREE.SphereGeometry(520, 64, 64);
        const material = new THREE.ShaderMaterial({
            side: THREE.BackSide,
            depthWrite: false,
            uniforms: {
                uZenithColor: { value: new THREE.Color(0x04101f) },
                uUpperColor: { value: new THREE.Color(0x0b1f39) },
                uLowerColor: { value: new THREE.Color(0x173963) },
                uHorizonColor: { value: new THREE.Color(0xe8ddcd) },
                uHazeColor: { value: new THREE.Color(0x9a93a3) },
                uCityGlowColor: { value: new THREE.Color(0xe2bf9c) },
                uResolution: { value: new THREE.Vector2(Math.max(window.innerWidth, 1), Math.max(window.innerHeight, 1)) },
            },
            vertexShader: `
                varying vec3 vWorldPosition;
                void main() {
                    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
                    vWorldPosition = worldPosition.xyz;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 uZenithColor;
                uniform vec3 uUpperColor;
                uniform vec3 uLowerColor;
                uniform vec3 uHorizonColor;
                uniform vec3 uHazeColor;
                uniform vec3 uCityGlowColor;
                uniform vec2 uResolution;
                varying vec3 vWorldPosition;

                void main() {
                    vec3 dir = normalize(vWorldPosition);
                    vec2 screenUv = gl_FragCoord.xy / max(uResolution, vec2(1.0));
                    float y = clamp(dir.y * 0.5 + 0.5, 0.0, 1.0);
                    vec3 sky = mix(uLowerColor, uUpperColor, smoothstep(0.06, 0.56, y));
                    sky = mix(sky, uZenithColor, smoothstep(0.56, 1.0, y));

                    float lowGlow = smoothstep(0.0, 0.2, y) * (1.0 - smoothstep(0.2, 0.36, y));
                    float horizon = smoothstep(0.0, 0.075, y) * (1.0 - smoothstep(0.075, 0.2, y));
                    float centeredX = abs(screenUv.x - 0.5) * 2.0;
                    float edgeBias = 1.04 + 0.16 * smoothstep(0.0, 0.94, centeredX);
                    float cityCore = exp(-screenUv.y * 10.4);
                    float cityGlow = exp(-screenUv.y * 4.8);
                    float cityMist = exp(-screenUv.y * 2.85);

                    sky += uHazeColor * lowGlow * 0.44;
                    sky += uHorizonColor * horizon * 0.065;
                    sky += uCityGlowColor * cityCore * 0.136 * edgeBias;
                    sky += uCityGlowColor * cityGlow * 0.066 * edgeBias;
                    sky += uHazeColor * cityMist * 0.056 * edgeBias;

                    gl_FragColor = vec4(sky, 1.0);
                }
            `,
        });
        return new THREE.Mesh(geometry, material);
    }

    function createStarField() {
        const isMobile = matchMedia("(max-width: 768px)").matches;
        const layerConfigs = isMobile
            ? [
                {
                    key: "moonNear",
                    count: 28,
                    radiusMin: 304,
                    radiusMax: 342,
                    scaleMin: 2.28,
                    scaleMax: 3.54,
                    alphaMin: 0.84,
                    alphaMax: 1.0,
                    depthMin: 1.34,
                    depthMax: 1.86,
                    yBias: 24,
                    yScale: 0.68,
                    brightChance: 0.5,
                    midChance: 0.94,
                    twinkleChance: 0.56,
                    twinkleMin: 0.46,
                    twinkleMax: 0.88,
                },
                {
                    key: "near",
                    count: 78,
                    radiusMin: 346,
                    radiusMax: 392,
                    scaleMin: 1.54,
                    scaleMax: 2.42,
                    alphaMin: 0.66,
                    alphaMax: 0.9,
                    depthMin: 1.12,
                    depthMax: 1.58,
                    yBias: 21,
                    yScale: 0.65,
                    brightChance: 0.36,
                    midChance: 0.88,
                    twinkleChance: 0.48,
                    twinkleMin: 0.42,
                    twinkleMax: 0.82,
                },
                {
                    key: "mid",
                    count: 226,
                    radiusMin: 402,
                    radiusMax: 458,
                    scaleMin: 0.92,
                    scaleMax: 1.58,
                    alphaMin: 0.34,
                    alphaMax: 0.56,
                    depthMin: 0.94,
                    depthMax: 1.34,
                    yBias: 18,
                    yScale: 0.62,
                    brightChance: 0.08,
                    midChance: 0.28,
                    twinkleChance: 0.34,
                    twinkleMin: 0.34,
                    twinkleMax: 0.7,
                },
                {
                    key: "far",
                    count: 316,
                    radiusMin: 466,
                    radiusMax: 522,
                    scaleMin: 0.5,
                    scaleMax: 0.9,
                    alphaMin: 0.15,
                    alphaMax: 0.28,
                    depthMin: 0.72,
                    depthMax: 1.0,
                    yBias: 14,
                    yScale: 0.58,
                    brightChance: 0.0,
                    midChance: 0.0,
                    twinkleChance: 0.24,
                    twinkleMin: 0.24,
                    twinkleMax: 0.52,
                },
            ]
            : [
                {
                    key: "moonNear",
                    count: 58,
                    radiusMin: 308,
                    radiusMax: 348,
                    scaleMin: 2.32,
                    scaleMax: 3.68,
                    alphaMin: 0.84,
                    alphaMax: 1.0,
                    depthMin: 1.36,
                    depthMax: 1.9,
                    yBias: 24,
                    yScale: 0.68,
                    brightChance: 0.52,
                    midChance: 0.94,
                    twinkleChance: 0.54,
                    twinkleMin: 0.44,
                    twinkleMax: 0.88,
                },
                {
                    key: "near",
                    count: 154,
                    radiusMin: 344,
                    radiusMax: 394,
                    scaleMin: 1.56,
                    scaleMax: 2.46,
                    alphaMin: 0.66,
                    alphaMax: 0.92,
                    depthMin: 1.12,
                    depthMax: 1.6,
                    yBias: 21,
                    yScale: 0.65,
                    brightChance: 0.36,
                    midChance: 0.88,
                    twinkleChance: 0.48,
                    twinkleMin: 0.42,
                    twinkleMax: 0.84,
                },
                {
                    key: "mid",
                    count: 378,
                    radiusMin: 406,
                    radiusMax: 462,
                    scaleMin: 0.92,
                    scaleMax: 1.62,
                    alphaMin: 0.32,
                    alphaMax: 0.56,
                    depthMin: 0.96,
                    depthMax: 1.36,
                    yBias: 18,
                    yScale: 0.62,
                    brightChance: 0.08,
                    midChance: 0.28,
                    twinkleChance: 0.32,
                    twinkleMin: 0.32,
                    twinkleMax: 0.68,
                },
                {
                    key: "far",
                    count: 520,
                    radiusMin: 468,
                    radiusMax: 528,
                    scaleMin: 0.5,
                    scaleMax: 0.92,
                    alphaMin: 0.15,
                    alphaMax: 0.28,
                    depthMin: 0.72,
                    depthMax: 1.0,
                    yBias: 14,
                    yScale: 0.58,
                    brightChance: 0.0,
                    midChance: 0.0,
                    twinkleChance: 0.22,
                    twinkleMin: 0.22,
                    twinkleMax: 0.48,
                },
            ];
        const moonDirection = new THREE.Vector3(168, 120, -312).normalize();
        const moonMaskDot = Math.cos(0.018);

        const layers = {};
        for (const config of layerConfigs) {
            layers[config.key] = buildStarLayer(config, moonDirection, moonMaskDot);
        }
        return layers;
    }

    function buildStarLayer(config, moonDirection, moonMaskDot) {
        const positions = new Float32Array(config.count * 3);
        const scales = new Float32Array(config.count);
        const alphas = new Float32Array(config.count);
        const phases = new Float32Array(config.count);
        const twinkles = new Float32Array(config.count);
        const depths = new Float32Array(config.count);

        for (let i = 0; i < config.count; i += 1) {
            const radius = config.radiusMin + Math.random() * (config.radiusMax - config.radiusMin);
            let x = 0;
            let y = 0;
            let z = 0;

            for (let attempt = 0; attempt < 12; attempt += 1) {
                const azimuth = Math.random() * Math.PI * 2;
                const elevation = Math.pow(Math.random(), 0.72) * Math.PI * 0.88;
                const sinPhi = Math.sin(elevation);
                x = radius * sinPhi * Math.cos(azimuth);
                z = -Math.abs(radius * Math.cos(elevation));
                y = radius * sinPhi * Math.sin(azimuth);
                const direction = new THREE.Vector3(x, y * config.yScale + config.yBias, z).normalize();
                if (direction.dot(moonDirection) < moonMaskDot) {
                    break;
                }
            }

            positions[i * 3] = x;
            positions[i * 3 + 1] = y * config.yScale + config.yBias;
            positions[i * 3 + 2] = z;
            depths[i] = config.depthMin + Math.random() * (config.depthMax - config.depthMin);

            const brightRoll = Math.random();
            if (brightRoll > config.midChance) {
                scales[i] = config.scaleMin + (config.scaleMax - config.scaleMin) * (0.74 + Math.random() * 0.26);
                alphas[i] = config.alphaMin + (config.alphaMax - config.alphaMin) * (0.76 + Math.random() * 0.24);
            } else if (brightRoll > config.brightChance) {
                scales[i] = config.scaleMin + (config.scaleMax - config.scaleMin) * (0.34 + Math.random() * 0.36);
                alphas[i] = config.alphaMin + (config.alphaMax - config.alphaMin) * (0.4 + Math.random() * 0.28);
            } else {
                scales[i] = config.scaleMin + Math.random() * (config.scaleMax - config.scaleMin) * 0.24;
                alphas[i] = config.alphaMin + Math.random() * (config.alphaMax - config.alphaMin) * 0.18;
            }

            phases[i] = Math.random() * Math.PI * 2;
            twinkles[i] = Math.random() > (1 - config.twinkleChance)
                ? config.twinkleMin + Math.random() * (config.twinkleMax - config.twinkleMin)
                : 0.0;
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute("aScale", new THREE.BufferAttribute(scales, 1));
        geometry.setAttribute("aAlpha", new THREE.BufferAttribute(alphas, 1));
        geometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
        geometry.setAttribute("aTwinkle", new THREE.BufferAttribute(twinkles, 1));
        geometry.setAttribute("aDepth", new THREE.BufferAttribute(depths, 1));

        const material = new THREE.ShaderMaterial({
            transparent: true,
            depthTest: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            uniforms: {
                uTime: { value: 0 },
                uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 1.75) },
            },
            vertexShader: `
                attribute float aScale;
                attribute float aAlpha;
                attribute float aPhase;
                attribute float aTwinkle;
                attribute float aDepth;
                varying float vAlpha;
                varying float vPhase;
                varying float vTwinkle;
                uniform float uPixelRatio;
                void main() {
                    vAlpha = aAlpha;
                    vPhase = aPhase;
                    vTwinkle = aTwinkle;
                    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                    gl_PointSize = aScale * aDepth * uPixelRatio * (244.0 / -mvPosition.z);
                    gl_Position = projectionMatrix * mvPosition;
                }
            `,
            fragmentShader: `
                uniform float uTime;
                varying float vAlpha;
                varying float vPhase;
                varying float vTwinkle;
                void main() {
                    vec2 centered = gl_PointCoord - vec2(0.5);
                    float dist = length(centered);
                    float body = smoothstep(0.52, 0.0, dist);
                    float glow = smoothstep(0.82, 0.0, dist) * 0.66;
                    float flicker = vTwinkle > 0.0 ? sin(uTime * vTwinkle + vPhase) * 0.22 : 0.0;
                    float alpha = max(0.0, vAlpha + flicker) * (body + glow);
                    gl_FragColor = vec4(vec3(0.94, 0.97, 1.0), alpha);
                }
            `,
        });

        const points = new THREE.Points(geometry, material);
        points.renderOrder = 10;
        return { geometry, material, points };
    }

    function createMoon() {
        const moonTexture = new THREE.TextureLoader().load("/static/moon.png");
        moonTexture.colorSpace = THREE.SRGBColorSpace;

        const occluderMaterial = new THREE.SpriteMaterial({
            transparent: false,
            depthWrite: true,
            depthTest: false,
            opacity: 1,
            color: 0xffffff,
        });
        occluderMaterial.colorWrite = false;
        const occluderSprite = new THREE.Sprite(occluderMaterial);
        occluderSprite.position.set(168, 120, -312);
        occluderSprite.scale.set(60, 60, 1);
        occluderSprite.renderOrder = 9;

        const moonMaterial = new THREE.SpriteMaterial({
            map: moonTexture,
            transparent: true,
            depthWrite: false,
            depthTest: false,
            opacity: 0.95,
            color: 0xf5f4ef,
        });
        const moonSprite = new THREE.Sprite(moonMaterial);
        moonSprite.position.set(168, 120, -312);
        moonSprite.scale.set(58, 58, 1);
        moonSprite.renderOrder = 30;

        const glowTexture = buildGlowTexture();
        const glowMaterial = new THREE.SpriteMaterial({
            map: glowTexture,
            transparent: true,
            depthWrite: false,
            depthTest: false,
            opacity: 0.42,
            color: 0xe7eef9,
        });
        const glowSprite = new THREE.Sprite(glowMaterial);
        glowSprite.position.copy(moonSprite.position);
        glowSprite.scale.set(148, 148, 1);
        glowSprite.renderOrder = 29;

        return {
            occluder: occluderSprite,
            sprite: moonSprite,
            glow: glowSprite,
        };
    }

    function positionMoon(moon, width, height) {
        const aspect = width / Math.max(height, 1);
        const narrowness = THREE.MathUtils.clamp((1.82 - aspect) / 1.08, 0, 1);
        const moonX = THREE.MathUtils.lerp(160, 54, narrowness);
        const moonY = THREE.MathUtils.lerp(116, 86, narrowness);
        const moonScale = THREE.MathUtils.lerp(58, 46, narrowness);
        const glowScale = THREE.MathUtils.lerp(148, 112, narrowness);
        const occluderScale = moonScale * 1.08;

        moon.occluder.position.set(moonX, moonY, -312);
        moon.occluder.scale.set(occluderScale, occluderScale, 1);
        moon.sprite.position.set(moonX, moonY, -312);
        moon.glow.position.copy(moon.sprite.position);
        moon.sprite.scale.set(moonScale, moonScale, 1);
        moon.glow.scale.set(glowScale, glowScale, 1);
    }

    function createMotionController(gyroVelocity) {
        const controller = { active: false, lastEventAt: 0, cleanup() {} };
        let lastSampleYaw = null;
        let lastSamplePitch = null;

        if (matchMedia("(pointer:fine)").matches || typeof window.DeviceOrientationEvent === "undefined") {
            return controller;
        }

        const onOrientation = (event) => {
            if (typeof event.gamma !== "number" || typeof event.beta !== "number") {
                return;
            }
            controller.active = true;
            controller.lastEventAt = performance.now();
            const sampleYaw = THREE.MathUtils.clamp(event.gamma / 32, -1, 1);
            const samplePitch = THREE.MathUtils.clamp((event.beta - 45) / 40, -1, 1);

            if (lastSampleYaw !== null && lastSamplePitch !== null) {
                let deltaYaw = sampleYaw - lastSampleYaw;
                let deltaPitch = samplePitch - lastSamplePitch;

                if (Math.abs(deltaYaw) < 0.014) deltaYaw = 0;
                if (Math.abs(deltaPitch) < 0.014) deltaPitch = 0;

                gyroVelocity.yaw = accumulateGyroVelocity(gyroVelocity.yaw, deltaYaw * 0.9, 0.12);
                gyroVelocity.pitch = accumulateGyroVelocity(gyroVelocity.pitch, deltaPitch * 0.78, 0.1);
            }

            lastSampleYaw = sampleYaw;
            lastSamplePitch = samplePitch;
        };

        const bindOrientation = () => {
            window.addEventListener("deviceorientation", onOrientation);
        };

        const requestPermission = async () => {
            try {
                if (typeof window.DeviceOrientationEvent?.requestPermission === "function") {
                    const result = await window.DeviceOrientationEvent.requestPermission();
                    if (result === "granted") {
                        bindOrientation();
                    }
                } else {
                    bindOrientation();
                }
            } catch (_error) {
                // ignore permission errors
            }
            window.removeEventListener("touchstart", requestPermission);
            window.removeEventListener("pointerdown", requestPermission);
        };

        if (typeof window.DeviceOrientationEvent?.requestPermission === "function") {
            window.addEventListener("touchstart", requestPermission, { once: true });
            window.addEventListener("pointerdown", requestPermission, { once: true });
        } else {
            requestPermission();
        }
        controller.cleanup = () => {
            window.removeEventListener("deviceorientation", onOrientation);
            window.removeEventListener("touchstart", requestPermission);
            window.removeEventListener("pointerdown", requestPermission);
        };

        return controller;
    }

    function accumulateGyroVelocity(current, delta, limit) {
        if (!delta) {
            return current;
        }
        const ratio = Math.min(Math.abs(current) / limit, 1);
        const headroom = THREE.MathUtils.lerp(1, 0.18, ratio * ratio);
        const next = current + delta * headroom;
        return THREE.MathUtils.clamp(next, -limit, limit);
    }

    function buildGlowTexture() {
        const canvas = document.createElement("canvas");
        canvas.width = 256;
        canvas.height = 256;
        const context = canvas.getContext("2d");
        const gradient = context.createRadialGradient(128, 128, 18, 128, 128, 128);
        gradient.addColorStop(0, "rgba(255, 249, 236, 0.48)");
        gradient.addColorStop(0.22, "rgba(241, 244, 250, 0.26)");
        gradient.addColorStop(0.48, "rgba(217, 228, 245, 0.11)");
        gradient.addColorStop(1, "rgba(217, 228, 245, 0)");
        context.fillStyle = gradient;
        context.fillRect(0, 0, canvas.width, canvas.height);

        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        return texture;
    }
})();
