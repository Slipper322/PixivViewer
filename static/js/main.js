// pixiv_viewer/static/js/main.js

// DOM Elements
const currentImageEl = document.getElementById('currentImage');
const imageLoaderSpinnerEl = document.getElementById('imageLoaderSpinner');
const thumbnailsSidebarEl = document.getElementById('thumbnailsSidebar');
const imageInfoTextEl = document.getElementById('imageInfoText');
const pageInfoEl = document.getElementById('pageInfo');
// Buttons
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const bookmarkBtn = document.getElementById('bookmarkBtn');
const openOriginalBtn = document.getElementById('openOriginalBtn');
const downloadOriginalBtn = document.getElementById('downloadOriginalBtn'); // New
const searchIqdbBtn = document.getElementById('searchIqdbBtn'); // New
const infoToggleBtn = document.getElementById('infoToggleBtn');
const modeToggleBtn = document.getElementById('modeToggleBtn');
// Panel Elements (замена Modal)
const illustInfoPanelEl = document.getElementById('illustInfoPanel');
const panelIllustTitleEl = document.getElementById('panelIllustTitle');
const panelIllustAuthorEl = document.getElementById('panelIllustAuthor');
// These will be made interactive for copying
const panelIllustResolutionEl = document.getElementById('panelIllustResolution');
const panelIllustPixivLinkEl = document.getElementById('panelIllustPixivLink');
const panelIllustTagsEl = document.getElementById('panelIllustTags');
// const closeModalBtn = document.getElementById('closeIllustInfoModalBtn'); // Если была кнопка закрытия панели
const sidebarResizerEl = document.getElementById('sidebarResizer');
// const imageViewerContainerEl = document.getElementById('imageViewerContainer'); // Если нужен

// App State
const PRELOAD_COUNT = 2;
let illustList = [];
let currentIllustListIndex = -1;
let currentPixivApiPageForList = 1;
let isLoadingIllustList = false;
let globalCsrfToken = '';
let hotkeyCooldown = false;
const HOTKEY_COOLDOWN_MS = 200;

let currentViewMode = 'new_illust'; // 'new_illust' или 'user_bookmarks'
let currentOffsetForBookmarks = 0; // Для пагинации закладок
const BOOKMARKS_PAGE_LIMIT = 48; // Должно совпадать с BOOKMARKS_API_LIMIT в app.py

const MIN_SIDEBAR_WIDTH = 150; // px
const MAX_SIDEBAR_WIDTH = 600; // px
let isResizingSidebar = false;

// Bookmark animation elements
const bookmarkAnimationOverlayEl = document.getElementById('bookmarkAnimationOverlay');
const bookmarkAnimationIconEl = document.getElementById('bookmarkAnimationIcon');
// --- UI Update Functions ---
function initUI() {
    currentImageEl.src = "";
    currentImageEl.alt = "Ожидание загрузки";
    imageInfoTextEl.textContent = 'Загрузка данных...';
    pageInfoEl.textContent = '';
    bookmarkBtn.disabled = true;
    openOriginalBtn.classList.add('hidden');
    downloadOriginalBtn.classList.add('hidden');
    searchIqdbBtn.classList.add('hidden');
    infoToggleBtn.classList.add('hidden');
    thumbnailsSidebarEl.innerHTML = '';
    hideImageSpinner();
    hideInfoPanel(); // Используем новую функцию для скрытия панели
    updateModeToggleUI(); // Обновляем иконку кнопки режима
}

function updateModeToggleUI() {
    const newIllustIcon = modeToggleBtn.querySelector('.mode-new-illust');
    const userBookmarksIcon = modeToggleBtn.querySelector('.mode-user-bookmarks');
    if (currentViewMode === 'new_illust') {
        modeToggleBtn.classList.remove('view-user-bookmarks'); // Keep for semantics if needed
        modeToggleBtn.classList.add('view-new-illust');     // Keep for semantics if needed
        if (newIllustIcon) newIllustIcon.classList.remove('hidden');
        if (userBookmarksIcon) userBookmarksIcon.classList.add('hidden');
        modeToggleBtn.title = "Переключить на Мои Закладки";
    } else { // user_bookmarks
        modeToggleBtn.classList.remove('view-new-illust');   // Keep for semantics if needed
        modeToggleBtn.classList.add('view-user-bookmarks'); // Keep for semantics if needed
        if (newIllustIcon) newIllustIcon.classList.add('hidden');
        if (userBookmarksIcon) userBookmarksIcon.classList.remove('hidden');
        modeToggleBtn.title = "Переключить на Новое от подписок";
    }
}

function showImageSpinner() {
    if (imageLoaderSpinnerEl) imageLoaderSpinnerEl.style.display = 'block';
    currentImageEl.style.opacity = '0.3';
}

function hideImageSpinner() {
    if (imageLoaderSpinnerEl) imageLoaderSpinnerEl.style.display = 'none';
    currentImageEl.style.opacity = '1';
}

function updateBookmarkButtonUI(illustDataItem) {
    if (!illustDataItem) {
        bookmarkBtn.disabled = true;
        bookmarkBtn.classList.remove('bookmarked');
        bookmarkBtn.title = "В закладки (F)";
        return;
    }
    bookmarkBtn.disabled = false;
    if (illustDataItem.is_bookmarked) {
        bookmarkBtn.classList.add('bookmarked');
        bookmarkBtn.title = "Убрать из закладок (F)";
    } else {
        bookmarkBtn.classList.remove('bookmarked');
        bookmarkBtn.title = "В закладки (F)";
    }
}

