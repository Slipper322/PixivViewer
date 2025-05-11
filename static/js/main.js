// --- DOM Elements ---
// Элементы для отображения основного изображения и индикаторов
const currentImageEl = document.getElementById('currentImage');
const imageLoaderSpinnerEl = document.getElementById('imageLoaderSpinner');

// Элементы управления и информации
const thumbnailsSidebarEl = document.getElementById('thumbnailsSidebar');
const imageInfoTextEl = document.getElementById('imageInfoText');
const pageInfoEl = document.getElementById('pageInfo');

// Кнопки управления просмотром и действиями
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const bookmarkBtn = document.getElementById('bookmarkBtn');
const openOriginalBtn = document.getElementById('openOriginalBtn');
const downloadOriginalBtn = document.getElementById('downloadOriginalBtn');
const searchIqdbBtn = document.getElementById('searchIqdbBtn');
const infoToggleBtn = document.getElementById('infoToggleBtn');
const modeToggleBtn = document.getElementById('modeToggleBtn');

// Элементы информационной панели
const illustInfoPanelEl = document.getElementById('illustInfoPanel');
const panelIllustTitleEl = document.getElementById('panelIllustTitle');
const panelIllustAuthorEl = document.getElementById('panelIllustAuthor');
const panelIllustResolutionEl = document.getElementById('panelIllustResolution');
const panelIllustPixivLinkEl = document.getElementById('panelIllustPixivLink');
const panelIllustTagsEl = document.getElementById('panelIllustTags');

// Элемент для управления размером сайдбара
const sidebarResizerEl = document.getElementById('sidebarResizer');

// Элементы для анимации закладки
const bookmarkAnimationOverlayEl = document.getElementById('bookmarkAnimationOverlay');
const bookmarkAnimationIconEl = document.getElementById('bookmarkAnimationIcon');


// --- Application State ---
const PRELOAD_COUNT = 2; // Количество следующих иллюстраций для предзагрузки данных

let illustList = []; // Основной массив, хранящий объекты иллюстраций и их состояние
let currentIllustListIndex = -1; // Индекс текущей отображаемой иллюстрации в illustList

let currentPixivApiPageForList = 1; // Номер страницы для API Pixiv при загрузке "новых иллюстраций"
let currentOffsetForBookmarks = 0;  // Смещение для API Pixiv при загрузке "закладок пользователя"
const BOOKMARKS_PAGE_LIMIT = 48;    // Количество закладок, запрашиваемое за раз (должно совпадать с BOOKMARKS_API_LIMIT в app.py)

let isLoadingIllustList = false; // Флаг, идет ли в данный момент загрузка списка иллюстраций
let globalCsrfToken = '';      // Глобальный CSRF-токен, полученный от бэкенда

let currentViewMode = 'new_illust'; // Текущий режим просмотра: 'new_illust' или 'user_bookmarks'

// Состояние для горячих клавиш и изменения размера сайдбара
let hotkeyCooldown = false;
const HOTKEY_COOLDOWN_MS = 200; // Задержка между срабатываниями горячих клавиш
const MIN_SIDEBAR_WIDTH = 150;  // Минимальная ширина сайдбара в px
const MAX_SIDEBAR_WIDTH = 600;  // Максимальная ширина сайдбара в px
let isResizingSidebar = false;  // Флаг, изменяется ли размер сайдбара в данный момент


// --- UI Initialization and Update Functions ---

/**
 * Инициализирует или сбрасывает UI к начальному состоянию.
 * Вызывается при первой загрузке и при смене режима просмотра.
 */
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
    thumbnailsSidebarEl.innerHTML = ''; // Очистка миниатюр
    hideImageSpinner();
    hideInfoPanel();
    updateModeToggleUI(); // Обновление UI кнопки переключения режимов
}

/**
 * Обновляет внешний вид кнопки переключения режимов просмотра (иконка и title).
 */
function updateModeToggleUI() {
    const newIllustIcon = modeToggleBtn.querySelector('.mode-new-illust');
    const userBookmarksIcon = modeToggleBtn.querySelector('.mode-user-bookmarks');

    if (currentViewMode === 'new_illust') {
        if (newIllustIcon) newIllustIcon.classList.remove('hidden');
        if (userBookmarksIcon) userBookmarksIcon.classList.add('hidden');
        modeToggleBtn.title = "Переключить на Мои Закладки";
    } else { // user_bookmarks
        if (newIllustIcon) newIllustIcon.classList.add('hidden');
        if (userBookmarksIcon) userBookmarksIcon.classList.remove('hidden');
        modeToggleBtn.title = "Переключить на Новое от подписок";
    }
}

/** Показывает спиннер загрузки для основного изображения. */
function showImageSpinner() {
    if (imageLoaderSpinnerEl) imageLoaderSpinnerEl.style.display = 'block';
    currentImageEl.style.opacity = '0.3';
}

/** Скрывает спиннер загрузки для основного изображения. */
function hideImageSpinner() {
    if (imageLoaderSpinnerEl) imageLoaderSpinnerEl.style.display = 'none';
    currentImageEl.style.opacity = '1';
}

/**
 * Обновляет состояние и вид кнопки закладки в зависимости от статуса текущей иллюстрации.
 * @param {object} illustDataItem - Объект текущей иллюстрации из illustList.
 */
