(function () {
    const state = {
        albums: [],
        currentAlbum: null,
        currentImageIndex: 0,
    };

    const albumsGrid = document.getElementById("albums-grid");
    const albumsMeta = document.getElementById("albums-meta");
    const albumsEmpty = document.getElementById("albums-empty");
    const modal = document.getElementById("gallery-modal");
    const modalImage = document.getElementById("gallery-modal-image");
    const secretEntry = document.getElementById("secret-entry");
    const secretEntryImage = document.getElementById("secret-entry-image");

    secretEntryImage.addEventListener("error", () => {
        const fallback = secretEntryImage.dataset.fallbackSrc;
        if (fallback && secretEntryImage.src !== fallback) {
            secretEntryImage.src = fallback;
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
        albumsGrid.innerHTML = "";
        albumsMeta.textContent = `${state.albums.length} albums`;
        albumsEmpty.hidden = state.albums.length > 0;

        state.albums.forEach((album) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "album-card";
            button.innerHTML = `<img class="album-cover" src="${album.cover_url}" alt="">`;
            button.addEventListener("click", () => openAlbum(album.slug));
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
        if (!state.currentAlbum || !state.currentAlbum.images.length) {
            return;
        }
        const currentImage = state.currentAlbum.images[state.currentImageIndex];
        modalImage.src = currentImage.url;
        modalImage.alt = "";
    }

    function showNextImage() {
        if (!state.currentAlbum) return;
        state.currentImageIndex = (state.currentImageIndex + 1) % state.currentAlbum.images.length;
        renderModalImage();
    }

    function showPrevImage() {
        if (!state.currentAlbum) return;
        state.currentImageIndex =
            (state.currentImageIndex - 1 + state.currentAlbum.images.length) % state.currentAlbum.images.length;
        renderModalImage();
    }

    function closeModal() {
        modal.hidden = true;
        document.body.style.overflow = "";
    }

    document.getElementById("gallery-prev").addEventListener("click", showPrevImage);
    document.getElementById("gallery-next").addEventListener("click", showNextImage);
    document.getElementById("gallery-modal-close").addEventListener("click", closeModal);
    document.querySelector("[data-modal-close]").addEventListener("click", closeModal);
    document.addEventListener("keydown", (event) => {
        if (modal.hidden) return;
        if (event.key === "Escape") closeModal();
        if (event.key === "ArrowRight") showNextImage();
        if (event.key === "ArrowLeft") showPrevImage();
    });

    loadAlbums().catch(() => {
        albumsMeta.textContent = "Albums unavailable";
        albumsEmpty.hidden = false;
    });
})();