// При инициализации или обновлении списка иллюстраций
function processRawIllustList(rawIllusts) {
    return rawIllusts.map(meta => ({
        id: meta.id,
        title: meta.title,
        preview_url_p0: meta.preview_url_p0,
        page_count: parseInt(meta.page_count, 10) || 1,
        is_bookmarked: meta.is_bookmarked, // Это должно быть установлено сервером
        bookmark_id: meta.bookmark_id || null, // Попытка получить bookmark_id, если он есть в ответе списка
        width: meta.width,
        height: meta.height,
        pages_data: [],
        current_page_in_illust: 0,
        pages_data_loading_status: 'idle',
        detail_info_fetched: meta.bookmark_id ? true : false, // Если bookmark_id уже есть, считаем детали частично загруженными
        detail_info_fetched_pending: false,
        author_name: meta.author_name || null, // Если сервер передает
        author_id: meta.author_id || null,     // Если сервер передает
        tags: meta.tags || []                  // Если сервер передает
    }));
}


// --- Thumbnail Rendering and UI ---
function renderThumbnails() {
    thumbnailsSidebarEl.innerHTML = '';
    illustList.forEach((illust, index) => {
        const thumbItem = document.createElement('div');
        thumbItem.classList.add('thumbnail-item');
        thumbItem.dataset.index = index;
        thumbItem.dataset.id = illust.id;

        const img = document.createElement('img');
        if (illust.preview_url_p0) {
            const proxyThumbUrl = `/api/image_proxy?image_url=${encodeURIComponent(illust.preview_url_p0)}&illust_id=${encodeURIComponent(illust.id)}`;
            img.src = proxyThumbUrl;
            img.alt = illust.title.substring(0, 30);
            img.title = illust.title;
        } else { img.alt = "Нет превью"; }
        thumbItem.appendChild(img);

        const progressIndicatorContainer = document.createElement('div');
        progressIndicatorContainer.classList.add('thumb-progress-indicator');
        progressIndicatorContainer.innerHTML = `<div class="circular-loader"></div><div class="error-icon hidden">!</div>`;
        thumbItem.appendChild(progressIndicatorContainer);
        
        const pageCounterEl = document.createElement('div');
        pageCounterEl.classList.add('thumb-page-counter');
        thumbItem.appendChild(pageCounterEl);

        thumbItem.addEventListener('click', async () => {
            if (currentIllustListIndex === index && illustList[currentIllustListIndex]?.pages_data_loading_status === 'loaded') {
                thumbItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                return;
            }
            currentIllustListIndex = index;
            await displayCurrentIllustAndPage();
        });
        thumbnailsSidebarEl.appendChild(thumbItem);
        updateThumbnailUI(illust);
    });
    highlightActiveThumbnail();
}

function updateThumbnailUI(illustDataItem) {
    const thumbItem = thumbnailsSidebarEl.querySelector(`.thumbnail-item[data-id="${illustDataItem.id}"]`);
    if (!thumbItem) return;

    const progressContainer = thumbItem.querySelector('.thumb-progress-indicator');
    const loader = progressContainer.querySelector('.circular-loader');
    const errorIcon = progressContainer.querySelector('.error-icon');
    const pageCounter = thumbItem.querySelector('.thumb-page-counter');

    loader.style.display = 'none';
    errorIcon.style.display = 'none';
    progressContainer.style.display = 'none';

    if (illustDataItem.pages_data_loading_status === 'loading') {
        progressContainer.style.display = 'flex'; // Используем flex для центрирования
        loader.style.display = 'block';
    } else if (illustDataItem.pages_data_loading_status === 'error') {
        progressContainer.style.display = 'flex';
        errorIcon.style.display = 'block';
    }

    if (illustDataItem.page_count > 1) {
        pageCounter.style.display = 'block';
        let currentPageNum = (illustDataItem.id === (illustList[currentIllustListIndex]?.id)) 
                             ? illustDataItem.current_page_in_illust + 1 : 1;
        pageCounter.textContent = `${illustDataItem.page_count}`; // Только N
    } else {
        pageCounter.style.display = 'none';
    }
}