function updateBookmarkButtonUI(illustDataItem) {
    if (!illustDataItem) { // Если нет данных об иллюстрации
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

/**
 * Обрабатывает массив "сырых" данных об иллюстрациях, полученных от бэкенда,
 * и преобразует его в формат, используемый на клиенте.
 * @param {Array<object>} rawIllusts - Массив объектов иллюстраций от бэкенда.
 * @returns {Array<object>} Массив обработанных объектов иллюстраций.
 */
function processRawIllustList(rawIllusts) {
    return rawIllusts.map(meta => ({
        id: meta.id,
        title: meta.title,
        preview_url_p0: meta.preview_url_p0,
        page_count: parseInt(meta.page_count, 10) || 1,
        is_bookmarked: meta.is_bookmarked,
        bookmark_id: meta.bookmark_id || null,
        width: meta.width,
        height: meta.height,
        pages_data: [], // Данные о страницах будут загружены отдельно
        current_page_in_illust: 0, // Текущая отображаемая страница (для многостраничных)
        pages_data_loading_status: 'idle', // Статус загрузки данных о страницах ('idle', 'loading', 'loaded', 'error')
        // Флаги для отслеживания загрузки детальной информации (автор, теги, точный статус закладки)
        detail_info_fetched: meta.bookmark_id && meta.is_bookmarked ? true : false, // Если ID закладки известен, считаем часть инфо загруженной
        detail_info_fetched_pending: false,
        // Поля для детальной информации, которые могут быть загружены позже
        author_name: meta.author_name || null, 
        author_id: meta.author_id || null,
        tags: meta.tags || []
    }));
}


// --- Thumbnail Management ---

/**
 * Рендерит миниатюры в сайдбаре на основе текущего списка illustList.
 */
function renderThumbnails() {
    thumbnailsSidebarEl.innerHTML = ''; // Очищаем предыдущие миниатюры
    illustList.forEach((illust, index) => {
        const thumbItem = document.createElement('div');
        thumbItem.className = 'thumbnail-item';
        thumbItem.dataset.index = index; // Сохраняем индекс для быстрого доступа
        thumbItem.dataset.id = illust.id;    // Сохраняем ID иллюстрации

        const img = document.createElement('img');
        if (illust.preview_url_p0) {
            // Проксируем URL превью через бэкенд для добавления Referer
            const proxyThumbUrl = `/api/image_proxy?image_url=${encodeURIComponent(illust.preview_url_p0)}&illust_id=${encodeURIComponent(illust.id)}`;
            img.src = proxyThumbUrl;
            img.alt = illust.title.substring(0, 30); // Обрезаем длинные названия для alt
            img.title = illust.title;
        } else {
            img.alt = "Нет превью";
        }
        thumbItem.appendChild(img);

        // Контейнер для индикатора загрузки/ошибки на миниатюре
        const progressIndicatorContainer = document.createElement('div');
        progressIndicatorContainer.className = 'thumb-progress-indicator';
        progressIndicatorContainer.innerHTML = `<div class="circular-loader"></div><div class="error-icon hidden">!</div>`;
        thumbItem.appendChild(progressIndicatorContainer);
        
        // Элемент для отображения количества страниц на многостраничных иллюстрациях
        const pageCounterEl = document.createElement('div');
        pageCounterEl.className = 'thumb-page-counter';
        thumbItem.appendChild(pageCounterEl);

        // Обработчик клика по миниатюре
        thumbItem.addEventListener('click', async () => {
            // Если кликнули по уже активной и загруженной миниатюре, просто прокручиваем к ней
            if (currentIllustListIndex === index && illustList[currentIllustListIndex]?.pages_data_loading_status === 'loaded') {
                thumbItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                return;
            }
            currentIllustListIndex = index; // Устанавливаем новую текущую иллюстрацию
            await displayCurrentIllustAndPage(); // Отображаем ее
        });
        thumbnailsSidebarEl.appendChild(thumbItem);
        updateThumbnailUI(illust); // Обновляем UI для конкретной миниатюры (индикаторы)
    });
    highlightActiveThumbnail(); // Выделяем активную миниатюру
}

/**
 * Обновляет UI конкретной миниатюры (индикатор загрузки/ошибки, счетчик страниц).
 * @param {object} illustDataItem - Объект иллюстрации.
 */
function updateThumbnailUI(illustDataItem) {
    const thumbItem = thumbnailsSidebarEl.querySelector(`.thumbnail-item[data-id="${illustDataItem.id}"]`);
    if (!thumbItem) return;

    const progressContainer = thumbItem.querySelector('.thumb-progress-indicator');
    const loader = progressContainer.querySelector('.circular-loader');
    const errorIcon = progressContainer.querySelector('.error-icon');
    const pageCounter = thumbItem.querySelector('.thumb-page-counter');

    // Сбрасываем все индикаторы
    loader.style.display = 'none';
    errorIcon.style.display = 'none';
    progressContainer.style.display = 'none';

    // Показываем нужный индикатор в зависимости от статуса загрузки страниц
    if (illustDataItem.pages_data_loading_status === 'loading') {
        progressContainer.style.display = 'flex';
        loader.style.display = 'block';
    } else if (illustDataItem.pages_data_loading_status === 'error') {
        progressContainer.style.display = 'flex';
        errorIcon.style.display = 'block';
    }

    // Отображение счетчика страниц для многостраничных иллюстраций
    if (illustDataItem.page_count > 1) {
        pageCounter.style.display = 'block';
        pageCounter.textContent = `${illustDataItem.page_count}`; // Показываем общее количество страниц
    } else {
        pageCounter.style.display = 'none';
    }
}

/**
 * Выделяет текущую активную миниатюру в сайдбаре и прокручивает к ней.
 */
function highlightActiveThumbnail() {
    thumbnailsSidebarEl.querySelectorAll('.thumbnail-item').forEach(thumb => {
        const isActive = thumb.dataset.id === (illustList[currentIllustListIndex]?.id);
        thumb.classList.toggle('active', isActive);
        if (isActive) {
            // Прокрутка к активной миниатюре, чтобы она была в центре видимой области сайдбара
            thumb.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
}


// --- Data Fetching ---

/**
 * Загружает список иллюстраций с бэкенда в зависимости от текущего режима просмотра.
 * Обрабатывает пагинацию и обновление CSRF-токена.
 */
async function fetchIllustListFromBackend() {
    if (isLoadingIllustList) return; // Предотвращаем параллельные запросы
    isLoadingIllustList = true;
    
    let isFirstLoadForCurrentMode = false;
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
    imageInfoTextEl.classList.add('loading-text'); // Показываем анимацию загрузки в тексте
    console.log(`Fetching data for mode: ${currentViewMode}, URL: ${apiUrl}`);

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) { // Обработка HTTP ошибок от бэкенда
            const errorData = await response.json().catch(() => ({ error: `HTTP error ${response.status}` }));
            throw new Error(errorData.error || errorData.error_message || `Ошибка HTTP: ${response.status}`);
        }
        const data = await response.json();

        // Обновление CSRF-токена (только для 'new_illust' и первой страницы)
        if (currentViewMode === 'new_illust' && currentPixivApiPageForList === 1 && data.csrf_token) {
            if (!globalCsrfToken || globalCsrfToken !== data.csrf_token) {
                globalCsrfToken = data.csrf_token;
                console.log("CSRF token updated/received:", globalCsrfToken ? globalCsrfToken.substring(0,10) + "..." : "null");
            }
        }

        if (data.images && data.images.length > 0) {
            const newIllusts = processRawIllustList(data.images); // Обрабатываем полученные данные

            if (isFirstLoadForCurrentMode) { // Если это первая загрузка для текущего режима
                illustList = newIllusts;
                currentIllustListIndex = illustList.length > 0 ? 0 : -1; // Выбираем первую иллюстрацию, если список не пуст
            } else { // Если догружаем существующий список
                illustList = illustList.concat(newIllusts);
            }
            
            renderThumbnails(); // Обновляем миниатюры

            if (currentIllustListIndex !== -1 && isFirstLoadForCurrentMode) {
                await displayCurrentIllustAndPage(); // Отображаем первую иллюстрацию
            } else if (illustList.length === 0 && isFirstLoadForCurrentMode) {
                imageInfoTextEl.textContent = 'Иллюстрации не найдены.';
                pageInfoEl.textContent = '';
                currentImageEl.src = ""; currentImageEl.alt = "Нет иллюстраций";
            }
        } else { // Если иллюстраций не найдено
            if (!isFirstLoadForCurrentMode) { // Догружали, но новых нет
                imageInfoTextEl.textContent = (currentViewMode === 'new_illust') ? 'Больше новых иллюстраций не найдено.' : 'Больше закладок не найдено.';
            } else { // Первая загрузка, и ничего нет
                illustList = [];
                currentIllustListIndex = -1;
                imageInfoTextEl.textContent = 'Иллюстрации не найдены.';
                pageInfoEl.textContent = '';
                currentImageEl.src = ""; currentImageEl.alt = "Нет иллюстраций";
                renderThumbnails(); // Очищаем/обновляем сайдбар
            }
        }
    } catch (error) {
        console.error(`Ошибка при загрузке списка (${currentViewMode}):`, error);
        imageInfoTextEl.textContent = `Ошибка загрузки: ${error.message}.`;
    } finally {
        isLoadingIllustList = false;
        imageInfoTextEl.classList.remove('loading-text');
        // Дополнительная проверка на случай, если список пуст после всех операций
        if (illustList.length === 0 && !isLoadingIllustList && imageInfoTextEl.textContent.includes('Загрузка')) {
            imageInfoTextEl.textContent = 'Иллюстрации не найдены.';
        }
    }
}

/**
 * Загружает данные о страницах для конкретной иллюстрации (если она многостраничная).
 * @param {object} illustDataItem - Объект иллюстрации.
 */
async function fetchActualIllustPages(illustDataItem) {
    // Пропускаем, если данные уже загружаются, загружены, или нет ID
    if (!illustDataItem || !illustDataItem.id || illustDataItem.pages_data_loading_status === 'loading' || illustDataItem.pages_data_loading_status === 'loaded') return;
    
    illustDataItem.pages_data_loading_status = 'loading';
    updateThumbnailUI(illustDataItem); // Обновляем индикатор на миниатюре

    try {
        const response = await fetch(`/api/illust_pages/${illustDataItem.id}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: `HTTP error ${response.status}` }));
            throw new Error(errorData.error || `HTTP error ${response.status}`);
        }
        const data = await response.json();

        if (data.pages_data && data.pages_data.length > 0) {
            illustDataItem.pages_data = data.pages_data;
            illustDataItem.pages_data_loading_status = 'loaded';
        } else { // Если API вернуло пустой список страниц (например, для одностраничной иллюстрации или ошибки)
                 // Пытаемся использовать превью как единственную страницу, если есть
            if (illustDataItem.preview_url_p0 && illustDataItem.page_count === 1) {
                illustDataItem.pages_data = [{ 
                    url_master: illustDataItem.preview_url_p0, 
                    url_original: illustDataItem.preview_url_p0, // Предполагаем, что превью - это и есть оригинал для одностраничных без /pages
                    width: illustDataItem.width, 
                    height: illustDataItem.height 
                }];
                illustDataItem.pages_data_loading_status = 'loaded';
            } else {
                illustDataItem.pages_data_loading_status = 'error'; // Не удалось получить страницы
                console.warn(`No page data and no suitable fallback for illust ID: ${illustDataItem.id}`);
            }
        }
    } catch (error) {
        console.error(`Ошибка загрузки данных страниц для ${illustDataItem.id}:`, error);
        illustDataItem.pages_data_loading_status = 'error';
    } finally {
        updateThumbnailUI(illustDataItem); // Обновляем индикатор на миниатюре после загрузки
    }
}

/**
 * Загружает детальную информацию об иллюстрации (статус закладки, ID закладки, автор, теги).
 * @param {object} illustDataItem - Объект иллюстрации.
 */
async function fetchAndUpdateDetailedInfo(illustDataItem) {
    if (!illustDataItem || !illustDataItem.id || illustDataItem.detail_info_fetched_pending) return;
    
    // Если основные данные (статус закладки, ID закладки, автор, теги) уже есть, можно пропустить
    // (условие detail_info_fetched проверяется в displayCurrentIllustAndPage перед вызовом)
    // if (illustDataItem.detail_info_fetched) return;

    illustDataItem.detail_info_fetched_pending = true;
    try {
        const response = await fetch(`/api/illust_details_and_bookmark_status/${illustDataItem.id}`);
        if (!response.ok) {
            console.warn(`Не удалось загрузить детали для ${illustDataItem.id}: ${response.status}`);
            illustDataItem.detail_info_fetched_pending = false; // Запрос завершен (неудачно)
            // Не меняем detail_info_fetched на false, чтобы не терять ранее загруженные частичные данные
            return;
        }
        const data = await response.json();
        if (data && !data.error) { // Убедимся, что нет ошибки в теле ответа
            if (typeof data.is_bookmarked === 'boolean') illustDataItem.is_bookmarked = data.is_bookmarked;
            
            // Обновляем bookmark_id только если он пришел (может быть null)
            if (data.bookmark_id !== undefined) illustDataItem.bookmark_id = data.bookmark_id;

            // Обновляем автора и теги, стараясь не затирать существующие данные, если новые неполные
            illustDataItem.author_name = data.user_name || illustDataItem.author_name || "N/A";
            illustDataItem.author_id = data.user_id || illustDataItem.author_id || null;
            illustDataItem.tags = (data.tags && data.tags.length > 0) ? data.tags : (illustDataItem.tags || []);
            
            illustDataItem.detail_info_fetched = true; // Помечаем, что детали успешно загружены/обновлены

            // Если иллюстрация все еще текущая, обновляем UI
            if (illustList[currentIllustListIndex]?.id === illustDataItem.id) {
                updateBookmarkButtonUI(illustDataItem);
                if (isInfoPanelVisible()) {
                    populateAndShowInfoPanel(illustDataItem);
                }
            }
        } else if (data && data.error) {
            console.warn(`Ошибка API при загрузке деталей для ${illustDataItem.id}: ${data.error}`);
        }
    } catch (error) {
        console.warn(`Сетевая ошибка при загрузке деталей для ${illustDataItem.id}:`, error);
    } finally {
        illustDataItem.detail_info_fetched_pending = false; // Запрос завершен
    }
}


// --- Main Display Logic ---

/**
 * Отображает текущую выбранную иллюстрацию и ее текущую страницу.
 * Управляет загрузкой данных о страницах и детальной информации, если необходимо.
 */
async function displayCurrentIllustAndPage() {
    if (currentIllustListIndex < 0 || currentIllustListIndex >= illustList.length) {
        initUI(); // Если индекс некорректен, сбрасываем UI
        return;
    }
    const currentIllust = illustList[currentIllustListIndex];
    highlightActiveThumbnail(); // Выделяем активную миниатюру
    imageInfoTextEl.classList.remove('loading-text');
    infoToggleBtn.classList.remove('hidden'); // Показываем кнопку информации

    // Шаг 1: Убедиться, что детальная информация (включая статус закладки и bookmark_id) загружена
    if (!currentIllust.detail_info_fetched && !currentIllust.detail_info_fetched_pending) {
        await fetchAndUpdateDetailedInfo(currentIllust);
    }
    // После этого is_bookmarked и bookmark_id должны быть актуальны (или null, если не в закладках)
    // Кнопка закладки обновится внутри fetchAndUpdateDetailedInfo или далее в этой функции.

    // Шаг 2: Проверка состояния загрузки данных о страницах иллюстрации
    if (currentIllust.pages_data_loading_status === 'loading') {
        // Если страницы еще грузятся, показываем информацию о загрузке
        imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a> (Загрузка страниц...)`;
        imageInfoTextEl.classList.add('loading-text');
        showImageSpinner();
        openOriginalBtn.classList.add('hidden');
        downloadOriginalBtn.classList.add('hidden');
        searchIqdbBtn.classList.add('hidden');
        updateBookmarkButtonUI(currentIllust); // Обновляем кнопку, т.к. is_bookmarked может быть уже известен
        return;
    }

    // Если данные о страницах еще не запрашивались или была ошибка, инициируем загрузку
    if (currentIllust.pages_data_loading_status === 'idle' || 
       (currentIllust.pages_data_loading_status === 'error' && currentIllust.page_count > 1)) { // Перезагружаем если ошибка и страниц > 1
        
        // Отображаем превью или сообщение о загрузке, пока грузятся основные данные страниц
        if (currentIllust.preview_url_p0) {
            currentImageEl.src = `/api/image_proxy?image_url=${encodeURIComponent(currentIllust.preview_url_p0)}&illust_id=${encodeURIComponent(currentIllust.id)}`;
            currentImageEl.alt = `Превью: ${currentIllust.title}`;
        } else {
            currentImageEl.src = ""; currentImageEl.alt = "Загрузка...";
        }
        imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a> (Ожидание данных страниц...)`;
        pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1}/${illustList.length}.`;
        openOriginalBtn.classList.add('hidden');
        downloadOriginalBtn.classList.add('hidden');
        searchIqdbBtn.classList.add('hidden');
        updateBookmarkButtonUI(currentIllust);

        if (currentIllust.pages_data_loading_status !== 'error' || currentIllust.page_count > 1) {
            await fetchActualIllustPages(currentIllust); // Загружаем данные о страницах
        }
        
        // После загрузки данных о страницах, нужно снова вызвать эту функцию, чтобы отобразить их
        // Проверяем, что статус изменился, чтобы избежать бесконечного цикла, если загрузка не удалась
        if (currentIllust.pages_data_loading_status !== 'loading') { // Дожидаемся окончания fetchActualIllustPages
            await displayCurrentIllustAndPage(); // Рекурсивный вызов для отображения загруженных данных
        }
        return;
    }

    // Шаг 3: Данные о страницах загружены (или была ошибка, но мы ее обработали)
    hideImageSpinner();
    imageInfoTextEl.classList.remove('loading-text');

    if (currentIllust.pages_data && currentIllust.pages_data.length > 0) {
        // Нормализуем индекс текущей страницы внутри иллюстрации
        const pageIdx = Math.max(0, Math.min(currentIllust.current_page_in_illust, currentIllust.pages_data.length - 1));
        currentIllust.current_page_in_illust = pageIdx;
        
        const currentPageData = currentIllust.pages_data[pageIdx];
        const imageUrlToDisplay = currentPageData.url_master || currentPageData.url_original; // Предпочитаем 'master' (regular)
        
        let finalImageUrl = "";
        if (imageUrlToDisplay) {
            finalImageUrl = `/api/image_proxy?image_url=${encodeURIComponent(imageUrlToDisplay)}&illust_id=${encodeURIComponent(currentIllust.id)}`;
        }

        currentImageEl.alt = currentIllust.title;
        if (currentImageEl.src !== window.location.origin + finalImageUrl && finalImageUrl) {
            showImageSpinner(); // Показываем спиннер, пока грузится новая картинка
            currentImageEl.src = finalImageUrl;
        } else if (!finalImageUrl) { // Если URL пустой (ошибка или нет данных)
            currentImageEl.src = "";
            currentImageEl.alt = "Ошибка загрузки изображения страницы";
            hideImageSpinner();
        } else { // URL не изменился, или картинка уже загружена из кэша
            hideImageSpinner();
        }

        imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a>`;
        pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1}/${illustList.length}. Стр. ${pageIdx + 1}/${currentIllust.pages_data.length}.`;
        
        // Управляем видимостью кнопок "Открыть оригинал", "Скачать" и "IQDB"
        const hasOriginal = !!currentPageData.url_original;
        const hasMaster = !!currentPageData.url_master;
        openOriginalBtn.classList.toggle('hidden', !hasOriginal);
        downloadOriginalBtn.classList.toggle('hidden', !hasOriginal); // Скачиваем обычно оригинал
        searchIqdbBtn.classList.toggle('hidden', !(hasMaster || hasOriginal)); // Для IQDB используем master или original

        if(hasOriginal) {
            openOriginalBtn.onclick = () => window.open(`/api/image_proxy?image_url=${encodeURIComponent(currentPageData.url_original)}&illust_id=${encodeURIComponent(currentIllust.id)}`, '_blank');
        }
    } else { // Если нет данных о страницах (например, после ошибки загрузки)
        currentImageEl.src = "";
        currentImageEl.alt = "Ошибка загрузки страниц иллюстрации";
        imageInfoTextEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[P]</a> (Ошибка загрузки страниц)`;
        pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1}/${illustList.length}.`;
        openOriginalBtn.classList.add('hidden');
        downloadOriginalBtn.classList.add('hidden');
        searchIqdbBtn.classList.add('hidden');
        hideImageSpinner();
    }
    
    updateBookmarkButtonUI(currentIllust); // Обновляем кнопку закладки
    if (isInfoPanelVisible()) { // Если панель информации открыта, обновляем ее содержимое
        populateAndShowInfoPanel(currentIllust);
    }
    if (currentIllust.pages_data_loading_status === 'loaded') {
        preloadNextIllusts(); // Запускаем предзагрузку следующих иллюстраций
    }
    updateThumbnailUI(currentIllust); // Обновляем UI миниатюры (например, счетчик страниц)
}


// --- Preloading ---

/**
 * Инициирует предзагрузку данных (информации о страницах и первого изображения)
 * для следующих PRELOAD_COUNT иллюстраций в списке.
 */
async function preloadNextIllusts() {
    if (isLoadingIllustList) return; // Не предзагружаем, если основной список еще грузится
    let preloadedCount = 0;
    for (let i = 1; i <= PRELOAD_COUNT; i++) {
        const nextIdx = currentIllustListIndex + i;
        if (nextIdx < illustList.length) {
            const illustToPreload = illustList[nextIdx];
            // Предзагружаем только если данные страниц еще не запрашивались
            if (illustToPreload && illustToPreload.pages_data_loading_status === 'idle') {
                console.log(`Preloading page data for illust ID: ${illustToPreload.id} (index ${nextIdx})`);
                fetchActualIllustPages(illustToPreload).then(() => {
                    // После загрузки данных о страницах, пытаемся предзагрузить само изображение (первую страницу)
                    if (illustToPreload.pages_data_loading_status === 'loaded' && illustToPreload.pages_data.length > 0) {
                        const firstPageData = illustToPreload.pages_data[0];
                        const imageUrlToPreload = firstPageData.url_master || firstPageData.url_original;
                        if (imageUrlToPreload) {
                            const proxyPreloadUrl = `/api/image_proxy?image_url=${encodeURIComponent(imageUrlToPreload)}&illust_id=${encodeURIComponent(illustToPreload.id)}`;
                            const tempImg = new Image(); // Создаем объект Image для кэширования браузером
                            tempImg.src = proxyPreloadUrl;
                            console.log(`Preloading image (p0) for illust ID: ${illustToPreload.id}`);
                        }
                    }
                }).catch(error => {
                    console.warn(`Error during preloading page data for ${illustToPreload.id}:`, error);
                });
                preloadedCount++;
            }
        } else {
            break; // Выходим из цикла, если достигли конца списка
        }
    }
    if (preloadedCount > 0) {
        console.log(`Initiated preload for ${preloadedCount} illust(s).`);
    }
}


// --- Information Panel Logic ---

/** Проверяет, видима ли информационная панель. */
function isInfoPanelVisible() {
    return illustInfoPanelEl.classList.contains('visible');
}

/**
 * Заполняет информационную панель данными о текущей иллюстрации и отображает ее.
 * @param {object} illustDataItem - Объект текущей иллюстрации.
 */
function populateAndShowInfoPanel(illustDataItem) {
    if (!illustDataItem) return;

    panelIllustTitleEl.textContent = illustDataItem.title;
    panelIllustAuthorEl.textContent = illustDataItem.author_name || "N/A";
    panelIllustAuthorEl.href = illustDataItem.author_id ? `https://www.pixiv.net/users/${illustDataItem.author_id}` : "javascript:void(0);";
    
    let resolutionText = "N/A";
    if (illustDataItem.pages_data && illustDataItem.pages_data.length > 0) {
        const firstPage = illustDataItem.pages_data[0]; // Разрешение обычно берется с первой страницы
        resolutionText = (firstPage.width && firstPage.height) ? `${firstPage.width}x${firstPage.height}` : "N/A";
    } else if (illustDataItem.width && illustDataItem.height) { // Если нет данных о страницах, используем общие размеры (могут быть от превью)
        resolutionText = `${illustDataItem.width}x${illustDataItem.height} (превью)`;
    }
    panelIllustResolutionEl.textContent = resolutionText;
    panelIllustResolutionEl.classList.toggle('copyable', resolutionText !== "N/A"); // Делаем копируемым, если есть значение
    
    panelIllustPixivLinkEl.href = `https://www.pixiv.net/artworks/${illustDataItem.id}`;
    panelIllustPixivLinkEl.textContent = `artworks/${illustDataItem.id}`;
    panelIllustPixivLinkEl.classList.add('copyable');

    // Заполнение тегов
    panelIllustTagsEl.innerHTML = '';
    if (illustDataItem.tags && illustDataItem.tags.length > 0) {
        illustDataItem.tags.forEach(tag => {
            const tagElement = document.createElement('span');
            tagElement.className = 'tag';
            tagElement.textContent = tag;
            panelIllustTagsEl.appendChild(tagElement);
        });
    } else {
        panelIllustTagsEl.textContent = "Нет тегов";
    }

    // Позиционирование панели относительно кнопки "info"
    const btnRect = infoToggleBtn.getBoundingClientRect();
    illustInfoPanelEl.style.bottom = (window.innerHeight - btnRect.top) + 'px';
    illustInfoPanelEl.style.right = (window.innerWidth - btnRect.right) + 'px';
    
    // Анимация появления
    illustInfoPanelEl.style.transform = 'translateY(10px) scale(0.95)'; // Начальное состояние для анимации
    illustInfoPanelEl.classList.remove('hidden');
    requestAnimationFrame(() => { // Двойной requestAnimationFrame для корректного старта CSS-перехода
        requestAnimationFrame(() => {
            illustInfoPanelEl.classList.add('visible');
        });
    });
}

/** Скрывает информационную панель с анимацией. */
function hideInfoPanel() {
    illustInfoPanelEl.classList.remove('visible');
    // Скрываем элемент из DOM после завершения анимации, чтобы не мешал другим элементам
    setTimeout(() => {
        if (!isInfoPanelVisible()) { // Проверяем, не была ли панель снова открыта за это время
            illustInfoPanelEl.classList.add('hidden');
        }
    }, 200); // Время должно соответствовать длительности CSS-перехода
}

/**
 * Показывает визуальную обратную связь при копировании текста.
 * @param {HTMLElement} element - Элемент, для которого показывается обратная связь.
 * @param {string} [originalTitleText="Скопировать"] - Исходный title элемента.
 */
function showCopyFeedback(element, originalTitleText = "Скопировать") {
    element.classList.add('copied-feedback');
    const currentTitle = element.title;
    element.title = "Скопировано!";
    setTimeout(() => {
        element.classList.remove('copied-feedback');
        element.title = currentTitle || originalTitleText;
    }, 1500);
}


// --- Event Listeners ---

document.addEventListener('DOMContentLoaded', () => {
    initUI(); // Инициализация интерфейса
    fetchIllustListFromBackend(); // Начальная загрузка списка иллюстраций
    initSidebarResizer(); // Инициализация функционала изменения размера сайдбара

    // Обработчики кликов для копирования из информационной панели
    panelIllustResolutionEl.addEventListener('click', function() {
        if (this.textContent && this.textContent !== "N/A") {
            navigator.clipboard.writeText(this.textContent)
                .then(() => showCopyFeedback(this, "Копировать разрешение"))
                .catch(err => console.error('Не удалось скопировать разрешение: ', err));
        }
    });

    panelIllustPixivLinkEl.addEventListener('click', function(event) {
        event.preventDefault(); // Предотвращаем стандартный переход по ссылке
        if (event.ctrlKey || event.metaKey) { // Ctrl/Cmd + Click открывает ссылку
            window.open(this.href, '_blank');
        } else { // Обычный клик копирует ссылку
            navigator.clipboard.writeText(this.href)
                .then(() => showCopyFeedback(this, "Копировать ссылку на пост"))
                .catch(err => console.error('Не удалось скопировать ссылку: ', err));
        }
    });
});

// Обработчики загрузки/ошибки для основного изображения
currentImageEl.onload = () => hideImageSpinner();
currentImageEl.onerror = () => {
    hideImageSpinner();
    currentImageEl.alt = "Ошибка загрузки изображения";
    // Можно добавить какой-то placeholder или сообщение об ошибке на самом изображении
};

// Обработчики кликов по кнопкам управления
prevBtn.addEventListener('click', () => navigateIllust(-1));
nextBtn.addEventListener('click', () => navigateIllust(1));
bookmarkBtn.addEventListener('click', toggleBookmark);
downloadOriginalBtn.addEventListener('click', handleDownloadOriginal);
searchIqdbBtn.addEventListener('click', handleSearchIqdb);

infoToggleBtn.addEventListener('click', (e) => {
    e.stopPropagation(); // Предотвращаем всплытие, чтобы не закрыть панель сразу, если клик вне панели
    const currentIllust = illustList[currentIllustListIndex];
    if (currentIllust) {
        if (isInfoPanelVisible()) {
            hideInfoPanel();
        } else {
            // Если детальная информация еще не загружена, загружаем ее перед показом панели
            (currentIllust.detail_info_fetched ? Promise.resolve() : fetchAndUpdateDetailedInfo(currentIllust))
            .then(() => populateAndShowInfoPanel(currentIllust))
            .catch(err => { // На случай ошибки в fetchAndUpdateDetailedInfo или populateAndShowInfoPanel
                console.error("Ошибка при подготовке или отображении инфо-панели:", err);
                // Все равно пытаемся показать панель с тем, что есть
                populateAndShowInfoPanel(currentIllust); 
            });
        }
    }
});

// Глобальный обработчик кликов для закрытия информационной панели при клике вне ее
document.addEventListener('click', (e) => {
    if (isInfoPanelVisible() && !illustInfoPanelEl.contains(e.target) && e.target !== infoToggleBtn && !infoToggleBtn.contains(e.target)) {
        hideInfoPanel();
    }
});

// Обработчик горячих клавиш
document.addEventListener('keydown', handleHotkeys);

// Обработчик клика по кнопке переключения режима просмотра
modeToggleBtn.addEventListener('click', () => {
    if (isLoadingIllustList) return; // Не переключаем режим во время загрузки списка

    // Смена режима и сброс пагинации для нового режима
    if (currentViewMode === 'new_illust') {
        currentViewMode = 'user_bookmarks';
        currentOffsetForBookmarks = 0;
    } else {
        currentViewMode = 'new_illust';
        currentPixivApiPageForList = 1;
    }
    updateModeToggleUI(); // Обновляем UI кнопки
    illustList = []; // Очищаем текущий список иллюстраций
    currentIllustListIndex = -1; // Сбрасываем индекс
    renderThumbnails(); // Очищаем миниатюры в сайдбаре
    initUI(); // Сбрасываем основной UI к начальному состоянию
    fetchIllustListFromBackend(); // Загружаем данные для нового режима
});


// --- Navigation and Actions ---

/**
 * Осуществляет навигацию по иллюстрациям и страницам внутри них.
 * @param {number} direction - Направление навигации: -1 (назад) или 1 (вперед).
 */
async function navigateIllust(direction) {
    if (hotkeyCooldown) return; // Предотвращаем слишком частое срабатывание
    setHotkeyCooldown();

    if (currentIllustListIndex < 0 && illustList.length > 0) { // Если ничего не выбрано, но список есть
        if (direction === 1) { // При "вперед" переходим к первой иллюстрации
            currentIllustListIndex = 0;
            await displayCurrentIllustAndPage();
        }
        return;
    }
    if (currentIllustListIndex < 0 || !illustList[currentIllustListIndex]) return; // Если список пуст или индекс невалиден

    let currentIllust = illustList[currentIllustListIndex];

    if (direction === 1) { // Вперед
        // Сначала пытаемся перейти на следующую страницу текущей иллюстрации
        if (currentIllust.pages_data_loading_status === 'loaded' && currentIllust.pages_data && currentIllust.current_page_in_illust < currentIllust.pages_data.length - 1) {
            currentIllust.current_page_in_illust++;
            await displayCurrentIllustAndPage();
        } 
        // Если это последняя страница, или страниц нет, переходим к следующей иллюстрации в списке
        else if (currentIllustListIndex < illustList.length - 1) {
            currentIllustListIndex++;
            if (illustList[currentIllustListIndex]) {
                illustList[currentIllustListIndex].current_page_in_illust = 0; // Сбрасываем на первую страницу для новой иллюстрации
                await displayCurrentIllustAndPage();
            }
        } 
        // Если это последняя иллюстрация в списке, пытаемся загрузить еще (пагинация)
        else if (!isLoadingIllustList) {
            if (currentViewMode === 'new_illust') {
                currentPixivApiPageForList++;
                imageInfoTextEl.textContent = `Загрузка следующей страницы новых иллюстраций...`;
            } else { // user_bookmarks
                currentOffsetForBookmarks += BOOKMARKS_PAGE_LIMIT;
                imageInfoTextEl.textContent = `Загрузка следующих закладок...`;
            }
            imageInfoTextEl.classList.add('loading-text');
            await fetchIllustListFromBackend(); // Загружаем следующую порцию данных
            // После загрузки, если появились новые элементы, пользователь сможет перейти к ним.
        }
    } else if (direction === -1) { // Назад
        // Сначала пытаемся перейти на предыдущую страницу текущей иллюстрации
        if (currentIllust.pages_data_loading_status === 'loaded' && currentIllust.pages_data && currentIllust.current_page_in_illust > 0) {
            currentIllust.current_page_in_illust--;
            await displayCurrentIllustAndPage();
        } 
        // Если это первая страница, переходим к предыдущей иллюстрации в списке
        else if (currentIllustListIndex > 0) {
            currentIllustListIndex--;
            currentIllust = illustList[currentIllustListIndex]; // Обновляем ссылку на (теперь уже) текущую иллюстрацию
            if (currentIllust) {
                // Устанавливаем на последнюю страницу предыдущей иллюстрации
                currentIllust.current_page_in_illust = (currentIllust.pages_data_loading_status === 'loaded' && currentIllust.pages_data && currentIllust.pages_data.length > 0) 
                                                      ? currentIllust.pages_data.length - 1 
                                                      : 0;
                await displayCurrentIllustAndPage();
            }
        }
        // Если это первая иллюстрация и первая страница, ничего не делаем
    }
}

/**
 * Переключает статус закладки для текущей иллюстрации (добавляет/удаляет).
 */
async function toggleBookmark() {
    if (hotkeyCooldown) return; setHotkeyCooldown();
    if (currentIllustListIndex < 0 || !illustList[currentIllustListIndex] || !globalCsrfToken) {
        console.warn("Невозможно переключить закладку: не выбрана иллюстрация или отсутствует CSRF-токен.");
        return;
    }
    
    const illust = illustList[currentIllustListIndex];
    const action = illust.is_bookmarked ? 'delete' : 'add';

    // Если удаляем и нет bookmark_id, а детальная информация еще не загружена, пытаемся загрузить
    if (action === 'delete' && !illust.bookmark_id && !illust.detail_info_fetched && !illust.detail_info_fetched_pending) {
        console.log(`ID закладки для удаления ${illust.id} отсутствует, сначала загружаем детали...`);
        imageInfoTextEl.textContent = `Обновление данных для удаления из закладок...`;
        imageInfoTextEl.classList.add('loading-text');
        bookmarkBtn.disabled = true; // Блокируем кнопку на время загрузки деталей
        
        await fetchAndUpdateDetailedInfo(illust); // Ждем загрузки
        
        // Восстанавливаем текст и состояние кнопки, если иллюстрация все еще текущая
        imageInfoTextEl.classList.remove('loading-text');
        if (illustList[currentIllustListIndex]?.id === illust.id) {
             imageInfoTextEl.innerHTML = `<b>${illust.title}</b> (ID: ${illust.id}) <a href="https://www.pixiv.net/artworks/${illust.id}" target="_blank">[P]</a>`;
        }
        // После fetchAndUpdateDetailedInfo, illust.bookmark_id должен быть обновлен.
        // Если его все еще нет, следующая проверка это обработает.
    }

    // Если после попытки загрузки деталей ID закладки все еще отсутствует для удаления
    if (action === 'delete' && !illust.bookmark_id) {
        alert(`Не удалось получить ID закладки для иллюстрации ${illust.id} для удаления. Попробуйте обновить информацию об иллюстрации (кнопка 'i') и повторить.`);
        bookmarkBtn.disabled = false; // Разблокируем кнопку, т.к. операция не была отправлена на сервер
        return;
    }

    bookmarkBtn.disabled = true; // Блокируем кнопку на время основного запроса

    // Формируем payload для запроса к бэкенду
    const payload = {
        illust_id: illust.id,
        action: action,
        csrf_token: globalCsrfToken
    };
    if (action === 'delete') {
        payload.bookmark_id = illust.bookmark_id; // Добавляем ID закладки для удаления
    }

    try {
        const resp = await fetch('/api/bookmark', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload) 
        });
        const res = await resp.json();
        
        if (resp.ok && res.success) { 
            illust.is_bookmarked = (action === 'add'); // Обновляем статус в локальном объекте
            
            if (action === 'add') {
                if (res.last_bookmark_id) { // Если бэкенд вернул ID новой закладки
                    illust.bookmark_id = res.last_bookmark_id;
                } else if (res.already_bookmarked) { // Если иллюстрация УЖЕ была в закладках (по версии Pixiv)
                    if (!illust.bookmark_id) { // ...но у нас не было ID закладки
                        illust.is_bookmarked = true; // Подтверждаем статус
                        illust.detail_info_fetched = false; // Помечаем, что детали нужно перезагрузить для получения bookmark_id
                    }
                } else { // Добавлено, но ID закладки не пришел (маловероятно при успехе)
                    illust.bookmark_id = null; 
                }
            } else { // action === 'delete'
                illust.bookmark_id = null; // Сбрасываем ID закладки после успешного удаления
            }
            
            // Если не было случая "already_bookmarked" без ID (что требует перезагрузки деталей),
            // то считаем, что информация о закладке (статус и ID) теперь актуальна.
            if (!(res.already_bookmarked && !illust.bookmark_id)) {
                 illust.detail_info_fetched = true; 
            }
            triggerBookmarkAnimation(action === 'add'); // Запускаем анимацию
        } else {
             alert(`Ошибка закладки для ${illust.id}: ${res.error || resp.statusText || 'Неизвестная ошибка'}`);
        }
    } catch (e) { 
        alert(`Сетевая ошибка (закладка для ${illust.id}): ${e.message}`); 
    } finally { 
        // Обновляем UI, чтобы отразить изменения (особенно кнопку закладки)
        // Если detail_info_fetched был сброшен, displayCurrentIllustAndPage вызовет fetchAndUpdateDetailedInfo
        if (illustList[currentIllustListIndex]?.id === illust.id) {
            await displayCurrentIllustAndPage(); 
        } else { // Если иллюстрация сменилась во время запроса, просто разблокируем кнопку
             bookmarkBtn.disabled = false; 
        }
    }
}

/**
 * Запускает анимацию добавления/удаления закладки.
 * @param {boolean} isAdding - True, если закладка добавляется, false - если удаляется.
 */
function triggerBookmarkAnimation(isAdding) {
    if (!bookmarkAnimationOverlayEl || !bookmarkAnimationIconEl) return;

    bookmarkAnimationIconEl.classList.remove('animate-add', 'animate-remove');
    void bookmarkAnimationIconEl.offsetWidth; // Форсируем reflow для перезапуска анимации

    const heartPath = bookmarkAnimationIconEl.querySelector('.heart-path');
    if (heartPath) { // Устанавливаем соответствующую иконку (целое или "сломанное" сердце)
        heartPath.setAttribute('d', isAdding ? 
            "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" : 
            "M12.022 5.662l-1.063-1.06a5.503 5.503 0 00-7.782 7.782l1.063 1.06L12 21.23l7.76-7.788 1.063-1.06a5.503 5.503 0 000-7.782A5.508 5.508 0 0017.5 3.128l-1.26 1.26m-4.218 1.274L12 5.67M9.922 14.142l-1.5-1.5M14.078 14.142l1.5-1.5m-4.273-3.045L8.25 9.542m7.5 1.555l1.555-1.555"
        );
    }
    bookmarkAnimationIconEl.classList.add(isAdding ? 'animate-add' : 'animate-remove');
    bookmarkAnimationOverlayEl.classList.remove('hidden');

    // Скрываем оверлей после завершения анимации
    const onAnimationEnd = () => {
        bookmarkAnimationOverlayEl.classList.add('hidden');
        bookmarkAnimationIconEl.removeEventListener('animationend', onAnimationEnd);
    };
    bookmarkAnimationIconEl.addEventListener('animationend', onAnimationEnd);
}

/** Открывает оригинальное изображение текущей страницы в новой вкладке. */
function handleOpenOriginal() {
    if (hotkeyCooldown) return; setHotkeyCooldown();
    const currentIllust = illustList[currentIllustListIndex];
    if (!currentIllust || openOriginalBtn.classList.contains('hidden')) return;
    openOriginalBtn.click(); // Просто имитируем клик по кнопке
}

/** Инициирует скачивание оригинального изображения текущей страницы. */
function handleDownloadOriginal() {
    if (hotkeyCooldown) return; setHotkeyCooldown();
    const currentIllust = illustList[currentIllustListIndex];
    if (!currentIllust || downloadOriginalBtn.classList.contains('hidden')) return;
    
    const pageIdx = currentIllust.current_page_in_illust;
    const originalUrl = currentIllust.pages_data?.[pageIdx]?.url_original;
    if (originalUrl) {
        // Формируем URL к прокси с параметром download=true
        const downloadUrl = `/api/image_proxy?image_url=${encodeURIComponent(originalUrl)}&illust_id=${encodeURIComponent(currentIllust.id)}&download=true`;
        // Создаем временную ссылку и кликаем по ней для начала скачивания
        const a = document.createElement('a');
        a.href = downloadUrl;
        // Имя файла будет установлено сервером через Content-Disposition
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } else {
        console.warn("Нет URL оригинала для скачивания.");
    }
}

/** Открывает поиск текущего изображения на IQDB в новой вкладке. */
function handleSearchIqdb() {
    if (hotkeyCooldown) return; setHotkeyCooldown();
    const currentIllust = illustList[currentIllustListIndex];
    if (!currentIllust || searchIqdbBtn.classList.contains('hidden')) return;

    const pageIdx = currentIllust.current_page_in_illust;
    // Для IQDB предпочтительнее master URL (regular), если есть, иначе original
    const imageUrlForSearch = currentIllust.pages_data?.[pageIdx]?.url_master || currentIllust.pages_data?.[pageIdx]?.url_original;
    
    if (imageUrlForSearch) {
        const iqdbSearchUrl = `https://www.iqdb.org/?url=${encodeURIComponent(imageUrlForSearch)}`;
        window.open(iqdbSearchUrl, '_blank');
    } else {
        console.warn("Нет URL для поиска на IQDB.");
    }
}

/** Устанавливает временную задержку для горячих клавиш, чтобы предотвратить многократное срабатывание. */
function setHotkeyCooldown() {
    hotkeyCooldown = true;
    setTimeout(() => { hotkeyCooldown = false; }, HOTKEY_COOLDOWN_MS);
}

/**
 * Обрабатывает нажатия горячих клавиш.
 * @param {KeyboardEvent} event - Событие нажатия клавиши.
 */
function handleHotkeys(event) {
    // Игнорируем, если зажаты модификаторы (Ctrl, Alt, Meta), кроме случаев, когда это часть хоткея
    if (event.ctrlKey || event.metaKey || event.altKey) return;

    // Игнорируем, если фокус на поле ввода (чтобы не мешать печатать)
    const activeElement = document.activeElement;
    const isInputFocused = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.isContentEditable);
    if (isInputFocused) return;

    const keyActionMap = { 
        "ArrowLeft": () => navigateIllust(-1), 
        "ArrowRight": () => navigateIllust(1), 
        "f": toggleBookmark, // Латинская 'f'
        "F": toggleBookmark,
        "а": toggleBookmark, // Русская 'а'
        "А": toggleBookmark,
        "o": handleOpenOriginal, // Латинская 'o'
        "O": handleOpenOriginal,
        "щ": handleOpenOriginal, // Русская 'щ'
        "Щ": handleOpenOriginal,
        "d": handleDownloadOriginal, // Латинская 'd'
        "D": handleDownloadOriginal,
        "в": handleDownloadOriginal, // Русская 'в'
        "В": handleDownloadOriginal,
        "q": handleSearchIqdb, // Латинская 'q'
        "Q": handleSearchIqdb,
        "й": handleSearchIqdb, // Русская 'й'
        "Й": handleSearchIqdb,
        "i": () => infoToggleBtn.click(), // Латинская 'i'
        "I": () => infoToggleBtn.click(),
        "ш": () => infoToggleBtn.click(), // Русская 'ш'
        "Ш": () => infoToggleBtn.click(),
    };
        
    if (keyActionMap[event.key]) {
        event.preventDefault(); // Предотвращаем стандартное действие браузера (например, скроллинг страницы стрелками)
        keyActionMap[event.key]();
    }
}


// --- Sidebar Resizing Logic ---

/**
 * Инициализирует функционал изменения размера сайдбара перетаскиванием.
 */
function initSidebarResizer() {
    if (!sidebarResizerEl || !thumbnailsSidebarEl) return;

    sidebarResizerEl.addEventListener('mousedown', (e) => {
        e.preventDefault();
        isResizingSidebar = true;
        sidebarResizerEl.classList.add('active'); // Визуальное выделение ресайзера
        document.body.style.cursor = 'col-resize'; // Изменение курсора для всего документа
        document.body.style.userSelect = 'none';   // Отключение выделения текста

        const startX = e.clientX;
        const startWidth = thumbnailsSidebarEl.offsetWidth;

        const doDrag = (moveEvent) => {
            if (!isResizingSidebar) return;
            const currentX = moveEvent.clientX;
            const diffX = currentX - startX;
            let newWidth = startWidth + diffX;

            // Применение ограничений минимальной и максимальной ширины
            newWidth = Math.max(MIN_SIDEBAR_WIDTH, Math.min(newWidth, MAX_SIDEBAR_WIDTH));
            
            thumbnailsSidebarEl.style.width = `${newWidth}px`;
            // Если сайдбар не position:fixed, flex-контейнер автоматически подстроит image-viewer-container
        };

        const stopDrag = () => {
            if (!isResizingSidebar) return;
            isResizingSidebar = false;
            sidebarResizerEl.classList.remove('active');
            document.body.style.cursor = ''; // Возврат курсора по умолчанию
            document.body.style.userSelect = '';

            document.removeEventListener('mousemove', doDrag);
            document.removeEventListener('mouseup', stopDrag);
            
            // Сохранение новой ширины в localStorage для ее восстановления при следующей загрузке
            localStorage.setItem('sidebarWidth', thumbnailsSidebarEl.style.width);
        };

        document.addEventListener('mousemove', doDrag);
        document.addEventListener('mouseup', stopDrag);
    });

    // Восстановление ширины сайдбара из localStorage при загрузке страницы
    const savedWidth = localStorage.getItem('sidebarWidth');
    if (savedWidth) {
        const numericWidth = parseInt(savedWidth, 10);
        if (numericWidth >= MIN_SIDEBAR_WIDTH && numericWidth <= MAX_SIDEBAR_WIDTH) {
            thumbnailsSidebarEl.style.width = savedWidth;
        }
    }
}

// Инициализация ресайзера происходит в общем DOMContentLoaded выше