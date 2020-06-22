#include <windows.h>
#include <stdio.h>


#ifndef HAT_WIN32_LAUNCHER_PYTHON_PATH
#define HAT_WIN32_LAUNCHER_PYTHON_PATH "python\\pythonw.exe"
#endif

#ifndef HAT_WIN32_LAUNCHER_PYTHON_MODULE
#error "definition HAT_WIN32_LAUNCHER_PYTHON_MODULE required"
#endif


int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR pCmdLine,
                   int nCmdShow) {

    char cmd[0x10000];
    GetModuleFileName(NULL, cmd, sizeof(cmd));

    size_t cmd_len = strlen(cmd);
    while (cmd_len && cmd[cmd_len - 1] != '\\')
        cmd_len -= 1;
    if (!cmd_len)
        return 1;

    snprintf(cmd + cmd_len, sizeof(cmd) - cmd_len, "%s -m %s %s",
             HAT_WIN32_LAUNCHER_PYTHON_PATH, HAT_WIN32_LAUNCHER_PYTHON_MODULE,
             pCmdLine);
    cmd[sizeof(cmd) - 1] = 0;

    STARTUPINFO si;
    PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof(si));
    si.cb = sizeof(si);
    if (!CreateProcess(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        return 1;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);

    return 0;
}