function highlightActiveThumbnail() {
    thumbnailsSidebarEl.querySelectorAll('.thumbnail-item').forEach(thumb => {
        const isActive = thumb.dataset.id === (illustList[currentIllustListIndex]?.id);
        thumb.classList.toggle('active', isActive);
        if (isActive) {
                thumb.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
}

// --- Data Fetching Functions ---
async function fetchIllustListFromBackend() {
    if (isLoadingIllustList) return;
    isLoadingIllustList = true;
    
    let isFirstLoadForCurrentMode = false; // Флаг, является ли это первой загрузкой для текущего режима
    let apiUrl = '';

    if (currentViewMode === 'new_illust') {
        imageInfoTextEl.textContent = 'Загрузка новых иллюстраций';
        apiUrl = `/api/images?page=${currentPixivApiPageForList}`;
        isFirstLoadForCurrentMode = (currentPixivApiPageForList === 1);
    } else { // user_bookmarks
        imageInfoTextEl.textContent = 'Загрузка ваших закладок';
        apiUrl = `/api/user_bookmarks?offset=${currentOffsetForBookmarks}&limit=${BOOKMARKS_PAGE_LIMIT}`;
        isFirstLoadForCurrentMode = (currentOffsetForBookmarks === 0);
    }
    imageInfoTextEl.classList.add('loading-text');
    console.log(`Fetching data for mode: ${currentViewMode}, URL: ${apiUrl}`);

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || errorData.error_message || `Ошибка HTTP: ${response.status}`);
        }
        const data = await response.json();

        // CSRF токен обновляется только при загрузке "новых иллюстраций" и только на первой странице
        if (currentViewMode === 'new_illust' && currentPixivApiPageForList === 1 && data.csrf_token) {
            if (!globalCsrfToken || globalCsrfToken !== data.csrf_token) {
                globalCsrfToken = data.csrf_token;
                console.log("CSRF token updated/received:", globalCsrfToken);
            }
        }

        if (data.images && data.images.length > 0) {
            // Используем новую функцию для обработки
            const newIllusts = processRawIllustList(data.images);

            if (isFirstLoadForCurrentMode) {
                illustList = newIllusts;
                currentIllustListIndex = illustList.length > 0 ? 0 : -1;
            } else {
                illustList = illustList.concat(newIllusts);
                // currentIllustListIndex не меняем, если догружаем, чтобы не сбивать просмотр
            }
            
            renderThumbnails(); 

            if (currentIllustListIndex !== -1 && isFirstLoadForCurrentMode) { // Показываем первую, только если это первая загрузка
                await displayCurrentIllustAndPage();
            } else if (illustList.length === 0) { // Если и после первой загрузки ничего
                imageInfoTextEl.textContent = 'Иллюстрации не найдены.';
                pageInfoEl.textContent = '';
                currentImageEl.src = ""; currentImageEl.alt = "Нет иллюстраций";
            }
            // Если догружали, то текущая иллюстрация остается, displayCurrentIllustAndPage не нужен,
            // т.к. пользователь сам нажмет "вперед"
        } else { 
            if (!isFirstLoadForCurrentMode) { // Догружали, но новых нет
                imageInfoTextEl.textContent = (currentViewMode === 'new_illust') ? 'Больше новых иллюстраций не найдено.' : 'Больше закладок не найдено.';
            } else { // Первая загрузка и ничего нет
                illustList = [];
                currentIllustListIndex = -1;
                imageInfoTextEl.textContent = 'Иллюстрации не найдены.';
                pageInfoEl.textContent = '';
                currentImageEl.src = ""; currentImageEl.alt = "Нет иллюстраций";
                renderThumbnails(); 
            }
        }
    } catch (error) {
        console.error(`Ошибка при загрузке (${currentViewMode}):`, error);
        imageInfoTextEl.textContent = `Ошибка загрузки: ${error.message}.`;
    } finally {
        isLoadingIllustList = false;
        imageInfoTextEl.classList.remove('loading-text');
        if (illustList.length === 0 && !isLoadingIllustList) { // Если список все еще пуст
             if (imageInfoTextEl.textContent.includes('Загрузка')) { // Предотвращаем затирание сообщения об ошибке
                imageInfoTextEl.textContent = 'Иллюстрации не найдены.';
             }
        }
    }
}

async function fetchActualIllustPages(illustDataItem) {
    if (!illustDataItem || illustDataItem.pages_data_loading_status === 'loading' || illustDataItem.pages_data_loading_status === 'loaded') return;
    illustDataItem.pages_data_loading_status = 'loading';
    updateThumbnailUI(illustDataItem);
    try {
        const response = await fetch(`/api/illust_pages/${illustDataItem.id}`);
        if (!response.ok) throw new Error((await response.json()).error || `HTTP error ${response.status}`);
        const data = await response.json();
        if (data.pages_data && data.pages_data.length > 0) {
            illustDataItem.pages_data = data.pages_data;
            illustDataItem.pages_data_loading_status = 'loaded';
        } else {
            if (illustDataItem.preview_url_p0) {
                 illustDataItem.pages_data = [{ url_master: illustDataItem.preview_url_p0, url_original: illustDataItem.preview_url_p0, width: illustDataItem.width, height: illustDataItem.height }];
                 illustDataItem.pages_data_loading_status = 'loaded';
            } else { illustDataItem.pages_data_loading_status = 'error'; }
        }
    } catch (error) { console.error(`Fetch page data error for ${illustDataItem.id}:`, error); illustDataItem.pages_data_loading_status = 'error';
    } finally { updateThumbnailUI(illustDataItem); }
}

async function fetchAndUpdateDetailedInfo(illustDataItem) { // Загружает статус закладки, автора, теги
    if (!illustDataItem || illustDataItem.detail_info_fetched_pending) return; // Изменим флаг
    if (illustDataItem.detail_info_fetched && illustDataItem.bookmark_id && illustDataItem.is_bookmarked) {
        // Если закладка есть, и ID закладки известен, и мы считаем, что детали загружены,
        // то можно пропустить, ЕСЛИ нам не нужны теги/автор.
        // Для простоты, пока оставим как есть: если detail_info_fetched false, то грузим.
        // Если true, то уже все есть (или было загружено ранее).
    }
    if (illustDataItem.detail_info_fetched) { // Если уже считаем, что все загружено
        console.log(`Details for ${illustDataItem.id} already marked as fetched.`);
        return;
    }
    illustDataItem.detail_info_fetched_pending = true; // Помечаем, что запрос в процессе
    try {
        const response = await fetch(`/api/illust_details_and_bookmark_status/${illustDataItem.id}`);
        if (!response.ok) { 
            console.warn(`Failed to fetch details for ${illustDataItem.id}: ${response.status}`); 
            // Не меняем detail_info_fetched на false, если оно уже было true от предыдущей успешной загрузки
            // illustDataItem.detail_info_fetched = false; 
            illustDataItem.detail_info_fetched_pending = false;
            return; 
        }
        const data = await response.json();
        if (data) {
            if (typeof data.is_bookmarked === 'boolean') illustDataItem.is_bookmarked = data.is_bookmarked;
            // Обновляем bookmark_id только если он пришел и отличается, или если его не было
            if (data.bookmark_id !== undefined) { // data.bookmark_id может быть null
                illustDataItem.bookmark_id = data.bookmark_id;
            }

            illustDataItem.author_name = data.user_name || illustDataItem.author_name || "N/A"; // Сохраняем предыдущее значение, если новое N/A
            illustDataItem.author_id = data.user_id || illustDataItem.author_id || null;
            illustDataItem.tags = data.tags && data.tags.length > 0 ? data.tags : illustDataItem.tags || [];
            illustDataItem.detail_info_fetched = true; // Успешно загружено
            
            if (illustList[currentIllustListIndex]?.id === illustDataItem.id) {
                updateBookmarkButtonUI(illustDataItem);
                if (isInfoPanelVisible()) { 
                    populateAndShowInfoPanel(illustDataItem);
                }
            }
        }
    } catch (error) { 
        console.warn(`Error fetching details for ${illustDataItem.id}:`, error); 
        //illustDataItem.detail_info_fetched = false; // Помечаем как неудачную попытку
    } finally {
        illustDataItem.detail_info_fetched_pending = false; // Запрос завершен (успешно или нет)
    }
}

