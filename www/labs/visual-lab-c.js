import * as THREE from "/static/shared/vendor/three.module.min.js";

(function () {
    const sceneHost = document.getElementById("lab-scene");
    const grid = document.getElementById("lab-grid");
    const modal = document.getElementById("lab-modal");
    const modalImage = document.getElementById("lab-modal-image");
    const modalClose = document.getElementById("lab-modal-close");
    const modalBackdrop = document.querySelector("[data-modal-close]");
    const fallback = "/static/shared/images/favicon.jpg";

    let disposeScene = null;

    initPreviewCards();

    if (sceneHost) {
        disposeScene = createNightSky(sceneHost);
        window.addEventListener("beforeunload", () => {
            if (disposeScene) {
                disposeScene();
            }
        }, { once: true });
    }

    if (modalClose) {
        modalClose.addEventListener("click", closeModal);
    }
    if (modalBackdrop) {
        modalBackdrop.addEventListener("click", closeModal);
    }
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && modal && !modal.hidden) {
            closeModal();
        }
    });

    async function initPreviewCards() {
        try {
            const response = await fetch("/api/gallery/albums");
            if (!response.ok) {
                throw new Error("albums unavailable");
            }
            const data = await response.json();
            const cards = (data.albums || []).slice(0, 4);
            if (cards.length > 0) {
                renderCards(cards.map((album) => album.cover_url || fallback));
                return;
            }
        } catch (_error) {
            // ignore and fall back
        }

        renderCards(Array.from({ length: 4 }, () => fallback));
    }

    function renderCards(images) {
        grid.replaceChildren();
        images.forEach((src) => {
            const card = document.createElement("button");
            card.type = "button";
            card.className = "lab-card";
            card.addEventListener("click", () => openModal(src));

            const image = document.createElement("img");
            image.src = src;
            image.alt = "";
            card.appendChild(image);
            grid.appendChild(card);
        });
    }

    function openModal(src) {
        if (!modal || !modalImage) return;
        modalImage.src = src;
        modal.hidden = false;
        document.body.style.overflow = "hidden";
    }

    function closeModal() {
        if (!modal || !modalImage) return;
        modal.hidden = true;
        modalImage.src = "";
        document.body.style.overflow = "";
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
        const farStarGroup = new THREE.Group();
        const midStarGroup = new THREE.Group();
        const nearStarGroup = new THREE.Group();
        const moonGroup = new THREE.Group();
        const cloudGroup = new THREE.Group();
        scene.add(skyGroup);
        scene.add(starGroup);
        scene.add(moonGroup);
        scene.add(cloudGroup);
        starGroup.add(moonNearStarGroup);
        starGroup.add(farStarGroup);
        starGroup.add(midStarGroup);
        starGroup.add(nearStarGroup);

        const target = { yaw: 0, pitch: 0 };
        const current = { yaw: 0, pitch: 0 };
        let rafId = 0;
        let disposed = false;

        const sky = createSkyDome();
        skyGroup.add(sky);

        const stars = createStarField();
        moonNearStarGroup.add(stars.moonNear.points);
        farStarGroup.add(stars.far.points);
        midStarGroup.add(stars.mid.points);
        nearStarGroup.add(stars.near.points);

        const moon = createMoon();
        moonGroup.add(moon.occluder);
        moonGroup.add(moon.glow);
        moonGroup.add(moon.sprite);

        const autoDriftSeed = Math.random() * Math.PI * 2;

        function resize() {
            const width = host.clientWidth || window.innerWidth;
            const height = host.clientHeight || window.innerHeight;
            camera.aspect = width / Math.max(height, 1);
            camera.updateProjectionMatrix();
            renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
            renderer.setSize(width, height, false);
            sky.material.uniforms.uAspect.value = width / Math.max(height, 1);
            sky.material.uniforms.uResolution.value.set(width, height);
            positionMoon(moon, width, height);
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
            const mobileDrift = !matchMedia("(pointer:fine)").matches;
            if (mobileDrift) {
                target.yaw = Math.sin(time * 0.18 + autoDriftSeed) * 0.024;
                target.pitch = Math.cos(time * 0.13 + autoDriftSeed) * 0.024;
            }

            current.yaw += (target.yaw - current.yaw) * 0.035;
            current.pitch += (target.pitch - current.pitch) * 0.04;

            skyGroup.rotation.y = current.yaw * 0.28;
            skyGroup.rotation.x = current.pitch * 0.34;
            moonNearStarGroup.rotation.y = current.yaw * 0.92;
            moonNearStarGroup.rotation.x = current.pitch * 1.04;
            nearStarGroup.rotation.y = current.yaw * 1.14;
            nearStarGroup.rotation.x = current.pitch * 1.26;
            midStarGroup.rotation.y = current.yaw * 1.42;
            midStarGroup.rotation.x = current.pitch * 1.58;
            farStarGroup.rotation.y = current.yaw * 1.78;
            farStarGroup.rotation.x = current.pitch * 1.96;
            moonGroup.rotation.y = current.yaw * 0.64;
            moonGroup.rotation.x = current.pitch * 0.76;
            cloudGroup.rotation.y = current.yaw * 1.62;
            cloudGroup.rotation.x = current.pitch * 1.82;

            stars.moonNear.material.uniforms.uTime.value = time;
            stars.near.material.uniforms.uTime.value = time;
            stars.mid.material.uniforms.uTime.value = time;
            stars.far.material.uniforms.uTime.value = time;

            renderer.render(scene, camera);
            rafId = window.requestAnimationFrame(animate);
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
                uAspect: { value: Math.max(window.innerWidth, 1) / Math.max(window.innerHeight, 1) },
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
                uniform float uAspect;
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
        const moonTexture = new THREE.TextureLoader().load("/static/home/moon.png");
        moonTexture.colorSpace = THREE.SRGBColorSpace;

        const maskMaterial = new THREE.SpriteMaterial({
            transparent: false,
            depthWrite: true,
            depthTest: false,
            opacity: 1,
            color: 0xffffff,
        });
        maskMaterial.colorWrite = false;
        const maskSprite = new THREE.Sprite(maskMaterial);
        maskSprite.position.set(168, 120, -312);
        maskSprite.scale.set(60, 60, 1);
        maskSprite.renderOrder = 9;

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
            occluder: maskSprite,
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
