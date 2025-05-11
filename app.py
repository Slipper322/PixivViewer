from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import requests
from bs4 import BeautifulSoup
import json
import re
import os
import logging

# Константа для API Pixiv: количество закладок, запрашиваемых за один раз.
BOOKMARKS_API_LIMIT = 48

app = Flask(__name__)

# Файл конфигурации и глобальный словарь для хранения конфигурации.
CONFIG_FILE = 'config.json'
CONFIG = {}

def load_config():
    """
    Загружает конфигурацию из файла config.json.
    Проверяет наличие PHPSESSID. Создает файл-заглушку, если config.json отсутствует.
    Возвращает True при успехе, False при ошибке.
    """
    global CONFIG
    try:
        with open(CONFIG_FILE, 'r') as f:
            CONFIG = json.load(f)
        if not CONFIG.get('PHPSESSID'): # PHPSESSID критичен для работы
            app.logger.warning(f"PHPSESSID не найден или пуст в {CONFIG_FILE}. Приложение может не работать корректно.")
            return False
        app.logger.info(f"Конфигурация из {CONFIG_FILE} успешно загружена.")
        return True
    except FileNotFoundError:
        app.logger.error(f"Файл конфигурации {CONFIG_FILE} не найден. Будет создан файл-заглушка.")
        try:
            default_config = {
                "PHPSESSID": "ВАША_PHPSESSID_КУКА_СЮДА",
                "USER_ID": "ВАШ_USER_ID_PIXIV_СЮДА (для просмотра своих закладок)"
            }
            with open(CONFIG_FILE, 'w') as f:
                    json.dump(default_config, f, indent=4)
            app.logger.info(f"Создан файл-заглушка {CONFIG_FILE}. Пожалуйста, заполните его.")
        except Exception as e_create_conf:
            app.logger.error(f"Не удалось создать файл-заглушку {CONFIG_FILE}: {e_create_conf}")
        return False
    except json.JSONDecodeError:
        app.logger.error(f"Ошибка декодирования JSON в файле {CONFIG_FILE}.")
        return False
    except Exception as e:
        app.logger.error(f"Неизвестная ошибка при загрузке конфигурации: {e}", exc_info=True)
        return False