// --- Main Display Function ---
async function displayCurrentIllustAndPage() {
    if (currentIllustListIndex < 0 || currentIllustListIndex >= illustList.length) { initUI(); return; }
    const currentIllust = illustList[currentIllustListIndex];
    highlightActiveThumbnail();
    imageInfoTextEl.classList.remove('loading-text');
    infoToggleBtn.classList.remove('hidden');

    // Сначала загружаем/проверяем детальную информацию (включая статус закладки)
    if (!currentIllust.detail_info_fetched) {
        await fetchAndUpdateDetailedInfo(currentIllust); // Ждем загрузки, чтобы кнопка закладки была актуальна
    }

    if (currentIllust.pages_data_loading_status === 'loading') {
        imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a> (Загрузка страниц...)`;
        imageInfoTextEl.classList.add('loading-text'); showImageSpinner(); openOriginalBtn.classList.add('hidden');
        downloadOriginalBtn.classList.add('hidden');
        searchIqdbBtn.classList.add('hidden');
        updateBookmarkButtonUI(currentIllust); // Обновляем кнопку на случай, если статус уже известен
        return;
    }
    if (currentIllust.pages_data_loading_status === 'idle' || currentIllust.pages_data_loading_status === 'error') {
        if (currentIllust.preview_url_p0) {
             currentImageEl.src = `/api/image_proxy?image_url=${encodeURIComponent(currentIllust.preview_url_p0)}&illust_id=${encodeURIComponent(currentIllust.id)}`;
             currentImageEl.alt = `Превью: ${currentIllust.title}`;
        } else { currentImageEl.src = ""; currentImageEl.alt = "Загрузка..."; }
        imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a> (Ожидание данных...)`;
        pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1}/${illustList.length}.`;
        openOriginalBtn.classList.add('hidden'); 
        downloadOriginalBtn.classList.add('hidden');
        searchIqdbBtn.classList.add('hidden');
        updateBookmarkButtonUI(currentIllust);
        if(currentIllust.pages_data_loading_status !== 'error') await fetchActualIllustPages(currentIllust);
        if (currentIllust.pages_data_loading_status !== 'loading') await displayCurrentIllustAndPage();
        return;
    }

    // Pages data loaded
    hideImageSpinner(); imageInfoTextEl.classList.remove('loading-text');
    if (currentIllust.pages_data.length > 0) {
        const pageIdx = Math.max(0, Math.min(currentIllust.current_page_in_illust, currentIllust.pages_data.length - 1));
        currentIllust.current_page_in_illust = pageIdx;
        const currentPageData = currentIllust.pages_data[pageIdx];
        const imageUrlToDisplay = currentPageData.url_master || currentPageData.url_original;
        let finalImageUrl = imageUrlToDisplay ? `/api/image_proxy?image_url=${encodeURIComponent(imageUrlToDisplay)}&illust_id=${encodeURIComponent(currentIllust.id)}` : "";
        currentImageEl.alt = currentIllust.title;
        if (currentImageEl.src !== window.location.origin + finalImageUrl && finalImageUrl) {
            showImageSpinner(); currentImageEl.src = finalImageUrl;
        } else if (!finalImageUrl) { currentImageEl.src = ""; hideImageSpinner(); }
        else { hideImageSpinner(); } // URL не изменился
        imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a>`;
        pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1}/${illustList.length}. Стр. ${pageIdx + 1}/${currentIllust.pages_data.length}.`;
        openOriginalBtn.classList.toggle('hidden', !currentPageData.url_original);
        downloadOriginalBtn.classList.toggle('hidden', !currentPageData.url_original);
        searchIqdbBtn.classList.toggle('hidden', !(currentPageData.url_master || currentPageData.url_original)); // Prefer master, fallback to original for IQDB
        if(currentPageData.url_original) openOriginalBtn.onclick = () => window.open(`/api/image_proxy?image_url=${encodeURIComponent(currentPageData.url_original)}&illust_id=${encodeURIComponent(currentIllust.id)}`, '_blank');
    } else {
        currentImageEl.src = ""; imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a> (Ошибка загрузки страниц)`;
        pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1}/${illustList.length}.`; 
        openOriginalBtn.classList.add('hidden'); 
        downloadOriginalBtn.classList.add('hidden');
        searchIqdbBtn.classList.add('hidden');
        hideImageSpinner();
    }
    
    updateBookmarkButtonUI(currentIllust);
    if (isInfoPanelVisible()) { // Если панель открыта, обновляем ее содержимое
        populateAndShowInfoPanel(currentIllust);
    }
    if (currentIllust.pages_data_loading_status === 'loaded') preloadNextIllusts();
    updateThumbnailUI(currentIllust);
}

// --- Preloading, Panel Logic, Event Listeners, Navigation, Hotkeys ---
// (Эти функции остаются такими же, как в моем предыдущем ответе, где мы их подробно разбирали)
// Только в preloadNextIllusts, если pages_data_loading_status 'idle' - запускаем fetchActualIllustPages
// и в then уже грузим картинку.

// Пересмотренная preloadNextIllusts:
async function preloadNextIllusts() {
    if (isLoadingIllustList) return;
    let preloadedCount = 0;
    for (let i = 1; i <= PRELOAD_COUNT; i++) {
        const nextIdx = currentIllustListIndex + i;
        if (nextIdx < illustList.length) {
            const illustToPreload = illustList[nextIdx];
            if (illustToPreload && illustToPreload.pages_data_loading_status === 'idle') {
                console.log(`Preloading data for illust ID: ${illustToPreload.id} (index ${nextIdx})`);
                // Запускаем загрузку страниц, и в .then() пытаемся загрузить само изображение
                fetchActualIllustPages(illustToPreload).then(() => {
                    if (illustToPreload.pages_data_loading_status === 'loaded' && illustToPreload.pages_data.length > 0) {
                        const firstPageData = illustToPreload.pages_data[0];
                        const imageUrlToPreload = firstPageData.url_master || firstPageData.url_original;
                        if (imageUrlToPreload) {
                            const proxyPreloadUrl = `/api/image_proxy?image_url=${encodeURIComponent(imageUrlToPreload)}&illust_id=${encodeURIComponent(illustToPreload.id)}`;
                            const tempImg = new Image();
                            tempImg.src = proxyPreloadUrl;
                            console.log(`Preloading image (p0) for illust ID: ${illustToPreload.id}`);
                        }
                    }
                }).catch(error => { /* Обработка ошибки предзагрузки страниц, если нужна */ });
                preloadedCount++;
            }
        } else { break; }
    }
    if (preloadedCount > 0) { console.log(`Initiated preload for ${preloadedCount} illust(s).`); }
}

// Panel Logic
function isInfoPanelVisible() { return illustInfoPanelEl.classList.contains('visible'); }
function populateAndShowInfoPanel(illustDataItem) {
    if (!illustDataItem) return;
    panelIllustTitleEl.textContent = illustDataItem.title;
    panelIllustAuthorEl.textContent = illustDataItem.author_name || "N/A";
    panelIllustAuthorEl.href = illustDataItem.author_id ? `https://www.pixiv.net/users/${illustDataItem.author_id}` : "javascript:void(0);";
    
    
    let resolutionText = "N/A";

    if (illustDataItem.pages_data && illustDataItem.pages_data.length > 0) {
        const firstPage = illustDataItem.pages_data[0];
        resolutionText = (firstPage.width && firstPage.height) ? `${firstPage.width}x${firstPage.height}` : "N/A";
    } else if (illustDataItem.width && illustDataItem.height) {
        resolutionText = `${illustDataItem.width}x${illustDataItem.height} (превью)`; 
    }
    panelIllustResolutionEl.textContent = resolutionText;
    panelIllustResolutionEl.classList.toggle('copyable', resolutionText !== "N/A");
    panelIllustPixivLinkEl.href = `https://www.pixiv.net/artworks/${illustDataItem.id}`;
    panelIllustPixivLinkEl.textContent = `artworks/${illustDataItem.id}`;
    panelIllustPixivLinkEl.classList.add('copyable');

    panelIllustTagsEl.innerHTML = '';
    if (illustDataItem.tags && illustDataItem.tags.length > 0) {
        illustDataItem.tags.forEach(tag => { const t = document.createElement('span'); t.className = 'tag'; t.textContent = tag; panelIllustTagsEl.appendChild(t); });
    } else { panelIllustTagsEl.textContent = "Нет тегов"; }

    const btnRect = infoToggleBtn.getBoundingClientRect();
    illustInfoPanelEl.style.bottom = (window.innerHeight - btnRect.top) + 'px';
    illustInfoPanelEl.style.right = (window.innerWidth - btnRect.right) + 'px';
    illustInfoPanelEl.style.transform = 'translateY(10px) scale(0.95)';
    illustInfoPanelEl.classList.remove('hidden');
    requestAnimationFrame(() => { requestAnimationFrame(() => { illustInfoPanelEl.classList.add('visible'); }); });
}
function hideInfoPanel() {
    illustInfoPanelEl.classList.remove('visible');
    setTimeout(() => { if (!isInfoPanelVisible()) illustInfoPanelEl.classList.add('hidden'); }, 200);
}
// Helper for copy feedback
function showCopyFeedback(element, originalTitleText = "Скопировать") {
    element.classList.add('copied-feedback');
    const currentText = element.title; // Save current specific title if any
    element.title = "Скопировано!";
    setTimeout(() => {
        element.classList.remove('copied-feedback');
        element.title = currentText || originalTitleText; // Restore or set default
    }, 1500);
}
// Event Listeners
document.addEventListener('DOMContentLoaded', () => { 
        initUI(); 
        fetchIllustListFromBackend(); 
        // Add copy listeners for info panel elements
        panelIllustResolutionEl.addEventListener('click', function() {
            if (this.textContent && this.textContent !== "N/A") {
                navigator.clipboard.writeText(this.textContent)
                    .then(() => showCopyFeedback(this, "Копировать разрешение"))
                    .catch(err => console.error('Failed to copy resolution: ', err));
            }
        });
        panelIllustPixivLinkEl.addEventListener('click', function(event) {
            event.preventDefault(); // Prevent default link navigation
            if (event.ctrlKey || event.metaKey) { // Allow opening with Ctrl/Cmd + Click
                window.open(this.href, '_blank');
            } else {
                navigator.clipboard.writeText(this.href)
                    .then(() => showCopyFeedback(this, "Копировать ссылку на пост"))
                    .catch(err => console.error('Failed to copy link: ', err));
            }
        });
    });
