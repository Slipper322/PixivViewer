from flask import Flask, render_template_string, request, jsonify, Response, stream_with_context
import requests
from bs4 import BeautifulSoup
import json
import re # re может быть нужен для разбора URL или других вещей

app = Flask(__name__)

# HTML_TEMPLATE (остается таким же, как в предыдущем вашем ответе, где был JS)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pixiv Slideshow</title>
    <style>
        body { font-family: sans-serif; margin: 0; background-color: #333; color: #eee; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
        .container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; }
        .image-viewer {
            position: relative;
            width: 90vw; height: 80vh;
            display: flex; align-items: center; justify-content: center;
            margin-bottom: 20px; overflow: hidden;
        }
        .image-viewer img {
            max-width: 100%; max-height: 100%;
            object-fit: contain; border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
        }
        .controls { display: flex; align-items: center; margin-bottom: 20px; }
        .controls button, .controls input, .controls label {
            padding: 10px 15px; margin: 0 5px;
            background-color: #555; color: white; border: none;
            border-radius: 5px; cursor: pointer; font-size: 16px;
        }
        .controls button:hover { background-color: #777; }
        .controls input[type="text"] { background-color: #444; color: #eee; width: 250px; }
        .info { text-align: center; margin-bottom: 10px; }
        .loading { font-size: 1.5em; }
        .bookmark-btn.bookmarked { background-color: #ff69b4; }
        .bookmark-btn.bookmarked:hover { background-color: #ff85c1; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="controls">
            <label for="phpsessid">PHPSESSID:</label>
            <input type="text" id="phpsessid" placeholder="Ваша PHPSESSID кука">
            <button id="loadBtn">Загрузить</button>
        </div>

        <div class="image-viewer">
            <img id="currentImage" src="" alt="Иллюстрация">
        </div>
         <div id="imageInfo" class="info">Загрузка...</div>

        <div class="controls">
            <button id="prevBtn">« Пред.</button>
            <button id="bookmarkBtn">В закладки</button>
            <button id="nextBtn">След. »</button>
        </div>
        <div id="pageInfo" class="info"></div>
    </div>

    <script>
        const currentImageEl = document.getElementById('currentImage');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const loadBtn = document.getElementById('loadBtn');
        const phpsessidInput = document.getElementById('phpsessid');
        const imageInfoEl = document.getElementById('imageInfo');
        const pageInfoEl = document.getElementById('pageInfo');
        const bookmarkBtn = document.getElementById('bookmarkBtn');

        let illustList = []; 
        let currentIllustListIndex = -1; 
        
        let currentPixivApiPageForList = 1; 
        let isLoadingIllustList = false;
        let globalCsrfToken = '';

        function initUI() {
            currentImageEl.src = "";
            currentImageEl.alt = "Ожидание загрузки";
            imageInfoEl.textContent = 'Введите PHPSESSID и нажмите "Загрузить"';
            pageInfoEl.textContent = '';
            bookmarkBtn.disabled = true;
            bookmarkBtn.classList.remove('bookmarked');
            bookmarkBtn.textContent = 'В закладки';
        }
        initUI();

        async function fetchIllustListFromBackend(pixivPageNum = 1) {
            if (isLoadingIllustList) return;
            isLoadingIllustList = true;
            imageInfoEl.textContent = 'Загрузка списка иллюстраций...';
            const phpsessid = phpsessidInput.value;
            if (!phpsessid) {
                alert('Пожалуйста, введите PHPSESSID.');
                isLoadingIllustList = false;
                initUI();
                return;
            }

            try {
                const apiUrl = `/api/images?page=${pixivPageNum}&phpsessid=${encodeURIComponent(phpsessid)}`;
                const response = await fetch(apiUrl);
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `Ошибка HTTP: ${response.status}`);
                }
                const data = await response.json();

                if (data.csrf_token && (!globalCsrfToken || globalCsrfToken !== data.csrf_token)) {
                    globalCsrfToken = data.csrf_token;
                    console.log("CSRF token updated/received:", globalCsrfToken);
                }

                if (data.images && data.images.length > 0) {
                    const newIllustsMetadata = data.images.map(illustMeta => ({
                        id: illustMeta.id,
                        title: illustMeta.title,
                        preview_url_p0: illustMeta.preview_url_p0,
                        page_count: parseInt(illustMeta.page_count, 10) || 1,
                        is_bookmarked: illustMeta.is_bookmarked,
                        actual_page_urls: [], 
                        current_page_in_illust: 0,
                        pages_data_loaded: false,
                        pages_data_loading: false
                    }));

                    if (pixivPageNum === 1) {
                        illustList = newIllustsMetadata;
                        currentIllustListIndex = illustList.length > 0 ? 0 : -1;
                    } else {
                        illustList = illustList.concat(newIllustsMetadata);
                    }
                    
                    if (currentIllustListIndex !== -1) {
                        await displayCurrentIllustAndPage();
                    } else if (illustList.length === 0) { 
                        imageInfoEl.textContent = 'Иллюстрации не найдены.';
                        pageInfoEl.textContent = '';
                        currentImageEl.src = ""; currentImageEl.alt = "Нет иллюстраций";
                    }
                } else { 
                    if (pixivPageNum > 1) { 
                        imageInfoEl.textContent = 'Больше иллюстраций не найдено на Pixiv.';
                    } else { 
                        illustList = [];
                        currentIllustListIndex = -1;
                        imageInfoEl.textContent = 'Иллюстрации не найдены.';
                        pageInfoEl.textContent = '';
                        currentImageEl.src = ""; currentImageEl.alt = "Нет иллюстраций";
                    }
                }
            } catch (error) {
                console.error('Ошибка при загрузке списка иллюстраций:', error);
                imageInfoEl.textContent = `Ошибка списка: ${error.message}.`;
            } finally {
                isLoadingIllustList = false;
            }
        }

        async function fetchActualIllustPages(illustDataItem) {
            if (illustDataItem.pages_data_loaded || illustDataItem.pages_data_loading) {
                return; 
            }
            illustDataItem.pages_data_loading = true;
            const phpsessid = phpsessidInput.value;

            try {
                const response = await fetch(`/api/illust_pages/${illustDataItem.id}?phpsessid=${encodeURIComponent(phpsessid)}`);
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `Ошибка HTTP: ${response.status} при загрузке страниц`);
                }
                const data = await response.json();

                if (data.pages && data.pages.length > 0) {
                    illustDataItem.actual_page_urls = data.pages;
                } else { 
                    if (illustDataItem.page_count > 0 && illustDataItem.preview_url_p0) {
                        illustDataItem.actual_page_urls = [illustDataItem.preview_url_p0]; // Используем превью как fallback для отображения через прокси
                        console.warn(`API /api/illust_pages для ${illustDataItem.id} не вернуло URL страниц. Используем preview_url_p0 для прокси.`);
                    } else {
                        illustDataItem.actual_page_urls = [];
                        console.warn(`API /api/illust_pages для ${illustDataItem.id} не вернуло URL страниц и нет preview_url_p0.`);
                    }
                }
                illustDataItem.pages_data_loaded = true;
                console.log(`Загружено ${illustDataItem.actual_page_urls.length} URL(ов) страниц для ${illustDataItem.id}`);
            } catch (error) {
                console.error(`Ошибка при загрузке страниц для ${illustDataItem.id}:`, error);
                imageInfoEl.textContent = `Ошибка загрузки страниц: ${error.message}`;
                illustDataItem.pages_data_loaded = false; 
            } finally {
                illustDataItem.pages_data_loading = false;
            }
        }

        async function displayCurrentIllustAndPage() {
            if (currentIllustListIndex < 0 || currentIllustListIndex >= illustList.length) {
                initUI();
                if (illustList.length > 0) { 
                     imageInfoEl.textContent = 'Выберите иллюстрацию.';
                } else if (phpsessidInput.value && !isLoadingIllustList) { 
                     imageInfoEl.textContent = 'Иллюстрации не найдены.';
                }
                return;
            }

            const currentIllust = illustList[currentIllustListIndex];
            const phpsessid = phpsessidInput.value; // Нужен для URL прокси

            if (!currentIllust.pages_data_loaded && !currentIllust.pages_data_loading) {
                if (currentIllust.preview_url_p0) {
                    // Формируем URL для прокси даже для превью, если оно будет использоваться как fallback
                     const proxyPreviewUrl = `/api/image_proxy?image_url=${encodeURIComponent(currentIllust.preview_url_p0)}&illust_id=${encodeURIComponent(currentIllust.id)}&phpsessid=${encodeURIComponent(phpsessid)}`;
                    currentImageEl.src = proxyPreviewUrl;
                    currentImageEl.alt = `Превью: ${currentIllust.title}`;
                } else {
                    currentImageEl.src = "";
                    currentImageEl.alt = "Загрузка данных иллюстрации...";
                }
                imageInfoEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[Открыть на Pixiv]</a> (загрузка страниц...)`;
                pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1} из ${illustList.length}. (API списка стр. ${currentPixivApiPageForList})`;
                
                await fetchActualIllustPages(currentIllust);
                await displayCurrentIllustAndPage(); 
                return; 
            }
            
            if (currentIllust.pages_data_loading) {
                // ... (логика показа превью или "загрузка")
                 if (currentIllust.preview_url_p0) {
                     const proxyPreviewUrl = `/api/image_proxy?image_url=${encodeURIComponent(currentIllust.preview_url_p0)}&illust_id=${encodeURIComponent(currentIllust.id)}&phpsessid=${encodeURIComponent(phpsessid)}`;
                    currentImageEl.src = proxyPreviewUrl;
                    currentImageEl.alt = `Превью: ${currentIllust.title}`;
                } else {
                    currentImageEl.src = ""; currentImageEl.alt = "Загрузка...";
                }
                imageInfoEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[Открыть на Pixiv]</a> (загрузка страниц...)`;
                pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1} из ${illustList.length}. (API списка стр. ${currentPixivApiPageForList})`;
                return; 
            }

            if (currentIllust.pages_data_loaded) {
                if (currentIllust.actual_page_urls.length > 0) {
                    if (currentIllust.current_page_in_illust < 0) currentIllust.current_page_in_illust = 0;
                    if (currentIllust.current_page_in_illust >= currentIllust.actual_page_urls.length) {
                        currentIllust.current_page_in_illust = currentIllust.actual_page_urls.length - 1;
                    }
                    
                    const actualImageUrl = currentIllust.actual_page_urls[currentIllust.current_page_in_illust];
                    // *** КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: используем прокси ***
                    const proxyImageUrl = `/api/image_proxy?image_url=${encodeURIComponent(actualImageUrl)}&illust_id=${encodeURIComponent(currentIllust.id)}&phpsessid=${encodeURIComponent(phpsessid)}`;
                    currentImageEl.src = proxyImageUrl;
                    currentImageEl.alt = currentIllust.title;

                    imageInfoEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[Открыть на Pixiv]</a>`;
                    let pageNumberSubInfo = `Стр. ${currentIllust.current_page_in_illust + 1} из ${currentIllust.actual_page_urls.length}`;
                    pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1} из ${illustList.length}. ${pageNumberSubInfo}. (API списка стр. ${currentPixivApiPageForList})`;
                } else { 
                    currentImageEl.src = "";
                    currentImageEl.alt = `Нет страниц для: ${currentIllust.title}`;
                    imageInfoEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) <a href="https://www.pixiv.net/artworks/${currentIllust.id}" target="_blank">[Открыть на Pixiv]</a>`;
                    pageInfoEl.textContent = `Иллюстрация ${currentIllustListIndex + 1} из ${illustList.length}. Нет страниц. (API списка стр. ${currentPixivApiPageForList})`;
                }
            }
            
            bookmarkBtn.disabled = false;
            bookmarkBtn.textContent = currentIllust.is_bookmarked ? 'Убрать из закладок' : 'В закладки';
            currentIllust.is_bookmarked ? bookmarkBtn.classList.add('bookmarked') : bookmarkBtn.classList.remove('bookmarked');
        }

        // prevBtn, nextBtn, loadBtn, bookmarkBtn - логика остается такой же, как в вашем предыдущем ответе
        // с учетом новой структуры illustList и вызовов displayCurrentIllustAndPage()
        prevBtn.addEventListener('click', async () => {
            if (currentIllustListIndex < 0) return;
            const currentIllust = illustList[currentIllustListIndex];

            if (currentIllust.pages_data_loaded && currentIllust.current_page_in_illust > 0) {
                currentIllust.current_page_in_illust--;
                await displayCurrentIllustAndPage();
            } else if (currentIllustListIndex > 0) { 
                currentIllustListIndex--;
                const prevIllust = illustList[currentIllustListIndex];
                prevIllust.current_page_in_illust = (prevIllust.pages_data_loaded && prevIllust.actual_page_urls.length > 0) ? prevIllust.actual_page_urls.length - 1 : 0;
                await displayCurrentIllustAndPage();
            }
        });

        nextBtn.addEventListener('click', async () => {
            if (currentIllustListIndex < 0 && illustList.length > 0) { 
                currentIllustListIndex = 0; 
                await displayCurrentIllustAndPage();
                return;
            }
            if (currentIllustListIndex < 0) return; 

            const currentIllust = illustList[currentIllustListIndex];
            
            if (currentIllust.page_count > 0 && !currentIllust.pages_data_loaded && !currentIllust.pages_data_loading) {
                imageInfoEl.innerHTML = `<b>${currentIllust.title}</b> (ID: ${currentIllust.id}) (Загрузка страниц для перехода...)`;
                await fetchActualIllustPages(currentIllust); 
            }

            if (currentIllust.pages_data_loaded && currentIllust.current_page_in_illust < currentIllust.actual_page_urls.length - 1) {
                currentIllust.current_page_in_illust++;
                await displayCurrentIllustAndPage();
            } else if (currentIllustListIndex < illustList.length - 1) { 
                currentIllustListIndex++;
                illustList[currentIllustListIndex].current_page_in_illust = 0; 
                await displayCurrentIllustAndPage();
            } else if (!isLoadingIllustList) { 
                currentPixivApiPageForList++;
                imageInfoEl.textContent = `Загрузка следующей страницы списка иллюстраций (API стр. ${currentPixivApiPageForList})...`;
                await fetchIllustListFromBackend(currentPixivApiPageForList);
            }
        });

        loadBtn.addEventListener('click', () => {
            illustList = [];
            currentIllustListIndex = -1;
            currentPixivApiPageForList = 1;
            fetchIllustListFromBackend(currentPixivApiPageForList);
        });

        bookmarkBtn.addEventListener('click', async () => {
            if (currentIllustListIndex < 0 || currentIllustListIndex >= illustList.length) return;
            if (!globalCsrfToken) {
                alert("CSRF токен не найден. Попробуйте перезагрузить данные (кнопка 'Загрузить').");
                return;
            }
            const currentIllust = illustList[currentIllustListIndex];
            const action = currentIllust.is_bookmarked ? 'delete' : 'add';
            const phpsessid = phpsessidInput.value;
            const originalButtonText = bookmarkBtn.textContent;
            bookmarkBtn.disabled = true;
            bookmarkBtn.textContent = 'Обновление...';
            try {
                const response = await fetch('/api/bookmark', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        illust_id: currentIllust.id,
                        action: action,
                        phpsessid: phpsessid,
                        csrf_token: globalCsrfToken
                    })
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    currentIllust.is_bookmarked = (action === 'add');
                } else {
                    alert(`Ошибка закладки: ${result.error || 'Неизвестная ошибка с сервера'}`);
                }
            } catch (error) {
                console.error('Ошибка при изменении закладки:', error);
                alert(`Сетевая ошибка при изменении закладки: ${error.message}`);
            } finally {
                if (currentIllustListIndex >=0 && currentIllustListIndex < illustList.length) {
                    await displayCurrentIllustAndPage(); 
                } else { 
                     bookmarkBtn.textContent = originalButtonText; 
                     bookmarkBtn.disabled = true;
                }
            }
        });
    </script>
</body>
</html>
"""


# --- Функции Python ---
def extract_csrf_from_html(html_content):
    # ... (код этой функции без изменений из предыдущего ответа) ...
    soup = BeautifulSoup(html_content, 'html.parser')
    csrf_token = None
    next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
    if next_data_script:
        try:
            next_data_json = json.loads(next_data_script.string)
            preloaded_state_str = next_data_json.get('props', {}).get('pageProps', {}).get('serverSerializedPreloadedState')
            if preloaded_state_str:
                preloaded_state = json.loads(preloaded_state_str)
                csrf_token = preloaded_state.get('api', {}).get('token')
                if csrf_token:
                    print(f"DEBUG (extract_csrf_from_html): CSRF Token found in __NEXT_DATA__: {csrf_token}")
                else:
                    print("DEBUG (extract_csrf_from_html): CSRF Token NOT found in preloaded_state.api.token path.")
            else:
                print("DEBUG (extract_csrf_from_html): __NEXT_DATA__ does not contain serverSerializedPreloadedState.")
        except Exception as e:
            print(f"DEBUG (extract_csrf_from_html): Error processing __NEXT_DATA__ for CSRF: {e}")
    
    if not csrf_token:
        csrf_meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if csrf_meta_tag and csrf_meta_tag.get('content'):
            csrf_token = csrf_meta_tag['content']
            print(f"DEBUG (extract_csrf_from_html): CSRF Token found via fallback meta tag: {csrf_token}")
    
    if not csrf_token:
        print("WARNING (extract_csrf_from_html): CSRF Token could not be extracted.")
    return csrf_token


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/images')
def get_images_api_route():
    # ... (код этой функции без изменений из предыдущего ответа) ...
    page_num_str = request.args.get('page', '1')
    phpsessid = request.args.get('phpsessid')
    
    if not phpsessid:
        return jsonify({'error': 'PHPSESSID не предоставлен'}), 400

    api_url_for_images = f"https://www.pixiv.net/ajax/follow_latest/illust?p={page_num_str}&mode=all"
    print(f"DEBUG (API /api/images): Requesting page {page_num_str} from Pixiv API: {api_url_for_images}")

    headers_for_api = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': f'https://www.pixiv.net/bookmark_new_illust.php?p={page_num_str}',
        'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    cookies_for_api = {'PHPSESSID': phpsessid}
    
    fetched_csrf_token = None
    if page_num_str == '1':
        print(f"DEBUG (API /api/images): Fetching main page for CSRF token.")
        try:
            main_page_url = "https://www.pixiv.net/bookmark_new_illust.php"
            headers_for_html = {**headers_for_api, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'}
            if 'X-Requested-With' in headers_for_html: del headers_for_html['X-Requested-With']
            response_main_page = requests.get(main_page_url, headers=headers_for_html, cookies=cookies_for_api, timeout=15)
            response_main_page.raise_for_status()
            if 'login.php' in response_main_page.url or 'accounts.pixiv.net' in response_main_page.url:
                 return jsonify({'error': 'Ошибка авторизации при получении CSRF токена.'}), 401
            fetched_csrf_token = extract_csrf_from_html(response_main_page.text)
        except Exception as e:
            print(f"ERROR (API /api/images): Error fetching/parsing main page for CSRF: {str(e)}")

    parsed_illust_metadata_list = []
    try:
        response_pixiv_api = requests.get(api_url_for_images, headers=headers_for_api, cookies=cookies_for_api, timeout=15)
        response_pixiv_api.raise_for_status()
        if 'login.php' in response_pixiv_api.url or 'accounts.pixiv.net' in response_pixiv_api.url:
             return jsonify({'error': 'Ошибка авторизации при запросе к API изображений.'}), 401

        api_json_data = response_pixiv_api.json()

        if api_json_data.get("error"):
            error_message = api_json_data.get("message", "Pixiv API вернул ошибку.")
            if "該当作品は存在しません" in error_message or "no new illustrations" in error_message.lower():
                print(f"DEBUG (API /api/images): Pixiv API reports no new images on page {page_num_str}.")
            else: 
                print(f"ERROR (API /api/images): Pixiv API error: {error_message}")
            return jsonify({'images': [], 'csrf_token': fetched_csrf_token}) 

        if 'body' in api_json_data and 'thumbnails' in api_json_data['body'] and 'illust' in api_json_data['body']['thumbnails']:
            raw_illust_list = api_json_data['body']['thumbnails']['illust']
            for item in raw_illust_list:
                parsed_illust_metadata_list.append({
                    'id': str(item.get('id')),
                    'title': item.get('title', 'Без названия'),
                    'preview_url_p0': item.get('url'), 
                    'page_count': item.get('pageCount', 1),
                    'is_bookmarked': item.get('isBookmarked', False) 
                })
            print(f"DEBUG (API /api/images): Parsed metadata for {len(parsed_illust_metadata_list)} illusts from Pixiv API page {page_num_str}")
        else:
            print(f"WARNING (API /api/images): Pixiv API response for images (page {page_num_str}) has unexpected structure. Data: {str(api_json_data)[:500]}...")
        return jsonify({'images': parsed_illust_metadata_list, 'csrf_token': fetched_csrf_token})
    except requests.exceptions.HTTPError as e_http:
        error_msg = f'Ошибка Pixiv API списка иллюстраций (HTTP {e_http.response.status_code})'
        try: error_msg += f': {e_http.response.json().get("message", str(e_http))}'
        except: error_msg += f': {e_http.response.text[:200]}'
        print(f"ERROR (API /api/images): {error_msg}")
        return jsonify({'error': error_msg, 'csrf_token': fetched_csrf_token}), e_http.response.status_code
    except requests.exceptions.RequestException as e_req: # Должно быть выше общего Exception
        print(f"ERROR (API /api/images): Network error: {str(e_req)}")
        return jsonify({'error': f'Сеть: {str(e_req)}', 'csrf_token': fetched_csrf_token}), 500
    except json.JSONDecodeError as e_json: # Должно быть выше общего Exception
        resp_text = response_pixiv_api.text[:500] if 'response_pixiv_api' in locals() else "N/A"
        print(f"ERROR (API /api/images): JSON Decode Error: {str(e_json)}. Response: {resp_text}")
        return jsonify({'error': f'JSON Parse: {str(e_json)}', 'csrf_token': fetched_csrf_token}), 500
    except Exception as e_exc:
        import traceback
        print(f"ERROR (API /api/images): Unexpected: {str(e_exc)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Сервер: {str(e_exc)}', 'csrf_token': fetched_csrf_token}), 500

@app.route('/api/illust_pages/<illust_id>')
def get_illust_pages_api_route(illust_id):
    phpsessid = request.args.get('phpsessid')
    if not phpsessid:
        return jsonify({'error': 'PHPSESSID не предоставлен'}), 400

    illust_pages_api_url = f"https://www.pixiv.net/ajax/illust/{illust_id}/pages"
    print(f"DEBUG (API /api/illust_pages): Requesting pages for illust_id {illust_id} from {illust_pages_api_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': f'https://www.pixiv.net/artworks/{illust_id}',
        'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    cookies = {'PHPSESSID': phpsessid}

    try:
        response = requests.get(illust_pages_api_url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        if 'login.php' in response.url or 'accounts.pixiv.net' in response.url:
             return jsonify({'error': f'Ошибка авторизации при запросе страниц для illust_id {illust_id}.'}), 401
        
        data = response.json()
        if data.get("error"):
            print(f"ERROR (API /api/illust_pages): Pixiv API error for illust_id {illust_id}: {data.get('message')}")
            return jsonify({"error": data.get("message", "Pixiv API вернул ошибку для страниц")}), 200 
        
        page_urls = []
        if 'body' in data and isinstance(data['body'], list):
            for page_data in data['body']:
                if 'urls' in page_data and isinstance(page_data['urls'], dict):
                    # *** Для проксирования нам нужен URL наилучшего качества, обычно 'original' ***
                    url_to_return = page_data['urls'].get('original') or \
                                    page_data['urls'].get('regular') or \
                                    page_data['urls'].get('small') # Fallback
                    if url_to_return:
                        page_urls.append(url_to_return)
                        print(f"DEBUG (API /api/illust_pages): IllustID {illust_id}, page: Selected URL for proxying: {url_to_return}")
            print(f"DEBUG (API /api/illust_pages): Found {len(page_urls)} page URLs for illust_id {illust_id}")
        else:
            print(f"WARNING (API /api/illust_pages): Unexpected response structure for illust_id {illust_id}. Data: {str(data)[:300]}...")
            
        return jsonify({'pages': page_urls})

    except requests.exceptions.HTTPError as e_http_pages:
        error_msg_pages = f'Ошибка Pixiv API страниц (HTTP {e_http_pages.response.status_code})'
        try: error_msg_pages += f': {e_http_pages.response.json().get("message", str(e_http_pages))}'
        except: error_msg_pages += f': {e_http_pages.response.text[:200]}'
        print(f"ERROR (API /api/illust_pages): {error_msg_pages}")
        return jsonify({'error': error_msg_pages}), e_http_pages.response.status_code
    except requests.exceptions.RequestException as e_req_pages: # Должно быть выше общего Exception
        print(f"ERROR (API /api/illust_pages): Network error: {str(e_req_pages)}")
        return jsonify({'error': f'Сеть (страницы): {str(e_req_pages)}'}), 500
    except json.JSONDecodeError as e_json_pages: # Должно быть выше общего Exception
        resp_text_pages = response.text[:300] if 'response' in locals() else "N/A"
        print(f"ERROR (API /api/illust_pages): JSON Decode Error: {str(e_json_pages)}. Response: {resp_text_pages}")
        return jsonify({'error': f'JSON Parse (страницы): {str(e_json_pages)}'}), 500
    except Exception as e_exc_pages:
        import traceback
        print(f"ERROR (API /api/illust_pages): Unexpected: {str(e_exc_pages)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Сервер (страницы): {str(e_exc_pages)}'}), 500


# *** НОВЫЙ ЭНДПОИНТ ДЛЯ ПРОКСИРОВАНИЯ ИЗОБРАЖЕНИЙ ***
@app.route('/api/image_proxy')
def image_proxy():
    image_url = request.args.get('image_url')
    illust_id = request.args.get('illust_id')
    phpsessid = request.args.get('phpsessid') # PHPSESSID из URL

    if not image_url or not illust_id:
        return "Missing image_url or illust_id parameter", 400
    
    # Куки для запроса к Pixiv. PHPSESSID может быть не обязателен для картинки, но не помешает.
    # Если phpsessid передан в URL, используем его.
    proxy_cookies = {}
    if phpsessid:
        proxy_cookies['PHPSESSID'] = phpsessid
    elif 'PHPSESSID' in request.cookies: # Если phpsessid не передан в URL, пробуем взять из кук запроса к прокси
        proxy_cookies['PHPSESSID'] = request.cookies['PHPSESSID']


    headers_for_pixiv_image = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': f'https://www.pixiv.net/artworks/{illust_id}' # Ключевой заголовок
    }
    
    print(f"DEBUG (PROXY): Requesting image: {image_url} with Referer: {headers_for_pixiv_image['Referer']}")

    try:
        # Используем stream=True для эффективной передачи больших файлов
        pixiv_response = requests.get(image_url, headers=headers_for_pixiv_image, cookies=proxy_cookies, stream=True, timeout=20)
        pixiv_response.raise_for_status() # Проверка на HTTP ошибки от Pixiv

        # Получаем Content-Type от ответа Pixiv, чтобы передать его клиенту
        content_type = pixiv_response.headers.get('Content-Type', 'application/octet-stream')
        
        # Используем stream_with_context для потоковой передачи данных клиенту
        # Это важно для больших изображений, чтобы не загружать их полностью в память сервера
        return Response(stream_with_context(pixiv_response.iter_content(chunk_size=8192)), content_type=content_type)

    except requests.exceptions.HTTPError as e_http_proxy:
        error_msg_proxy = f"Proxy HTTP Error {e_http_proxy.response.status_code} for {image_url}: {e_http_proxy.response.text[:200]}"
        print(f"ERROR (PROXY): {error_msg_proxy}")
        # Возвращаем ошибку с тем же кодом, что и от Pixiv
        return error_msg_proxy, e_http_proxy.response.status_code 
    except requests.exceptions.RequestException as e_req_proxy:
        error_msg_proxy = f"Proxy Network Error for {image_url}: {str(e_req_proxy)}"
        print(f"ERROR (PROXY): {error_msg_proxy}")
        return error_msg_proxy, 502 # Bad Gateway
    except Exception as e_exc_proxy:
        import traceback
        error_msg_proxy = f"Proxy Unexpected Error for {image_url}: {str(e_exc_proxy)}"
        print(f"ERROR (PROXY): {error_msg_proxy}\n{traceback.format_exc()}")
        return error_msg_proxy, 500


@app.route('/api/bookmark', methods=['POST'])
def toggle_bookmark_api_route():
    # ... (код этой функции без изменений из предыдущего ответа) ...
    data = request.json
    illust_id = data.get('illust_id')
    action = data.get('action') 
    phpsessid = data.get('phpsessid')
    client_csrf_token = data.get('csrf_token')

    if not all([illust_id, action, phpsessid, client_csrf_token]):
        return jsonify({'error': 'Отсутствуют параметры (illust_id, action, phpsessid, csrf_token)'}), 400
    if action not in ['add', 'delete']:
        return jsonify({'error': 'Неверное действие (add/delete)'}), 400

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': f'https://www.pixiv.net/artworks/{illust_id}', 
        'X-CSRF-Token': client_csrf_token, 
        'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    
    bookmark_url = f'https://www.pixiv.net/ajax/illusts/bookmarks/{action}' # add или delete
    payload = {"illust_id": str(illust_id)}
    if action == 'add':
        payload.update({"restrict": 0, "comment": "", "tags": []})

    print(f"DEBUG (API /api/bookmark): Action: {action}, URL: {bookmark_url}, IllustID: {illust_id}, CSRF: {client_csrf_token[:10]}...")
    try:
        response = requests.post(bookmark_url, headers=headers, cookies=cookies, json=payload, timeout=10)
        response.raise_for_status()
        result_json = response.json()

        if result_json.get('error'):
            msg = result_json.get('message', '')
            if (action == 'add' and ("Уже добавлено в закладки" in msg or "Already bookmarked" in msg)) or \
               (action == 'delete' and ("не найдено в закладках" in msg.lower() or "not bookmarked" in msg.lower())):
                print(f"INFO (API /api/bookmark): Illust {illust_id} - состояние уже соответствует '{action}'.")
                return jsonify({'success': True, 'message': f'Состояние уже "{action}" (сервер)'})
            
            print(f"ERROR (API /api/bookmark): Pixiv API error: {msg}")
            return jsonify({'success': False, 'error': msg or 'Pixiv вернул ошибку'}), 200
        
        print(f"SUCCESS (API /api/bookmark): Response: {result_json}")
        return jsonify({'success': True, 'message': result_json.get('message', 'Операция успешна')})

    except requests.exceptions.HTTPError as e_http_bm:
        error_msg_bm = f'Ошибка Pixiv Bookmark API (HTTP {e_http_bm.response.status_code})'
        try:
            err_body = e_http_bm.response.json()
            err_text = err_body.get("message", str(e_http_bm))
            if "invalid_token" in err_body.get("error", "") or "token" in err_text.lower() or "トークン" in err_text:
                 err_text += " (Попробуйте обновить страницу (F5) и снова загрузить данные, чтобы получить новый CSRF токен.)"
            error_msg_bm += f': {err_text}'
        except: error_msg_bm += f': {e_http_bm.response.text[:200]}'
        print(f"ERROR (API /api/bookmark): {error_msg_bm}")
        return jsonify({'success': False, 'error': error_msg_bm}), e_http_bm.response.status_code
    except requests.exceptions.RequestException as e_req_bm: # Должно быть выше общего Exception
        print(f"ERROR (API /api/bookmark): Network error: {str(e_req_bm)}")
        return jsonify({'success': False, 'error': f'Сеть (закладка): {str(e_req_bm)}'}), 500
    except Exception as e_exc_bm:
        import traceback
        print(f"ERROR (API /api/bookmark): Unexpected: {str(e_exc_bm)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Сервер (закладка): {str(e_exc_bm)}'}), 500


if __name__ == '__main__':
    print("Запустите приложение и откройте http://127.0.0.1:5000/ в браузере.")
    print("Не забудьте ввести свой PHPSESSID от Pixiv в поле на странице.")
    app.run(debug=True, host='0.0.0.0')