# PixivPreview Контекст и Идеи

## Текущая Архитектура проекта
PixivPreview - веб-приложение для просмотра иллюстраций с Pixiv в streamlined интерфейсе.

### Ключевые компоненты:
- **Backend (app.py)**: Flask-based, предоставляет API:
  - `/api/images` - список новых иллюстраций с подписок (paging).
  - `/api/user_bookmarks` - закладки пользователя (paging).
  - `/api/illust_pages/<id>` - массивы URL для страниц одного поста.
  - `/api/illust_details_and_bookmark_status/<id>` - мета-инфо (автор, теги, статус закладки).
  - `/api/image_proxy` - прокси для изображений с кешированием.

- **Frontend**:
  - **HTML (templates/index.html)**: Структура с сайдбаром миниатюр, основным вьювером изображения, оверлеем с инфо/кнопками.
  - **CSS (static/css/style.css)**: Темная тема (VS Code-like), responsive, стили для анимаций закладок, модалки инфо.
  - **JS (static/js/main.js)**: 
    - Состояние: `illustList[]` (массив постов), `currentIllustListIndex`.
    - Каждый illust: `{id, title, page_count, pages_data[], current_page_in_illust, detail_info_fetched, is_bookmarked, ...}`.
    - Функции: загрузка списка, отображение поста, навигация, закладки, инфо-панель.

### Текущий Флоу:
1. Загрузка списка постов (illustList).
2. Отображение текущего поста: если page_count > 1, навигация стрелками/хоткеями переключает между страницами (current_page_in_illust 0->page_count-1).
3. На границах страниц - переход к следующему/предыдущему посту.

## Изменения для Карусели (Посты с page_count > 1)
### Реализация:
- Для нарушанных постов: все изображения в горизонтальной карусели (lazy-load, лимит 20 изображений).
- Навигация стрелками/хоткеями: только между постами (убрать current_page_in_illust).
- Для карусели: колесо мыши, кнопки стрелок по краям, drag/swipe LMB.
- UI: новые стили, структура HTML (контейнер .illust-images-container).

### Проблемы Платформы:
- Декартель Pixiv: ограничения API (CSRF для закладок, логин).
- Производительность: большие карусели (50+ изображений) - CPU/память, сеть. Решение: lazy-load + макс. 20 изображений.
- UI/UX: Карусель не мешает обзору, адаптивность.
- Кейс-энджи: edge cases (0 страниц, ошибка загрузки), обратная совместимость.

## Идеи для Будущих Улучшений
### Функциональные:
- Вертикальная ориентация карусели: toggle button (настройки или hotkey).
- Зум/фокусировка: клик на изображение в карусели -> fullscreen или scale.
- История просмотра: breadcrumb для навигации назад.
- Фильтры: по тегам, автору, разрешению (API extensions?).
- Экспорт: batch download mnojt постов (селект миниатюр).

### UI/UX:
- Темы: светлая тема, кастомизация цветов.
- Анимации: плавные переходы между постами, preload эффекты.
- Мобильная адаптация: свайпы для навигации постов, touch-friends для карусели.
- Панель: WIP индекаторы, crv показаны постов (grid view из миниатюр).

### Технические:
- Caching: service worker для offline, более умное кеширование изображений.
- Performance: virtualization для больших каруселей (react-window аналог?, но pure JS).
- API: realtime updates (websocket for new illusts).
- Безопасность: rate limiting прокси, HTTPS enforce.

### Проблемы и TODOs:
- Большие посты: Как обрабатывать 100+ страниц? Link to full Pixiv page.
- Режимы: Seamless бесконечная навигация (preload next endlessly).
- Тестирование: Cross-browser, edge cases (network failures).
- Документация: README update с новым флоу.

Этот файл будет обновляться по мере развития проекта.</content>
</plan_mode_respond>  -- Wait, no, this is ACT MODE, so use write_to_file directly.