currentImageEl.onload = () => hideImageSpinner();
currentImageEl.onerror = () => { hideImageSpinner(); currentImageEl.alt = "Ошибка загрузки изображения"; };
prevBtn.addEventListener('click', () => navigateIllust(-1));
nextBtn.addEventListener('click', () => navigateIllust(1));
bookmarkBtn.addEventListener('click', toggleBookmark);
downloadOriginalBtn.addEventListener('click', handleDownloadOriginal); // New
searchIqdbBtn.addEventListener('click', handleSearchIqdb); // New
infoToggleBtn.addEventListener('click', (e) => {
    e.stopPropagation(); const currentIllust = illustList[currentIllustListIndex];
    if (currentIllust) {
        if (isInfoPanelVisible()) hideInfoPanel();
        else {
            (currentIllust.detail_info_fetched ? Promise.resolve() : fetchAndUpdateDetailedInfo(currentIllust))
            .then(() => populateAndShowInfoPanel(currentIllust))
            .catch(err => { console.error("Error before populating panel:", err); populateAndShowInfoPanel(currentIllust);});
        }
    }
});
//document.addEventListener('click', (e) => { if (isInfoPanelVisible() && !illustInfoPanelEl.contains(e.target) && e.target !== infoToggleBtn && !infoToggleBtn.contains(e.target)) hideInfoPanel(); });
document.addEventListener('keydown', handleHotkeys);

