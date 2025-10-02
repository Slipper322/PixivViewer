from ipaddress import ip_address
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import requests
from bs4 import BeautifulSoup
import json
import re
import os
import logging

BOOKMARKS_API_LIMIT = 48 # Сколько закладок запрашивать за раз у Pixiv
AUTHOR_ALIASES_FILE = 'author_aliases.json'
AUTHOR_ALIASES = {} # Словарь для хранения алиасов {user_id: alias}

app = Flask(__name__)

CONFIG_FILE = 'config.json'
CONFIG = {}
TIME_OUT = 30
DEF_COVER_SIZE = "360x360"
def load_config():
    global CONFIG
    try:
        with open(CONFIG_FILE, 'r') as f:
            CONFIG = json.load(f)
        if not CONFIG.get('PHPSESSID'):
            app.logger.warning(f"PHPSESSID не найден или пуст в {CONFIG_FILE}. Приложение может не работать корректно.")
            return False
        app.logger.info(f"Конфигурация из {CONFIG_FILE} успешно загружена.")
        return True
    except FileNotFoundError:
        app.logger.error(f"Файл конфигурации {CONFIG_FILE} не найден. Создайте его с вашим PHPSESSID.")
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

def load_author_aliases():
    """Загружает псевдонимы авторов из файла AUTHOR_ALIASES_FILE."""
    global AUTHOR_ALIASES
    try:
        with open(AUTHOR_ALIASES_FILE, 'r', encoding='utf-8') as f:
            AUTHOR_ALIASES = json.load(f)
        app.logger.info(f"Псевдонимы авторов из {AUTHOR_ALIASES_FILE} успешно загружены. Найдено: {len(AUTHOR_ALIASES)} записей.")
        # Убедимся, что все ключи (user_id) являются строками, как они приходят от API Pixiv
        AUTHOR_ALIASES = {str(k): v for k, v in AUTHOR_ALIASES.items()}
    except FileNotFoundError:
        app.logger.warning(f"Файл псевдонимов авторов {AUTHOR_ALIASES_FILE} не найден. Псевдонимы использоваться не будут.")
        AUTHOR_ALIASES = {} # Оставляем пустым, если файла нет
        # Можно создать файл-заглушку, если хотите
        # try:
        #     with open(AUTHOR_ALIASES_FILE, 'w', encoding='utf-8') as f:
        #         json.dump({"12345": "Пример Псевдонима"}, f, indent=4, ensure_ascii=False)
        #     app.logger.info(f"Создан файл-заглушка для псевдонимов: {AUTHOR_ALIASES_FILE}")
        # except Exception as e:
        #     app.logger.error(f"Не удалось создать файл-заглушку {AUTHOR_ALIASES_FILE}: {e}")
    except json.JSONDecodeError:
        app.logger.error(f"Ошибка декодирования JSON в файле псевдонимов {AUTHOR_ALIASES_FILE}. Псевдонимы не загружены.")
        AUTHOR_ALIASES = {}
    except Exception as e:
        app.logger.error(f"Неизвестная ошибка при загрузке псевдонимов авторов: {e}", exc_info=True)
        AUTHOR_ALIASES = {}

def get_author_display_name(user_id: str | None, user_name: str | None) -> str:
    """
    Возвращает отображаемое имя автора.
    Если для user_id есть алиас, возвращает "Алиас (Оригинальное Имя)".
    Иначе возвращает оригинальное имя или "N/A".
    """
    if not user_name:
        user_name = "N/A"
    
    if user_id:
        user_id_str = str(user_id) # Убедимся, что ID - строка для поиска в словаре
        alias = AUTHOR_ALIASES.get(user_id_str)
        if alias:
            # Если оригинальное имя уже содержится в алиасе (например, "Alias (OriginalName)"), не дублируем
            #if user_name != "N/A" and user_name.lower() in alias.lower():
            return alias
            #return f"{alias} ({user_name})" if user_name != "N/A" else alias
    return user_name

