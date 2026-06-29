#include <windows.h>
#include <iostream>
#include <thread>
#include <atomic>
#include <vector>
#include <random>
#include <chrono>

std::atomic<bool> playing(false);
std::atomic<int> cycle_count(0);

struct MacroAction {
    int type; 
    DWORD code;
    bool key_up;
    int delay_ms;
    int rand_ms;
};

std::vector<MacroAction> sequence = {
    {0, MOUSEEVENTF_LEFTDOWN, false, 650, 15},
    {0, MOUSEEVENTF_LEFTUP, false, 0, 15},
    {1, 'Q', false, 0, 15},
    {1, 'Q', true, 1680, 15},
    {0, MOUSEEVENTF_LEFTDOWN, false, 260, 15},
    {0, MOUSEEVENTF_LEFTUP, false, 140, 15},
    {0, MOUSEEVENTF_LEFTDOWN, false, 180, 15},
    {0, MOUSEEVENTF_RIGHTDOWN, false, 120, 15},
    {0, MOUSEEVENTF_RIGHTUP, false, 2260, 15},
    {0, MOUSEEVENTF_LEFTUP, false, 580, 15},
    {0, MOUSEEVENTF_LEFTDOWN, false, 190, 15},
    {0, MOUSEEVENTF_RIGHTDOWN, false, 180, 15},
    {0, MOUSEEVENTF_RIGHTUP, false, 720, 15},
    {0, MOUSEEVENTF_LEFTUP, false, 580, 15},
    {0, MOUSEEVENTF_LEFTDOWN, false, 160, 15},
    {0, MOUSEEVENTF_RIGHTDOWN, false, 220, 15},
    {0, MOUSEEVENTF_RIGHTUP, false, 660, 15},
    {0, MOUSEEVENTF_LEFTUP, false, 540, 15},
    {0, MOUSEEVENTF_LEFTDOWN, false, 200, 15},
    {0, MOUSEEVENTF_RIGHTDOWN, false, 190, 15},
    {0, MOUSEEVENTF_RIGHTUP, false, 600, 15},
    {0, MOUSEEVENTF_LEFTUP, false, 890, 15}
};

void send_mouse(DWORD flags) {
    INPUT input = {0};
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = flags;
    SendInput(1, &input, sizeof(INPUT));
}

void send_action(const MacroAction& action) {
    INPUT input = {0};
    if (action.type == 0) {
        input.type = INPUT_MOUSE;
        input.mi.dwFlags = action.code;
    } else if (action.type == 1) {
        input.type = INPUT_KEYBOARD;
        input.ki.wVk = 0; 
        input.ki.wScan = MapVirtualKeyA(action.code, MAPVK_VK_TO_VSC);
        input.ki.dwFlags = KEYEVENTF_SCANCODE;
        if (action.key_up) {
            input.ki.dwFlags |= KEYEVENTF_KEYUP;
        }
    }
    SendInput(1, &input, sizeof(INPUT));
}

void macro_thread_func() {
    std::cout << "▶ Виконується (Зациклено)...\n";
    
    std::random_device rd;
    std::mt19937 gen(rd());
    
    using clock = std::chrono::high_resolution_clock;
    auto target_time = clock::now();

    while (playing.load()) {
        for (const auto& action : sequence) {
            if (!playing.load()) break;
            
            send_action(action);
            
            target_time += std::chrono::milliseconds(action.delay_ms);
            
            std::uniform_int_distribution<> dist(-action.rand_ms, action.rand_ms);
            int jitter = dist(gen);
            auto actual_target = target_time + std::chrono::milliseconds(jitter);
            
            while (true) {
                auto now = clock::now();
                if (now >= actual_target || !playing.load()) break;
                
                auto diff = std::chrono::duration_cast<std::chrono::milliseconds>(actual_target - now).count();
                if (diff > 15) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                } else {
                    std::this_thread::yield(); 
                }
            }
        }
        
        if (playing.load()) {
            cycle_count++;
            std::cout << "\rЦиклів: " << cycle_count << std::flush;
        }
    }
    
    playing.store(false);
    send_mouse(MOUSEEVENTF_LEFTUP);
    send_mouse(MOUSEEVENTF_RIGHTUP);
    std::cout << "\nОчікує натискання\n";
}

bool is_admin() {
    BOOL isAdmin = FALSE;
    PSID adminGroup = NULL;
    SID_IDENTIFIER_AUTHORITY ntAuthority = SECURITY_NT_AUTHORITY;
    if (AllocateAndInitializeSid(&ntAuthority, 2, SECURITY_BUILTIN_DOMAIN_RID, DOMAIN_ALIAS_RID_ADMINS,
                                 0, 0, 0, 0, 0, 0, &adminGroup)) {
        CheckTokenMembership(NULL, adminGroup, &isAdmin);
        FreeSid(adminGroup);
    }
    return isAdmin == TRUE;
}

std::thread* active_macro_thread = nullptr;

void fire_macro() {
    if (playing.load()) {
        playing.store(false);
        return;
    }
    playing.store(true);
    if (active_macro_thread && active_macro_thread->joinable()) {
        active_macro_thread->join();
        delete active_macro_thread;
    }
    active_macro_thread = new std::thread(macro_thread_func);
}

LRESULT CALLBACK ms_proc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode >= 0 && wParam == WM_XBUTTONDOWN) {
        MSLLHOOKSTRUCT* ms = (MSLLHOOKSTRUCT*)lParam;
        if (!(ms->flags & LLMHF_INJECTED)) {
            WORD xbtn = GET_XBUTTON_WPARAM(ms->mouseData);
            if (xbtn == XBUTTON1) { 
                fire_macro();
            }
        }
    }
    return CallNextHookEx(NULL, nCode, wParam, lParam);
}

int main(int argc, char* argv[]) {
    SetConsoleOutputCP(CP_UTF8);

    if (!is_admin()) {
        wchar_t szPath[MAX_PATH];
        if (GetModuleFileNameW(NULL, szPath, ARRAYSIZE(szPath))) {
            SHELLEXECUTEINFOW sei = { sizeof(sei) };
            sei.lpVerb = L"runas";
            sei.lpFile = szPath;
            sei.hwnd = NULL;
            sei.nShow = SW_NORMAL;
            if (!ShellExecuteExW(&sei)) {
                std::cerr << "Не вдалося отримати права адміністратора.\n";
                return 1;
            }
        }
        return 0; 
    }

    HHOOK ms_hook = SetWindowsHookExW(WH_MOUSE_LL, ms_proc, NULL, 0);
    if (!ms_hook) {
        std::cerr << "❌ Помилка хуку: " << GetLastError() << "\n";
        return 1;
    }

    std::cout << "Очікує натискання\n";
    
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    UnhookWindowsHookEx(ms_hook);
    
    if (active_macro_thread && active_macro_thread->joinable()) {
        playing.store(false);
        active_macro_thread->join();
        delete active_macro_thread;
    }
    
    return 0;
}