modeToggleBtn.addEventListener('click', () => {
    if (isLoadingIllustList) return; // Не переключаем во время загрузки

    if (currentViewMode === 'new_illust') {
        currentViewMode = 'user_bookmarks';
        currentOffsetForBookmarks = 0; // Сбрасываем offset для закладок
    } else {
        currentViewMode = 'new_illust';
        currentPixivApiPageForList = 1; // Сбрасываем страницу для новых иллюстраций
    }
    updateModeToggleUI();
    illustList = []; // Очищаем текущий список
    currentIllustListIndex = -1;
    renderThumbnails(); // Очищаем миниатюры
    initUI(); // Сбрасываем основной UI
    fetchIllustListFromBackend(); // Запускаем загрузку для нового режима
});


// Navigation and Actions
async function navigateIllust(direction) { // direction: -1 for prev, 1 for next
    if (hotkeyCooldown) return;
    setHotkeyCooldown();

    if (currentIllustListIndex < 0) { // Если ничего не выбрано
        if (direction === 1 && illustList.length > 0) { // Пытаемся перейти к первой при "вперед"
            currentIllustListIndex = 0;
            await displayCurrentIllustAndPage();
        }
        return; // Для "назад" ничего не делаем, если не выбрано
    }

    let currentIllust = illustList[currentIllustListIndex];
    if (!currentIllust) return; // На всякий случай

    if (direction === 1) { // Вперед
        if (currentIllust.pages_data_loading_status === 'loaded' && currentIllust.current_page_in_illust < currentIllust.pages_data.length - 1) {
            currentIllust.current_page_in_illust++;
            await displayCurrentIllustAndPage();
        } else if (currentIllustListIndex < illustList.length - 1) { // Следующая иллюстрация в списке
            currentIllustListIndex++;
            if (illustList[currentIllustListIndex]) { // Проверяем, что следующая иллюстрация существует
                illustList[currentIllustListIndex].current_page_in_illust = 0;
                await displayCurrentIllustAndPage();
            }
        } else if (!isLoadingIllustList) { // Конец списка, пытаемся загрузить еще
            if (currentViewMode === 'new_illust') {
                currentPixivApiPageForList++;
                imageInfoTextEl.textContent = `Загрузка следующей страницы новых иллюстраций...`;
            } else { // user_bookmarks
                currentOffsetForBookmarks += BOOKMARKS_PAGE_LIMIT;
                imageInfoTextEl.textContent = `Загрузка следующих закладок...`;
            }
            imageInfoTextEl.classList.add('loading-text');
            await fetchIllustListFromBackend(); // Загрузит следующую порцию
            // После загрузки, если появились новые элементы, пользователь сможет перейти к ним.
            // Если нет, сообщение об этом будет в fetchIllustListFromBackend.
        }
    } else if (direction === -1) { // Назад
        if (currentIllust.pages_data_loading_status === 'loaded' && currentIllust.current_page_in_illust > 0) {
            currentIllust.current_page_in_illust--;
            await displayCurrentIllustAndPage();
        } else if (currentIllustListIndex > 0) { // Предыдущая иллюстрация в списке
            currentIllustListIndex--;
            currentIllust = illustList[currentIllustListIndex]; // Обновляем currentIllust
            if (currentIllust) { // Проверяем, что предыдущая иллюстрация существует
                 // Устанавливаем на последнюю страницу предыдущей иллюстрации
                currentIllust.current_page_in_illust = (currentIllust.pages_data_loading_status === 'loaded' && currentIllust.pages_data.length > 0) 
                                                       ? currentIllust.pages_data.length - 1 
                                                       : 0;
                await displayCurrentIllustAndPage();
            }
        }
        // Если это первая иллюстрация и первая страница, ничего не делаем
    }
}
async function toggleBookmark() {
    if (hotkeyCooldown) return; setHotkeyCooldown();
    if (currentIllustListIndex < 0 || !illustList[currentIllustListIndex] || !globalCsrfToken) return;
    
    const illust = illustList[currentIllustListIndex];
    const action = illust.is_bookmarked ? 'delete' : 'add';

    // Логика предварительного запроса bookmark_id, если его нет и действие 'delete'
    if (action === 'delete' && !illust.bookmark_id && !illust.detail_info_fetched && !illust.detail_info_fetched_pending) {
        console.log(`Bookmark ID missing for delete on ${illust.id}, fetching details first...`);
        imageInfoTextEl.textContent = `Обновление данных для удаления из закладок...`;
        imageInfoTextEl.classList.add('loading-text');
        bookmarkBtn.disabled = true;
        
        await fetchAndUpdateDetailedInfo(illust); // Ждем получения деталей
        
        imageInfoTextEl.classList.remove('loading-text');
        if (illustList[currentIllustListIndex]?.id === illust.id) {
             imageInfoTextEl.innerHTML = `<b>${illust.title}</b> (ID: ${illust.id}) <a href="https://www.pixiv.net/artworks/${illust.id}" target="_blank">[P]</a>`;
        }
    }

    if (action === 'delete' && !illust.bookmark_id) {
        alert(`Не удалось получить ID закладки для иллюстрации ${illust.id} для удаления. Возможно, она не в закладках, или информация не успела обновиться. Попробуйте еще раз или обновите информацию об иллюстрации (кнопка 'i').`);
        bookmarkBtn.disabled = false;
        return;
    }

    bookmarkBtn.disabled = true;

    const payload = {
        illust_id: illust.id, // illust_id все еще нужен для Referer и логов
        action: action,
        csrf_token: globalCsrfToken
    };
    if (action === 'delete') {
        payload.bookmark_id = illust.bookmark_id;
    }

    try {
        const resp = await fetch('/api/bookmark', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload) 
        });
        const res = await resp.json();
        
        if (resp.ok && res.success) { 
            illust.is_bookmarked = (action === 'add');
            
            if (action === 'add') {
                if (res.last_bookmark_id) {
                    illust.bookmark_id = res.last_bookmark_id;
                    console.log(`Bookmark added for ${illust.id}, new bookmark_id: ${illust.bookmark_id}`);
                } else if (res.already_bookmarked) {
                    // Если уже была в закладках, но у нас не было bookmark_id, нужно его запросить
                    if (!illust.bookmark_id) {
                        console.log(`Already bookmarked (${illust.id}), but bookmark_id unknown. Fetching details.`);
                        // Устанавливаем is_bookmarked, чтобы кнопка правильно отображалась
                        illust.is_bookmarked = true; 
                        // Сбрасываем detail_info_fetched, чтобы следующий displayCurrentIllustAndPage инициировал загрузку
                        illust.detail_info_fetched = false; 
                    }
                } else {
                    console.warn(`Bookmark added for ${illust.id}, but no last_bookmark_id in response. Will need to fetch details later if delete is attempted.`);
                    illust.bookmark_id = null; // Явно сбрасываем, если не пришел
                }
            } else { // action === 'delete'
                illust.bookmark_id = null; // Успешно удалено
                console.log(`Bookmark removed for ${illust.id}.`);
            }
            
            // Статус is_bookmarked теперь точно актуален.
            // Флаг detail_info_fetched можно считать true в части is_bookmarked и bookmark_id.
            // Но теги и автор могли не обновляться.
            // Если res.already_bookmarked и не было bookmark_id, то detail_info_fetched сброшен для перезагрузки.
            if (!(res.already_bookmarked && !illust.bookmark_id)) { // Не меняем, если запланирована перезагрузка
                 illust.detail_info_fetched = true; 
            }


            triggerBookmarkAnimation(action === 'add');
        } else {
             alert(`Ошибка закладки для ${illust.id}: ${res.error || resp.statusText || 'Неизвестная ошибка'}`);
        }
    } catch (e) { 
        alert(`Сеть (закладка для ${illust.id}): ${e.message}`); 
    } finally { 
        if (illustList[currentIllustListIndex]?.id === illust.id) {
            // Если detail_info_fetched был сброшен (например, already_bookmarked и не было ID),
            // displayCurrentIllustAndPage должен инициировать fetchAndUpdateDetailedInfo.
            await displayCurrentIllustAndPage(); 
        } else {
             bookmarkBtn.disabled = false; 
        }
    }
}

