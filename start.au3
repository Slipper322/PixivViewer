#include <Constants.au3> ; Подключение стандартных констант AutoIt

; --- НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ ---
; !!! ВАЖНО: Измените эти пути на ваши реальные значения !!!
Global Const $g_sPythonExePath = "D:\Slipper\Study\Works\PixivPreview\.conda\python.exe"  ; Пример: "C:\Users\ИмяПользователя\miniconda3\envs\myenv\python.exe"
Global Const $g_sPythonScriptPath = "D:\Slipper\Study\Works\PixivPreview\app.py"       ; Пример: "D:\МоиПроекты\FlaskServer\app.py"
Global Const $g_sWebAppURL = "https://pixiv-viewer.local/"                 ; URL, который будет открываться в браузере (стандартный для Flask)
Global Const $g_sTrayToolTip =  "Pixiv Preview"               ; Текст подсказки при наведении на иконку в трее
Global Const $TrayIconPath_User = "static\images\favicon.ico"
; --- КОНЕЦ НАСТРОЕК ПОЛЬЗОВАТЕЛЯ ---

Global $g_iPythonPID = 0      ; PID (идентификатор процесса) запущенного скрипта Python
Global $g_hOpenMenuItem       ; Дескриптор пункта меню "Открыть"
Global $g_hCloseMenuItem      ; Дескриптор пункта меню "Закрыть"
Global Const $g_sScriptName = @ScriptName ; Имя текущего скрипта AutoIt

Main()

Func Main()
    ; Проверка, не запущен ли уже экземпляр этого скрипта AutoIt
    Local $aProcessList = ProcessList($g_sScriptName)
    If $aProcessList[0][0] > 1 Then
        For $i = 1 To $aProcessList[0][0]
            If $aProcessList[$i][1] <> @AutoItPID Then ; Если найден другой процесс с таким же именем
                MsgBox(48, "Информация", "Экземпляр скрипта '" & $g_sScriptName & "' уже запущен.")
                Exit
            EndIf
        Next
    EndIf

    ; Устанавливаем заголовок для окна AutoIt (полезно, если скрипт когда-либо создаст видимое окно)
    AutoItWinSetTitle($g_sScriptName)

    ; Проверка существования необходимых файлов
    If Not FileExists($g_sPythonExePath) Then
        MsgBox(16, "Ошибка конфигурации", "Не найден исполняемый файл Python:" & @CRLF & $g_sPythonExePath & @CRLF & "Пожалуйста, проверьте путь в настройках скрипта.")
        Exit
    EndIf
    If Not FileExists($g_sPythonScriptPath) Then
        MsgBox(16, "Ошибка конфигурации", "Не найден Python скрипт:" & @CRLF & $g_sPythonScriptPath & @CRLF & "Пожалуйста, проверьте путь в настройках скрипта.")
        Exit
    EndIf

    ; Определяем рабочую директорию для Python скрипта (папка, где находится app.py)
    ; Это важно, если app.py использует относительные пути для доступа к другим файлам
    Local $sPythonScriptWorkDir = StringRegExpReplace($g_sPythonScriptPath, "(.*)\\[^\\]+$", "$1")

    ; Формируем команду для запуска Python скрипта
    Local $sCommandToRun = '"' & $g_sPythonExePath & '" "' & $g_sPythonScriptPath & '"'

    ; Запускаем Python скрипт в скрытом режиме
    $g_iPythonPID = Run($sCommandToRun, $sPythonScriptWorkDir, @SW_HIDE)

    ; Проверяем, успешно ли запустился процесс
    If @error Or $g_iPythonPID = 0 Then
        MsgBox(16, "Ошибка запуска", "Не удалось запустить Python скрипт." & @CRLF & _
            "Команда: " & $sCommandToRun & @CRLF & _
            "Рабочая директория: " & $sPythonScriptWorkDir & @CRLF & _
            "Код ошибки AutoIt Run(): " & @error)
        Exit
    EndIf

    ; Настройки для меню в трее
    Opt("TrayMenuMode", 1) ; Отображать стандартные элементы меню

    ; Создаем элементы меню в трее
    $g_hOpenMenuItem = TrayCreateItem("Открыть")
    TrayCreateItem("") ; Пустой элемент создает разделитель
    $g_hCloseMenuItem = TrayCreateItem("Закрыть")

    TraySetIcon($TrayIconPath_User) ; Устанавливаем иконку для трея (можно заменить на свою .ico)
                                    ; Например: TraySetIcon("путь\к\вашей\иконке.ico")
                                    ; -23 из shell32.dll это иконка "компьютерной сети" или похожая.
    TraySetToolTip($g_sTrayToolTip) ; Устанавливаем подсказку
    TraySetState($TRAY_ICONSTATE_SHOW)   ; Показываем иконку (обычно она и так показывается после TrayCreateItem)

    ; Регистрируем функцию, которая будет вызвана при завершении AutoIt скрипта
    OnAutoItExitRegister("CleanupBeforeExit")

    ; Основной цикл ожидания событий от иконки в трее
    While 1
        Local $nMsg = TrayGetMsg() ; Получаем сообщение из трея

        Switch $nMsg
            Case 0 ; Нет сообщений, просто ждем
                Sleep(100) ; Небольшая задержка для снижения нагрузки на CPU
                ContinueLoop

            Case $g_hOpenMenuItem ; Клик по пункту "Открыть"
                ShellExecute($g_sWebAppURL) ; Открываем URL в браузере по умолчанию

            Case $g_hCloseMenuItem ; Клик по пункту "Закрыть"
                ShutdownPythonScript() ; Закрываем Python скрипт
                Exit ; Завершаем AutoIt скрипт
        EndSwitch
    WEnd
EndFunc   ;==>Main

; Функция для корректного завершения Python скрипта
Func ShutdownPythonScript()
    If $g_iPythonPID <> 0 And ProcessExists($g_iPythonPID) Then
        ProcessClose($g_iPythonPID) ; Отправляем команду на закрытие процесса Python

        ; Даем процессу некоторое время на завершение
        Local $iTimer = TimerInit()
        While ProcessExists($g_iPythonPID) And TimerDiff($iTimer) < 5000 ; Ждем до 5 секунд
            Sleep(250)
        WEnd

        If ProcessExists($g_iPythonPID) Then
            MsgBox(48, "Предупреждение", "Python скрипт не был остановлен в течение 5 секунд." & @CRLF & "Возможно, его придется закрыть вручную через Диспетчер задач.")
        Else
            ; Опционально: сообщение об успешной остановке
            ; TrayTip("Информация", "Сервер Python остановлен.", 10, 1)
            $g_iPythonPID = 0 ; Сбрасываем PID, так как процесс остановлен
        EndIf
    EndIf
EndFunc   ;==>ShutdownPythonScript

; Функция, вызываемая автоматически при выходе из AutoIt скрипта
Func CleanupBeforeExit()
    ShutdownPythonScript() ; Гарантированно пытаемся закрыть Python скрипт
EndFunc   ;==>CleanupBeforeExit