def extract_csrf_from_html(html_content: str) -> str | None:
    """
    Извлекает CSRF-токен из HTML-содержимого страницы Pixiv.
    Сначала пытается найти токен в JSON-блоке __NEXT_DATA__, затем в мета-теге csrf-token.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    csrf_token = None
    
    # Попытка №1: Извлечение из __NEXT_DATA__ (предпочтительный метод для новых страниц Pixiv)
    next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
    if next_data_script and next_data_script.string:
        try:
            next_data_json = json.loads(next_data_script.string)
            # Путь к токену может меняться, здесь один из известных вариантов
            preloaded_state_str = next_data_json.get('props', {}).get('pageProps', {}).get('serverSerializedPreloadedState')
            if preloaded_state_str:
                preloaded_state = json.loads(preloaded_state_str)
                csrf_token = preloaded_state.get('api', {}).get('token')
                if csrf_token:
                    app.logger.debug(f"(extract_csrf): CSRF Token from __NEXT_DATA__ found.")
        except Exception as e: # json.JSONDecodeError или другие ошибки доступа к ключам
            app.logger.error(f"(extract_csrf): Error processing __NEXT_DATA__ for CSRF token: {e}", exc_info=True)
    
    # Попытка №2: Извлечение из мета-тега (более старый или запасной метод)
    if not csrf_token:
        csrf_meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if csrf_meta_tag and csrf_meta_tag.get('content'):
            csrf_token = csrf_meta_tag['content']
            app.logger.debug(f"(extract_csrf): CSRF Token from meta tag found.")
    
    if not csrf_token:
        app.logger.warning("(extract_csrf): CSRF Token not extracted from HTML.")
    return csrf_token

@app.route('/')
def index():
    """Рендерит главную страницу приложения."""
    return render_template('index.html')

@app.route('/api/images')
def get_images_api_route():
    """
    API эндпоинт для получения списка новых иллюстраций от пользователей, на которых подписан юзер.
    Также извлекает CSRF-токен при запросе первой страницы.
    """
    page_num_str = request.args.get('page', '1')
    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid: # Проверка и попытка загрузки PHPSESSID, если он отсутствует
        if not load_config() or not CONFIG.get('PHPSESSID'):
            return jsonify({'error': f'PHPSESSID не настроен в {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    # URL API Pixiv для получения новых иллюстраций от подписок
    api_url = f"https://www.pixiv.net/ajax/follow_latest/illust?p={page_num_str}&mode=all"
    app.logger.debug(f"API /api/images: Requesting URL: {api_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0', # Стандартный User-Agent
        'Referer': f'https://www.pixiv.net/bookmark_new_illust.php?p={page_num_str}', # Важный Referer
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest' # Указывает, что это AJAX-запрос
    }
    cookies = {'PHPSESSID': phpsessid}
    
    csrf_token = None
    if page_num_str == '1': # CSRF-токен запрашивается только для первой страницы
        try:
            # URL для получения HTML-страницы, с которой можно извлечь CSRF-токен
            main_page_url = "https://www.pixiv.net/bookmark_new_illust.php"
            html_headers = {**headers} # Копируем основные заголовки
            html_headers['Accept'] = 'text/html,application/xhtml+xml' # Указываем, что ожидаем HTML
            if 'X-Requested-With' in html_headers: del html_headers['X-Requested-With'] # Для HTML-запроса этот заголовок не нужен
            
            resp_main = requests.get(main_page_url, headers=html_headers, cookies=cookies, timeout=15)
            resp_main.raise_for_status() # Проверка на HTTP ошибки
            
            # Проверка на редирект на страницу логина
            if 'login.php' in resp_main.url or 'accounts.pixiv.net' in resp_main.url:
                app.logger.warning("API /api/images: Auth error on CSRF fetch (redirected to login). Continuing without new CSRF.")
            else:
                csrf_token = extract_csrf_from_html(resp_main.text)
                if csrf_token:
                    app.logger.info(f"API /api/images: CSRF token extracted/updated on page 1.")
                else:
                    app.logger.warning("API /api/images: Failed to extract CSRF token on page 1.")
        except Exception as e:
            app.logger.error(f"API /api/images: CSRF fetch error on page 1: {e}", exc_info=True)

    illusts_meta = []
    try:
        resp_api = requests.get(api_url, headers=headers, cookies=cookies, timeout=15)
        resp_api.raise_for_status()
        if 'login.php' in resp_api.url or 'accounts.pixiv.net' in resp_api.url:
            return jsonify({'error': 'Auth error on images API (redirected to login).'}), 401
        
        data = resp_api.json()

        if data.get("error"):
            msg = data.get("message", "Pixiv API error.")
            # Сообщения о конце списка или отсутствии новых иллюстраций логируем как INFO
            if "該当作品は存在しません" in msg or "no new illustrations" in msg.lower():
                app.logger.info(f"API /api/images: Pixiv message (no more new illusts): {msg}")
            else:
                app.logger.error(f"API /api/images: Pixiv API error: {msg}")
            return jsonify({'images': [], 'csrf_token': csrf_token}) 

        if data.get('body', {}).get('thumbnails', {}).get('illust'):
            for item in data['body']['thumbnails']['illust']:
                bookmark_data = item.get('bookmarkData')
                is_bookmarked_val = isinstance(bookmark_data, dict) and bookmark_data.get('id') is not None
                bookmark_id_val = bookmark_data.get('id') if is_bookmarked_val else None
                
                preview_url_to_use = item.get('url') # URL превью по умолчанию
                item_urls_dict = item.get('urls') # Словарь с разными размерами превью
                if isinstance(item_urls_dict, dict):
                    # Выбор наилучшего доступного URL для превью
                    if item_urls_dict.get('1200x1200'): preview_url_to_use = item_urls_dict['1200x1200']
                    elif item_urls_dict.get('540x540'): preview_url_to_use = item_urls_dict['540x540']
                    elif item_urls_dict.get('360x360'): preview_url_to_use = item_urls_dict['360x360']
                
                illusts_meta.append({
                    'id': str(item.get('id')),
                    'title': item.get('title', 'N/A'),
                    'preview_url_p0': preview_url_to_use,
                    'page_count': item.get('pageCount', 1),
                    'is_bookmarked': is_bookmarked_val,
                    'bookmark_id': str(bookmark_id_val) if bookmark_id_val else None,
                    'width': item.get('width'),
                    'height': item.get('height'),
                    # Данные об авторе, если они есть в этом API, могут быть переданы сразу
                    # 'author_name': item.get('userName'),
                    # 'author_id': str(item.get('userId')) if item.get('userId') else None,
                })
            app.logger.debug(f"API /api/images: Parsed {len(illusts_meta)} illusts.")
        else:
            app.logger.warning(f"API /api/images: Unexpected API response structure from Pixiv: {str(data)[:200]}")
        
        return jsonify({'images': illusts_meta, 'csrf_token': csrf_token})
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API /api/images: Network error: {e}", exc_info=True)
        return jsonify({'error': f'Network error: {e}', 'csrf_token': csrf_token}), 500
    except Exception as e:
        app.logger.error(f"API /api/images: General error: {e}", exc_info=True)
        return jsonify({'error': f'Server error: {e}', 'csrf_token': csrf_token}), 500

@app.route('/api/illust_pages/<illust_id>')
def get_illust_pages_api_route(illust_id: str):
    """Получает информацию о страницах (для многостраничных иллюстраций) по ID иллюстрации."""
    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid:
        if not load_config() or not CONFIG.get('PHPSESSID'): return jsonify({'error': f'PHPSESSID not in {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    api_url = f"https://www.pixiv.net/ajax/illust/{illust_id}/pages"
    app.logger.debug(f"API /illust_pages: ID {illust_id}, URL: {api_url}")
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': f'https://www.pixiv.net/artworks/{illust_id}', # Referer важен
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    pages_info = []
    try:
        resp = requests.get(api_url, headers=headers, cookies=cookies, timeout=10)
        resp.raise_for_status()
        if 'login.php' in resp.url or 'accounts.pixiv.net' in resp.url:
            return jsonify({'error': f'Auth error for illust pages {illust_id} (redirected to login).'}), 401
        
        data = resp.json()
        if data.get("error"):
            app.logger.error(f"API /illust_pages: Pixiv API error for {illust_id}: {data.get('message')}")
            return jsonify({"error": data.get("message", "Pixiv API error (pages data)")}), 200 # Возвращаем 200 с ошибкой в теле
        
        if data.get('body') and isinstance(data['body'], list):
            for page_data in data['body']:
                if page_data.get('urls') and isinstance(page_data['urls'], dict):
                    pages_info.append({
                        'url_master': page_data['urls'].get('regular'), # 'regular' часто используется как 'master' или близкое к нему качество
                        'url_original': page_data['urls'].get('original'),
                        'width': page_data.get('width'),
                        'height': page_data.get('height')
                    })
            app.logger.debug(f"API /illust_pages: Found {len(pages_info)} pages for illust ID {illust_id}")
        else:
            app.logger.warning(f"API /illust_pages: Unexpected response structure for {illust_id}: {str(data)[:200]}")
        
        return jsonify({'pages_data': pages_info})
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API /illust_pages: Network error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Network error (pages data): {e}'}), 500
    except Exception as e:
        app.logger.error(f"API /illust_pages: General error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Server error (pages data): {e}'}), 500

@app.route('/api/image_proxy')
def image_proxy():
    """
    Проксирует запросы к изображениям Pixiv, добавляя необходимые заголовки (Referer)
    и куки для обхода защиты от хотлинкинга. Позволяет принудительно скачивать файл.
    """
    image_url_param = request.args.get('image_url')
    illust_id_param = request.args.get('illust_id') # Для формирования Referer
    force_download = request.args.get('download', 'false').lower() == 'true' # Параметр для принудительной загрузки

    phpsessid_config = CONFIG.get('PHPSESSID')
    if not phpsessid_config:
        if not load_config() or not CONFIG.get('PHPSESSID'):
            app.logger.error("PROXY: PHPSESSID не настроен на сервере.")
            return "PHPSESSID не настроен на сервере.", 503
        phpsessid_config = CONFIG.get('PHPSESSID')
    
    if not image_url_param:
        app.logger.warning("PROXY: Отсутствует параметр image_url.")
        return "Отсутствует параметр image_url", 400
    
    proxy_cookies = {'PHPSESSID': phpsessid_config} if phpsessid_config else {}
    headers_for_pixiv_image = {'User-Agent': 'Mozilla/5.0'}
    if illust_id_param: # Referer критичен для оригинальных изображений
        headers_for_pixiv_image['Referer'] = f'https://www.pixiv.net/artworks/{illust_id_param}'
    
    app.logger.debug(f"PROXY: Requesting image: {image_url_param} with Referer: {headers_for_pixiv_image.get('Referer', 'None')}")

    try:
        pixiv_response = requests.get(
            image_url_param,
            headers=headers_for_pixiv_image,
            cookies=proxy_cookies,
            stream=True, # Для потоковой передачи больших файлов
            timeout=25
        )
        pixiv_response.raise_for_status()

        content_type = pixiv_response.headers.get('Content-Type', 'application/octet-stream')
        
        # Определение имени файла для Content-Disposition
        filename = "pixiv_image" # Имя по умолчанию
        try:
            parsed_url_path = requests.utils.urlparse(image_url_param).path
            potential_filename_match = re.search(r'/([^/]+)$', parsed_url_path)
            if potential_filename_match:
                potential_filename = potential_filename_match.group(1).split('?')[0] # Убираем query-параметры, если есть
                # Эвристика для определения корректного имени файла Pixiv
                if re.match(r'\d+(_p\d+)?\.\w+', potential_filename):
                    filename = potential_filename
                else:
                    app.logger.warning(f"PROXY: Extracted filename '{potential_filename}' does not match expected Pixiv format. Using default.")
        except Exception as e_fn:
            app.logger.warning(f"PROXY: Failed to parse filename from URL {image_url_param}: {e_fn}")

        # Формирование ответа клиенту
        response_to_client = Response(
            stream_with_context(pixiv_response.iter_content(chunk_size=16384)), # Увеличен chunk_size для эффективности
            content_type=content_type
        )
        
        # Установка Content-Disposition для отображения или скачивания
        disposition_type = "attachment" if force_download else "inline"
        response_to_client.headers["Content-Disposition"] = f"{disposition_type}; filename=\"{filename}\""
        if force_download:
            app.logger.debug(f"PROXY: Forcing download for {filename} (Content-Disposition: attachment)")
            
        return response_to_client

    except requests.exceptions.HTTPError as e_http:
        status_code = e_http.response.status_code
        reason = e_http.response.reason
        response_text = e_http.response.text[:500] if e_http.response else "No response body"
        app.logger.error(f"PROXY HTTP Error: {status_code} {reason} for {image_url_param}. Response: {response_text}")
        return f"Proxy HTTP Error {status_code} for {image_url_param}: {reason}", status_code
    except requests.exceptions.Timeout:
        app.logger.error(f"PROXY: Timeout requesting {image_url_param} from Pixiv.")
        return "Proxy: Timeout when requesting image from Pixiv.", 504 # Gateway Timeout
    except requests.exceptions.RequestException as e_req:
        app.logger.error(f"PROXY: Network error for {image_url_param}: {e_req}", exc_info=True)
        return f"Proxy Network Error: {str(e_req)}", 502 # Bad Gateway
    except Exception as e_exc:
        app.logger.error(f"PROXY: Unexpected error for {image_url_param}: {e_exc}", exc_info=True)
        return f"Proxy Unexpected Error: {str(e_exc)}", 500

@app.route('/api/illust_details_and_bookmark_status/<illust_id>')
def get_illust_details_and_bookmark_status_api_route(illust_id: str):
    """
    Получает детальную информацию об иллюстрации, включая статус закладки, ID закладки,
    имя автора и теги.
    """
    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid:
        if not load_config() or not CONFIG.get('PHPSESSID'): return jsonify({'error': f'PHPSESSID not in {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    api_url = f"https://www.pixiv.net/ajax/illust/{illust_id}" # API для деталей иллюстрации
    app.logger.debug(f"API /illust_details: ID {illust_id}, URL: {api_url}")
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': f'https://www.pixiv.net/artworks/{illust_id}',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    try:
        resp = requests.get(api_url, headers=headers, cookies=cookies, timeout=10)
        resp.raise_for_status()
        if 'login.php' in resp.url or 'accounts.pixiv.net' in resp.url:
            return jsonify({'error': f'Auth error for illust details {illust_id} (redirected to login).'}), 401
        
        data = resp.json()
        if data.get("error"):
            app.logger.error(f"API /illust_details: Pixiv API error for {illust_id}: {data.get('message')}")
            return jsonify({"error": data.get("message", "Pixiv API error (details)")}), 200

        body = data.get('body', {})
        is_bookmarked = False
        bookmark_id_val = None
        
        # Статус закладки и ID закладки
        if isinstance(body.get('isBookmarked'), bool): # Прямой флаг
            is_bookmarked = body['isBookmarked']
        
        bookmark_data_obj = body.get('bookmarkData') # Объект с данными о закладке
        if isinstance(bookmark_data_obj, dict):
            is_bookmarked = True # Наличие bookmarkData означает, что работа в закладках
            bookmark_id_val = bookmark_data_obj.get('id')

        user_name = body.get('userName', "N/A")
        user_id = body.get('userId')
        
        tags_list = []
        tags_data_container = body.get('tags')
        if tags_data_container and isinstance(tags_data_container.get('tags'), list):
            unique_tags_for_illust = set() # Для избежания дубликатов тегов (оригинал + перевод)
            for tag_data in tags_data_container['tags']:
                original_tag = tag_data.get('tag')
                if original_tag:
                    unique_tags_for_illust.add(original_tag)
                    # Добавляем перевод, если он есть и отличается от оригинала
                    if tag_data.get('translation') and isinstance(tag_data['translation'], dict):
                        translated_tag = tag_data['translation'].get('en')
                        if translated_tag and translated_tag.lower() != original_tag.lower():
                            unique_tags_for_illust.add(f"{original_tag} ({translated_tag})")
            tags_list = sorted(list(unique_tags_for_illust)) # Сортируем для единообразия

        app.logger.debug(f"API /illust_details parsed for {illust_id}: bookmarked={is_bookmarked}, bookmark_id={bookmark_id_val}, user='{user_name}', tags_count={len(tags_list)}")
        return jsonify({
            'illust_id': illust_id,
            'is_bookmarked': is_bookmarked,
            'bookmark_id': str(bookmark_id_val) if bookmark_id_val else None,
            'user_name': user_name,
            'user_id': str(user_id) if user_id else None,
            'tags': tags_list
        })
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API /illust_details: Network error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Network error (details): {e}'}), 500
    except Exception as e:
        app.logger.error(f"API /illust_details: General error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Server error (details): {e}'}), 500

@app.route('/api/bookmark', methods=['POST'])
def toggle_bookmark_api_route():
    """
    Обрабатывает добавление или удаление иллюстрации из закладок Pixiv.
    Требует illust_id, action ('add'/'delete'), csrf_token.
    Для 'delete' также требуется bookmark_id.
    """
    client_data = request.json
    illust_id = client_data.get('illust_id')
    action = client_data.get('action')
    csrf_token_client = client_data.get('csrf_token')
    bookmark_id_from_client = client_data.get('bookmark_id') # Используется только для 'delete'

    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid:
        if not load_config() or not CONFIG.get('PHPSESSID'):
            return jsonify({'error': f'PHPSESSID not in {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    # Валидация входных параметров
    if not all([illust_id, action, csrf_token_client]):
        return jsonify({'error': 'Missing required parameters (illust_id, action, csrf_token).'}), 400
    if action not in ['add', 'delete']:
        return jsonify({'error': 'Invalid action specified.'}), 400
    if action == 'delete' and not bookmark_id_from_client:
        app.logger.warning(f"API /bookmark: Missing bookmark_id for delete action on illust_id {illust_id}.")
        return jsonify({'error': 'Missing bookmark_id for delete action. Please ensure details are fetched.'}), 400

    # Общие заголовки и куки для запроса к Pixiv
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': f'https://www.pixiv.net/artworks/{illust_id}', # Referer важен
        'X-CSRF-Token': csrf_token_client, # CSRF-токен от клиента
        'Accept': 'application/json', # Ожидаем JSON в ответе
        'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    
    api_url = ""
    payload_for_request = {}
    use_form_data = False # Флаг для определения типа Content-Type и способа передачи payload

    if action == 'add':
        api_url = 'https://www.pixiv.net/ajax/illusts/bookmarks/add'
        headers['Content-Type'] = 'application/json; charset=utf-8' # Для добавления используется JSON
        payload_for_request = {"illust_id": str(illust_id), "restrict": 0, "comment": "", "tags": []}
        app.logger.debug(f"API /bookmark ADD: IllustID {illust_id}, CSRF: {csrf_token_client[:10]}..., Payload: {json.dumps(payload_for_request)}")
    
    elif action == 'delete':
        api_url = 'https://www.pixiv.net/ajax/illusts/bookmarks/delete'
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8' # Для удаления - form-urlencoded
        payload_for_request = {'bookmark_id': str(bookmark_id_from_client)}
        use_form_data = True
        app.logger.debug(f"API /bookmark DELETE: IllustID {illust_id} (using BookmarkID {bookmark_id_from_client}), CSRF: {csrf_token_client[:10]}..., Payload: {payload_for_request}")

    try:
        # Отправка запроса в зависимости от use_form_data
        if use_form_data:
            resp = requests.post(api_url, headers=headers, cookies=cookies, data=payload_for_request, timeout=10)
        else:
            resp = requests.post(api_url, headers=headers, cookies=cookies, json=payload_for_request, timeout=10)
        
        response_body_sample = resp.text[:500] # Для логирования части ответа
        app.logger.debug(
            f"API /bookmark response for '{action}' ID {illust_id} - Status: {resp.status_code}, "
            f"Body Sample: {response_body_sample}"
        )

        # Обработка ошибок HTTP от Pixiv
        if resp.status_code >= 400:
            try:
                res_json_error = resp.json()
                error_message = res_json_error.get('message', res_json_error.get('error', 'Unknown Pixiv error'))
            except json.JSONDecodeError: # Если ответ не JSON
                error_message = response_body_sample if response_body_sample else f"Pixiv API Error {resp.status_code}"
            app.logger.error(f"API /bookmark: Pixiv API error ({resp.status_code}) for '{action}' ID {illust_id}. Message: '{error_message}'. Payload: {payload_for_request}")
            return jsonify({'success': False, 'error': error_message}), resp.status_code

        # Обработка успешных ответов (2xx)
        res_json = resp.json()
        response_to_client_data = {'success': True, 'message': res_json.get('message', 'Success')}

        if res_json.get('error'): # Если Pixiv вернул 200 OK, но с флагом error:true
            msg = res_json.get('message', 'Pixiv indicated an error despite 2xx status.')
            if action == 'add' and ("Уже добавлено" in msg or "Already bookmarked" in msg.lower()):
                app.logger.info(f"API /bookmark: IllustID {illust_id} already bookmarked. Pixiv msg: {msg}")
                response_to_client_data.update({'message': f'State already "{action}"', 'already_bookmarked': True})
            else: # Другая ошибка с флагом error:true
                app.logger.error(f"API /bookmark: Pixiv error (2xx with error:true): {msg} for {action} ID {illust_id}. Payload: {payload_for_request}")
                return jsonify({'success': False, 'error': msg}), 200 # Возвращаем 200, но с ошибкой в теле
        
        # Если это успешное добавление, извлекаем last_bookmark_id
        if action == 'add' and not res_json.get('error'):
            if res_json.get('body') and isinstance(res_json['body'], dict):
                last_bookmark_id = res_json['body'].get('last_bookmark_id')
                if last_bookmark_id:
                    response_to_client_data['last_bookmark_id'] = str(last_bookmark_id)
                    app.logger.info(f"API /bookmark ADD: IllustID {illust_id} - Acquired last_bookmark_id: {last_bookmark_id}")
        
        app.logger.info(f"API /bookmark: Success for '{action}' ID {illust_id}. Response to client: {response_to_client_data}")
        return jsonify(response_to_client_data)

    except requests.exceptions.HTTPError as e_http: # Ловит ошибки, если raise_for_status был бы вызван (оставлено на всякий случай)
        # Этот блок может быть избыточен, если все HTTP ошибки обрабатываются выше
        status_code = e_http.response.status_code if e_http.response is not None else 500
        error_text = e_http.response.text[:200] if e_http.response is not None else str(e_http)
        app.logger.error(f"API /bookmark: HTTPError {status_code} during '{action}' for ID {illust_id}. Details: {error_text}", exc_info=True)
        return jsonify({'success': False, 'error': f"Pixiv HTTP Error: {status_code} - {error_text}"}), status_code
    except requests.exceptions.RequestException as e_req: # Сетевые ошибки
        app.logger.error(f"API /bookmark: Network error during '{action}' for ID {illust_id}: {e_req}", exc_info=True)
        return jsonify({'success': False, 'error': f'Network Error: {str(e_req)}'}), 500
    except Exception as e_gen: # Другие непредвиденные ошибки
        app.logger.error(f"API /bookmark: General error during '{action}' for ID {illust_id}: {e_gen}", exc_info=True)
        return jsonify({'success': False, 'error': f'Server error: {str(e_gen)}'}), 500

@app.route('/api/user_bookmarks')
def get_user_bookmarks_api_route():
    """Получает список закладок пользователя, указанного в CONFIG['USER_ID']."""
    offset_str = request.args.get('offset', '0')
    try:
        offset = int(offset_str)
    except ValueError:
        app.logger.warning(f"API /user_bookmarks: Invalid offset value '{offset_str}', using 0.")
        offset = 0

    phpsessid = CONFIG.get('PHPSESSID')
    user_id = CONFIG.get('USER_ID') # USER_ID должен быть в конфиге для этой функции

    if not phpsessid or not user_id:
        if not load_config() or not CONFIG.get('PHPSESSID') or not CONFIG.get('USER_ID'):
            return jsonify({'error': f'PHPSESSID или USER_ID не настроены в {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID') # Повторное получение после load_config
        user_id = CONFIG.get('USER_ID')

    # URL API Pixiv для получения списка закладок пользователя
    bookmarks_api_url = f"https://www.pixiv.net/ajax/user/{user_id}/illusts/bookmarks?tag=&offset={offset}&limit={BOOKMARKS_API_LIMIT}&rest=show"
    app.logger.debug(f"API /user_bookmarks: Requesting URL: {bookmarks_api_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': f'https://www.pixiv.net/users/{user_id}/bookmarks/artworks', # Важный Referer
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    
    illusts_meta = []
    try:
        response_api = requests.get(bookmarks_api_url, headers=headers, cookies=cookies, timeout=15)
        response_api.raise_for_status()
        if 'login.php' in response_api.url or 'accounts.pixiv.net' in response_api.url:
            return jsonify({'error': 'Auth error when requesting user bookmarks (redirected to login).'}), 401

        data = response_api.json()

        if data.get("error"):
            error_message = data.get("message", "Pixiv API returned an error for user bookmarks.")
            # Проверка на "конец списка" или отсутствие закладок
            if "ブックマークは存在しません" in error_message or "No bookmarks found" in error_message.lower() or "該当件数0件" in error_message:
                app.logger.info(f"API /user_bookmarks: No more bookmarks for user {user_id}. Pixiv msg: {error_message}")
                return jsonify({'images': [], 'total_bookmarks': data.get('body', {}).get('total', 0)}) # total может быть 0
            app.logger.error(f"API /user_bookmarks: Pixiv API error: {error_message}")
            return jsonify({'images': [], 'error_message': error_message}) # Возвращаем пустой список и ошибку

        if data.get('body') and isinstance(data['body'].get('works'), list):
            raw_illust_list = data['body']['works']
            for item in raw_illust_list:
                bookmark_data = item.get('bookmarkData') # Ожидается, что это поле есть
                bookmark_id_val = bookmark_data.get('id') if isinstance(bookmark_data, dict) else None

                illusts_meta.append({
                    'id': str(item.get('id')),
                    'title': item.get('title', 'N/A'),
                    'preview_url_p0': item.get('url'), # URL для превью из списка
                    'page_count': item.get('pageCount', 1),
                    'is_bookmarked': True, # Всегда True, так как это список закладок
                    'bookmark_id': str(bookmark_id_val) if bookmark_id_val else None,
                    'width': item.get('width'), 
                    'height': item.get('height'),
                    # 'author_name': item.get('userName'), 
                    # 'author_id': str(item.get('userId')) if item.get('userId') else None,
                })
            app.logger.debug(f"API /user_bookmarks: Parsed {len(illusts_meta)} bookmarked illusts. Total reported by API: {data.get('body', {}).get('total')}")
        else:
            app.logger.warning(f"API /user_bookmarks: Unexpected API response structure: {str(data)[:300]}...")
        
        return jsonify({'images': illusts_meta, 'total_bookmarks': data.get('body', {}).get('total')})

    except requests.exceptions.RequestException as e:
        app.logger.error(f"API /user_bookmarks: Network error: {e}", exc_info=True)
        return jsonify({'images': [], 'error_message': f'Network error: {e}'}), 500
    except Exception as e:
        app.logger.error(f"API /user_bookmarks: General error: {e}", exc_info=True)
        return jsonify({'images': [], 'error_message': f'Server error: {e}'}), 500

if __name__ == '__main__':
    # Настройка логирования
    log_level_str = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
    log_level = getattr(logging, log_level_str, logging.DEBUG)
    
    app.logger.setLevel(log_level)
    if not app.logger.handlers: # Предотвращаем дублирование хендлеров при перезагрузке Flask
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s PID:%(process)d %(levelname)s: %(message)s [in %(module)s:%(lineno)d]'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

    # Загрузка конфигурации при старте
    if not load_config():
        app.logger.critical(f"Failed to load configuration from {CONFIG_FILE}. Application might not work as expected.")
    
    app.logger.info(f"Starting Pixiv Viewer (Log Level: {log_level_str})...")
    
    # Создание необходимых директорий и файлов-заглушек, если они отсутствуют
    # Это полезно для первого запуска или развертывания.
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    placeholder_files = ["templates/index.html", "static/css/style.css", "static/js/main.js"]
    for p_file in placeholder_files:
        if not os.path.exists(p_file):
            try:
                with open(p_file, "w", encoding="utf-8") as f:
                    f.write(f"<!-- Placeholder for {os.path.basename(p_file)} -->\n")
                app.logger.info(f"Created placeholder file: {p_file}")
            except Exception as e_create_placeholder:
                app.logger.error(f"Could not create placeholder file {p_file}: {e_create_placeholder}")

    # Запуск Flask-приложения
    # use_reloader=True удобно для разработки, автоматически перезагружает сервер при изменениях кода.
    # debug=True включает отладчик Flask и более подробные сообщения об ошибках.
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=True)