function triggerBookmarkAnimation(isAdding) {
    if (!bookmarkAnimationOverlayEl || !bookmarkAnimationIconEl) return;

    // Ensure previous animations are cleared
    bookmarkAnimationIconEl.classList.remove('animate-add', 'animate-remove');
    // Force reflow to restart animation if classes are re-added quickly
    void bookmarkAnimationIconEl.offsetWidth; 

    const heartPath = bookmarkAnimationIconEl.querySelector('.heart-path');

    if (isAdding) {
        if (heartPath) heartPath.setAttribute('d', "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"); // Filled heart
        bookmarkAnimationIconEl.classList.add('animate-add');
    } else {
            // Simple 'broken' effect or just a faded out heart. Using same filled heart, animation makes it 'disappear'.
            // For a true broken heart, you'd change the path 'd' attribute here.
        if (heartPath) heartPath.setAttribute('d', "M12.022 5.662l-1.063-1.06a5.503 5.503 0 00-7.782 7.782l1.063 1.06L12 21.23l7.76-7.788 1.063-1.06a5.503 5.503 0 000-7.782A5.508 5.508 0 0017.5 3.128l-1.26 1.26m-4.218 1.274L12 5.67M9.922 14.142l-1.5-1.5M14.078 14.142l1.5-1.5m-4.273-3.045L8.25 9.542m7.5 1.555l1.555-1.555"); // Example broken heart
        bookmarkAnimationIconEl.classList.add('animate-remove');
    }

    bookmarkAnimationOverlayEl.classList.remove('hidden');

    // Use a single event listener for animation end
    const onAnimationEnd = () => {
        bookmarkAnimationOverlayEl.classList.add('hidden');
        bookmarkAnimationIconEl.classList.remove('animate-add', 'animate-remove');
        bookmarkAnimationIconEl.removeEventListener('animationend', onAnimationEnd);
    };
    bookmarkAnimationIconEl.addEventListener('animationend', onAnimationEnd);
}

function handleOpenOriginal() { if (hotkeyCooldown) return; setHotkeyCooldown(); if (currentIllustListIndex < 0 || !illustList[currentIllustListIndex] || openOriginalBtn.classList.contains('hidden')) return; openOriginalBtn.click(); }
function setHotkeyCooldown() { hotkeyCooldown = true; setTimeout(() => { hotkeyCooldown = false; }, HOTKEY_COOLDOWN_MS); }

