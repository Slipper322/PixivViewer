# PixivViewer

A web application for browsing and viewing Pixiv content with a clean interface. This app allows you to view new illustrations from your followed artists and your bookmarks in a convenient slideshow format.

## Features

- View new illustrations from followed artists
- Browse your bookmarks
- Add/remove bookmarks directly from the interface
- Multi-page illustration support
- Image preloading for smooth browsing
- Keyboard shortcuts for navigation
- Resizable sidebar
- Detailed illustration information panel
- Original image viewing and downloading
- IQDB reverse image search integration

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/Slipper322/PixivViewer.git
   cd PixivViewer
   ```

2. Install dependencies:
   ```
   pip install flask requests beautifulsoup4
   ```

3. Create a `config.json` file in the root directory with your Pixiv credentials:
   ```json
   {
     "PHPSESSID": "your_pixiv_phpsessid_cookie",
     "USER_ID": "your_pixiv_user_id"
   }
   ```
   
   To get your PHPSESSID:
   - Log in to Pixiv in your browser
   - Open developer tools (F12)
   - Go to Application/Storage > Cookies > www.pixiv.net
   - Find the PHPSESSID cookie and copy its value

4. Run the application:
   ```
   python app.py
   ```

5. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Keyboard Shortcuts

- `←` / `→`: Navigate between illustrations and pages
- `F`: Add/remove bookmark
- `O`: Open original image
- `D`: Download original image
- `Q`: Search image on IQDB
- `I`: Toggle information panel

## Note

This application is for personal use only. It uses your Pixiv account credentials to access content you would normally have access to through the Pixiv website. Please respect Pixiv's terms of service.

---

# PixivViewer (Русская версия)

Веб-приложение для просмотра контента Pixiv с удобным интерфейсом. Это приложение позволяет просматривать новые иллюстрации от художников, на которых вы подписаны, а также ваши закладки в удобном формате слайдшоу.

## Возможности

- Просмотр новых иллюстраций от подписок
- Просмотр ваших закладок
- Добавление/удаление закладок прямо из интерфейса
- Поддержка многостраничных иллюстраций
- Предзагрузка изображений для плавного просмотра
- Горячие клавиши для навигации
- Изменяемый размер боковой панели
- Детальная информационная панель об иллюстрации
- Просмотр и скачивание оригинальных изображений
- Интеграция с поиском по изображению IQDB

## Установка

1. Клонируйте репозиторий:
   ```
   git clone https://github.com/Slipper322/PixivViewer.git
   cd PixivViewer
   ```

2. Установите зависимости:
   ```
   pip install flask requests beautifulsoup4
   ```

3. Создайте файл `config.json` в корневой директории с вашими учетными данными Pixiv:
   ```json
   {
     "PHPSESSID": "ваш_pixiv_phpsessid_cookie",
     "USER_ID": "ваш_pixiv_user_id"
   }
   ```
   
   Чтобы получить PHPSESSID:
   - Войдите в Pixiv в вашем браузере
   - Откройте инструменты разработчика (F12)
   - Перейдите в Application/Storage > Cookies > www.pixiv.net
   - Найдите куки PHPSESSID и скопируйте его значение

4. Запустите приложение:
   ```
   python app.py
   ```

5. Откройте браузер и перейдите по адресу:
   ```
   http://localhost:5000
   ```

## Горячие клавиши

- `←` / `→`: Навигация между иллюстрациями и страницами
- `F`: Добавить/удалить закладку
- `O`: Открыть оригинальное изображение
- `D`: Скачать оригинальное изображение
- `Q`: Искать изображение на IQDB
- `I`: Переключить информационную панель

## Примечание

Это приложение предназначено только для личного использования. Оно использует учетные данные вашей учетной записи Pixiv для доступа к контенту, к которому у вас обычно есть доступ через веб-сайт Pixiv. Пожалуйста, соблюдайте условия использования Pixiv.