def extract_csrf_from_html(html_content):
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
                    app.logger.debug(f"(extract_csrf): CSRF Token from __NEXT_DATA__: {csrf_token}")
                else:
                    app.logger.debug("(extract_csrf): CSRF Token NOT in preloaded_state.api.token")
            else:
                app.logger.debug("(extract_csrf): __NEXT_DATA__ no serverSerializedPreloadedState.")
        except Exception as e:
            app.logger.error(f"(extract_csrf): Error processing __NEXT_DATA__: {e}", exc_info=True)
    
    if not csrf_token:
        csrf_meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if csrf_meta_tag and csrf_meta_tag.get('content'):
            csrf_token = csrf_meta_tag['content']
            app.logger.debug(f"(extract_csrf): CSRF Token from meta tag: {csrf_token}")
    
    if not csrf_token:
        app.logger.warning("(extract_csrf): CSRF Token not extracted.")
    return csrf_token

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/images') # Режим "Новое от подписок"
def get_images_api_route():
    page_num_str = request.args.get('page', '1')
    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid:
        if not load_config() or not CONFIG.get('PHPSESSID'):
            return jsonify({'error': f'PHPSESSID не настроен в {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    api_url = f"https://www.pixiv.net/ajax/follow_latest/illust?p={page_num_str}&mode=all"
    app.logger.debug(f"API /api/images: URL: {api_url}")
    headers = {
        'User-Agent': 'Mozilla/5.0', 'Referer': f'https://www.pixiv.net/bookmark_new_illust.php?p={page_num_str}',
        'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    
    csrf_token = None
    # CSRF токен нужен только для первой страницы, и только если мы его еще не получили или он устарел
    # На практике, CSRF для этого списка обычно не требуется, но оставим логику для page_num_str == '1'
    if page_num_str == '1': # Запрашиваем CSRF только на первой странице
        try:
            main_page_url = "https://www.pixiv.net/bookmark_new_illust.php" # или любая страница, где есть CSRF
            html_headers = {**headers, 'Accept': 'text/html,application/xhtml+xml'}
            if 'X-Requested-With' in html_headers: del html_headers['X-Requested-With']
            
            resp_main = requests.get(main_page_url, headers=html_headers, cookies=cookies, timeout=TIME_OUT)
            resp_main.raise_for_status()
            if 'login.php' in resp_main.url or 'accounts.pixiv.net' in resp_main.url:
                app.logger.warning("API /api/images: Auth error on CSRF fetch. Redirected to login.")
                # Не возвращаем ошибку здесь, так как CSRF может быть уже у клиента
                # или он может не понадобиться для этого конкретного запроса, если список все равно загрузится
            else:
                csrf_token = extract_csrf_from_html(resp_main.text)
                if csrf_token:
                    app.logger.info(f"API /api/images: CSRF token successfully extracted/updated on page 1.")
                else:
                    app.logger.warning("API /api/images: Failed to extract CSRF token on page 1, but continuing.")
        except Exception as e:
            app.logger.error(f"API /api/images: CSRF fetch error on page 1: {e}", exc_info=True)
            # Продолжаем без CSRF, если не удалось получить

    illusts_meta = []
    try:
        resp_api = requests.get(api_url, headers=headers, cookies=cookies, timeout=TIME_OUT)
        resp_api.raise_for_status()
        if 'login.php' in resp_api.url or 'accounts.pixiv.net' in resp_api.url:
            return jsonify({'error': 'Auth error on images API.'}), 401
        data = resp_api.json()

        if data.get("error"):
            msg = data.get("message", "Pixiv API error.")
            # Логируем как info, если это ожидаемое сообщение о конце списка
            if "該当作品は存在しません" in msg or "no new illustrations" in msg.lower():
                app.logger.info(f"API /api/images: Pixiv msg (no more new illusts): {msg}")
            else:
                app.logger.error(f"API /api/images: Pixiv API error: {msg}")
            return jsonify({'images': [], 'csrf_token': csrf_token}) 

        # Обработка thumbnails.illust (как в вашем логе Файл 2)
        if data.get('body', {}).get('thumbnails', {}).get('illust'):
            for item in data['body']['thumbnails']['illust']:
                bookmark_data = item.get('bookmarkData')
                is_bookmarked_val = isinstance(bookmark_data, dict) and bookmark_data.get('id') is not None
                bookmark_id_val = bookmark_data.get('id') if is_bookmarked_val else None
                preview_url_to_use = item.get('url') # URL по умолчанию
                item_urls_dict = item.get('urls')
                original_user_name = item.get('userName')
                user_id_val = str(item.get('userId')) if item.get('userId') else None
                display_user_name = get_author_display_name(user_id_val, original_user_name)
                if isinstance(item_urls_dict, dict):
                    preview_size = CONFIG.get("MINI_COVER_SIZE")
                    if item_urls_dict.get(preview_size):
                        preview_url_to_use = item_urls_dict[preview_size]
                    elif item_urls_dict.get(DEF_COVER_SIZE):
                        preview_url_to_use = item_urls_dict[DEF_COVER_SIZE]
                    # Пытаемся получить более качественное превью
                    # Можно выбрать и '540x540', если '1200x1200' слишком тяжелое для сайдбара
                    # Для миниатюр 1200x1200 может быть избыточно, но дает больше гибкости при масштабировании
                    #if item_urls_dict.get('1200x1200'):
                    #    preview_url_to_use = item_urls_dict['1200x1200']
                    #elif item_urls_dict.get('540x540'): # Запасной вариант получше
                    #    preview_url_to_use = item_urls_dict['540x540']
                    #elif item_urls_dict.get('360x360'): # Еще один запасной
                    #    preview_url_to_use = item_urls_dict['360x360']
                    # Если ничего из этого нет, останется preview_url_to_use = item.get('url')
                illusts_meta.append({
                    'id': str(item.get('id')),
                    'title': item.get('title', 'N/A'),
                    'preview_url_p0': preview_url_to_use, # Используем выбранный URL
                    'page_count': item.get('pageCount', 1),
                    'is_bookmarked': is_bookmarked_val,
                    'bookmark_id': str(bookmark_id_val) if bookmark_id_val else None, # ID самой закладки
                    'width': item.get('width'),
                    'height': item.get('height'),
                    'author_name': display_user_name, 
                    'author_id': user_id_val
                })
            app.logger.debug(f"API /api/images: Parsed {len(illusts_meta)} illusts.")
        else:
            app.logger.warning(f"API /api/images: Unexpected API response structure: {str(data)[:200]}")
        
        return jsonify({'images': illusts_meta, 'csrf_token': csrf_token})
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API /api/images: Network error: {e}", exc_info=True)
        return jsonify({'error': f'Network: {e}', 'csrf_token': csrf_token}), 500
    except Exception as e:
        app.logger.error(f"API /api/images: General error: {e}", exc_info=True)
        return jsonify({'error': f'Server: {e}', 'csrf_token': csrf_token}), 500

@app.route('/api/illust_pages/<illust_id>')
def get_illust_pages_api_route(illust_id):
    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid: # Duplicated logic, consider a decorator or middleware for PHPSESSID check
        if not load_config() or not CONFIG.get('PHPSESSID'): return jsonify({'error': f'PHPSESSID not in {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    api_url = f"https://www.pixiv.net/ajax/illust/{illust_id}/pages"
    app.logger.debug(f"API /illust_pages: ID {illust_id}, URL: {api_url}")
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': f'https://www.pixiv.net/artworks/{illust_id}', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    cookies = {'PHPSESSID': phpsessid}
    pages_info = []
    try:
        resp = requests.get(api_url, headers=headers, cookies=cookies, timeout=TIME_OUT)
        resp.raise_for_status()
        if 'login.php' in resp.url or 'accounts.pixiv.net' in resp.url: return jsonify({'error': f'Auth error for illust pages {illust_id}.'}), 401
        data = resp.json()
        if data.get("error"):
            app.logger.error(f"API /illust_pages: Pixiv error for {illust_id}: {data.get('message')}")
            return jsonify({"error": data.get("message", "Pixiv API error for pages")}), 200 
        
        if data.get('body') and isinstance(data['body'], list):
            for page in data['body']:
                if page.get('urls') and isinstance(page['urls'], dict):
                    pages_info.append({
                        'url_master': page['urls'].get('regular'),
                        'url_original': page['urls'].get('original'),
                        'width': page.get('width'), 'height': page.get('height')
                    })
            app.logger.debug(f"API /illust_pages: Found {len(pages_info)} pages for {illust_id}")
        else:
            app.logger.warning(f"API /illust_pages: Unexpected struct for {illust_id}: {str(data)[:200]}")
        return jsonify({'pages_data': pages_info})
    except requests.exceptions.RequestException as e: # Catch more specific exceptions first
        app.logger.error(f"API /illust_pages: Network error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Network (pages): {e}'}), 500
    except Exception as e:
        app.logger.error(f"API /illust_pages: General error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Server (pages): {e}'}), 500

@app.route('/api/image_proxy')
def image_proxy():
    image_url_param = request.args.get('image_url')
    illust_id_param = request.args.get('illust_id') # illust_id для Referer
    force_download = request.args.get('download', 'false').lower() == 'true'
    # Получаем PHPSESSID из конфигурации сервера
    phpsessid_config = CONFIG.get('PHPSESSID')
    if not phpsessid_config:
        # Попытка загрузить конфиг, если он не был загружен или PHPSESSID пуст
        if not load_config() or not CONFIG.get('PHPSESSID'):
            app.logger.error("PROXY: PHPSESSID не настроен на сервере.")
            return "PHPSESSID не настроен на сервере.", 503 # Service Unavailable
        phpsessid_config = CONFIG.get('PHPSESSID')
    
    if not image_url_param:
        app.logger.warning("PROXY: Отсутствует параметр image_url.")
        return "Отсутствует параметр image_url", 400
    
    # Куки для запроса к Pixiv
    proxy_cookies = {}
    if phpsessid_config:
        proxy_cookies['PHPSESSID'] = phpsessid_config

    # Заголовки для запроса изображения к Pixiv
    headers_for_pixiv_image = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    # Добавляем Referer только если есть illust_id_param, для оригиналов он критичен
    if illust_id_param:
        headers_for_pixiv_image['Referer'] = f'https://www.pixiv.net/artworks/{illust_id_param}'
    
    app.logger.debug(f"PROXY: Запрос изображения: {image_url_param} с Referer: {headers_for_pixiv_image.get('Referer', 'None')}")

    try:
        # Используем stream=True для эффективной передачи больших файлов
        pixiv_response = requests.get(
            image_url_param,
            headers=headers_for_pixiv_image,
            cookies=proxy_cookies,
            stream=True,
            timeout=TIME_OUT # Увеличим таймаут для больших изображений
        )
        pixiv_response.raise_for_status() # Проверка на HTTP ошибки от Pixiv (4xx, 5xx)

        # Получаем Content-Type от ответа Pixiv, чтобы передать его клиенту
        content_type = pixiv_response.headers.get('Content-Type', 'application/octet-stream')
        
        # Формирование имени файла для Content-Disposition
        filename = "pixiv_image" # Имя по умолчанию
        try:
            # Пытаемся извлечь имя файла из URL
            # Пример URL: https://i.pximg.net/img-original/img/2023/05/09/00/00/00/12345678_p0.png
            parsed_url_path = requests.utils.urlparse(image_url_param).path
            original_filename_match = re.search(r'/([^/]+)$', parsed_url_path)
            if original_filename_match:
                potential_filename = original_filename_match.group(1).split('?')[0]
                if re.match(r'^\d+(_p\d+)?(_(master|square|custom)\d+)?(_\d{1,2})?\.\w+$', potential_filename, re.IGNORECASE):
                    filename = potential_filename
                    app.logger.debug(f"PROXY: Successfully parsed filename: {filename}")
                else:
                    app.logger.warning(
                        f"PROXY: Extracted filename '{potential_filename}' does not fully match "
                        f"the expected Pixiv filename pattern (e.g., ID_pX_masterYYYY.ext or ID.ext). "
                        f"Using default filename 'pixiv_image'."
                    )
            app.logger.debug(f"PROXY: Определено имя файла: {filename}")
        except Exception as e_fn:
            app.logger.warning(f"PROXY: Не удалось определить имя файла из URL {image_url_param}: {e_fn}")

        # Создаем объект Response Flask
        response_to_client = Response(
            stream_with_context(pixiv_response.iter_content(chunk_size=16384)), # Увеличим chunk_size
            content_type=content_type
        )
        
        # Устанавливаем заголовок для отображения с именем (или для скачивания, если браузер решит)
        # "inline" говорит браузеру попытаться отобразить файл, если он может.
        # Для прямого скачивания используется "attachment".
        #response_to_client.headers["Content-Disposition"] = f"inline; filename=\"{filename}\""
        # Для прямого скачивания используется "attachment".            
        disposition_type = "attachment" if force_download else "inline"
        response_to_client.headers["Content-Disposition"] = f"{disposition_type}; filename=\"{filename}\""
        if force_download:
            app.logger.debug(f"PROXY: Forcing download for {filename}")
        return response_to_client

    except requests.exceptions.HTTPError as e_http_proxy:
        error_msg_proxy = f"Proxy HTTP Error {e_http_proxy.response.status_code} для {image_url_param}"
        # Логируем больше деталей об ошибке от Pixiv
        try:
            error_details = e_http_proxy.response.text[:500] # Первые 500 символов ответа
            app.logger.error(f"PROXY HTTP Error: {error_msg_proxy}. Response body from Pixiv: {error_details}")
        except Exception:
            app.logger.error(f"PROXY HTTP Error: {error_msg_proxy}. Could not read response body.")
        # Возвращаем ошибку с тем же кодом, что и от Pixiv, и частью сообщения
        return f"{error_msg_proxy}: {e_http_proxy.response.reason}", e_http_proxy.response.status_code 
    except requests.exceptions.Timeout:
        app.logger.error(f"PROXY: Timeout при запросе {image_url_param}")
        return "Proxy: Timeout при запросе изображения от Pixiv", 504 # Gateway Timeout
    except requests.exceptions.RequestException as e_req_proxy:
        error_msg_proxy = f"Proxy Network Error для {image_url_param}: {str(e_req_proxy)}"
        app.logger.error(f"PROXY: {error_msg_proxy}", exc_info=True)
        return error_msg_proxy, 502 # Bad Gateway
    except Exception as e_exc_proxy:
        app.logger.error(f"PROXY: Unexpected Error для {image_url_param}: {str(e_exc_proxy)}", exc_info=True)
        return f"Proxy Unexpected Error: {str(e_exc_proxy)}", 500

@app.route('/api/illust_details_and_bookmark_status/<illust_id>')
def get_illust_details_and_bookmark_status_api_route(illust_id):
    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid:
        if not load_config() or not CONFIG.get('PHPSESSID'): return jsonify({'error': f'PHPSESSID not in {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    api_url = f"https://www.pixiv.net/ajax/illust/{illust_id}"
    app.logger.debug(f"API /illust_details: ID {illust_id}, URL: {api_url}")
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': f'https://www.pixiv.net/artworks/{illust_id}', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    cookies = {'PHPSESSID': phpsessid}
    try:
        resp = requests.get(api_url, headers=headers, cookies=cookies, timeout=TIME_OUT)
        resp.raise_for_status()
        if 'login.php' in resp.url or 'accounts.pixiv.net' in resp.url: return jsonify({'error': f'Auth error for illust details {illust_id}.'}), 401
        data = resp.json()
        if data.get("error"):
            app.logger.error(f"API /illust_details: Pixiv API error for {illust_id}: {data.get('message')}")
            return jsonify({"error": data.get("message", "Pixiv API error for details")}), 200

        is_bookmarked = False
        bookmark_id_val = None # Новое поле для bookmark_id
        user_name = "N/A"
        user_id = None
        tags_list = []

        if data.get('body'):
            body = data['body']
            if isinstance(body.get('isBookmarked'), bool): is_bookmarked = body['isBookmarked']
            
            if body.get('bookmarkData') is not None and isinstance(body['bookmarkData'], dict):
                is_bookmarked = True # Если есть bookmarkData, значит в закладках
                bookmark_id_val = body['bookmarkData'].get('id') # Получаем ID закладки

            #user_name = body.get('userName', "N/A")
            #user_id = body.get('userId')
            original_user_name = body.get('userName', "N/A")
            user_id_val = str(body.get('userId')) if body.get('userId') else None
            display_user_name = get_author_display_name(user_id_val, original_user_name)
            if body.get('tags') and isinstance(body['tags'].get('tags'), list):
                for tag_data in body['tags']['tags']:
                    original_tag = tag_data.get('tag', 'unknown')
                    #tags_list.append(original_tag) # Всегда добавляем оригинальный тег
                    if tag_data.get('translation') and isinstance(tag_data['translation'], dict):
                        translated_tag = tag_data['translation'].get('en')
                        if translated_tag and translated_tag.lower() != original_tag.lower(): # Добавляем перевод, если он есть и отличается
                            tags_list.append(f"{original_tag} ({translated_tag})")
                        else:
                            tags_list.append(original_tag)  # Добавляем только оригинальный тег, если перевод отсутствует или совпадает
                    else:
                        romaji_tag = tag_data.get('romaji')
                        if romaji_tag:
                            tags_list.append(f"{original_tag} ({romaji_tag})")  # Если есть romaji, добавляем его в скобках
                        else:
                            tags_list.append(original_tag)  # Если нет ни перевода, ни romaji, добавляем только оригинальный тег
        app.logger.debug(f"API /illust_details: Tags for {illust_id}: {tags_list}")
        app.logger.debug(f"API /illust_details: {illust_id}, bookmarked: {is_bookmarked}, bookmark_id: {bookmark_id_val}, user: {user_name}, tags: {len(tags_list)}")
        return jsonify({
            'illust_id': illust_id,
            'is_bookmarked': is_bookmarked,
            'bookmark_id': bookmark_id_val, # Возвращаем bookmark_id клиенту
            'user_name': display_user_name,
            'user_id': user_id_val,
            'tags': list(dict.fromkeys(tags_list)) # Убираем дубликаты, если оригинальный тег и перевод одинаковы
        })
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API /illust_details: Network error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Network (details): {e}'}), 500
    except Exception as e:
        app.logger.error(f"API /illust_details: General error for {illust_id}: {e}", exc_info=True)
        return jsonify({'error': f'Server (details): {e}'}), 500

@app.route('/api/bookmark', methods=['POST'])
def toggle_bookmark_api_route():
    client_data = request.json
    illust_id = client_data.get('illust_id')
    action = client_data.get('action')
    csrf_token_client = client_data.get('csrf_token')
    bookmark_id_from_client = client_data.get('bookmark_id')

    phpsessid = CONFIG.get('PHPSESSID')
    if not phpsessid:
        if not load_config() or not CONFIG.get('PHPSESSID'):
            return jsonify({'error': f'PHPSESSID not in {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')

    if not all([illust_id, action, csrf_token_client]):
        return jsonify({'error': 'Missing params (illust_id, action, csrf_token)'}), 400
    if action not in ['add', 'delete']:
        return jsonify({'error': 'Invalid action'}), 400
    if action == 'delete' and not bookmark_id_from_client:
        app.logger.warning(f"API /bookmark: Missing bookmark_id for delete action on illust_id {illust_id}")
        return jsonify({'error': 'Missing bookmark_id for delete action. Try fetching details first.'}), 400

    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': f'https://www.pixiv.net/artworks/{illust_id}',
        'X-CSRF-Token': csrf_token_client,
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    
    api_url = ""
    payload_for_request = {}
    use_form_data = False
    response_to_client_data = {} # Для передачи данных клиенту, например, нового bookmark_id

    if action == 'add':
        api_url = 'https://www.pixiv.net/ajax/illusts/bookmarks/add'
        headers['Content-Type'] = 'application/json; charset=utf-8'
        payload_for_request = {
            "illust_id": str(illust_id),
            "restrict": 0, "comment": "", "tags": []
        }
        app.logger.debug(f"API /bookmark ADD: ID {illust_id}, CSRF: {csrf_token_client[:10]}..., Payload: {json.dumps(payload_for_request)}")
    
    elif action == 'delete':
        api_url = 'https://www.pixiv.net/ajax/illusts/bookmarks/delete'
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8'
        payload_for_request = {'bookmark_id': str(bookmark_id_from_client)}
        use_form_data = True
        app.logger.debug(f"API /bookmark DELETE: illust_id {illust_id}, bookmark_id {bookmark_id_from_client}, CSRF: {csrf_token_client[:10]}..., Payload: {payload_for_request}")

    try:
        if use_form_data:
            resp = requests.post(api_url, headers=headers, cookies=cookies, data=payload_for_request, timeout=TIME_OUT)
        else: # action == 'add'
            resp = requests.post(api_url, headers=headers, cookies=cookies, json=payload_for_request, timeout=TIME_OUT)
        
        response_body_sample = resp.text[:1000]
        app.logger.debug(
            f"API /bookmark response for '{action}' ID {illust_id} (bookmark_id: {bookmark_id_from_client if action == 'delete' else 'N/A'}) - Status: {resp.status_code}, "
            f"Content-Type: {resp.headers.get('Content-Type')}, Body Sample: {response_body_sample}"
        )

        if resp.status_code >= 400:
            try:
                res_json_error = resp.json()
                error_message_from_pixiv = res_json_error.get('message', res_json_error.get('error', 'Unknown Pixiv error structure'))
                app.logger.error(f"API /bookmark: Pixiv API error ({resp.status_code}) for '{action}' ID {illust_id}. Message: {error_message_from_pixiv}. Sent Payload: {payload_for_request}")
                return jsonify({'success': False, 'error': error_message_from_pixiv}), resp.status_code
            except json.JSONDecodeError:
                app.logger.error(f"API /bookmark: Pixiv API error ({resp.status_code}) for '{action}' ID {illust_id}. Response not JSON: {response_body_sample}. Sent Payload: {payload_for_request}")
                return jsonify({'success': False, 'error': f'Pixiv API Error ({resp.status_code}): {response_body_sample[:100]}'}), resp.status_code

        res_json = resp.json()
        
        if res_json.get('error'):
            msg = res_json.get('message', '')
            if action == 'add' and ("Уже добавлено" in msg or "Already bookmarked" in msg):
                app.logger.info(f"API /bookmark: ID {illust_id} state already '{action}'. Pixiv msg: {msg}")
                # Если уже добавлено, нам все равно нужен bookmark_id, если он есть в сообщении или мы можем его получить
                # Pixiv не возвращает last_bookmark_id в этом случае. Клиенту придется делать fetchAndUpdateDetailedInfo.
                return jsonify({'success': True, 'message': f'State already "{action}"', 'already_bookmarked': True})
            
            app.logger.error(f"API /bookmark: Pixiv error (2xx response with error flag): {msg} for {action} ID {illust_id}. Sent Payload: {payload_for_request}")
            return jsonify({'success': False, 'error': msg or 'Pixiv error (error flag in 2xx response)'}), 200

        # Успешный ответ от Pixiv (2xx и error:false)
        app.logger.info(f"API /bookmark: Success for '{action}' ID {illust_id}. Response: {res_json.get('message', str(res_json))}. Sent Payload: {payload_for_request}")
        
        response_to_client_data['success'] = True
        response_to_client_data['message'] = res_json.get('message', 'Success')

        if action == 'add' and res_json.get('body') and isinstance(res_json['body'], dict):
            last_bookmark_id = res_json['body'].get('last_bookmark_id')
            if last_bookmark_id:
                response_to_client_data['last_bookmark_id'] = last_bookmark_id
                app.logger.info(f"API /bookmark ADD: ID {illust_id} - Acquired last_bookmark_id: {last_bookmark_id}")
        
        return jsonify(response_to_client_data)

    # ... (except blocks remain largely the same, just ensure payload_for_request is in logs) ...
    except requests.exceptions.HTTPError as e_http: 
        err_msg_detail = "Pixiv HTTP Error"
        response_text_for_log = ""
        status_code_val = "N/A"
        if e_http.response is not None:
            status_code_val = e_http.response.status_code
            try:
                response_text_for_log = e_http.response.text[:500]
                err_json = e_http.response.json()
                err_msg_detail = err_json.get("message", err_json.get("error", response_text_for_log))
            except json.JSONDecodeError:
                err_msg_detail = response_text_for_log if response_text_for_log else str(e_http.response.reason)
        
        app.logger.error(
            f"API /bookmark: Unhandled HTTPError {status_code_val} during '{action}' for ID {illust_id}. "
            f"Pixiv Message: '{err_msg_detail}'. Full Response Sample: '{response_text_for_log}' Sent Payload: {payload_for_request}", 
            exc_info=False 
        )
        client_error_message = err_msg_detail if err_msg_detail != "Pixiv HTTP Error" else f"Pixiv API Error {status_code_val}"
        return jsonify({'success': False, 'error': client_error_message}), status_code_val if isinstance(status_code_val, int) else 500

    except requests.exceptions.RequestException as e_req:
        app.logger.error(f"API /bookmark: Network error during '{action}' for ID {illust_id}: {e_req}. Sent Payload: {payload_for_request}", exc_info=True)
        return jsonify({'success': False, 'error': f'Network Error: {str(e_req)}'}), 500
    
    except Exception as e_gen:
        app.logger.error(f"API /bookmark: General error during '{action}' for ID {illust_id}: {e_gen}. Sent Payload: {payload_for_request}", exc_info=True)
        return jsonify({'success': False, 'error': f'Server error: {str(e_gen)}'}), 500

@app.route('/api/user_bookmarks') # Режим "Закладки пользователя"
def get_user_bookmarks_api_route():
    offset_str = request.args.get('offset', '0')
    try:
        offset = int(offset_str)
    except ValueError:
        app.logger.warning(f"API /user_bookmarks: Invalid offset value: {offset_str}")
        offset = 0

    phpsessid = CONFIG.get('PHPSESSID')
    user_id = CONFIG.get('USER_ID')

    if not phpsessid or not user_id:
        if not load_config() or not CONFIG.get('PHPSESSID') or not CONFIG.get('USER_ID'):
            return jsonify({'error': f'PHPSESSID или USER_ID не настроены в {CONFIG_FILE}.'}), 503
        phpsessid = CONFIG.get('PHPSESSID')
        user_id = CONFIG.get('USER_ID')

    bookmarks_api_url = f"https://www.pixiv.net/ajax/user/{user_id}/illusts/bookmarks?tag=&offset={offset}&limit={BOOKMARKS_API_LIMIT}&rest=show"
    app.logger.debug(f"API /user_bookmarks: URL: {bookmarks_api_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': f'https://www.pixiv.net/users/{user_id}/bookmarks/artworks',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    cookies = {'PHPSESSID': phpsessid}
    
    illusts_meta = []
    try:
        response_api = requests.get(bookmarks_api_url, headers=headers, cookies=cookies, timeout=TIME_OUT)
        response_api.raise_for_status()
        if 'login.php' in response_api.url or 'accounts.pixiv.net' in response_api.url:
            return jsonify({'error': 'Ошибка авторизации при запросе закладок пользователя.'}), 401

        data = response_api.json()

        if data.get("error"):
            error_message = data.get("message", "Pixiv API закладок вернул ошибку.")
            app.logger.error(f"API /user_bookmarks: Pixiv API error: {error_message}")
            # Если это сообщение о конце списка, вернуть пустой список, а не ошибку
            if "ブックマークは存在しません" in error_message or "No bookmarks found" in error_message.lower() or \
            "該当件数0件" in error_message: # "0 results found"
                app.logger.info(f"API /user_bookmarks: No more bookmarks. Pixiv msg: {error_message}")
                return jsonify({'images': [], 'total_bookmarks': data.get('body', {}).get('total', 0)}) 
            return jsonify({'images': [], 'error_message': error_message})

        if data.get('body') and isinstance(data['body'].get('works'), list):
            raw_illust_list = data['body']['works']
            for item in raw_illust_list:
                bookmark_data = item.get('bookmarkData') # Это поле есть в ответе (см. Файл 1)
                # is_bookmarked здесь всегда true, так как это список закладок
                is_bookmarked_val = True 
                bookmark_id_val = bookmark_data.get('id') if isinstance(bookmark_data, dict) else None
                # Извлекаем теги из списка закладок (это будет список строк)
                tags_from_list = item.get('tags', []) 
                if not isinstance(tags_from_list, list): # На всякий случай проверка типа
                    tags_from_list = []
                original_user_name = item.get('userName')
                user_id_val = str(item.get('userId')) if item.get('userId') else None
                display_user_name = get_author_display_name(user_id_val, original_user_name)
                illusts_meta.append({
                    'id': str(item.get('id')),
                    'title': item.get('title', 'N/A'),
                    'preview_url_p0': item.get('url'), 
                    'page_count': item.get('pageCount', 1),
                    'is_bookmarked': is_bookmarked_val, 
                    'bookmark_id': str(bookmark_id_val) if bookmark_id_val else None, # ID самой закладки
                    'width': item.get('width'), 
                    'height': item.get('height'),
                    'author_name': display_user_name, 
                    'author_id': user_id_val,
                    'tags': tags_from_list # передаем теги из списка
                })
            app.logger.debug(f"API /user_bookmarks: Parsed {len(illusts_meta)} bookmarked illusts. Total reported by API: {data['body'].get('total')}")
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
    log_level = logging.DEBUG # Всегда DEBUG для разработки
    app.logger.setLevel(log_level)
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

    if not load_config():
        app.logger.critical(f"Failed to load config. App might not work.")
    load_author_aliases()
    app.logger.info("Starting Pixiv Viewer...")
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    # Simplified placeholder creation
    for p_file in ["templates/index.html", "static/css/style.css", "static/js/main.js"]:
        if not os.path.exists(p_file):
            with open(p_file, "w") as f: f.write(f"<!-- Placeholder for {os.path.basename(p_file)} -->\n")
    host_ip = CONFIG.get("IP", '0.0.0.0')
    host_port = CONFIG.get("PORT", 5000)
    app.run(debug=False, host=host_ip, port=host_port, use_reloader=False, ssl_context='adhoc') # use_reloader=True для удобства разработки