function handleHotkeys(event) {
    if (event.ctrlKey || event.metaKey || event.altKey) return; // Ignore if modifiers are pressed (except for specific combinations if needed later)
    const keyActionMap = { 
        "ArrowLeft": () => navigateIllust(-1), 
        "ArrowRight": () => navigateIllust(1), 
        "f": toggleBookmark, 
        "F": toggleBookmark, 
        "а": toggleBookmark, 
        "А": toggleBookmark, 
        "o": handleOpenOriginal, 
        "O": handleOpenOriginal, 
        "щ": handleOpenOriginal, 
        "Щ": handleOpenOriginal,
        "d": handleDownloadOriginal, // New
        "D": handleDownloadOriginal,
        "в": handleDownloadOriginal, // Cyrillic 'v' for download
        "В": handleDownloadOriginal,
        "q": handleSearchIqdb,       // New
        "Q": handleSearchIqdb,
        "й": handleSearchIqdb,       // Cyrillic 'q' (й)
        "Й": handleSearchIqdb,
        "i": () => infoToggleBtn.click(), 
        "ш": () => infoToggleBtn.click(),
        "Ш": () => infoToggleBtn.click(),
        "I": () => infoToggleBtn.click() };
            
    // Prevent default browser actions for keys we handle (e.g. arrows scrolling page)
    // if text input is not focused
    const activeElement = document.activeElement;
    const isInputFocused = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.isContentEditable);
    if (!isInputFocused && keyActionMap[event.key]) { event.preventDefault(); keyActionMap[event.key](); }
}
function handleDownloadOriginal() {
    if (hotkeyCooldown) return; setHotkeyCooldown();
    const currentIllust = illustList[currentIllustListIndex];
    if (!currentIllust || downloadOriginalBtn.classList.contains('hidden')) return;
    const pageIdx = currentIllust.current_page_in_illust;
    const originalUrl = currentIllust.pages_data?.[pageIdx]?.url_original;
    if (originalUrl) {
        const downloadUrl = `/api/image_proxy?image_url=${encodeURIComponent(originalUrl)}&illust_id=${encodeURIComponent(currentIllust.id)}&download=true`;
        const a = document.createElement('a');
        a.href = downloadUrl;
        // Filename is handled by Content-Disposition from server, but can be set here as a fallback
        // a.download = originalUrl.substring(originalUrl.lastIndexOf('/') + 1); 
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }
}
function handleSearchIqdb() {
    if (hotkeyCooldown) return; setHotkeyCooldown();
    const currentIllust = illustList[currentIllustListIndex];
    if (!currentIllust || searchIqdbBtn.classList.contains('hidden')) return;
    const pageIdx = currentIllust.current_page_in_illust;
    const masterUrl = currentIllust.pages_data?.[pageIdx]?.url_master || currentIllust.pages_data?.[pageIdx]?.url_original; // Prefer master
    if (masterUrl) {
        const iqdbSearchUrl = `https://www.iqdb.org/?url=${encodeURIComponent(masterUrl)}`;
        window.open(iqdbSearchUrl, '_blank');
    }
}

// --- Sidebar Resizing Logic ---
function initSidebarResizer() {
    if (!sidebarResizerEl || !thumbnailsSidebarEl) return;

    sidebarResizerEl.addEventListener('mousedown', (e) => {
        e.preventDefault(); // Предотвращаем выделение текста при перетаскивании
        isResizingSidebar = true;
        sidebarResizerEl.classList.add('active');
        document.body.style.cursor = 'col-resize'; // Меняем курсор для всего документа
        document.body.style.userSelect = 'none'; // Отключаем выделение текста

        // Начальная позиция X и начальная ширина сайдбара
        const startX = e.clientX;
        const startWidth = thumbnailsSidebarEl.offsetWidth;

        const doDrag = (moveEvent) => {
            if (!isResizingSidebar) return;
            const currentX = moveEvent.clientX;
            const diffX = currentX - startX;
            let newWidth = startWidth + diffX;

            // Ограничения по ширине
            newWidth = Math.max(MIN_SIDEBAR_WIDTH, Math.min(newWidth, MAX_SIDEBAR_WIDTH));
            
            thumbnailsSidebarEl.style.width = `${newWidth}px`;
            // imageViewerContainerEl.style.marginLeft = `${newWidth + sidebarResizerEl.offsetWidth}px`; // Если сайдбар fixed
            // Если не fixed, flex сам разберется.

            // Динамическое обновление размера превью (если нужно)
            // Можно просто перерендерить миниатюры или обновить стили существующих
            // Но CSS с width: 100% и height: auto для img должен справиться сам
        };

        const stopDrag = () => {
            if (!isResizingSidebar) return;
            isResizingSidebar = false;
            sidebarResizerEl.classList.remove('active');
            document.body.style.cursor = 'default';
            document.body.style.userSelect = '';

            document.removeEventListener('mousemove', doDrag);
            document.removeEventListener('mouseup', stopDrag);
            
            // Сохранить новую ширину в localStorage, если нужно
            localStorage.setItem('sidebarWidth', thumbnailsSidebarEl.style.width);

            // После изменения размера может потребоваться пересчитать/перерисовать что-то еще
            // Например, если элементы в сайдбаре зависят от его ширины сложным образом
        };

        document.addEventListener('mousemove', doDrag);
        document.addEventListener('mouseup', stopDrag);
    });

    // Восстановление ширины из localStorage при загрузке
    const savedWidth = localStorage.getItem('sidebarWidth');
    if (savedWidth) {
        const numericWidth = parseInt(savedWidth, 10);
        if (numericWidth >= MIN_SIDEBAR_WIDTH && numericWidth <= MAX_SIDEBAR_WIDTH) {
            thumbnailsSidebarEl.style.width = savedWidth;
        }
    }
}

// Вызов инициализации ресайзера
document.addEventListener('DOMContentLoaded', () => {
    // ... (ваш текущий код в DOMContentLoaded) ...
    initSidebarResizer(); 
});