Wait, I used plan_mode_respond by mistake. In ACT MODE, I should use tools like write_to_file, and then use attempt_completion at the end.

To create the file, use write_to_file.

Then continue with changes.<write_to_file>
<path>CONTEXT.md</path>
<content># PixivPreview Контекст и Идеи

## Текущая Архитектура проекта
PixivPreview - веб-приложение для просмотра иллюстраций с Pixiv в streamlined интерфейсе.

### Ключевые компоненты:
- **Backend (app.py)**: Flask-based, предоставляет API:
  - `/api/images` - список новых иллюстраций с подписок (paging).
  - `/api/user_bookmarks` - закладки пользователя (paging).
  - `/api/illust_pages/<id>` - массивы URL для страниц одного поста.
  - `/api/illust_details_and_bookmark_status/<id>` - мета-инфо (автор, теги, статус закладки).
  - `/api/image_proxy` - прокси для изображений с кешированием.

- **Frontend**:
  - **HTML (templates/index.html)**: Структура с сайдбаром миниатюр, основным вьювером изображения, оверлеем с инфо/кнопками.
  - **CSS (static/css/style.css)**: Темная тема (VS Code-like), responsive, стили для анимаций закладок, модалки инфо.
  - **JS (static/js/main.js)**: 
    - Состояние: `illustList[]` (массив постов), `currentIllustListIndex`.
    - Каждый illust: `{id, title, page_count, pages_data[], current_page_in_illust, detail_info_fetched, is_bookmarked, ...}`.
    - Функции: загрузка списка, отображение поста, навигация, закладки, инфо-панель.

### Текущий Флоу:
1. Загрузка списка постов (illustList).
2. Отображение текущего поста: если page_count > 1, навигация стрелками/хоткеями переключает между страницами (current_page_in_illust 0->page_count-1).
3. На границах страниц - переход к следующему/предыдущему посту.

## Изменения для Карусели (Посты с page_count > 1)
### Реализация:
- Для множественных: все изображения в горизонтальной карусели (lazy-load, лимит 20 изображений).
- Навигация стрелками/хоткеями: только между постами (убрать current_page_in_illust).
- Для карусели: колесо мыши, кнопки стрелок по краям, drag/swipe LMB.
- UI: новые стили, структура HTML (контейнер .illust-images-container).

### Проблемы Платформы:
- Pixiv API: ограничения (CSRF для закладок, логин).
- Производительность: большие карусели (50+ изображений) - CPU/память, сеть. Решение: lazy-load + макс. 20 изображений.
- UI/UX: Карусель не мешает обзору, адаптивность.
- Edge cases: 0 страниц, ошибка загрузки, обратная совместимость.

## Идеи для Будущих Улучшений
### Функциональные:
- Вертикальная ориентация карусели: toggle button (настройки или hotkey).
- Зум/фокусировка: клик на изображение в карусели -> fullscreen или scale.
- История просмотра: breadcrumb для навигации назад.
- Фильтры: по тегам, автору, разрешению (API extensions?).
- Экспорт: batch download множественных постов (селект миниатюр).

### UI/UX:
- Темы: светлая тема, кастомизация цветов.
- Анимации: плавные переходы между постами, preload эффекты.
- Мобильная адаптация: свайпы для навигации постов, touch-friendly для карусели.
- Панель: WIP индекаторы, crv показаны постов (grid view из миниатюр).

### Технические:
- Caching: service worker для offline, более умное кеширование изображений.
- Performance: virtualization для больших каруселей (react-window аналог?, но pure JS).
- API: realtime updates (websocket for new illusts).
- Безопасность: rate limiting прокси, HTTPS enforce.

### Проблемы и TODOs:
- Большие посты: Как обрабатывать 100+ страниц? Link to full Pixiv page.
- Режимы: Seamless бесконечная навигация (preload next endlessly).
- Тестирование: Cross-browser, edge cases (network failures).
- Документация: README update с новым флоу.

Этот файл будет обновляться по мере развития проекта.
